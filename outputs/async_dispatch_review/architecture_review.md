# Architecture Review: EA-Claude Async Dispatch

## Domain
Queue-Based Dispatch Architecture

## Files Reviewed
- `/home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/orchestrator_analysis.md` (orchestrator assignment and flags)
- `/home/apexaipc/projects/claudeclaw/BLUEPRINT-async-dispatch.md` (full blueprint, lines 1-172)
- `/home/apexaipc/projects/claudeclaw/src/db.ts` (database layer, lines 1-237)
- `/home/apexaipc/projects/claudeclaw/src/agent.ts` (Claude SDK integration, lines 1-328)
- `/home/apexaipc/projects/claudeclaw/src/bot.ts` (message handling, lines 1-591)
- `/home/apexaipc/projects/claudeclaw/src/scheduler.ts` (scheduler polling pattern, lines 1-107)
- `/home/apexaipc/projects/claudeclaw/src/index.ts` (pm2 entry point, lines 1-179)
- `/home/apexaipc/projects/claudeclaw/src/router.ts` (multi-backend routing, lines 1-171)
- `/home/apexaipc/projects/claudeclaw/src/config.ts` (configuration, lines 1-47)
- `/home/apexaipc/projects/claudeclaw/src/telemetry.ts` (JSONL telemetry, lines 1-89)
- `/home/apexaipc/projects/claudeclaw/src/memory.ts` (memory system, lines 1-78)

---

## Findings

### 1. Schema-Spec Mismatch: Missing `notified` Column (Critical)

The `dispatch_queue` schema (blueprint lines 46-58) defines status values as `'queued' | 'running' | 'completed' | 'failed'`. The result-poller specification (blueprint line 80) references `WHERE status = 'completed' AND NOT notified`, but no `notified` column exists in the schema.

There are two valid resolutions, and they have different architectural implications:

**Option A: Add a `notified` boolean column.**
This keeps the task lifecycle simple (completed = work done, notified = user informed) and allows re-querying for failed notifications.

```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  ...
  notified INTEGER DEFAULT 0,  -- 0 = not yet sent to user, 1 = delivered
  ...
);
CREATE INDEX IF NOT EXISTS idx_dispatch_pending_notify
  ON dispatch_queue(status, notified) WHERE status = 'completed' AND notified = 0;
```

**Option B: Add a `'delivered'` status value.** This collapses notification into the status state machine (`queued -> running -> completed -> delivered`). Simpler schema, but means `status` does double duty for work lifecycle and delivery lifecycle, which couples two independent concerns.

Recommendation: Option A. The `notified` column keeps work status and delivery status independent, which is the right separation for a system where delivery can fail independently of task completion.

### 2. No Busy Timeout Configuration for Multi-Process SQLite (Critical)

The current `initDatabase()` (db.ts lines 65-71) opens the connection and sets WAL mode but does not configure a busy timeout. With a single process this is fine. With 4+ processes (Data + 3 workers) all writing to the same SQLite file, concurrent write attempts will throw `SQLITE_BUSY` immediately rather than waiting for the lock to release.

The `better-sqlite3` library provides `db.pragma('busy_timeout = 5000')` which tells SQLite to wait up to 5 seconds for a write lock before failing. Without this, any two processes writing within the same WAL checkpoint window will collide.

```typescript
// db.ts, line 69 -- add after WAL mode
export function initDatabase(): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('busy_timeout = 5000');  // Wait up to 5s for write lock
  createSchema(db);
}
```

This is non-negotiable for the multi-process architecture. Without it, workers will intermittently fail to claim or complete tasks.

### 3. Task Claim Race Condition: No Atomic Claim Operation Specified (Critical)

The blueprint (line 91) describes workers claiming tasks as `SET status = 'running'`, but does not specify the atomic claim mechanism. A naive implementation would be:

```typescript
// WRONG -- race condition
const task = db.prepare("SELECT * FROM dispatch_queue WHERE status = 'queued' AND worker_type = ? LIMIT 1").get(type);
if (task) {
  db.prepare("UPDATE dispatch_queue SET status = 'running' WHERE id = ?").run(task.id);
}
```

Two workers of the same type (or a default worker competing with a typed worker) could SELECT the same row, then both UPDATE it. The second UPDATE is a no-op (row already `running`), but the second worker has a stale `task` object and will execute a duplicate.

