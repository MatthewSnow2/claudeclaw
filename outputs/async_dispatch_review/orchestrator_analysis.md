# Orchestrator Analysis: EA-Claude Async Dispatch Blueprint

**Date**: 2026-02-25
**Blueprint**: `/home/apexaipc/projects/claudeclaw/BLUEPRINT-async-dispatch.md`
**Codebase**: `/home/apexaipc/projects/claudeclaw/src/`

---

## 1. Domain Map

### Domain 1: Queue Architecture & Data Layer

**Why this needs review**: The dispatch queue is the central nervous system of the entire async design. If the schema is wrong, the polling logic is flawed, or SQLite can't handle the concurrent access pattern from multiple pm2 processes, the whole system deadlocks or loses tasks. SQLite has specific constraints around multi-process write access that can cause `SQLITE_BUSY` errors under contention.

**Key questions a specialist should answer**:
1. Can multiple pm2 processes (Data + 3 workers) safely read/write the same SQLite file concurrently? What WAL mode guarantees apply across OS-level processes (not just threads)?
2. Is the proposed schema sufficient? The `dispatch_queue` table (blueprint lines 46-58) lacks a `notified` column, yet `result-poller.ts` references `WHERE status = 'completed' AND NOT notified` (blueprint line 80). This is a schema/spec mismatch.
3. Is polling every 5s (workers) and 10s (result-poller) adequate, or does it introduce unacceptable latency? What's the CPU cost of 4 processes polling SQLite continuously?
4. Should there be a dead-letter mechanism for tasks that fail repeatedly?
5. What happens to the existing `scheduled_tasks` and `sessions` tables when workers start accessing `db.ts`? The current `db` singleton (line 7 of `db.ts`) is process-local.

**Blueprint sections to focus on**: Lines 42-58 (Phase 1: dispatch_queue schema), Lines 155-158 (Key Decisions: SQLite, polling, isolation)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/db.ts`: Lines 1-71 (database initialization, schema, WAL pragma), line 7 (`let db: Database.Database` -- process-local singleton), line 69 (`db.pragma('journal_mode = WAL')`)
- `/home/apexaipc/projects/claudeclaw/src/config.ts`: Lines 38-39 (`PROJECT_ROOT`, `STORE_DIR` -- determines where the DB file lives)

---

### Domain 2: Concurrency & Process Isolation

**Why this needs review**: The current system is explicitly single-threaded with `MAX_CONCURRENT_AGENTS = 1` (agent.ts line 80). The blueprint proposes moving to 4+ concurrent OS processes, each spawning Claude subprocesses. This is a fundamental architectural shift. Getting concurrency wrong means race conditions on the queue, API rate limit exhaustion, or Claude subprocess collisions.

**Key questions a specialist should answer**:
1. The existing `activeAgentCalls` guard (agent.ts lines 80-81) is an in-process counter. It provides zero protection across pm2 processes. Do workers need their own concurrency guard, or does per-worker `maxConcurrent: 1` (blueprint line 102) handle this?
2. What happens when Data is running a "quick" inline task (agent.ts) AND a worker is running a "long" task simultaneously? Both call `runAgent()` which spawns Claude subprocesses via the SDK. Will the Claude CLI handle concurrent OAuth sessions from the same machine?
3. The retry logic (agent.ts lines 83-95, `isRetryableError`, `RETRY_BASE_DELAY_MS`) handles 529/503 errors. If 4 processes all hit 529 simultaneously and retry with the same backoff schedule, they'll collide again. Is jitter needed?
4. Workers poll the queue and "claim" tasks (blueprint line 91: `SET status = 'running'`). Without row-level locking or atomic claim operations, two workers of the same type could claim the same task. How is this prevented?
5. The `singleTurn()` generator (agent.ts lines 103-115) creates a one-shot message. Workers would presumably reuse this. Is there any state leakage between invocations?

**Blueprint sections to focus on**: Lines 87-103 (worker.ts design), Lines 155-158 (Key Decisions), Lines 161-166 (Risk Mitigation)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/agent.ts`: Lines 78-95 (concurrency limiter, retry logic), lines 133-173 (`runAgent()` -- the function workers would call or replicate), lines 175-328 (`runAgentInner()` -- SDK subprocess spawning, env sanitization)
- `/home/apexaipc/projects/claudeclaw/src/scheduler.ts`: Lines 45-101 (`runDueTasks()` -- existing pattern for non-interactive agent calls; runs tasks sequentially in a for-loop with no parallelism)

