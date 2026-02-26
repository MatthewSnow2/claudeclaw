# EA-Claude Async Dispatch Blueprint

## Problem

Data currently runs one Claude subprocess at a time (`MAX_CONCURRENT_AGENTS = 1` in agent.ts). When a long task comes in (coding, research, multi-file analysis), the bot blocks until completion. No other messages can be processed. Scheduled tasks queue behind interactive ones.

This becomes critical as we add specialized workers (Starscream, Ravage, Soundwave) that need to run independently.

## Current Architecture

```
User (Telegram) -> bot.ts -> router.ts -> agent.ts -> Claude subprocess (blocking)
                                                    -> Reply to Telegram
Scheduler -> scheduler.ts -> agent.ts -> Claude subprocess (blocking)
                                       -> Reply to Telegram
```

Single-threaded. One agent at a time. Everything waits.

## Target Architecture

```
User (Telegram) -> bot.ts -> classifier (quick vs long)
                    |
                    +-> Quick: inline response (current flow, < 30s)
                    |
                    +-> Long: enqueue task + ACK user
                        |
                        +-> dispatch_queue (SQLite)
                            |
                            +-> Worker: Starscream (pm2) -- social media, Late API, LinkedIn
                            +-> Worker: Ravage (pm2) -- coding, GitHub, PRs
                            +-> Worker: Soundwave (pm2) -- research, HIL coaching, Metroplex/ST Factory
                            +-> Worker: Default (pm2) -- anything not classified above
                            |
                            +-> Worker completes -> writes result to queue
                            +-> Data polls results -> sends to Telegram
```

## Components

### Phase 1: Task Queue + Classification (unblocking piece)

**db.ts additions:**
```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  id TEXT PRIMARY KEY,           -- UUID
  chat_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  worker_type TEXT NOT NULL,     -- 'starscream' | 'ravage' | 'soundwave' | 'default'
  status TEXT DEFAULT 'queued',  -- 'queued' | 'running' | 'completed' | 'failed'
  result TEXT,
  session_id TEXT,               -- Claude session to resume (if applicable)
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  error TEXT
);
```

**classifier.ts (new):**
- Analyzes incoming message to determine: quick (<30s estimated) vs long
- Quick: social lookup, simple question, status check, memory recall
- Long: "build X", "review PR", "write code", "research X", "create slide deck"
- Routes long tasks to appropriate worker type based on keywords/intent
- Classification rules:
  - Contains "LinkedIn", "post", "schedule post" -> starscream
  - Contains "code", "build", "fix", "PR", "commit", "deploy" -> ravage
  - Contains "research", "analyze", "review pipeline", "morning report" -> soundwave
  - Everything else -> default

**bot.ts changes:**
- After classification, if long task:
  1. Insert into dispatch_queue
  2. Reply: "Got it. Dispatched to [worker]. I'll report back when done."
  3. Return immediately (don't block)

**result-poller.ts (new):**
- setInterval every 10s
- SELECT from dispatch_queue WHERE status = 'completed' AND NOT notified
- Send result to Telegram via bot API
- Mark as notified

### Phase 2: Worker Processes

Each worker is a standalone Node.js process managed by pm2.

**worker.ts (new, shared base):**
```typescript
// Generic worker loop:
// 1. Poll dispatch_queue for tasks matching this worker type
// 2. Claim task (SET status = 'running')
// 3. Run Claude subprocess with worker-specific CLAUDE.md
// 4. Write result back to queue
// 5. Loop

interface WorkerConfig {
  name: string;                    // 'starscream' | 'ravage' | 'soundwave'
  workerType: string;              // matches dispatch_queue.worker_type
  claudeMdPath: string;            // path to worker-specific CLAUDE.md
  pollIntervalMs: number;          // how often to check queue (default: 5000)
  maxConcurrent: number;           // concurrent tasks per worker (default: 1)
}
```

**Worker CLAUDE.md files:**
- `workers/starscream/CLAUDE.md` -- social media persona, Late API access, LinkedIn voice guide
- `workers/ravage/CLAUDE.md` -- coding specialist, GitHub tools, PR review focus
- `workers/soundwave/CLAUDE.md` -- research analyst, reads from Metroplex/ST Factory, HIL coaching

**pm2 ecosystem:**
```json
{
  "apps": [
    { "name": "ea-claude-data", "script": "dist/index.js" },
    { "name": "ea-claude-starscream", "script": "dist/worker.js", "args": "--type starscream" },
    { "name": "ea-claude-ravage", "script": "dist/worker.js", "args": "--type ravage" },
    { "name": "ea-claude-soundwave", "script": "dist/worker.js", "args": "--type soundwave" }
  ]
}
```

### Phase 3: Task Duration Estimation

Add to Data's capabilities:
- Track historical task durations by type (new SQLite table)
- When dispatching, estimate: "This looks like a ~5 min coding task"
- Inform user: "Dispatched to Ravage. Estimated: ~5 minutes."
- Over time, estimates improve from actual duration data

### Phase 4: Sky-Lynx Integration

- Workers emit outcome records to ST Factory (same contract as Ultra-Magnus)
- Sky-Lynx reads worker performance metrics weekly
- Recommendations feed back into worker CLAUDE.md updates
- Self-correcting loop: workers get better autonomously

## Implementation Order

1. [x] Architecture doc (this file)
2. [ ] dispatch_queue table in db.ts
3. [ ] classifier.ts -- message classification logic
4. [ ] result-poller.ts -- poll completed tasks, send to Telegram
5. [ ] bot.ts changes -- dispatch long tasks instead of blocking
6. [ ] worker.ts -- generic worker loop
7. [ ] Starscream CLAUDE.md + config
8. [ ] Ravage CLAUDE.md + config
9. [ ] Soundwave CLAUDE.md + config
10. [ ] pm2 ecosystem.config.js
11. [ ] Task duration estimation
12. [ ] Sky-Lynx integration hooks

## Key Decisions

- **Queue backend**: SQLite (same as existing db.ts, simple, no new deps)
- **IPC**: Polling, not pub/sub. Workers poll the queue. Simple, robust, no message broker needed.
- **Worker isolation**: Each worker gets its own Claude subprocess + CLAUDE.md. No shared state except the queue.
- **Concurrency**: Each worker runs 1 task at a time. Data (bot) handles quick tasks inline. No API rate limit collisions.
- **Session handling**: Workers don't share sessions with Data. Each dispatched task gets a fresh Claude session. Data maintains its own conversational session with Matthew.

## Risk Mitigation

- **API rate limits**: Workers stagger naturally (polling interval offsets). If overloaded, retry with backoff (existing pattern in agent.ts).
- **Queue starvation**: Result poller runs every 10s. Max latency from completion to notification: 10s.
- **Worker crash**: pm2 auto-restart. Unclaimed tasks (status='running' for >10min) get reset to 'queued'.
- **Cost**: Each worker spawns Claude subprocesses on Max plan OAuth. No API billing unless explicitly overridden.

---

Last updated: 2026-02-26
Status: Phase 1 ready for implementation