The fix is an atomic claim using `UPDATE ... RETURNING` (SQLite 3.35+, which better-sqlite3 supports):

```typescript
const task = db.prepare(`
  UPDATE dispatch_queue
  SET status = 'running', started_at = ?
  WHERE id = (
    SELECT id FROM dispatch_queue
    WHERE status = 'queued' AND worker_type = ?
    ORDER BY created_at ASC
    LIMIT 1
  )
  RETURNING *
`).get(Date.now(), workerType);
```

This is a single statement, executed atomically under SQLite's implicit write lock. No two processes can claim the same row. The blueprint MUST specify this pattern or workers will produce duplicate executions under load.

### 4. Result Poller Has No Access to Bot Instance or Formatting Pipeline (Critical)

The result-poller (blueprint lines 78-82) needs to:
1. Query completed tasks from SQLite
2. Format the result for Telegram (redact secrets, convert markdown, split messages)
3. Send via Telegram Bot API
4. Save to memory system

The blueprint says the poller runs on an interval inside the main Data process (it references `bot API`), but does not specify how the poller gets access to:

- **Bot API instance**: The `bot.api` object is created inside `index.ts` line 90 (`const bot = createBot()`) and refreshed on each 409 retry. The poller needs the `botApiRef.current` pattern already used by the scheduler (index.ts line 86).
- **Formatting functions**: `redactSecrets()`, `formatForTelegram()`, `splitMessage()` are exported from `bot.ts` (lines 62, 85, 149), so they are importable. This works.
- **Memory save**: `saveConversationTurn()` from `memory.ts` (line 58) requires the original user message. The dispatch_queue stores `prompt` (which includes memory context prefix from `buildMemoryContext()`), so the raw user message is lost by the time the poller runs unless stored separately.

Concrete design issue: the `prompt` column in the dispatch queue (blueprint line 49) will contain the memory-enriched `fullMessage` from bot.ts line 247 (`const fullMessage = memCtx ? \`${memCtx}\n\n${message}\` : message`). When the result comes back and the poller calls `saveConversationTurn()`, it would save the enriched prompt, not the original user message. This corrupts the memory system by feeding memory context back into itself recursively.

**Fix**: Add an `original_message TEXT` column to the dispatch_queue schema, storing the raw user input separately from the enriched prompt sent to Claude.

```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  id TEXT PRIMARY KEY,
  chat_id TEXT NOT NULL,
  original_message TEXT NOT NULL,  -- raw user input (for memory save)
  prompt TEXT NOT NULL,            -- enriched with memory context (sent to worker)
  worker_type TEXT NOT NULL,
  ...
);
```

### 5. No `priority` Column or Queue Ordering Beyond FIFO (Warning)

The schema uses `created_at` for ordering (implied by the worker poll pattern). But there is no `priority` column. This means:

- All tasks are strictly FIFO within a worker type.
- If 5 research tasks are queued and the user sends an urgent "check this PR NOW", it waits behind 4 earlier tasks.
- Scheduled tasks (if routed through the queue per Flag 5 in the orchestrator analysis) have no way to be distinguished from interactive tasks.

At minimum, a `priority INTEGER DEFAULT 0` column allows interactive tasks to be prioritized over scheduled/batch tasks. The worker claim query becomes `ORDER BY priority DESC, created_at ASC`.

### 6. No `retry_count` or Dead-Letter Mechanism (Warning)

The schema has an `error TEXT` column (line 57) but no retry count. The risk mitigation section (blueprint line 165) says tasks stuck as `running` for >10min get reset to `queued`. But there is no limit on how many times this happens.

Failure scenario: A task that consistently crashes the Claude subprocess (e.g., triggers an OOM or a malformed prompt that causes SDK errors) will be reset to `queued`, claimed again, crash again, reset again -- infinitely. This creates a "poison pill" that blocks the worker for 10-minute cycles forever.

**Fix**: Add `retry_count INTEGER DEFAULT 0` and `max_retries INTEGER DEFAULT 3`. The stale task recovery logic should increment `retry_count` and move tasks to a `'dead'` status once the limit is reached:

```typescript
// Stale task recovery (runs on a timer)
db.prepare(`
  UPDATE dispatch_queue
  SET status = CASE
    WHEN retry_count >= 3 THEN 'dead'
    ELSE 'queued'
  END,
  retry_count = retry_count + 1,
  started_at = NULL
  WHERE status = 'running'
  AND started_at < ?