---

### Domain 3: Message Classification & Routing

**Why this needs review**: The classifier is the gatekeeper. A bad classifier routes quick tasks to the async queue (unnecessary latency) or routes long tasks inline (blocks the bot). The existing router (`router.ts`) handles @prefix-based backend routing. The new classifier adds a second routing dimension (quick vs. long, worker type). These two routing layers must compose cleanly without creating a confusing decision matrix.

**Key questions a specialist should answer**:
1. The blueprint proposes keyword-based classification (lines 66-70). Is this robust enough? "Research my LinkedIn connections" contains both "research" (soundwave) and "LinkedIn" (starscream). Which wins? What's the priority order?
2. How does the classifier interact with the existing `parsePrefix()` in router.ts (lines 37-56)? If someone says `@gemini research this`, does the @prefix take precedence (route to Gemini directly), or does the classifier also run? The blueprint doesn't address non-Claude backends at all.
3. The quick vs. long classification (lines 63-64) uses a 30-second heuristic. Who estimates this? Is it a static keyword list, or does it call an LLM to classify? An LLM classification call itself adds latency to every message.
4. What happens when classification is wrong? Is there a way for the user to override ("run this inline" or "dispatch this")?
5. Where does the classifier sit in the existing pipeline? Before or after `buildMemoryContext()` in bot.ts (line 246)?

**Blueprint sections to focus on**: Lines 61-70 (classifier.ts design), Lines 72-76 (bot.ts changes)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/router.ts`: Lines 20-56 (`PREFIX_MAP`, `parsePrefix()` -- existing routing logic that must compose with the new classifier)
- `/home/apexaipc/projects/claudeclaw/src/bot.ts`: Lines 200-321 (`handleMessage()` -- the entry point that must be modified to support dispatch), lines 244-267 (memory context building, routing call -- the insertion point for classification)

---

### Domain 4: Process Management & Deployment

**Why this needs review**: Moving from a single Node.js process to a pm2-managed process fleet is an operational shift. pm2 introduces its own complexity: log management, environment variable propagation, restart policies, monitoring. The current `index.ts` already has sophisticated process lifecycle management (PID lock, 409 retry loop, signal handling). Workers need equivalent robustness.

**Key questions a specialist should answer**:
1. The current PID lock (index.ts lines 21-48, `acquireLock()`) handles single-process deduplication. With pm2 managing multiple processes, is this still needed, or does pm2's own process tracking supersede it?
2. Signal handling (index.ts lines 104-109) uses `process.on('SIGINT/SIGTERM')`. pm2 sends `SIGINT` by default for graceful shutdown. Workers need to handle in-flight tasks during shutdown -- finish the current task, mark it back to 'queued' if interrupted, then exit.
3. The 409 Conflict retry loop (index.ts lines 88-171) is specific to Telegram's long-polling. Workers don't interact with Telegram directly, so they don't need this. But they DO need their own health-check and recovery patterns.
4. Environment variable propagation: `agent.ts` lines 186-208 carefully sanitize `sdkEnv` to prevent API billing via inherited `ANTHROPIC_API_KEY`. Workers spawned by pm2 will inherit whatever environment pm2 has. Is this handled?
5. The ecosystem config (blueprint lines 112-120) shows 4 processes. What's the memory footprint? Each Claude subprocess is a separate `claude` CLI process. On a 32GB machine with other projects running, is this sustainable?

**Blueprint sections to focus on**: Lines 111-120 (pm2 ecosystem config), Lines 163-166 (Risk: worker crash, pm2 restart)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/index.ts`: Lines 21-48 (PID lock), Lines 54-172 (`main()` -- full process lifecycle, signal handling, 409 retry)
- `/home/apexaipc/projects/claudeclaw/src/agent.ts`: Lines 181-208 (environment sanitization for SDK subprocess)
- `/home/apexaipc/projects/claudeclaw/src/config.ts`: Lines 1-47 (env reading, path resolution -- workers need equivalent config loading)

