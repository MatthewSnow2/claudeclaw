# EA-Claude Async Dispatch Architecture

## Problem

Data currently processes messages **synchronously, one at a time**:

```
Message arrives → runAgent() blocks → 30s-5min wait → response sent → next message
```

`MAX_CONCURRENT_AGENTS = 1` in agent.ts (line 80). This prevents rate limit collisions but means:
- Long-running tasks (Starscream social media, Ravage coding) block all other messages
- Scheduled tasks run sequentially
- No parallel work possible

## Solution: Queue + Worker Pattern

### Architecture

```
TELEGRAM BOT (main process - stays responsive)
  ├── Interactive messages → runAgent() directly (low latency, existing behavior)
  └── Background tasks → enqueue to worker_tasks table
                              ↓
                         WORKER PROCESSES (separate pm2 instances)
                         ├── starscream-worker (social media, Late API)
                         ├── ravage-worker (coding, GitHub review)
                         └── soundwave-worker (research, HIL coaching)
                              ↓
                         Results posted back via bot.api.sendMessage()
```

### Key Design Decisions

1. **Single Telegram bot** -- Data remains the only Telegram identity. Workers don't poll Telegram.
2. **Workers are Claude Code subprocesses** -- Each worker calls `runAgent()` with a persona-specific system prompt.
3. **SQLite task queue** -- No Redis needed. WAL mode supports concurrent reads.
4. **PM2 process management** -- Each worker is a separate pm2 process with its own restart policy.

### Database Schema Addition

```sql
CREATE TABLE worker_tasks (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  persona TEXT NOT NULL,           -- 'starscream' | 'ravage' | 'soundwave'
  prompt TEXT NOT NULL,
  chat_id TEXT NOT NULL,           -- Telegram chat to post results to
  status TEXT NOT NULL DEFAULT 'queued',  -- queued | running | completed | failed
  priority INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  started_at TEXT,
  completed_at TEXT,
  result TEXT,
  error TEXT,
  session_id TEXT                  -- Claude Code session for resumption
);
CREATE INDEX idx_worker_tasks_status ON worker_tasks(status, priority DESC, created_at);
```

### New Files

```
src/
├── worker.ts          -- Worker entry point: poll DB, run agent, post results
├── dispatch.ts        -- Dispatch logic: decide interactive vs background
├── personas.ts        -- Persona definitions (system prompts, model config)
└── worker-cli.ts      -- CLI for manual task management

ecosystem.config.cjs additions:
├── starscream-worker  -- pm2 process
├── ravage-worker      -- pm2 process
└── soundwave-worker   -- pm2 process
```

### Modified Files

```
src/bot.ts        -- Add dispatch decision point in handleMessage()
src/db.ts         -- Add worker_tasks table, CRUD operations
src/agent.ts      -- Extract runAgent() config to support persona overrides
src/telemetry.ts  -- Add worker_task events
```

### Dispatch Logic (dispatch.ts)

```typescript
function shouldDispatchAsync(message: string, persona?: string): boolean {
  // Explicit persona routing
  if (persona) return true;

  // Duration estimation heuristics
  if (message.includes('write a post') || message.includes('schedule content')) return true;  // Starscream
  if (message.includes('review PR') || message.includes('build feature')) return true;         // Ravage
  if (message.includes('research') || message.includes('analyze market')) return true;         // Soundwave

  // Default: interactive
  return false;
}
```

### Worker Process (worker.ts)

```typescript
// Simplified worker loop
async function workerLoop(persona: string) {
  while (true) {
    const task = await db.claimNextTask(persona);
    if (!task) {
      await sleep(5000);  // Poll every 5s
      continue;
    }

    try {
      const result = await runAgent({
        prompt: task.prompt,
        systemPrompt: getPersonaPrompt(persona),
        sessionId: task.session_id,
      });

      await db.completeTask(task.id, result.text, result.newSessionId);
      await bot.api.sendMessage(task.chat_id, formatResult(persona, result.text));
    } catch (err) {
      await db.failTask(task.id, err.message);
      await bot.api.sendMessage(task.chat_id, `${persona} task failed: ${err.message}`);
    }
  }
}
```

