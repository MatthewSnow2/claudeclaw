# Concurrency Review: EA-Claude Async Dispatch

## Domain
Concurrency & Process Isolation

## Files Reviewed
- `/home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/orchestrator_analysis.md` (assignment brief)
- `/home/apexaipc/projects/claudeclaw/BLUEPRINT-async-dispatch.md` (full blueprint, all sections)
- `/home/apexaipc/projects/claudeclaw/src/db.ts` (lines 1-237: SQLite singleton, WAL pragma, schema, all query functions)
- `/home/apexaipc/projects/claudeclaw/src/agent.ts` (lines 1-328: MAX_CONCURRENT_AGENTS, retry logic, runAgent/runAgentInner, env sanitization)
- `/home/apexaipc/projects/claudeclaw/src/scheduler.ts` (lines 1-107: polling interval, runDueTasks sequential loop, runAgent call)
- `/home/apexaipc/projects/claudeclaw/src/index.ts` (lines 1-178: PID lock, signal handling, 409 retry, scheduler init)
- `/home/apexaipc/projects/claudeclaw/src/bot.ts` (lines 1-591: dedup cache, handleMessage, typing indicators, message formatting)
- `/home/apexaipc/projects/claudeclaw/src/router.ts` (lines 1-171: parsePrefix, routeMessage, backend dispatch)
- `/home/apexaipc/projects/claudeclaw/src/config.ts` (lines 1-47: STORE_DIR, PROJECT_ROOT)
- `/home/apexaipc/projects/claudeclaw/src/telemetry.ts` (lines 1-89: appendFileSync emit pattern)

---

## Findings

### 1. CRITICAL: Task Claiming Race Condition (Double-Claim)

The blueprint describes task claiming as a two-step process (line 91-92): poll for queued tasks, then `SET status = 'running'`. This is the classic SELECT-then-UPDATE race condition across OS processes.

**Exact failure sequence:**

```
T=0ms   Worker-Starscream: SELECT * FROM dispatch_queue WHERE worker_type='starscream' AND status='queued' ORDER BY created_at LIMIT 1
          -> Returns task id='abc-123'

T=1ms   Worker-Default:    SELECT * FROM dispatch_queue WHERE worker_type='starscream' AND status='queued' ORDER BY created_at LIMIT 1
          -> Also returns task id='abc-123' (status is still 'queued')

T=2ms   Worker-Starscream: UPDATE dispatch_queue SET status='running', started_at=? WHERE id='abc-123'
          -> Success

T=3ms   Worker-Default:    UPDATE dispatch_queue SET status='running', started_at=? WHERE id='abc-123'
          -> Also succeeds! (no WHERE status='queued' guard)
          -> Both workers now execute the same task
```

Even if you add `WHERE status='queued'` to the UPDATE, SQLite's WAL mode allows concurrent reads but serializes writes. The gap between the SELECT and UPDATE is the vulnerability window. Two processes can read the same row before either writes.

**Fix: Use an atomic claim with `UPDATE ... RETURNING` (SQLite 3.35+, Ubuntu 24.04 ships 3.45):**

```typescript
function claimTask(workerType: string): DispatchTask | null {
  const row = db.prepare(`
    UPDATE dispatch_queue
    SET status = 'running',
        started_at = ?
    WHERE id = (
      SELECT id FROM dispatch_queue
      WHERE worker_type = ? AND status = 'queued'
      ORDER BY created_at ASC
      LIMIT 1
    )
    RETURNING *
  `).get(Math.floor(Date.now() / 1000), workerType);

  return row ?? null;
}
```

This is a single SQL statement. SQLite acquires a RESERVED lock for the entire statement, so only one process can execute this UPDATE at a time. The inner SELECT and outer UPDATE happen atomically within the same lock acquisition. No two workers can claim the same row.

**Alternative for older SQLite (pre-3.35, no RETURNING):**

```typescript
function claimTask(workerType: string): DispatchTask | null {
  const claimId = crypto.randomUUID();
  const now = Math.floor(Date.now() / 1000);

  const changes = db.prepare(`
    UPDATE dispatch_queue
    SET status = 'running',
        started_at = ?,
        session_id = ?
    WHERE id = (
      SELECT id FROM dispatch_queue
      WHERE worker_type = ? AND status = 'queued'
      ORDER BY created_at ASC
      LIMIT 1
    )
  `).run(now, claimId, workerType);

  if (changes.changes === 0) return null;

  return db.prepare(
    `SELECT * FROM dispatch_queue WHERE session_id = ? AND status = 'running'`
  ).get(claimId) as DispatchTask;
}
```