`).run(Date.now() - 10 * 60 * 1000);
```

### 7. Stale Task Recovery Ownership Is Unspecified (Warning)

The blueprint states "Unclaimed tasks (status='running' for >10min) get reset to 'queued'" (line 165) but does not say which process runs this recovery.

Options:
- **Each worker runs it on its poll cycle**: Every 5s, each of the 4 processes checks for stale tasks. This means 4 processes redundantly scanning the same rows. Functionally harmless (the UPDATE is idempotent), but wasteful.
- **Data (main process) runs it**: Single-point recovery on a dedicated interval (e.g., every 60s, similar to the scheduler). This is cleaner but means recovery stops if Data crashes.
- **A dedicated sweep in the result-poller**: The poller already runs on a 10s interval and could piggyback stale recovery.

Recommendation: Data's main process runs it on a 60s interval (same pattern as the scheduler in `index.ts` line 68). If Data is down, workers are also unable to deliver results, so tying recovery to Data's lifecycle is acceptable.

### 8. Memory System Completely Bypassed for Async Tasks (Warning)

The orchestrator flagged this (Flag 6), but the architectural impact is larger than stated. The memory system serves two purposes:

1. **Context building** (`buildMemoryContext()` in memory.ts line 19): Enriches the prompt with relevant past context. For dispatched tasks, this happens at dispatch time (bot.ts line 246), so this works correctly.

2. **Context saving** (`saveConversationTurn()` in memory.ts line 58): Records the conversation turn for future recall. For dispatched tasks, the result arrives asynchronously via the poller. The poller must call `saveConversationTurn(chatId, originalMessage, resultText)` to close the loop.

Without this, every async interaction creates a "memory hole." If Matthew dispatches "research competitor pricing for X" and later asks "what did you find about competitor pricing?", the memory system has no record of either the question or the answer.

The result-poller specification (blueprint lines 78-82) must explicitly include:

```typescript
// After sending result to Telegram:
saveConversationTurn(task.chat_id, task.original_message, task.result);
```

This reinforces the need for the `original_message` column from Finding #4.

### 9. Scheduler Path Creates a Backdoor Around the Queue (Warning)

The scheduler (scheduler.ts line 59) calls `runAgent()` directly:

```typescript
const result = await runAgent(task.prompt, undefined, () => {});
```

This bypasses the dispatch queue entirely. In the current single-process model, this means scheduled tasks and interactive tasks compete for the same `MAX_CONCURRENT_AGENTS = 1` slot (agent.ts line 80). The async dispatch blueprint does not address this.

Two consequences:
1. A scheduled task running at 9am blocks all interactive messages until it completes -- exactly the problem the blueprint is trying to solve.
2. Scheduled tasks don't benefit from worker specialization. A scheduled "morning report" (research task) runs on Data instead of being dispatched to Soundwave.

**Recommendation**: The scheduler should insert into `dispatch_queue` instead of calling `runAgent()`:

```typescript
// scheduler.ts -- modified to dispatch through queue
import { v4 as uuid } from 'uuid';

async function runDueTasks(): Promise<void> {
  const tasks = getDueTasks();
  for (const task of tasks) {
    const workerType = classifyForWorker(task.prompt); // reuse classifier logic
    db.prepare(`
      INSERT INTO dispatch_queue (id, chat_id, original_message, prompt, worker_type, status, created_at)
      VALUES (?, ?, ?, ?, ?, 'queued', ?)
    `).run(uuid(), ALLOWED_CHAT_ID, task.prompt, task.prompt, workerType, Date.now());

    // Update next_run immediately so the task isn't re-queued next cycle
    const nextRun = computeNextRun(task.schedule);
    updateTaskAfterRun(task.id, nextRun, 'Dispatched to queue');
  }
}
```

This makes scheduled tasks first-class citizens of the dispatch system and eliminates the agent slot contention.

### 10. Result Poller Polling Interval Creates Notification Latency Floor (Suggestion)

The result-poller polls every 10 seconds (blueprint line 79). This means there is always a 0-10s delay between task completion and user notification. For a task that took 5 minutes, 10s is negligible. But the polling pattern also means:

- If 3 tasks complete within a 10s window, the user gets 3 separate Telegram messages in rapid succession. There is no batching or aggregation.
- The poller has no exponential backoff. When the queue is empty (the common case), it still runs SELECT every 10s -- 8,640 queries per day per process. With WAL mode this is cheap but not free.