---

### Domain 5: Result Delivery & User Experience

**Why this needs review**: The user experience shifts from synchronous (send message, see typing indicator, get response) to asynchronous (send message, get ACK, wait, get result later). This is a significant UX change. The result-poller pattern must handle edge cases: what if the result is too long for Telegram? What if the user has sent new messages while waiting? What if multiple results arrive simultaneously?

**Key questions a specialist should answer**:
1. The result-poller (blueprint lines 78-82) polls every 10s and sends results to Telegram. The current bot uses `ctx.reply()` (grammY context method). The poller won't have a `ctx` object -- it needs the raw Telegram Bot API (`bot.api.sendMessage()`). Where does it get the bot instance?
2. How does the poller format results? The current pipeline applies `redactSecrets()` (bot.ts line 287), `formatForTelegram()` (bot.ts line 305), and `splitMessage()` (bot.ts line 305). The poller needs the same pipeline.
3. Voice mode (bot.ts lines 294-303): if the user has voice mode enabled, should dispatched results also come back as voice? The poller doesn't have the `voiceEnabledChats` Set.
4. Memory: `saveConversationTurn()` (bot.ts line 290) saves the user message and response for future context. Dispatched tasks bypass this entirely. How do completed async results feed back into memory?
5. The "typing" indicator (bot.ts lines 238-242) provides real-time feedback. Dispatched tasks have no such feedback between ACK and result. Should workers send progress updates via the queue?
6. What if the user sends `/newchat` (bot.ts line 342) while a dispatched task is still running? The session is cleared, but the task is still in-flight with the old session context.