---

### 2. CRITICAL: No SQLite busy_timeout Configured

`db.ts` line 69 sets `journal_mode = WAL` but does not set `busy_timeout`. The default is 0ms, meaning any write that encounters a lock held by another process immediately throws `SQLITE_BUSY` rather than waiting.

With 4+ processes (Data bot + 3 workers) all writing to the same database file, write contention is guaranteed:
- Data inserts into `dispatch_queue` when dispatching
- Workers UPDATE `dispatch_queue` when claiming and completing tasks
- Scheduler reads `scheduled_tasks` (read-only, no contention in WAL)
- Data and workers both write to `memories` table
- Result-poller UPDATEs completed tasks as notified

Under WAL mode, multiple readers are fine, but only one writer can hold the RESERVED lock at any time. Without `busy_timeout`, the second writer immediately fails instead of retrying.

**Fix: Add `busy_timeout` pragma in `initDatabase()`:**

```typescript
export function initDatabase(): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('busy_timeout = 5000');  // Wait up to 5s for lock
  createSchema(db);
}
```

5000ms is appropriate here because:
- Claude subprocess writes (completing a task) could take a few hundred ms if the result text is large
- Memory system writes are small and fast
- 5s is generous enough to handle temporary lock contention without making the system feel slow
- If a lock is held for > 5s, something is seriously wrong and SQLITE_BUSY is the correct signal

Every process (Data, workers, result-poller) must set this pragma on its own connection.

---

### 3. CRITICAL: Retry Backoff Collision (Thundering Herd on 529)

`agent.ts` lines 83-95 implement exponential backoff for 529/503 API errors with delays of 10s, 20s, 40s. This is deterministic -- no jitter. If Data + 3 workers all hit the Claude API simultaneously and get 529 errors, they all retry at exactly the same intervals:

```
T=0s    Data, Starscream, Ravage, Soundwave all get 529
T=10s   All four retry simultaneously -> all get 529 again
T=20s   All four retry simultaneously -> all get 529 again
T=40s   All four retry simultaneously -> all get 529 again
T=???   All four exhaust retries and fail
```

**Fix: Add jitter to the retry delay:**

```typescript
function jitteredDelay(baseMs: number, attempt: number): number {
  const exponential = baseMs * Math.pow(2, attempt);
  // Full jitter: random value between 0 and the exponential delay
  // This decorrelates retries across processes
  return Math.floor(Math.random() * exponential) + (exponential * 0.5);
}

// In the retry loop (agent.ts line 154):
const delay = jitteredDelay(RETRY_BASE_DELAY_MS, attempt);
```

The "full jitter" strategy (as described in AWS's architecture blog) is ideal here because the processes have no coordination channel. Each process independently picks a random delay within the exponential window, spreading retries across time.

---

### 4. WARNING: Worker Crash Leaves Task in 'running' State -- Recovery Window Too Wide

Blueprint line 165: "Unclaimed tasks (status='running' for >10min) get reset to 'queued'." Several problems:

**a) 10 minutes is too long for many task types.** A simple "research X" task might take 2-3 minutes. If the worker crashes 30 seconds in, the user waits 10+ minutes (remaining timeout + re-execution) for what should be a 3-minute task.

**b) Who runs the recovery check?** The blueprint doesn't specify. If it runs inside each worker, a crashed worker can't recover its own tasks. It must run in a process that's always alive -- either the Data bot or a dedicated watchdog.

**c) pm2 restart creates a new PID.** When pm2 restarts a crashed worker, the new process has no knowledge of the old process's claimed task. The old task sits at `status='running'` for the full timeout period. Meanwhile, the new worker starts polling and claiming new tasks, ignoring the stuck one.

**d) Task re-execution side effects.** A task that was mid-execution (e.g., already pushed a git commit, already posted to LinkedIn) will be re-executed from scratch after recovery. There's no idempotency guarantee.

**Fix: Multi-layered approach:**

