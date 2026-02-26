# Consolidated Review: EA-Claude Async Dispatch Blueprint

**Date**: 2026-02-25
**Reviewers**: Blueprint Analyst (Orchestrator), Architecture Reviewer, Concurrency Specialist, Codebase Integration Reviewer, Devil's Advocate
**Blueprint**: `BLUEPRINT-async-dispatch.md`

---

## Executive Summary

The async dispatch blueprint solves a real problem -- long-running Claude tasks block the Telegram bot -- but proposes a solution whose complexity is disproportionate to the problem's severity for a single-user personal bot. All four specialists independently flagged the same three critical infrastructure gaps (no SQLite `busy_timeout`, no atomic task claiming, incomplete schema) that would cause immediate failures in production. The Devil's Advocate makes a compelling case that `MAX_CONCURRENT_AGENTS = 2` plus an in-process queue solves 80% of the problem with a one-line change. The team recommends a phased approach: ship a minimal "Phase 0" immediately, collect duration telemetry for 2 weeks, then graduate to the full dispatch architecture only if data justifies it.

---

## Overall Assessment: REVISE

The blueprint is architecturally sound in concept but needs significant revision before implementation. The core idea (SQLite queue + pm2 workers + result poller) can work at this scale, but the blueprint has critical gaps that would cause immediate production failures, and the implementation plan should be restructured to validate assumptions incrementally.

---

## Critical Issues (Must Fix Before Implementation)

### C1. No SQLite `busy_timeout` -- Immediate Write Failures
**Flagged by**: Architecture, Concurrency, Devil's Advocate (unanimous)

`db.ts` sets `journal_mode = WAL` but does not set `busy_timeout`. Default is 0ms. Any concurrent write from a second process throws `SQLITE_BUSY` immediately instead of waiting.

**Fix** (required regardless of dispatch architecture):
```typescript
db.pragma('busy_timeout = 5000');
```

Every process (Data, workers, poller) must set this on its own connection.

### C2. Task Claiming Race Condition -- Double Execution
**Flagged by**: Architecture, Concurrency, Integration (unanimous)

The blueprint's two-step SELECT-then-UPDATE allows two workers to claim the same task. All three specialists independently recommended the same fix:

```sql
UPDATE dispatch_queue
SET status = 'running', started_at = ?
WHERE id = (
  SELECT id FROM dispatch_queue
  WHERE worker_type = ? AND status = 'queued'
  ORDER BY created_at ASC LIMIT 1
)
RETURNING *
```

SQLite 3.35+ required (Ubuntu 24.04 ships 3.45). Single statement, atomic under SQLite's implicit write lock.

### C3. Schema Incomplete -- 5 Missing Columns
**Flagged by**: All specialists

The `dispatch_queue` schema is missing:
| Column | Purpose | Flagged by |
|--------|---------|------------|
| `notified` (or `'delivered'` status) | Result-poller references `WHERE NOT notified` but column doesn't exist | All 4 |
| `user_message` / `original_message` | Raw user input for memory system (vs enriched `prompt`) | Architecture, Integration |
| `retry_count` | Prevent infinite retry loops (poison pill tasks) | Architecture |
| `worker_id` / `worker_pid` | Crash recovery, debugging | Architecture, Concurrency |
| `priority` | Distinguish interactive vs scheduled tasks | Architecture |
| `telegram_message_id` | Reply threading, dispatch dedup on restart | Devil's Advocate, Concurrency |

**Corrected schema**:
```sql
CREATE TABLE IF NOT EXISTS dispatch_queue (
  id TEXT PRIMARY KEY,
  chat_id TEXT NOT NULL,
  user_message TEXT NOT NULL,
  prompt TEXT NOT NULL,
  worker_type TEXT NOT NULL,
  status TEXT DEFAULT 'queued',
  priority INTEGER DEFAULT 0,
  result TEXT,
  session_id TEXT,
  worker_id TEXT,
  worker_pid INTEGER,
  retry_count INTEGER DEFAULT 0,
  telegram_message_id INTEGER,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  error TEXT
);
```