**Blueprint sections to focus on**: Lines 72-82 (bot.ts changes, result-poller), Lines 123-129 (Phase 3: duration estimation as UX improvement)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/bot.ts`: Lines 279-308 (response formatting pipeline: redact, format, split, voice check), Lines 289-290 (memory save), Lines 237-242 (typing indicators)
- `/home/apexaipc/projects/claudeclaw/src/memory.ts`: Lines 58-71 (`saveConversationTurn()` -- needs async task awareness)
- `/home/apexaipc/projects/claudeclaw/src/bot.ts`: Lines 149-166 (`splitMessage()` -- needed by poller)

---

### Domain 6: Observability & Telemetry

**Why this needs review**: The existing telemetry system (telemetry.ts) writes JSONL events for Sky-Lynx consumption. Adding 4 worker processes means 4 additional event sources. If workers write to the same `telemetry.jsonl` file, concurrent appends could corrupt the file. The telemetry event types also need to be extended to capture dispatch lifecycle events.

**Key questions a specialist should answer**:
1. `telemetry.emit()` (telemetry.ts lines 73-80) uses `fs.appendFileSync()`. Multiple processes appending to the same file is generally safe on Linux for small writes (under PIPE_BUF, 4096 bytes), but is this guaranteed for JSONL lines that could exceed 4KB?
2. What new event types are needed? At minimum: `task_dispatched`, `task_claimed`, `task_completed`, `task_failed`, `worker_started`, `worker_stopped`. The blueprint doesn't specify any telemetry events for the dispatch lifecycle.
3. How do worker events correlate with Data's events? The `chat_id` field exists but the dispatch `id` (UUID) needs to thread through as a trace ID.
4. The existing `agent_completed` event (telemetry.ts lines 40-47) tracks `latency_ms`. For dispatched tasks, total latency = queue wait time + execution time + poller delivery time. These should be tracked separately.

**Blueprint sections to focus on**: Lines 131-136 (Phase 4: Sky-Lynx integration -- implies telemetry contract), Lines 163-166 (risk section mentions no monitoring)

**Existing code to focus on**:
- `/home/apexaipc/projects/claudeclaw/src/telemetry.ts`: Lines 1-89 (full file -- event types, `emit()` function, file-based approach)
- `/home/apexaipc/projects/claudeclaw/src/agent.ts`: Lines 277-282 (tool_used telemetry emission inside the agent loop)

---

## 2. Recommended Team Composition

### Specialist 1: Architecture Reviewer
**Focus**: Overall system design, component boundaries, data flow correctness
**Domains**: Covers Domain 1 (Queue), Domain 5 (Result Delivery), Domain 6 (Telemetry)
**Key mandate**: Validate that the proposed architecture is sound end-to-end. Check for missing components, undefined interfaces, and incomplete data flows. Answer: "Does this design actually solve the blocking problem without introducing worse problems?"
**Specific assignments**:
- Verify the dispatch_queue schema is complete (the missing `notified` column)
- Trace the full lifecycle of a dispatched task from message receipt to result delivery
- Identify any state that's currently in-memory (bot.ts) that needs to become persistent for the async model
- Evaluate whether the result-poller pattern is the right choice vs. alternatives (event-driven, callback)

### Specialist 2: Concurrency & Database Specialist
**Focus**: SQLite multi-process safety, race conditions, task claiming, deadlock scenarios
**Domains**: Covers Domain 1 (Queue -- database specifics), Domain 2 (Concurrency)
**Key mandate**: Determine whether SQLite can safely serve as a multi-process task queue. Identify all race conditions in the proposed claim/complete/poll cycle. Answer: "Will this work under real concurrent load, or will it produce SQLITE_BUSY errors and lost tasks?"
**Specific assignments**:
- Analyze SQLite WAL mode behavior with 4+ concurrent processes (reads vs. writes, lock contention)
- Design the atomic task claim operation (SELECT + UPDATE in a single transaction, or use `UPDATE ... RETURNING`)
- Evaluate the stale task recovery mechanism ("status='running' for >10min gets reset to 'queued'" -- blueprint line 165)
- Check the `db.ts` singleton pattern (line 7) -- each worker process creates its own connection, so the singleton is fine, but WAL checkpoint behavior across connections needs validation

### Specialist 3: Codebase Integration Reviewer
**Focus**: How the new components integrate with existing code without breaking current functionality
**Domains**: Covers Domain 3 (Classification/Routing), Domain 5 (Result Delivery -- bot.ts changes)
**Key mandate**: Produce a concrete integration plan showing exactly which functions change, which new modules are added, and how the existing test suite is affected. Answer: "Can this be implemented incrementally without breaking the current bot?"
**Specific assignments**:
- Map the exact insertion point in `handleMessage()` (bot.ts line 200) where classification and dispatch replace the current synchronous flow
- Design the classifier's interaction with `parsePrefix()` (router.ts) -- which runs first, how do they compose
- Plan how `result-poller.ts` accesses the bot API, formatting functions, and memory system
- Identify which existing functions become shared utilities (e.g., `redactSecrets`, `formatForTelegram`, `splitMessage`) vs. which stay bot-only
- Check if the existing test suite (`bot.test.ts`, `memory.test.ts`, `db.test.ts`, `env.test.ts`) needs updates

### Specialist 4: Process Management & Operations Reviewer
**Focus**: pm2 configuration, environment variables, worker lifecycle, deployment
**Domains**: Covers Domain 4 (Process Management)
**Key mandate**: Ensure the multi-process deployment is operationally sound. Answer: "Can Matthew deploy this, monitor it, debug it, and recover from failures without manual intervention?"
**Specific assignments**:
- Review pm2 ecosystem config for environment variable propagation (especially the `ANTHROPIC_API_KEY` sanitization pattern from agent.ts lines 186-208)
- Design worker graceful shutdown (handle in-flight tasks on SIGTERM)
- Evaluate memory footprint: 4 Node.js processes + N Claude CLI subprocesses on a 32GB i7 machine
- Define log management strategy (pm2 logs, per-worker log files, log rotation)
- Check if the PID lock pattern (index.ts lines 21-48) conflicts with pm2's process management

### Specialist 5: Devil's Advocate
**Focus**: Challenge assumptions, find failure modes, question whether this is the right solution
**Domains**: Cross-cutting -- all domains
**Key mandate**: Poke holes in the design. Find the scenarios the blueprint doesn't cover. Challenge whether the complexity is justified. Answer: "What will go wrong that nobody has thought of yet?"
**Specific assignments**:
- Challenge the SQLite-as-queue choice: is polling + SQLite the right pattern, or would a simple in-process queue (e.g., `async-queue` npm package) be simpler for the actual concurrency level?
- Challenge the worker-per-persona model: does the current workload actually need 3 specialized workers, or would 1 generic worker pool with configurable concurrency solve the blocking problem more simply?
- Find failure cascades: What if one worker crashes and its task is stuck at 'running' for 10 minutes? What if ALL workers crash?
- Question the 30-second quick/long threshold: is this based on real data, or is it a guess?
- Stress-test the UX: What happens when 5 dispatched tasks complete simultaneously and the user gets 5 separate Telegram messages? Is that a good experience?
- Ask: Does the scheduler (scheduler.ts) also need to dispatch through the queue, or does it remain a separate path?

---

## 3. Dependencies Between Specialists

### Dependency Graph

```
                    Architecture Reviewer
                   /          |          \
                  v           v           v
    Concurrency       Integration       Operations
    Specialist        Reviewer          Reviewer
         \              |              /
          \             |             /
           v            v            v
                  Devil's Advocate