```typescript
// 1. Add worker_pid column to dispatch_queue schema
//    ALTER TABLE dispatch_queue ADD COLUMN worker_pid INTEGER;

// 2. When claiming, record the PID:
function claimTask(workerType: string): DispatchTask | null {
  return db.prepare(`
    UPDATE dispatch_queue
    SET status = 'running',
        started_at = ?,
        worker_pid = ?
    WHERE id = (
      SELECT id FROM dispatch_queue
      WHERE worker_type = ? AND status = 'queued'
      ORDER BY created_at ASC
      LIMIT 1
    )
    RETURNING *
  `).get(Math.floor(Date.now() / 1000), process.pid, workerType) ?? null;
}

// 3. Stale task recovery (runs in Data bot every 60s):
function recoverStaleTasks(): number {
  const staleThreshold = Math.floor(Date.now() / 1000) - 600; // 10 min

  // First: check if the PID is still alive (fast recovery)
  const runningTasks = db.prepare(`
    SELECT id, worker_pid FROM dispatch_queue WHERE status = 'running'
  `).all() as Array<{ id: string; worker_pid: number | null }>;

  let recovered = 0;
  for (const task of runningTasks) {
    if (task.worker_pid) {
      try {
        process.kill(task.worker_pid, 0); // Check if alive (signal 0)
        continue; // Process alive, task is legitimately running
      } catch {
        // Process is dead -- immediate recovery, no need to wait 10 min
        db.prepare(`
          UPDATE dispatch_queue SET status = 'queued', started_at = NULL, worker_pid = NULL
          WHERE id = ? AND status = 'running'
        `).run(task.id);
        recovered++;
      }
    }
  }

  // Fallback: time-based recovery for tasks without PID (shouldn't happen, belt + suspenders)
  const result = db.prepare(`
    UPDATE dispatch_queue SET status = 'queued', started_at = NULL, worker_pid = NULL
    WHERE status = 'running' AND started_at < ? AND worker_pid IS NULL
  `).run(staleThreshold);
  recovered += result.changes;

  return recovered;
}
```

PID-based recovery detects crashes in seconds rather than waiting 10 minutes. The time-based fallback handles edge cases where the PID check fails (e.g., PID reuse, though extremely unlikely in the timeframe).

---

### 5. WARNING: Scheduler Contention with Dispatch Queue

`scheduler.ts` line 59 calls `runAgent()` directly, which checks the per-process `activeAgentCalls` counter. In the current single-process model, this means a scheduled task blocks interactive messages.

In the proposed multi-process model, the scheduler still runs inside the Data bot process (index.ts initializes it). This creates a problem:

- User sends a message classified as "quick" (inline execution)
- Simultaneously, the scheduler fires `runAgent()` for a due task
- `runAgent()` checks `activeAgentCalls >= 1` and returns "Already processing another request"
- Either the user's message or the scheduled task gets rejected

The blueprint (line 158) says "Data (bot) handles quick tasks inline" but doesn't address how the scheduler shares the single agent slot in the Data process.

**Fix: Route scheduled tasks through the dispatch queue:**

```typescript
// In scheduler.ts, replace direct runAgent call:
async function runDueTasks(): Promise<void> {
  const tasks = getDueTasks();
  if (tasks.length === 0) return;

  for (const task of tasks) {
    // Insert into dispatch queue instead of blocking inline
    db.prepare(`
      INSERT INTO dispatch_queue (id, chat_id, prompt, worker_type, status, created_at)
      VALUES (?, ?, ?, 'default', 'queued', ?)
    `).run(
      crypto.randomUUID(),
      ALLOWED_CHAT_ID,  // Results go to Matthew's chat
      task.prompt,
      Math.floor(Date.now() / 1000)
    );

    updateTaskAfterRun(task.id, computeNextRun(task.schedule), 'dispatched');
    logger.info({ taskId: task.id }, 'Scheduled task dispatched to queue');
  }
}
```

This keeps the Data bot's single agent slot free for interactive quick tasks and leverages the worker pool for scheduled work.

---

### 6. WARNING: Polling Interval Synchronization (Soft Thundering Herd)

All workers poll every 5000ms (blueprint line 101, `pollIntervalMs: 5000`). If workers start simultaneously (pm2 launches them together), they poll in lockstep:

```
T=0s     All 3 workers start, all poll immediately
T=5s     All 3 workers poll simultaneously
T=10s    All 3 workers poll simultaneously
...
```

While SQLite WAL handles concurrent reads fine, the synchronized writes (even just for polling SELECTs that find nothing) create unnecessary contention spikes. More critically, when tasks do arrive, all workers attempt the claim simultaneously, increasing the chance of `SQLITE_BUSY` errors (mitigated by busy_timeout from Finding #2, but still wasteful).

**Fix: Randomize initial delay per worker:**

```typescript
// In worker startup:
const JITTER_MAX_MS = 3000; // Random offset up to 3s
const initialDelay = Math.floor(Math.random() * JITTER_MAX_MS);

await sleep(initialDelay);  // Desynchronize from other workers
setInterval(() => void pollAndClaim(), config.pollIntervalMs);
```

This spreads the 3 workers across the 5-second window so they never poll at exactly the same time. Simple, no coordination needed.

---

### 7. WARNING: `activeAgentCalls` Counter Provides No Cross-Process Protection

`agent.ts` line 80-81:
```typescript
const MAX_CONCURRENT_AGENTS = 1;
let activeAgentCalls = 0;
```

This is a module-level variable. Each process (Data, Starscream, Ravage, Soundwave) gets its own copy. The guard prevents concurrent calls within a single process, but across 4 processes, up to 4 simultaneous Claude subprocesses can run.

The blueprint acknowledges this (line 158: "Each worker runs 1 task at a time"), and per-worker `maxConcurrent: 1` is correct for the worker design. But the blueprint also claims (line 158): "No API rate limit collisions."

This is false. With Data handling quick tasks inline + 3 workers + scheduler tasks, you could have 5 simultaneous Claude API calls. The Max plan's concurrency limits (if any exist) could be hit. The retry logic (Finding #3) handles this reactively, but it should be documented as an expected condition, not dismissed.

**Recommendation:** The `activeAgentCalls` guard inside each worker process is correct and sufficient for per-process protection. No change needed to the guard itself. But:
- Add a global concurrency observation mechanism (a `dispatch_queue` query counting `status='running'`) to the telemetry
- If the Max plan has a known concurrency limit, add a global semaphore via the database (a simple `SELECT COUNT(*) FROM dispatch_queue WHERE status='running'` before claiming)

---

### 8. WARNING: `singleTurn()` Generator State Isolation

`agent.ts` lines 103-115 define `singleTurn()` as an async generator function. Each call to `singleTurn()` creates a new generator instance with its own closure, so there is no shared state between invocations. Workers calling `runAgent()` (which calls `runAgentInner()`, which creates a new `singleTurn()`) are safe.

However, `runAgentInner()` creates several closures that reference the `onTyping` and `onProgress` callbacks (lines 224, 267). In the worker context:
- `onTyping` is a no-op (workers don't own Telegram context)
- `onProgress` could be used to write progress updates to the dispatch_queue

This is not a concurrency bug, but workers must explicitly pass safe callbacks. If a worker accidentally passes a stale or shared callback that references Telegram state from the Data process, it would fail or corrupt state.

**Recommendation:** Workers should call `runAgent(prompt, undefined, () => {}, undefined)` with a no-op typing callback and no progress callback (or a queue-writing progress callback). The blueprint should specify this explicitly.

---

### 9. SUGGESTION: Dedup Cache in bot.ts Does Not Interact with Dispatch

The `processedMessages` Map (bot.ts lines 35-49) deduplicates Telegram message IDs within the Data bot process. It prevents re-processing of messages during 409 restart cycles.

This cache is process-local and has no interaction with the dispatch queue. A message that gets dispatched to the queue won't be deduped by this mechanism because the dedup happens before classification and dispatch.

However, there's a subtle edge case: if the Data bot crashes and restarts (pm2 restart) while a dispatched task is still running in a worker, the bot picks up the same Telegram message again (if within Telegram's pending update window), classifies it as long again, and inserts a duplicate task into the queue. The dedup cache is lost on restart because it's in-memory.

**Fix: Add a dedup column to dispatch_queue:**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_dispatch_dedup
  ON dispatch_queue(chat_id, prompt)
  WHERE status IN ('queued', 'running');
```

Then use `INSERT OR IGNORE` when dispatching. This prevents duplicate tasks even if the Data bot restarts and re-processes the same message. The UNIQUE constraint is partial (only for active tasks), so completed/failed tasks don't block future identical requests.

Alternatively, store the Telegram `message_id` in the dispatch_queue table and check before inserting:

```sql
ALTER TABLE dispatch_queue ADD COLUMN telegram_message_id INTEGER;
CREATE UNIQUE INDEX IF NOT EXISTS idx_dispatch_msg_dedup
  ON dispatch_queue(telegram_message_id)
  WHERE telegram_message_id IS NOT NULL;
```

---

### 10. SUGGESTION: WAL Checkpoint Behavior Under Multi-Process Access

SQLite's WAL mode accumulates write-ahead log entries in the `-wal` file. Checkpointing (flushing WAL back to the main DB file) is normally triggered automatically when the WAL file exceeds ~1000 pages (4MB with default page size).

With multiple processes holding open database connections:
- An auto-checkpoint can only run when no other connection is reading
- If workers poll every 5s (each poll opens a read transaction briefly), there's always a window for checkpointing
- But if a worker's read transaction overlaps with a checkpoint attempt, the checkpoint is deferred

This is unlikely to be a real problem at the expected throughput (tens of tasks per day, not thousands per second), but the WAL file could grow unboundedly if something goes wrong (e.g., a worker holds a read transaction open for the duration of a Claude subprocess call).

**Recommendation:** Ensure workers do NOT hold database connections open during Claude subprocess execution. The pattern should be:
1. Claim task (single transaction, releases immediately)
2. Run Claude subprocess (no DB involvement)
3. Write result (single transaction, releases immediately)

This is the natural pattern with `better-sqlite3` synchronous API since it auto-commits after each `.run()` / `.get()` call. Just verify no one wraps the entire claim-execute-complete cycle in a `db.transaction()`.

---

### 11. SUGGESTION: Signal Handling for Worker Graceful Shutdown

Workers need to handle `SIGTERM` (sent by pm2 on stop/restart) to clean up in-flight tasks. The current Data bot has signal handling (index.ts lines 104-111), but workers need different behavior:

```
pm2 sends SIGTERM
  -> Worker receives signal
  -> If no task running: exit immediately
  -> If task running:
     a) Set flag: "shutting down, don't claim new tasks"
     b) Wait for current task to complete (up to N seconds)
     c) If task completes: write result, exit
     d) If timeout: set task status back to 'queued', exit