### C4. Memory System Bypassed -- Context Amnesia
**Flagged by**: Architecture, Integration, Devil's Advocate (unanimous)

`saveConversationTurn()` is called in `bot.ts` after inline execution. Dispatched tasks bypass this entirely. Workers run in isolated sessions. The result-poller delivers results but never saves to memory. Consequence: Matthew asks "what did you find?" and Data says "I don't know what you're referring to."

**Fix**: Result-poller must call `saveConversationTurn(chatId, userMessage, result)` after delivering each result. Requires the `user_message` column (C3 above).

### C5. Result-Poller Integration Undefined
**Flagged by**: Architecture, Integration

The blueprint doesn't specify:
- WHERE the result-poller runs (must be inside Data's process, not a separate pm2 process)
- HOW it accesses bot API (must use `botApiRef.current` pattern from `index.ts`)
- HOW it formats results (must reuse `redactSecrets()`, `formatForTelegram()`, `splitMessage()`)
- HOW it handles failed tasks (must notify user of failures, not swallow them)

**Fix**: Integration reviewer provided complete `result-poller.ts` implementation (see integration_review.md R5).

### C6. Classifier-Router Composition Undefined
**Flagged by**: Orchestrator, Integration, Devil's Advocate

The blueprint introduces a classifier but doesn't specify its relationship to `parsePrefix()` in router.ts. Two critical unanswered questions:
1. Classification must happen AFTER @prefix parsing but BEFORE the backend call
2. Non-Claude backends (`@gemini`, `@perplexity`, `@ollama`) must NEVER be dispatched

**Fix**: Export `parsePrefix()` from router.ts. In bot.ts, parse prefix first, only classify if `backend === 'claude'`.

### C7. Complexity vs. Benefit -- The "Phase 0" Question
**Flagged by**: Devil's Advocate (Critical), partially supported by others

The blueprint adds ~800 lines of new code, 4 OS processes, multi-process SQLite coordination, and a keyword classifier for a single-user bot. The core problem ("second message gets bounced") could be 80% solved by:
- Changing `MAX_CONCURRENT_AGENTS` from 1 to 2 (one line)
- Adding an in-process FIFO queue (50 lines)

**This is the most contentious finding.** Architecture and Concurrency reviewers accept the multi-process approach as sound but acknowledge it's heavy. The Devil's Advocate argues it's unjustified.

**Recommendation**: Ship a minimal Phase 0 first (see Revised Implementation Plan below).

---

## Warnings (Should Fix -- Implementation May Proceed With Caution)

### W1. Retry Backoff Thundering Herd
**Flagged by**: Concurrency

`agent.ts` retry delays are deterministic (10s, 20s, 40s). If 4 processes all get 529 simultaneously, they all retry at the same instants.

**Fix**: Add jitter: `Math.floor(base * 0.5 + Math.random() * base)`

### W2. Scheduler Bypass -- The 9am Time Bomb
**Flagged by**: Concurrency, Integration, Devil's Advocate (unanimous)

The scheduler calls `runAgent()` directly, blocking Data's single agent slot. The morning report at 9am blocks all interactive messages for 2-5 minutes. This is the most concrete pain point and the blueprint doesn't address it.

**Fix**: Scheduler inserts into `dispatch_queue` instead of calling `runAgent()`.

### W3. Worker Crash Recovery Too Slow
**Flagged by**: Concurrency, Devil's Advocate

10-minute stale task timeout is too long. PID-based crash detection (checking if `worker_pid` is alive) enables recovery in seconds.

**Fix**: Add `worker_pid` column, check PID liveness every 60s, fall back to time-based recovery.

### W4. No Worker Graceful Shutdown
**Flagged by**: Concurrency, Integration

Workers must handle SIGTERM: stop claiming, wait for current task, release if timeout. pm2's default `kill_timeout` (1600ms) is too short. Set to 35000ms.

### W5. Polling Interval Synchronization
**Flagged by**: Concurrency

All workers poll at 5s intervals starting simultaneously. Add random initial delay (0-3s) to desynchronize.

### W6. No User-Facing Task Management
**Flagged by**: Devil's Advocate, Architecture

No `/tasks`, `/cancel`, or `/status` commands. Matthew has no visibility into the queue. Add at minimum `/tasks` (show pending/running) and `/cancel <id>`.

### W7. Ghost Conversation -- No Reply Threading
**Flagged by**: Devil's Advocate

Results arrive as floating messages with no visual connection to the original request. Store `telegram_message_id` and use `reply_to_message_id` when delivering results.

### W8. Named Workers Are Premature Optimization
**Flagged by**: Devil's Advocate

3 specialized workers (Starscream, Ravage, Soundwave) based on predicted workload, not observed patterns. Start with 1 generic worker. Add specialization when data justifies it.

### W9. Media Messages Unaddressed
**Flagged by**: Integration, Devil's Advocate

Photos, documents, videos can trigger dispatch but the schema only stores text. File paths could be cleaned up before workers access them. Force media messages inline for v1.

---

## Suggestions (Nice to Have -- Can Be Deferred)

### S1. Adaptive polling intervals for result-poller (Architecture)
Poll every 30s when idle, 5s when tasks are active, 1s immediately after delivery to check for more.

### S2. Voice mode persistence to SQLite (Architecture)
`voiceEnabledChats` is in-memory. Move to a `chat_settings` table if voice consistency matters for async results.

### S3. Telemetry events for dispatch lifecycle (Architecture, Integration)
Add: `task_dispatched`, `task_claimed`, `task_completed`, `task_delivered`, `task_stale_recovered`. Track `queue_wait_ms`, `execution_ms`, `total_latency_ms` separately.

### S4. Dispatch dedup via UNIQUE index on `telegram_message_id` (Concurrency)
Prevents duplicate task insertion when Data restarts during 409 cycle.

### S5. WAL checkpoint hygiene (Concurrency)
Ensure workers don't hold read transactions during Claude subprocess execution. Natural with `better-sqlite3` sync API but worth documenting.

### S6. Feature flag for dispatch (Devil's Advocate)
Add `DISPATCH_ENABLED=true|false` in config to allow rollback without code revert.

---

## Cross-Reference: Specialist Agreement Matrix

| Finding | Architecture | Concurrency | Integration | Devil's Advocate |
|---------|:-----------:|:-----------:|:-----------:|:----------------:|
| busy_timeout missing | Critical | Critical | Critical | Critical |
| Atomic claim needed | Critical | Critical | Critical | Critical |
| Schema incomplete | Critical | Critical | Critical | Warning |
| Memory bypass | Warning | -- | Critical | Critical |
| Result-poller undefined | Critical | -- | Critical | Warning |
| Scheduler bypass | Warning | Warning | Warning | Warning |
| Worker crash recovery | -- | Warning | -- | Warning |
| Classifier unreliable | -- | -- | -- | Critical |
| Complexity unjustified | -- | -- | -- | Critical |

**No contradictions found.** All specialists agree on the infrastructure fixes. The only disagreement is severity: the Devil's Advocate rates the overall approach as unjustified complexity, while Architecture/Concurrency/Integration accept the approach as sound given the fixes.

---

## Gaps Identified

1. **Operations review not performed**: The orchestrator recommended a Process Management & Operations Reviewer. This was not spawned. pm2 ecosystem config, environment variable propagation, and memory footprint analysis are only partially covered by Concurrency and Devil's Advocate.

2. **No Claude Max plan concurrency testing**: All specialists flagged this as an unknown. Nobody has tested whether 4 concurrent Claude Code sessions work under the Max plan. This should be validated before any multi-process work.

3. **No rollback plan**: Devil's Advocate flagged that there's no feature flag or quick rollback path if dispatch breaks the core message flow.

---

## Revised Implementation Plan

Based on cross-referenced specialist recommendations, the blueprint should be restructured into data-gated phases:

### Phase 0: Minimal Fixes (Ship This Week)
No multi-process changes. Solves 80% of the blocking problem.

1. `MAX_CONCURRENT_AGENTS = 2` (agent.ts line 80)
2. `busy_timeout = 5000` (db.ts, needed regardless)
3. Add jitter to retry backoff (agent.ts)
4. Add duration telemetry to every `runAgent()` call (log actual execution time)
5. In-process FIFO queue: if both agent slots busy, queue message with "You're next in line"

**Success metric**: Collect 2 weeks of data. How often does queueing actually occur? What's the distribution of task durations?

### Phase 1: Single-Process Queue (If Phase 0 data justifies it)
Queue + poller within Data's process. No new pm2 processes yet.

1. `dispatch_queue` table with corrected schema (all columns from C3)
2. Classifier (conservative: only dispatch explicit long-task signals)
3. Result-poller inside Data's process (using `botApiRef` pattern)
4. Scheduler routes through dispatch queue
5. Memory system integration (save async results)
6. `/tasks` and `/cancel` commands
7. Feature flag: `DISPATCH_ENABLED` config var

Data processes queued tasks itself when inline agent is free. This validates the queue logic without multi-process complexity.

### Phase 2: Worker Process (If Phase 1 data justifies it)
1. One generic worker (no specialization)
2. Atomic claim with `UPDATE...RETURNING`
3. Worker graceful shutdown (SIGTERM handling, pm2 `kill_timeout`)
4. PID-based crash recovery
5. Reply threading (`reply_to_message_id`)

### Phase 3: Specialization (If Phase 2 data justifies it)
1. Worker-specific CLAUDE.md files
2. Keyword classification by worker type
3. Multiple specialized workers
4. Sky-Lynx integration
5. Duration estimation

---

## Blueprint Modifications Required

If proceeding with the original blueprint structure (not the Phase 0 alternative), these edits are mandatory:

1. **Schema**: Replace the dispatch_queue definition with the corrected schema from C3
2. **Add section**: "SQLite Multi-Process Configuration" -- document `busy_timeout`, WAL mode, atomic claiming
3. **Add section**: "Classifier-Router Composition" -- specify that classification happens after `parsePrefix()`, only for Claude backend
4. **Add section**: "Result-Poller Architecture" -- specify it runs inside Data's process, uses `botApiRef` pattern, calls `saveConversationTurn()`
5. **Modify Phase 1**: Include scheduler integration (route scheduled tasks through queue)
6. **Add section**: "Worker Lifecycle" -- graceful shutdown protocol, SIGTERM handling, pm2 `kill_timeout`
7. **Add section**: "User-Facing Commands" -- `/tasks`, `/cancel`
8. **Modify risk section**: Remove "No API rate limit collisions" claim. Document that concurrent Claude sessions are expected and handled by retry logic with jitter.
9. **Add section**: "Rollback Plan" -- feature flag, how to disable dispatch without reverting code

---

## Files Produced

| File | Agent | Content |
|------|-------|---------|
| `orchestrator_analysis.md` | Blueprint Analyst | 6 domains, 9 flags, team composition |
| `architecture_review.md` | Architecture Reviewer | 13 findings, 5 recommendations, corrected schema |
| `concurrency_review.md` | Concurrency Specialist | 11 findings, 10 recommendations, atomic claim SQL |
| `integration_review.md` | Integration Reviewer | 16 findings, 8 recommendations with code snippets |
| `devils_advocate.md` | Devil's Advocate | 11 objections, Phase 0 alternative, verdict: REJECT as written |
| `consolidated_review.md` | Synthesis | This document |