### Persona Definitions (personas.ts)

```typescript
const PERSONAS = {
  starscream: {
    name: 'Starscream',
    model: 'sonnet',
    systemPrompt: `You are Starscream, Matthew's social media and content automation agent.
      You have access to the Late API for posting/scheduling across platforms.
      You follow Matthew's voice guide and LinkedIn strategy.
      You NEVER post without HIL review gate approval.`,
    tools: ['social-media', 'late-api'],
  },
  ravage: {
    name: 'Ravage',
    model: 'sonnet',
    systemPrompt: `You are Ravage, Matthew's coding and GitHub review agent.
      You write code, review PRs, manage branches, and handle deployments.
      You follow project CLAUDE.md conventions strictly.
      You use TDD-first development.`,
    tools: ['github-orgs', 'agent-sdk-dev'],
  },
  soundwave: {
    name: 'Soundwave',
    model: 'sonnet',
    systemPrompt: `You are Soundwave, Matthew's research and HIL coaching agent.
      You surface insights from Metroplex, ST Factory, and market research.
      You read from persona_metrics.db and ideaforge.db.
      You coach Matthew on bottlenecks and strategic gaps.`,
    tools: ['aws-services'],
  },
};
```

### PM2 Config Addition

```javascript
// ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: 'ea-claude',
      script: 'dist/index.js',
      // ... existing config
    },
    {
      name: 'starscream-worker',
      script: 'dist/worker.js',
      args: '--persona starscream',
      restart_delay: 10000,
      max_restarts: 5,
    },
    {
      name: 'ravage-worker',
      script: 'dist/worker.js',
      args: '--persona ravage',
      restart_delay: 10000,
      max_restarts: 5,
    },
    {
      name: 'soundwave-worker',
      script: 'dist/worker.js',
      args: '--persona soundwave',
      restart_delay: 10000,
      max_restarts: 5,
    },
  ],
};
```

### Implementation Order

**Phase 1: Foundation (2-3 hours)**
1. Add `worker_tasks` table to db.ts
2. Create `worker.ts` with basic poll-and-execute loop
3. Create `personas.ts` with Starscream definition only
4. Create `dispatch.ts` with basic routing
5. Test: manual task insertion -> worker picks up -> executes -> posts result

**Phase 2: Integration (2-3 hours)**
1. Wire dispatch into `bot.ts` handleMessage()
2. Add pm2 config for starscream-worker
3. Add telemetry events for worker lifecycle
4. Test: Telegram message -> async dispatch -> background execution -> result in Telegram

**Phase 3: Additional Workers (1-2 hours each)**
1. Ravage worker + persona prompt
2. Soundwave worker + persona prompt + Metroplex/ST Factory DB reads
3. Task duration estimation heuristic

**Phase 4: Sky-Lynx Integration (1 hour)**
1. Worker telemetry events readable by Sky-Lynx
2. Outcome tracking per persona
3. Persona performance metrics in ST Factory

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Rate limiting with Claude API | Each worker has its own concurrency=1 limiter |
| Worker crashes | PM2 auto-restart with exponential backoff |
| Stale tasks | 30-minute timeout, auto-fail if no progress |
| Telegram API limits | Workers rate-limit sendMessage to 1/second |
| SQLite lock contention | WAL mode + short transactions + retry logic |

### Task Duration Estimation

For the "how long will this take?" feature:

```typescript
function estimateDuration(prompt: string): { estimate: string; confidence: string } {
  const wordCount = prompt.split(' ').length;

  if (prompt.match(/post|schedule|tweet|linkedin/i)) return { estimate: '2-5 min', confidence: 'high' };
  if (prompt.match(/review PR|code review/i)) return { estimate: '5-15 min', confidence: 'medium' };
  if (prompt.match(/build|implement|create.*feature/i)) return { estimate: '15-60 min', confidence: 'low' };
  if (prompt.match(/research|analyze|investigate/i)) return { estimate: '5-20 min', confidence: 'medium' };

  return { estimate: '5-30 min', confidence: 'low' };
}
```

---

*Ready for implementation. Phase 1 can start immediately.*