**Suggestion**: Use an adaptive polling interval. When the queue has no pending tasks, poll every 30s. When a task is dispatched, drop to 5s polling. When a task completes and is delivered, check immediately for more, then ramp back up.

```typescript
let pollInterval = 30_000; // Idle interval

function onTaskDispatched() {
  pollInterval = 5_000; // Active interval
}

function pollResults() {
  const results = getCompletedUnnotified();
  if (results.length > 0) {
    // deliver results...
    pollInterval = 1_000; // Check for more immediately
  } else {
    pollInterval = Math.min(pollInterval * 2, 30_000); // Ramp back to idle
  }
  setTimeout(pollResults, pollInterval);
}
```

### 11. Voice Mode State Is In-Memory and Inaccessible to Poller (Suggestion)

`voiceEnabledChats` (bot.ts line 25) is a `Set<string>` stored in-memory. The result-poller cannot check whether the user has voice mode enabled for a given chat. This means dispatched task results always come back as text, even if the user has voice mode on.

This is likely acceptable for the MVP (voice mode is a nice-to-have for async results), but if voice consistency matters, `voiceEnabledChats` needs to move to SQLite:

```sql
CREATE TABLE IF NOT EXISTS chat_settings (
  chat_id TEXT PRIMARY KEY,
  voice_enabled INTEGER DEFAULT 0
);
```

### 12. No `worker_id` Column to Track Which Worker Claimed a Task (Suggestion)

When a task is stuck at `status = 'running'` and the stale recovery logic kicks in, there is no way to determine WHICH worker claimed it. For debugging and telemetry, a `worker_id TEXT` column (set at claim time) would identify the responsible worker. This also helps detect if a specific worker is consistently crashing.

```sql
ALTER TABLE dispatch_queue ADD COLUMN worker_id TEXT;
```

### 13. Telemetry File Contention Across Processes (Suggestion)

`telemetry.emit()` (telemetry.ts line 73) uses `fs.appendFileSync()`. With 4 processes writing to the same `telemetry.jsonl` file, concurrent appends are generally safe on Linux for writes under `PIPE_BUF` (4096 bytes) -- each write is atomic at the kernel level.

However, a JSONL event line that exceeds 4KB (possible if `tool_summary` or `error_message` contains large content) could interleave with another process's write, producing a corrupted line.

Mitigation options:
- Truncate event fields before serialization to ensure lines stay under 4KB.
- Use per-process telemetry files (`telemetry-data.jsonl`, `telemetry-starscream.jsonl`, etc.) and have Sky-Lynx read all of them.
- Use `fs.open()` with `O_APPEND` flag and `fs.writeSync()` for guaranteed atomic append semantics.

For the current workload (4 processes, low event rate), this is low risk but worth documenting as a known limitation.

---

## Missing Elements

### 1. No Interface Contract Between Classifier and Queue
The blueprint defines the classifier (lines 61-70) and the queue schema (lines 46-58) independently. There is no explicit TypeScript interface connecting them. What does the classifier return? What does the dispatch insertion function accept? A `DispatchRequest` interface should be specified:

```typescript
interface DispatchRequest {
  chatId: string;
  originalMessage: string;
  enrichedPrompt: string;
  workerType: 'starscream' | 'ravage' | 'soundwave' | 'default';
  priority?: number;
}
```

### 2. No Defined Status State Machine
The blueprint lists status values (`queued`, `running`, `completed`, `failed`) but does not define which transitions are valid. Without this, bugs can silently corrupt the queue state. The valid transitions should be:

```
queued -> running (worker claims)
running -> completed (worker finishes)
running -> failed (worker errors)
running -> queued (stale recovery)
failed -> queued (manual retry, if implemented)
completed -> delivered (after notification -- if using status-based approach)
```

Any UPDATE that violates these transitions should be rejected or logged.

### 3. No Queue Size Limits or Backpressure
The blueprint has no mechanism for backpressure. If tasks are queued faster than workers process them (e.g., 10 scheduled tasks fire at once while the user also sends 3 messages), the queue grows unboundedly. There should be:
- A maximum queue depth per worker type (e.g., 10 pending tasks per type).
- Behavior when the limit is hit: reject with a user-facing message ("Queue full, try again later"), or silently queue with a warning.