```

Without this, pm2's default behavior is:
1. Send SIGTERM
2. Wait 1600ms (default `kill_timeout`)
3. Send SIGKILL

If a Claude subprocess is mid-execution, SIGKILL kills the worker and the Node.js process, but the Claude CLI subprocess may become an orphan (it's a child process of the now-dead worker). The task remains at `status='running'` until the stale-task recovery runs.

**Fix:**

```typescript
// In worker.ts:
let shuttingDown = false;
let currentTaskId: string | null = null;

process.on('SIGTERM', async () => {
  shuttingDown = true;
  logger.info('SIGTERM received, finishing current task...');

  // If no task running, exit immediately
  if (!currentTaskId) {
    process.exit(0);
  }

  // Give the current task 30s to finish, then release it
  setTimeout(() => {
    if (currentTaskId) {
      db.prepare(`
        UPDATE dispatch_queue
        SET status = 'queued', started_at = NULL, worker_pid = NULL
        WHERE id = ? AND status = 'running'
      `).run(currentTaskId);
      logger.warn({ taskId: currentTaskId }, 'Released task on shutdown timeout');
    }
    process.exit(0);
  }, 30_000);
});

// In the poll loop:
while (!shuttingDown) {
  const task = claimTask(config.workerType);
  if (!task) {
    await sleep(config.pollIntervalMs);
    continue;
  }

  currentTaskId = task.id;
  // ... execute task ...
  currentTaskId = null;
}
```

Also set pm2's `kill_timeout` to 35000ms in the ecosystem config to give the worker time to finish:

```json
{
  "name": "ea-claude-starscream",
  "script": "dist/worker.js",
  "args": "--type starscream",
  "kill_timeout": 35000
}
```

---

## Missing Elements

### 1. No `busy_timeout` pragma anywhere in the codebase
The most fundamental requirement for multi-process SQLite is absent. Without it, every concurrent write throws `SQLITE_BUSY` immediately. This must be the first thing implemented before any multi-process work begins.

### 2. No atomic claim operation specified
The blueprint describes claim as a two-step operation (poll then update). The actual SQL for atomic claiming is not provided.

### 3. No worker_pid tracking in dispatch_queue schema
The schema (blueprint lines 46-58) has no column to track which worker process owns a task. This is needed for crash recovery (Finding #4).

### 4. No `notified` column in dispatch_queue schema
Flagged by the orchestrator but worth repeating: the result-poller references `WHERE NOT notified` but the schema has no such column. Either add `notified INTEGER DEFAULT 0` or use a `status = 'delivered'` state.

### 5. No specification of who runs stale-task recovery
The blueprint mentions the 10-minute timeout but doesn't specify which process runs the recovery sweep, how often it runs, or whether it's a separate scheduled task or part of an existing polling loop.

### 6. No global rate limit coordination
The blueprint states "No API rate limit collisions" (line 158) without justification. With 4-5 concurrent Claude processes, rate limit collisions are likely. The system needs either:
- A global concurrency limit via the database
- Documented acceptance that 529 errors will occur and retry logic handles them

### 7. No worker graceful shutdown specification
Signal handling for workers is not addressed. pm2's default SIGKILL after 1.6s will orphan Claude subprocesses and leave tasks stuck.

### 8. No Telegram message_id tracking for dispatch dedup
The dispatch queue has no way to prevent duplicate task insertion when the Data bot restarts during a 409 cycle.

---

## Recommendations

### R1: Add `busy_timeout` to every database connection (MUST DO)

```typescript
// db.ts initDatabase():
db.pragma('journal_mode = WAL');
db.pragma('busy_timeout = 5000');
```

Workers must also set this when they initialize their own connection. If workers import and call `initDatabase()`, this is automatic. If they create their own connection, they must replicate these pragmas.

### R2: Implement atomic task claiming with UPDATE...RETURNING (MUST DO)

See Finding #1 for the exact SQL. This is non-negotiable. Without it, double-claiming is a certainty under any real load.

### R3: Add jitter to API retry logic (MUST DO)

Replace the deterministic backoff in `agent.ts` line 154:

```typescript
// Before:
const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);