```

### Execution Order

**Phase 2a (parallel -- can run simultaneously):**
- Architecture Reviewer
- Concurrency & Database Specialist
- Codebase Integration Reviewer
- Process Management & Operations Reviewer

**Rationale for parallelism**: Each specialist has a distinct domain with minimal overlap. They reference different sections of the blueprint and different source files. Their analyses are independent -- they don't need each other's conclusions to do their work.

**Phase 2b (sequential -- runs after 2a):**
- Devil's Advocate

**Rationale for sequentiality**: The Devil's Advocate needs ALL other specialists' findings as input. Their job is to challenge conclusions, find gaps between specialist analyses, and identify risks that emerge from the intersection of domains. Running the DA in parallel would miss cross-domain concerns.

---

## 4. Initial Flags

### Flag 1: Schema Mismatch (CRITICAL)

The `dispatch_queue` schema (blueprint lines 46-58) does not include a `notified` column. But the result-poller specification (line 80) references `WHERE status = 'completed' AND NOT notified`. Either the schema needs the column or the poller needs a different mechanism (e.g., a separate `status = 'delivered'` state).

### Flag 2: Single db.ts Singleton vs. Multi-Process Access (CRITICAL)

The current `db.ts` uses a module-level singleton (`let db: Database.Database` on line 7). This works for a single process. Workers will each import `db.ts` and create their own connection to the same SQLite file. While SQLite WAL mode supports concurrent readers, concurrent writers will block each other. The blueprint doesn't address connection configuration for multi-process access (e.g., busy timeout, retry-on-SQLITE_BUSY).

### Flag 3: Worker Reuse of agent.ts (HIGH)

The blueprint says workers run Claude subprocesses (line 93) but doesn't specify whether workers import and call `runAgent()` from agent.ts or have their own implementation. If they reuse `runAgent()`:
- The `MAX_CONCURRENT_AGENTS` guard (agent.ts line 80) is per-process, so each worker allows 1 concurrent call -- this is correct.
- The environment sanitization (agent.ts lines 186-208) works correctly in worker processes.
- BUT: `runAgent()` accepts `onTyping` and `onProgress` callbacks that reference Telegram context. Workers don't have Telegram context. These callbacks need to be optional or replaced with queue-based progress updates.

### Flag 4: Classifier-Router Composition Undefined (HIGH)

The blueprint introduces a classifier (lines 61-70) but doesn't specify its relationship to the existing router (router.ts). Two open questions:
- Does classification happen before or after @prefix routing?
- Do non-Claude backends (Gemini, Perplexity, Ollama) ever get dispatched to workers, or is dispatch Claude-only?

The logical answer is: @prefix routing happens first (it's cheap, string matching). If the backend is Claude, THEN the classifier decides quick vs. long. If the backend is non-Claude, it runs inline (these are simple HTTP calls that complete fast). But the blueprint doesn't state this.

### Flag 5: Scheduler Path Not Addressed (MEDIUM)

The scheduler (scheduler.ts) currently calls `runAgent()` directly (line 59). This means scheduled tasks ALSO block the single agent slot. The blueprint doesn't explicitly address whether scheduled tasks should go through the dispatch queue. If they should, the scheduler needs to insert into `dispatch_queue` instead of calling `runAgent()`. If they shouldn't, the scheduler continues to block inline -- which partially defeats the purpose of the async dispatch.

### Flag 6: Memory System Bypassed for Async Tasks (MEDIUM)

`saveConversationTurn()` (bot.ts line 290) saves the user's message and Claude's response to the memory system. For dispatched tasks, the response arrives later via the result-poller, which has no access to the memory system's `saveConversationTurn()` function. This means async interactions are invisible to the memory system, degrading context quality over time.

### Flag 7: No Cancellation Mechanism (LOW)

The blueprint provides no way for the user to cancel a dispatched task. Once a task is queued, it runs to completion. If the user realizes they made a typo or want to modify the request, they have no recourse. A `/cancel` command or `/cancel <task-id>` would be valuable.

### Flag 8: Worker CLAUDE.md Path Resolution (LOW)

The blueprint specifies `workers/starscream/CLAUDE.md` etc. (lines 107-109) as worker-specific Claude configuration files. The current `runAgentInner()` passes `cwd: PROJECT_ROOT` (agent.ts line 236), which causes the Claude CLI to load `CLAUDE.md` from the project root. Workers need a different `cwd` pointing to their worker directory, OR they need to use a different SDK option to specify the CLAUDE.md path. This is an implementation detail but easy to get wrong.

### Flag 9: Cost Model Assumption (LOW)

The blueprint states "Each worker spawns Claude subprocesses on Max plan OAuth. No API billing unless explicitly overridden." (line 166). This assumes the Max plan allows unlimited concurrent sessions. If the Max plan has any concurrency limits, 4 simultaneous Claude sessions could fail. This needs verification against current Anthropic Max plan terms.

---

## 5. Summary for Phase 2 Dispatch

| Specialist | Priority | Parallel? | Primary Files | Key Deliverable |
|---|---|---|---|---|
| Architecture Reviewer | P0 | Yes (Phase 2a) | blueprint, db.ts, bot.ts, agent.ts | End-to-end data flow validation, schema corrections |
| Concurrency Specialist | P0 | Yes (Phase 2a) | db.ts, agent.ts, scheduler.ts | SQLite multi-process safety verdict, atomic claim design |
| Integration Reviewer | P1 | Yes (Phase 2a) | bot.ts, router.ts, memory.ts, telemetry.ts | Step-by-step integration plan with function-level diffs |
| Operations Reviewer | P1 | Yes (Phase 2a) | index.ts, agent.ts, config.ts, env.ts | pm2 config, env propagation, resource budget |
| Devil's Advocate | P0 | No (Phase 2b) | All specialist outputs | Consolidated risk register, alternative approaches |

Total estimated review time: Phase 2a (parallel) + Phase 2b (sequential) = 2 rounds.