### 4. No `/status` or `/queue` Command for User Visibility
The user has no way to see what is in the queue, what is running, or what completed. A `/queue` or `/status` command should show:
- Number of pending tasks per worker type
- Currently running tasks with elapsed time
- Recently completed tasks

### 5. No Cancellation Mechanism
The orchestrator flagged this (Flag 7). The user cannot cancel a queued or running task. At minimum, a `/cancel <id>` command should set `status = 'cancelled'` for queued tasks. For running tasks, cancellation is harder (requires signaling the worker), but marking the task as cancelled in the DB and having the worker check periodically is a reasonable approach.

### 6. No Telemetry Events for Dispatch Lifecycle
The telemetry system (telemetry.ts) has no event types for:
- `task_dispatched` (classifier sent task to queue)
- `task_claimed` (worker picked up task)
- `task_completed` (worker finished)
- `task_failed` (worker errored)
- `task_delivered` (result sent to user)
- `task_stale_recovered` (stale recovery kicked in)

Without these, Sky-Lynx (Phase 4) has no visibility into the dispatch system's performance.

### 7. No Graceful Worker Shutdown Behavior
The blueprint mentions pm2 auto-restart (line 165) but does not specify what happens to in-flight tasks when a worker receives SIGTERM. The worker must:
1. Stop claiming new tasks.
2. Wait for the current task to complete (with a timeout).
3. If the timeout expires, leave the task as `running` for stale recovery.
4. Exit cleanly.

This is the same pattern as the existing `shutdown()` in index.ts (line 104) but with an in-flight task check.

### 8. No Error Reporting Format for Failed Tasks
When a task fails, the `error TEXT` column stores the error message. But the result-poller specification (blueprint lines 78-82) only handles `status = 'completed'`. There is no specification for how failed tasks are reported to the user. Should they:
- Be sent as "Task failed: [error message]"?
- Be silently logged?
- Trigger a retry before notifying?

---

## Recommendations

### R1: Define the Complete Dispatch Data Flow (Priority: P0)

Create a sequence diagram covering the full lifecycle of a dispatched task. The current blueprint describes components but not the data flow between them. Here is what it should look like:

```
1. User sends message to Telegram
2. bot.ts:handleMessage() receives message
3. router.ts:parsePrefix() checks for @prefix -- if non-Claude, handle inline (no dispatch)
4. classifier.ts:classify() determines quick vs. long
5. If quick: existing flow (router.ts -> agent.ts -> reply)
6. If long:
   a. buildMemoryContext() enriches the prompt
   b. INSERT into dispatch_queue (original_message + enriched prompt + worker_type)
   c. Reply to user: "Dispatched to [worker]. I'll report back when done."
   d. Return immediately
7. Worker polls dispatch_queue, claims task (atomic UPDATE ... RETURNING)
8. Worker calls runAgent() with enriched prompt and worker-specific CLAUDE.md path
9. Worker writes result to dispatch_queue (SET status='completed', result=...)
10. Result-poller detects completed task
11. Result-poller: redactSecrets() -> formatForTelegram() -> splitMessage()
12. Result-poller: bot.api.sendMessage() to chat_id
13. Result-poller: saveConversationTurn(chat_id, original_message, result)
14. Result-poller: SET notified = 1
```

### R2: Implement the Result Poller as a Module Within Data's Process (Priority: P0)

The result-poller should NOT be a separate pm2 process. It should be a `setInterval` inside Data's main process (index.ts), similar to the scheduler. Reasons:
- It needs access to `botApiRef.current` (the mutable bot API reference).
- It needs the formatting pipeline functions from `bot.ts`.
- It needs the memory system.
- It shares the same lifecycle as the bot (if Data is down, nobody delivers results).

```typescript
// result-poller.ts
import { getCompletedUnnotified, markNotified } from './db.js';
import { redactSecrets, formatForTelegram, splitMessage } from './bot.js';
import { saveConversationTurn } from './memory.js';
import { logger } from './logger.js';

type Sender = (chatId: string, text: string) => Promise<void>;

let pollerInterval: ReturnType<typeof setInterval> | null = null;

export function initResultPoller(send: Sender): void {
  if (pollerInterval) clearInterval(pollerInterval);
  pollerInterval = setInterval(() => void pollResults(send), 10_000);
  logger.info('Result poller started (checking every 10s)');
}

async function pollResults(send: Sender): Promise<void> {
  const tasks = getCompletedUnnotified();
  for (const task of tasks) {
    try {
      let text = task.result?.trim() || 'Task completed with no output.';
      text = redactSecrets(text);
      const formatted = formatForTelegram(text);
      for (const part of splitMessage(formatted)) {
        await send(task.chat_id, part);
      }
      saveConversationTurn(task.chat_id, task.original_message, text);
      markNotified(task.id);
    } catch (err) {
      logger.error({ err, taskId: task.id }, 'Failed to deliver task result');
    }
  }
}
```

