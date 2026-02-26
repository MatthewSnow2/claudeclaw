# Codebase Integration Review: EA-Claude Async Dispatch

## Domain
Codebase Integration

## Files Reviewed

### Blueprint
- `BLUEPRINT-async-dispatch.md` -- full blueprint, all 4 phases, schema, component descriptions

### Source Files (with key functions/exports)
- `src/bot.ts` -- `handleMessage()` (line 201), `createBot()` (line 324), `isDuplicate()` (line 38), `redactSecrets()` (line 62), `formatForTelegram()` (line 85), `splitMessage()` (line 149), `sendTyping()` (line 171), `isAuthorised()` (line 186), `voiceEnabledChats` (line 25), `processedMessages` (line 35)
- `src/agent.ts` -- `runAgent()` (line 133), `runAgentInner()` (line 175), `singleTurn()` (line 103), `describeToolUse()` (line 24), `MAX_CONCURRENT_AGENTS` (line 80), `activeAgentCalls` (line 81), retry logic (lines 83-95)
- `src/router.ts` -- `routeMessage()` (line 68), `parsePrefix()` (line 37), `PREFIX_MAP` (line 20), `RouteResult` interface (line 7)
- `src/memory.ts` -- `buildMemoryContext()` (line 19), `saveConversationTurn()` (line 58), `runDecaySweep()` (line 76)
- `src/scheduler.ts` -- `initScheduler()` (line 29), `runDueTasks()` (line 45), `schedulerInterval` (line 22), `sender` (line 15)
- `src/db.ts` -- `initDatabase()` (line 65), `createSchema()` (line 9), all session/memory/task CRUD functions, `db` singleton (line 7)
- `src/config.ts` -- `PROJECT_ROOT` (line 38), `STORE_DIR` (line 39), `ALLOWED_CHAT_ID` (line 25), env loading
- `src/index.ts` -- `main()` (line 54), `acquireLock()` (line 21), `botApiRef` (line 86), 409 retry loop (lines 88-171), scheduler init (lines 96-101)
- `src/telemetry.ts` -- `emit()` (line 73), `TelemetryEvent` union type (line 14), `TELEMETRY_FILE` (line 6)
- `src/llm-backends.ts` -- `callGemini()`, `callPerplexity()`, `callOllama()`, `callOpenAI()` -- all simple HTTP calls
- `src/env.ts` -- `readEnvFile()` (line 47), `readLocalEnvFile()` (line 70)
- `src/bot.test.ts` -- tests for `splitMessage()` only
- `src/db.test.ts` -- tests for sessions, memories, FTS5, decay

## Findings

### 1. Classification must happen AFTER parsePrefix(), BEFORE routeMessage() -- Critical

The blueprint says "bot.ts -> classifier (quick vs long)" but does not specify where in the existing pipeline this sits. The correct insertion point is inside `handleMessage()` at line 261, between the `parsePrefix()` call (which happens inside `routeMessage()`) and the actual backend call. However, the current architecture calls `routeMessage()` as a single unit -- prefix parsing and backend dispatch are coupled inside router.ts.

**The problem**: `parsePrefix()` is a private function inside `router.ts` (line 37). The classifier needs the parsed prefix result to know if this is a Claude message (only Claude messages should be classifiable for dispatch). But the classifier also needs the original message text for keyword matching. This means either:
- (a) `parsePrefix()` must be exported from router.ts so bot.ts can call it first, then decide whether to classify+dispatch or route normally, OR
- (b) Classification logic goes inside `routeMessage()` itself, before the `case 'claude':` branch

Option (a) is cleaner because it keeps classification as a separate concern. The flow becomes:

```typescript
// bot.ts handleMessage(), replacing lines 261-267
const { backend, message: strippedMessage } = parsePrefix(message); // export this from router.ts

if (backend === 'ignore') return;

if (backend === 'claude') {
  const classification = classify(strippedMessage);
  if (classification.type === 'long') {
    // Dispatch to queue
    enqueueTask(chatIdStr, fullMessage, classification.workerType);
    await ctx.reply(`Got it. Dispatched to ${classification.workerType}. I'll report back when done.`);
    return;
  }
  // Fall through to existing inline flow for 'quick' classification
}