// After:
const base = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
const delay = Math.floor(base * 0.5 + Math.random() * base);
```

This change benefits the existing single-process system too (scheduler + interactive can collide on retries), so it should be made regardless of whether async dispatch ships.

### R4: Add worker_pid column and PID-based crash recovery (SHOULD DO)

Schema addition + recovery function as described in Finding #4. The PID-based approach detects crashes in seconds rather than the 10-minute timeout.

### R5: Route scheduled tasks through the dispatch queue (SHOULD DO)

Eliminates the scheduler vs. interactive contention in the Data process (Finding #5). Simple change, high impact.

### R6: Randomize worker startup and poll timing (SHOULD DO)

See Finding #6. Add a random initial delay (0-3s) before each worker starts its polling loop. Low effort, prevents synchronized contention spikes.

### R7: Implement worker graceful shutdown (SHOULD DO)

See Finding #11. Workers must handle SIGTERM, finish in-flight tasks or release them, and pm2's `kill_timeout` must exceed the grace period.

### R8: Add telegram_message_id to dispatch_queue for dedup (NICE TO HAVE)

See Finding #9. Prevents duplicate task dispatch on Data bot restart. The UNIQUE partial index approach is clean and requires minimal code change.

### R9: Verify SQLite version supports RETURNING clause

```bash
sqlite3 --version
# Must be >= 3.35.0 for UPDATE...RETURNING
```

Ubuntu 24.04 ships SQLite 3.45.1, so this is fine. But if the `better-sqlite3` npm package bundles its own SQLite, check that version too:

```typescript
const version = db.pragma('compile_options');
// Or:
console.log(Database.prototype.constructor.name); // Check docs for version API
```

### R10: Document expected concurrent Claude sessions

The blueprint should explicitly state: "Under peak load, up to 5 concurrent Claude sessions may run (1 inline via Data + 3 workers + 1 scheduled task). If the Max plan has a concurrency limit below 5, reduce worker count accordingly."