### R3: Add the Missing Schema Columns Before Phase 1 Implementation (Priority: P0)

The final schema should be:

```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  id TEXT PRIMARY KEY,
  chat_id TEXT NOT NULL,
  original_message TEXT NOT NULL,
  prompt TEXT NOT NULL,
  worker_type TEXT NOT NULL,
  status TEXT DEFAULT 'queued',
  priority INTEGER DEFAULT 0,
  result TEXT,
  session_id TEXT,
  worker_id TEXT,
  retry_count INTEGER DEFAULT 0,
  notified INTEGER DEFAULT 0,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_dispatch_claimable
  ON dispatch_queue(worker_type, status, priority DESC, created_at ASC)
  WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_dispatch_notify
  ON dispatch_queue(status, notified)
  WHERE status = 'completed' AND notified = 0;

CREATE INDEX IF NOT EXISTS idx_dispatch_stale
  ON dispatch_queue(status, started_at)
  WHERE status = 'running';
```

### R4: Restructure the 4-Phase Plan (Priority: P1)

The current phase ordering (blueprint lines 138-152) intermixes infrastructure and features. A revised order that produces a working system at each phase boundary:

**Phase 1a (Foundation):** dispatch_queue schema + db.ts additions + atomic claim function + busy timeout
**Phase 1b (Dispatch):** classifier.ts + bot.ts changes (dispatch long tasks, ACK user)
**Phase 1c (Delivery):** result-poller.ts + index.ts integration (init poller alongside scheduler)
**Phase 1d (Test):** End-to-end test: send long message -> see ACK -> see result. This is the first deployable milestone.

**Phase 2 (Workers):** worker.ts + pm2 ecosystem config + worker CLAUDE.md files + graceful shutdown
**Phase 3 (Reliability):** Stale recovery, retry/dead-letter, `/queue` and `/cancel` commands, scheduler integration
**Phase 4 (Observability):** Dispatch telemetry events, Sky-Lynx integration, duration estimation

The key change: Phase 1 can be tested entirely within the single Data process (using a single "default" worker thread or even running queued tasks inline) before introducing pm2 multi-process complexity in Phase 2. This de-risks the most dangerous architectural change (multi-process SQLite access) by first validating the queue logic in a single process.

### R5: Worker `runAgent()` Callback Adaptation (Priority: P1)

Workers cannot use the existing `onTyping` and `onProgress` callbacks since they have no Telegram context. The `runAgent()` function signature (agent.ts line 133) should be called with no-op callbacks from workers:

```typescript
// worker.ts
const result = await runAgent(
  task.prompt,
  undefined,        // no session resume for dispatched tasks
  () => {},          // no typing indicator
  undefined,         // no progress callback (or write to queue for progress tracking)
);
```

This works today because both callbacks are already optional/no-op safe. But consider adding an optional `onProgress` that writes to a `progress TEXT` column in the dispatch queue, allowing the result-poller to send interim updates to the user.

---

## Summary Verdict

The core idea is sound: SQLite as a task queue with pm2-managed workers is a reasonable architecture for this workload level (single user, <100 tasks/day, 3-4 workers). The polling pattern, while not the most efficient, is the right choice for simplicity and debuggability.

The blueprint has three critical gaps that must be resolved before implementation:
1. The schema is incomplete (missing `notified`, `original_message`, `retry_count`, `worker_id`, `priority` columns).
2. The atomic task claim operation is unspecified, creating a race condition.
3. The result-poller's integration with the existing bot (API access, formatting, memory) is hand-waved.

The 4-phase plan should be restructured to deliver a testable single-process queue system before introducing multi-process workers. This reduces the blast radius of the most dangerous change (multi-process SQLite access) and provides an early validation point.

The scheduler path (scheduler.ts calling `runAgent()` directly) should be routed through the dispatch queue to fully solve the blocking problem. Otherwise, scheduled tasks remain a source of the exact contention this blueprint is designed to eliminate.