// Existing routeMessage() call for all backends
const result = await routeMessage(message, fullMessage, sessionId, ...);
```

### 2. Non-Claude backends should NEVER be dispatched -- Critical

The blueprint does not address what happens to `@gemini`, `@perplexity`, `@ollama`, and `@gpt` prefixed messages. These backends (in `src/llm-backends.ts`) are simple HTTP request/response calls that complete in 1-10 seconds. They should never go through the dispatch queue.

**Required specification**: The classifier must only apply to the `claude` backend. All other backends bypass classification entirely and run inline as they do today. The blueprint should state this explicitly. The code change in Finding 1 handles this by checking `if (backend === 'claude')` before classifying.

### 3. Workers have no Telegram bot instance for sending results -- Critical

The `result-poller.ts` blueprint (line 78-82) says it polls completed tasks and sends results to Telegram. But the blueprint doesn't specify WHERE the result-poller runs or how it gets a `Bot` or `Api` instance.

There are two viable architectures:

**(a) Result-poller runs inside the Data process (index.ts)**: This is the simplest approach. Data already has the bot instance (`botApiRef.current` at index.ts line 86). The poller would be initialized alongside the scheduler in `index.ts` lines 96-101, using the same `botApiRef` pattern:

```typescript
// index.ts, after initScheduler() call (~line 101)
initResultPoller((chatId, text) => {
  if (!botApiRef.current) return Promise.resolve();
  return botApiRef.current.sendMessage(chatId, text, { parse_mode: 'HTML' }).then(() => {});
});
```

**(b) Result-poller runs as a separate pm2 process**: This requires creating a standalone Grammy `Bot` instance just for sending messages (no `getUpdates` polling), which means instantiating `new Api(TELEGRAM_BOT_TOKEN)` and calling `api.sendMessage()` directly. This adds complexity with no benefit.

**Recommendation**: Option (a). The result-poller should be a setInterval inside the Data process, not a separate process. It shares the same polling pattern as the scheduler (scheduler.ts line 41: `setInterval(() => void runDueTasks(), 60_000)`).

### 4. Response formatting pipeline must be extracted from bot.ts -- Critical

When the result-poller delivers completed tasks, it must apply the same output pipeline as `handleMessage()` (bot.ts lines 279-308):
1. `redactSecrets()` (line 287)
2. `formatForTelegram()` (line 305)
3. `splitMessage()` (line 305)
4. Voice mode check (lines 293-303)

Currently, `redactSecrets()`, `formatForTelegram()`, and `splitMessage()` are already exported from bot.ts. But the voice mode check uses `voiceEnabledChats` (line 25), which is a module-private `Set<string>`. The result-poller cannot access this.

**Required changes**:
- The formatting functions (`redactSecrets`, `formatForTelegram`, `splitMessage`) are already exported. The result-poller can import them directly.
- Voice mode for dispatched results should be skipped initially (voice is for interactive conversation, not async results). Or `voiceEnabledChats` must be moved to a shared module/db table.
- The result-poller's send function should be:

```typescript
async function deliverResult(chatId: string, rawResult: string, sendFn: Sender): Promise<void> {
  const redacted = redactSecrets(rawResult);
  const formatted = formatForTelegram(redacted);
  for (const part of splitMessage(formatted)) {
    await sendFn(chatId, part);
  }
}
```

### 5. Memory system is completely bypassed for async tasks -- Critical

`saveConversationTurn()` (memory.ts line 58) is called at bot.ts line 290 with both the user message and Claude's response. For dispatched tasks:
- The user message IS available at dispatch time (in `handleMessage()`)
- The Claude response is only available when the worker writes it to the queue
- The result-poller delivers the result but has no reference to the original user message

**Required changes to dispatch_queue schema**: Add a `user_message` column (the original message before memory context) so the result-poller can reconstruct the conversation turn:

```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  id TEXT PRIMARY KEY,
  chat_id TEXT NOT NULL,
  user_message TEXT NOT NULL,     -- original user message (for memory)
  prompt TEXT NOT NULL,            -- full prompt with memory context (for worker)
  worker_type TEXT NOT NULL,
  status TEXT DEFAULT 'queued',
  result TEXT,
  session_id TEXT,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  error TEXT
);
```

The result-poller then calls `saveConversationTurn(task.chat_id, task.user_message, task.result)` after delivering the result.

### 6. Schema missing `notified` column (confirmed from orchestrator) -- Critical

The blueprint's result-poller references `WHERE status = 'completed' AND NOT notified` (line 80), but the schema (lines 46-58) has no `notified` column.

**Two options**:
- (a) Add `notified INTEGER DEFAULT 0` column to schema
- (b) Use a terminal status: `status = 'delivered'` (after the poller sends it). This is cleaner because it avoids a boolean column on a status-driven table.

**Recommendation**: Option (b). Add `'delivered'` to the status enum. The result-poller query becomes `WHERE status = 'completed'`, and after successful delivery it updates to `SET status = 'delivered'`. This also allows querying for "completed but undelivered" tasks for retry.

### 7. Scheduler should dispatch through the queue -- Warning

The scheduler (scheduler.ts line 59) calls `runAgent()` directly, which means scheduled tasks block the single agent slot just like interactive messages. The blueprint doesn't address this.

**Impact**: If a scheduled task runs at 9am and takes 5 minutes, any Telegram messages during that window get the "Already processing another request" response (agent.ts line 142). This is the exact problem async dispatch is supposed to solve.

**Required change**: The scheduler should insert into `dispatch_queue` instead of calling `runAgent()`:

```typescript
// scheduler.ts runDueTasks(), replacing line 59
import { enqueueTask } from './dispatch.js';

// Instead of: const result = await runAgent(task.prompt, undefined, () => {});
enqueueTask(ALLOWED_CHAT_ID, task.prompt, 'default', task.prompt);
await sender(`Scheduled task dispatched: "${task.prompt.slice(0, 80)}..."`);
```

However, this changes the scheduler's behavior -- results now arrive asynchronously via the poller instead of inline. The scheduler currently sends the result directly (line 62). This UX change should be documented.

### 8. Workers need runAgent() but with modified callbacks -- Warning

`runAgent()` (agent.ts line 133) accepts `onTyping` and `onProgress` callbacks that reference Telegram interactions. Workers don't have Telegram context.

**What workers need**:
- `onTyping`: Pass a no-op (`() => {}`) -- same pattern as scheduler.ts line 59
- `onProgress`: Either skip entirely (workers don't send progress to Telegram) or write progress updates to the queue for the poller to surface

The good news: `runAgent()` already handles this. The `onProgress` parameter is optional (agent.ts line 137: `onProgress?: (msg: string) => Promise<void>`), and the scheduler already passes `() => {}` for `onTyping`. Workers can do the same:

```typescript
// worker.ts
const result = await runAgent(task.prompt, task.session_id ?? undefined, () => {}, undefined);
```

No changes to agent.ts are needed for basic worker support.

### 9. Worker CLAUDE.md path requires cwd override in runAgentInner() -- Warning

The blueprint specifies per-worker CLAUDE.md files (lines 107-109: `workers/starscream/CLAUDE.md`). Currently, `runAgentInner()` hardcodes `cwd: PROJECT_ROOT` (agent.ts line 236), which causes Claude CLI to load `CLAUDE.md` from the project root.

Workers need to override this. Two approaches:

**(a) Add a `cwd` parameter to `runAgent()`**:
```typescript
export async function runAgent(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
  cwd?: string,  // NEW: override working directory
): Promise<AgentResult> {
```

Then pass it through to `runAgentInner()` and use it at line 236:
```typescript
cwd: cwd ?? PROJECT_ROOT,
```

**(b) Workers set `PROJECT_ROOT` via environment**: Workers could set a different `PROJECT_ROOT` when starting. But this is hacky and breaks other path resolution.

**Recommendation**: Option (a). It's a backward-compatible change -- existing callers don't pass the parameter, defaulting to `PROJECT_ROOT`.

### 10. The "thinking..." ACK message timing and content -- Warning

The blueprint says (line 75): `Reply: "Got it. Dispatched to [worker]. I'll report back when done."` This reply happens in `handleMessage()` after classification. The exact insertion point is after the dispatch-queue INSERT, before `return`.

But there's a timing issue: the typing indicator (`typingInterval` at bot.ts line 239) is started at the top of `handleMessage()`. For dispatched tasks, the interval must be cleared before the ACK reply, not after. Currently, `clearInterval(typingInterval)` is at line 269 (after `routeMessage()` returns). For dispatched tasks, we need:

```typescript
// Inside handleMessage(), after classification determines 'long':
clearInterval(typingInterval);  // Stop typing before ACK
await ctx.reply(`Got it. Dispatched to ${classification.workerType}. I'll report back when done.`);
return;  // Don't fall through to routeMessage()
```

### 11. Dedup cache is insufficient for dispatched tasks -- Warning

The existing `processedMessages` Map (bot.ts line 35) deduplicates incoming Telegram messages by `message_id`. This prevents re-processing on 409 restart replays. For dispatched tasks, there's a different dedup concern:

**Scenario**: Data crashes after inserting into `dispatch_queue` but before sending the ACK reply. On restart, the message is replayed (if not expired from dedup cache, which has a 5-minute TTL at line 36). The message gets classified as 'long' again and inserted into the queue a second time.

**Required**: Before inserting into `dispatch_queue`, check if a task with the same `chat_id` and `prompt` already exists in `queued` or `running` status:

```typescript
function isAlreadyDispatched(chatId: string, prompt: string): boolean {
  const row = db.prepare(
    `SELECT 1 FROM dispatch_queue WHERE chat_id = ? AND prompt = ? AND status IN ('queued', 'running') LIMIT 1`
  ).get(chatId, prompt);
  return !!row;
}
```

### 12. Voice messages, photos, documents, and videos with dispatch -- Warning

The blueprint doesn't mention how media messages interact with dispatch. Currently:
- Voice messages are transcribed then passed to `handleMessage()` as text (bot.ts line 435)
- Photos are downloaded and passed as a structured message via `buildPhotoMessage()` (line 469)
- Documents are downloaded via `buildDocumentMessage()` (line 505)
- Videos are downloaded via `buildVideoMessage()` (line 540)

These all flow into `handleMessage()` as text. The classifier will see the text representation (e.g., `[Voice transcribed]: build me a landing page`). The classifier should handle these correctly if it's keyword-based.

**But there's a problem**: Photo/document/video messages include local file paths in the structured message (e.g., `[Photo: /path/to/uploads/photo.jpg]`). If this message gets dispatched to a worker process, the worker needs access to the same file system path. Since workers run on the same machine via pm2, the paths remain valid. But the uploads directory cleanup (`cleanupOldUploads()` at index.ts line 70) could delete the file before the worker processes it.

**Required**: Either (a) don't clean up uploads while tasks referencing them are in `queued` status, or (b) copy media files to a dispatch-specific location, or (c) skip dispatch for media messages entirely (force inline). Option (c) is simplest for v1.

### 13. Result-poller and scheduler coexistence -- Warning

Both the scheduler (scheduler.ts line 41) and the result-poller will use `setInterval` inside the Data process. They coexist fine -- Node.js handles multiple intervals without issue. But their patterns should be consistent:

| Component | Interval | Pattern |
|-----------|----------|---------|
| Scheduler | 60s | `setInterval(() => void runDueTasks(), 60_000)` |
| Result-poller | 10s | `setInterval(() => void pollResults(), 10_000)` |
| Memory decay | 24h | `setInterval(() => runDecaySweep(), 86_400_000)` |

The result-poller should follow the same `initResultPoller(send)` pattern as `initScheduler(send)` for consistency:

```typescript
// result-poller.ts
let pollerInterval: ReturnType<typeof setInterval> | null = null;

export function initResultPoller(send: (chatId: string, text: string) => Promise<void>): void {
  if (pollerInterval) clearInterval(pollerInterval);
  pollerInterval = setInterval(() => void pollCompletedTasks(send), 10_000);
}
```

### 14. buildMemoryContext() should run before dispatch, not in the worker -- Suggestion

Currently, `buildMemoryContext()` is called at bot.ts line 246 to prepend memory context to the user's message. For dispatched tasks, this context must be built at dispatch time (in Data's process), not by the worker.

Reason: The memory system queries SQLite with `searchMemories()` and `getRecentMemories()` which are optimized for Data's process. Workers don't need memory system access -- they just need the enriched prompt.

The dispatch flow should be:
1. Build memory context: `const memCtx = await buildMemoryContext(chatIdStr, message);`
2. Build full message: `const fullMessage = memCtx ? \`${memCtx}\n\n${message}\` : message;`
3. Classify based on original `message` (not `fullMessage`)
4. Enqueue `fullMessage` as the prompt, `message` as `user_message`

This means memory context building (lines 246-247) must happen BEFORE the classification branch, which it already does in the current code. The dispatch path can reuse `fullMessage` directly.

### 15. /newchat interaction with in-flight dispatched tasks -- Suggestion

The `/newchat` command (bot.ts line 342) calls `clearSession()`. If a dispatched task is still running with the old session, the session mismatch is harmless because workers use fresh sessions (blueprint line 159: "Workers don't share sessions with Data"). But the result of the dispatched task will still be delivered to the user, potentially confusing them if they've started a new conversation thread.

**Suggestion**: When `/newchat` is invoked, optionally cancel any pending dispatched tasks for that `chat_id`:

```typescript
bot.command('newchat', async (ctx) => {
  if (!isAuthorised(ctx.chat!.id, ctx.from?.id)) return;
  clearSession(ctx.chat!.id.toString());
  cancelPendingTasks(ctx.chat!.id.toString()); // NEW: cancel queued tasks
  await ctx.reply('Session cleared. Starting fresh.');
});
```

### 16. Existing test suite impact assessment -- Suggestion

Current test files:
- `bot.test.ts` -- Tests `splitMessage()` only. No changes needed (pure function, no integration).
- `db.test.ts` -- Tests sessions, memories, FTS5, decay. Needs new tests for `dispatch_queue` CRUD operations.
- `memory.test.ts` -- Tests `buildMemoryContext()` and `saveConversationTurn()`. No changes unless these functions change signature.
- `env.test.ts` -- Tests env file parsing. No changes needed.
- `media.test.ts` -- Tests media handling. No changes needed.
- `voice.test.ts` -- Tests voice handling. No changes needed.

**New test files needed**:
- `classifier.test.ts` -- Test keyword classification rules, edge cases (multi-keyword messages), @prefix interaction
- `dispatch.test.ts` or `result-poller.test.ts` -- Test queue insertion, claiming, completion, delivery lifecycle

## Missing Elements

### 1. Classifier-to-Router composition diagram
The blueprint shows the target architecture (lines 22-38) but doesn't show exactly how the classifier sits between `parsePrefix()` and the backend call. A sequence diagram showing the decision flow for: (a) `@gemini` message, (b) quick Claude message, (c) long Claude message would eliminate ambiguity.

### 2. Queue CRUD function signatures
The blueprint defines the schema but doesn't specify the TypeScript functions needed in `db.ts`:
- `enqueueTask(chatId, userMessage, prompt, workerType): string` -- returns task UUID
- `claimTask(workerType): DispatchTask | null` -- atomic claim
- `completeTask(id, result): void`
- `failTask(id, error): void`
- `getCompletedTasks(): DispatchTask[]` -- for poller
- `markDelivered(id): void`
- `cancelPendingTasks(chatId): void` -- for /newchat
- `resetStaleTasks(timeoutMinutes): number` -- for stale task recovery

### 3. Error handling for worker failures in the result-poller
What does the user see when a task fails? The blueprint says the queue has an `error` column but doesn't specify:
- Does the poller also deliver error results?
- What format? `"Task failed: [error message]"` or something more informative?
- Does it retry failed tasks?

### 4. Worker heartbeat or liveness check
The blueprint mentions stale task recovery (line 165: "status='running' for >10min gets reset to 'queued'"). But there's no specification for WHO runs this check. It should be the result-poller or a separate interval in Data's process:

```typescript
// Run every 60s alongside the poller
function recoverStaleTasks(): void {
  const tenMinutesAgo = Math.floor(Date.now() / 1000) - 600;
  db.prepare(
    `UPDATE dispatch_queue SET status = 'queued', started_at = NULL WHERE status = 'running' AND started_at < ?`
  ).run(tenMinutesAgo);
}
```

### 5. /status or /tasks command
No command for Matthew to check the dispatch queue. A `/tasks` command showing pending/running/completed tasks would be valuable:

```typescript
bot.command('tasks', async (ctx) => {
  const tasks = getPendingAndRunningTasks();
  if (tasks.length === 0) { await ctx.reply('No tasks in queue.'); return; }
  const lines = tasks.map(t => `${t.status === 'running' ? '...' : 'o'} [${t.worker_type}] ${t.prompt.slice(0,60)}`);
  await ctx.reply(lines.join('\n'));
});
```

### 6. Telemetry events for dispatch lifecycle
The blueprint doesn't specify any telemetry events for the dispatch system. Based on the existing telemetry pattern, these are needed:

```typescript
// New event types for telemetry.ts
interface TaskDispatchedEvent extends BaseEvent {
  event_type: 'task_dispatched';
  task_id: string;
  worker_type: string;
  prompt_preview: string;
}

interface TaskClaimedEvent extends BaseEvent {
  event_type: 'task_claimed';
  task_id: string;
  worker_type: string;
  worker_name: string;
}

interface TaskCompletedEvent extends BaseEvent {
  event_type: 'task_completed';
  task_id: string;
  worker_type: string;
  queue_wait_ms: number;    // time from queued to running
  execution_ms: number;     // time from running to completed
  result_length: number;
}

interface TaskDeliveredEvent extends BaseEvent {
  event_type: 'task_delivered';
  task_id: string;
  total_latency_ms: number; // time from queued to delivered
}
```

### 7. Graceful worker shutdown protocol
The blueprint mentions pm2 auto-restart (line 165) but not graceful shutdown. Workers need to handle SIGTERM:

```typescript
// worker.ts
process.on('SIGTERM', () => {
  isShuttingDown = true;
  // Don't claim new tasks
  // Wait for current task to complete (with timeout)
  // Exit
});
```

If a worker is killed mid-task, the stale task recovery mechanism (Finding 4 in Missing Elements) resets it to 'queued'. But the half-completed Claude subprocess may leave orphaned processes. The worker should `kill` its child subprocess on SIGTERM.

## Recommendations

### R1: Export parsePrefix() from router.ts (Required for Phase 1)

```typescript
// router.ts -- change line 37 from:
function parsePrefix(raw: string): ParsedMessage {
// to:
export function parsePrefix(raw: string): ParsedMessage {
```

Also export the `ParsedMessage` interface (line 15-18).

### R2: Restructure handleMessage() with classification branch (Phase 1 core change)

The following shows the exact diff for `bot.ts` `handleMessage()`:

```typescript
// bot.ts -- replace lines 244-267 with:

    // Build memory context (only used by Claude backend)
    const memCtx = await buildMemoryContext(chatIdStr, message);
    const fullMessage = memCtx ? `${memCtx}\n\n${message}` : message;

    // Route based on @prefix first
    const { backend, message: strippedMessage } = parsePrefix(message);

    if (backend === 'ignore') {
      clearInterval(typingInterval);
      return;
    }

    // Classify Claude messages for dispatch
    if (backend === 'claude') {
      const classification = classify(strippedMessage);
      if (classification.type === 'long') {
        clearInterval(typingInterval);
        const taskId = enqueueTask(chatIdStr, message, fullMessage, classification.workerType);
        telemetry.emit({
          timestamp: new Date().toISOString(),
          event_type: 'task_dispatched',
          chat_id: chatIdStr,
          task_id: taskId,
          worker_type: classification.workerType,
          prompt_preview: message.slice(0, 80),
        });
        await ctx.reply(`Got it. Dispatched to ${classification.workerType}. I'll report back when done.`);
        return;
      }
    }

    // Progress callback: send intermediate status updates to Telegram
    const onProgress = async (status: string): Promise<void> => {
      try {
        await ctx.reply(`<i>${status}</i>`, { parse_mode: 'HTML' });
      } catch {
        // Best-effort
      }
    };

    // Inline execution (quick Claude tasks + all non-Claude backends)
    const result = await routeMessage(
      message,
      fullMessage,
      sessionId,
      () => void sendTyping(ctx.api, chatId),
      onProgress,
    );
    // ... rest of existing handler unchanged
```

### R3: Create classifier.ts with clear priority rules

```typescript
// src/classifier.ts
export interface Classification {
  type: 'quick' | 'long';
  workerType: 'starscream' | 'ravage' | 'soundwave' | 'default';
}

const WORKER_RULES: Array<{ patterns: RegExp; worker: Classification['workerType'] }> = [
  { patterns: /\b(linkedin|post|schedule\s+post|social\s+media|tweet|late\s+api)\b/i, worker: 'starscream' },
  { patterns: /\b(code|build|fix|pr\b|commit|deploy|refactor|implement|debug|test)\b/i, worker: 'ravage' },
  { patterns: /\b(research|analyze|review\s+pipeline|morning\s+report|investigate|deep\s+dive)\b/i, worker: 'soundwave' },
];

const LONG_TASK_SIGNALS = /\b(build|create|write|implement|refactor|research|analyze|review|deploy|migrate|generate|design|plan|investigate|audit|deep\s+dive)\b/i;

export function classify(message: string): Classification {
  // If no long-task signal, it's quick
  if (!LONG_TASK_SIGNALS.test(message)) {
    return { type: 'quick', workerType: 'default' };
  }

  // Match to worker type (first match wins -- order matters)
  for (const rule of WORKER_RULES) {
    if (rule.patterns.test(message)) {
      return { type: 'long', workerType: rule.worker };
    }
  }

  return { type: 'long', workerType: 'default' };
}
```

### R4: Add dispatch_queue to db.ts with corrected schema

```typescript
// db.ts -- add to createSchema(), after existing tables

    CREATE TABLE IF NOT EXISTS dispatch_queue (
      id TEXT PRIMARY KEY,
      chat_id TEXT NOT NULL,
      user_message TEXT NOT NULL,
      prompt TEXT NOT NULL,
      worker_type TEXT NOT NULL,
      status TEXT DEFAULT 'queued',
      result TEXT,
      session_id TEXT,
      created_at INTEGER NOT NULL,
      started_at INTEGER,
      completed_at INTEGER,
      error TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_queue(worker_type, status, created_at);
```

```typescript
// db.ts -- new CRUD functions

import { randomUUID } from 'crypto';

export interface DispatchTask {
  id: string;
  chat_id: string;
  user_message: string;
  prompt: string;
  worker_type: string;
  status: string;
  result: string | null;
  session_id: string | null;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  error: string | null;
}

export function enqueueTask(chatId: string, userMessage: string, prompt: string, workerType: string): string {
  const id = randomUUID();
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO dispatch_queue (id, chat_id, user_message, prompt, worker_type, status, created_at)
     VALUES (?, ?, ?, ?, ?, 'queued', ?)`
  ).run(id, chatId, userMessage, prompt, workerType, now);
  return id;
}

export function claimTask(workerType: string): DispatchTask | null {
  // Atomic claim using UPDATE ... RETURNING (SQLite 3.35+)
  const row = db.prepare(
    `UPDATE dispatch_queue SET status = 'running', started_at = ?
     WHERE id = (SELECT id FROM dispatch_queue WHERE worker_type = ? AND status = 'queued' ORDER BY created_at LIMIT 1)
     RETURNING *`
  ).get(Math.floor(Date.now() / 1000), workerType) as DispatchTask | undefined;
  return row ?? null;
}

export function completeTask(id: string, result: string): void {
  db.prepare(
    `UPDATE dispatch_queue SET status = 'completed', result = ?, completed_at = ? WHERE id = ?`
  ).run(result, Math.floor(Date.now() / 1000), id);
}

export function failTask(id: string, error: string): void {
  db.prepare(
    `UPDATE dispatch_queue SET status = 'failed', error = ?, completed_at = ? WHERE id = ?`
  ).run(error, Math.floor(Date.now() / 1000), id);
}

export function getCompletedTasks(): DispatchTask[] {
  return db.prepare(
    `SELECT * FROM dispatch_queue WHERE status = 'completed' ORDER BY completed_at`
  ).all() as DispatchTask[];
}

export function markDelivered(id: string): void {
  db.prepare(`UPDATE dispatch_queue SET status = 'delivered' WHERE id = ?`).run(id);
}

export function getFailedTasks(): DispatchTask[] {
  return db.prepare(
    `SELECT * FROM dispatch_queue WHERE status = 'failed' ORDER BY completed_at`
  ).all() as DispatchTask[];
}

export function cancelPendingTasks(chatId: string): number {
  const result = db.prepare(
    `DELETE FROM dispatch_queue WHERE chat_id = ? AND status = 'queued'`
  ).run(chatId);
  return result.changes;
}

export function resetStaleTasks(timeoutSeconds: number): number {
  const cutoff = Math.floor(Date.now() / 1000) - timeoutSeconds;
  const result = db.prepare(
    `UPDATE dispatch_queue SET status = 'queued', started_at = NULL WHERE status = 'running' AND started_at < ?`
  ).run(cutoff);
  return result.changes;
}
```

### R5: Create result-poller.ts as an in-process interval

```typescript
// src/result-poller.ts
import { getCompletedTasks, getFailedTasks, markDelivered, resetStaleTasks } from './db.js';
import { redactSecrets, formatForTelegram, splitMessage } from './bot.js';
import { saveConversationTurn } from './memory.js';
import { logger } from './logger.js';
import * as telemetry from './telemetry.js';

type ResultSender = (chatId: string, text: string) => Promise<void>;

let pollerInterval: ReturnType<typeof setInterval> | null = null;
let staleRecoveryInterval: ReturnType<typeof setInterval> | null = null;

export function initResultPoller(send: ResultSender): void {
  if (pollerInterval) clearInterval(pollerInterval);
  if (staleRecoveryInterval) clearInterval(staleRecoveryInterval);

  pollerInterval = setInterval(() => void pollResults(send), 10_000);
  staleRecoveryInterval = setInterval(() => recoverStaleTasks(), 60_000);
  logger.info('Result poller started (every 10s, stale recovery every 60s)');
}

async function pollResults(send: ResultSender): Promise<void> {
  // Deliver completed tasks
  const completed = getCompletedTasks();
  for (const task of completed) {
    try {
      const responseText = redactSecrets(task.result ?? 'Task completed with no output.');
      const formatted = formatForTelegram(responseText);
      for (const part of splitMessage(formatted)) {
        await send(task.chat_id, part);
      }

      // Save to memory system
      saveConversationTurn(task.chat_id, task.user_message, responseText);

      markDelivered(task.id);

      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'task_delivered' as any,
        task_id: task.id,
        chat_id: task.chat_id,
        total_latency_ms: task.completed_at && task.created_at
          ? (task.completed_at - task.created_at) * 1000
          : 0,
      });

      logger.info({ taskId: task.id, workerType: task.worker_type }, 'Task result delivered');
    } catch (err) {
      logger.error({ err, taskId: task.id }, 'Failed to deliver task result');
    }
  }

  // Deliver failed task notifications
  const failed = getFailedTasks();
  for (const task of failed) {
    try {
      const errorMsg = `Task failed: "${task.user_message.slice(0, 60)}..." -- ${task.error ?? 'unknown error'}`;
      await send(task.chat_id, redactSecrets(errorMsg));
      markDelivered(task.id);
      logger.warn({ taskId: task.id }, 'Task failure notification delivered');
    } catch (err) {
      logger.error({ err, taskId: task.id }, 'Failed to deliver failure notification');
    }
  }
}

function recoverStaleTasks(): void {
  const recovered = resetStaleTasks(600); // 10 minutes
  if (recovered > 0) {
    logger.warn({ recovered }, 'Reset stale tasks back to queued');
  }
}
```

### R6: Add cwd parameter to runAgent() for worker support

```typescript
// agent.ts line 133 -- add optional cwd parameter
export async function runAgent(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
  cwd?: string,
): Promise<AgentResult> {
  // ... existing concurrency check ...
  // Pass cwd to runAgentInner:
  return await runAgentInner(message, sessionId, onTyping, onProgress, cwd);
}

// agent.ts line 175 -- add cwd parameter
async function runAgentInner(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
  cwd?: string,
): Promise<AgentResult> {
  // ... existing code ...
  // Line 236 -- use parameter:
  cwd: cwd ?? PROJECT_ROOT,
}
```

### R7: Initialize result-poller in index.ts alongside scheduler

```typescript
// index.ts -- add import
import { initResultPoller } from './result-poller.js';

// index.ts -- after initScheduler() block (~line 101), add:
initResultPoller((chatId, text) => {
  if (!botApiRef.current) return Promise.resolve();
  return botApiRef.current.sendMessage(chatId, text, { parse_mode: 'HTML' }).then(() => {});
});
```

### R8: Add SQLite busy_timeout for multi-process safety

```typescript
// db.ts -- add to initDatabase() after WAL pragma (line 69)
db.pragma('busy_timeout = 5000');  // Wait up to 5s for write lock instead of failing immediately
```

This is essential for the multi-process architecture. Without it, workers hitting a write lock will get immediate `SQLITE_BUSY` errors instead of waiting for the lock to be released.
