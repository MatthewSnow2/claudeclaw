# Orchestration Issues Tracker

---

## Open Issues

No open issues -- all recorded issues have a fix applied.

---

## readEnvFile Timeout Bug

**Date:** 2026-03-16

### What Happened

The orchestration layer hung indefinitely during startup when `readEnvFile` was called to load environment variables. The process stalled at the env-loading step and never proceeded to agent initialization, causing ClaudeClaw to fail to start without any visible error.

### Root Cause

`readEnvFile` was implemented as an async function but was called without `await` at the orchestration entry point. The Promise was created and discarded — env vars were never actually loaded — and downstream code that depended on those vars (API keys, config flags) received `undefined`. In some execution paths this caused a silent hang rather than a thrown error, because dependent async calls would wait on values that never resolved.

### Fix Applied

Added `await` to the `readEnvFile` call at the orchestration entry point so the environment is fully loaded before agent startup continues. Also added a 5-second timeout guard around the call so that if the file read fails or blocks, the process throws a clear error rather than hanging silently.

### Notes

- Bug only manifested on cold starts, not session resumptions (where env was already in memory).
- No data loss resulted from this issue.

---

## No `/stop` for Missions

**Date:** 2026-03-16

### What Happened

When a mission was running and the user attempted to cancel it using `/stop`, the command had no effect on the active mission. `/stop` only cancelled the current Claude Code session turn — it did not propagate a cancellation signal to the underlying mission task. Missions continued running in the background with no way to interrupt them through the normal chat interface.

### Root Cause

The `/stop` command was wired to the session-level abort mechanism only. Mission tasks run as independent background processes tracked in the `missions` table, and the session abort signal was never connected to the mission lifecycle. There was no handler that checked whether a `/stop` issued mid-mission should also mark the mission as cancelled and kill the associated subprocess.

### Fix Applied

Added mission-aware cancellation to the `/stop` handler:

1. On `/stop`, the bot now checks if any mission is in `running` state for the current chat.
2. If a running mission is found, it sends `SIGTERM` to the mission subprocess (looked up via the `pid` column in the `missions` table).
3. The mission row is updated to `status = 'cancelled'` and a cancellation message is sent to the user confirming which mission was stopped.
4. If no mission is running, `/stop` behaves as before (cancels the current session turn).

---

## Mission Blocking on messageQueue

**Date:** 2026-03-16

### What Happened

Missions were blocking indefinitely during orchestration. After a mission was dispatched, the orchestrator stalled and never progressed to the next step. The system appeared to hang with no error output, leaving agents idle and pipelines frozen.

### Root Cause

The `messageQueue` was not being drained after a mission was enqueued. The orchestrator was awaiting a response on the queue before allowing execution to continue, but nothing was consuming from the queue on the other end. This created a deadlock: the mission couldn't start because the orchestrator was blocked, and the orchestrator was blocked because the mission hadn't started.

### Fix Applied

Added a non-blocking queue drain step so the orchestrator no longer awaits queue consumption before continuing. Missions are now fire-and-forget onto the queue, and the orchestrator proceeds immediately. Consumers process the queue independently without holding up the orchestration loop.

---

## Subtask Timeout-Stop Gap

**Date:** 2026-03-16

### What Happened

When a subtask hit its execution timeout, the orchestrator logged the timeout but did not issue a corresponding stop or kill signal to the running subtask process. The subtask continued executing past its timeout deadline -- consuming tokens, time, and potentially producing stale or conflicting output -- while the orchestrator had already moved on and treated the subtask as expired. This created a gap between the timeout being declared and the subtask actually stopping, with no guarantee of clean termination.

### Root Cause

The timeout logic and the stop/kill logic were implemented in separate code paths with no connection between them. The timeout handler set a flag and emitted a timeout event, but it never called into the stop mechanism. The stop mechanism only ran when explicitly triggered by a user `/stop` command or a mission cancellation. Neither path called the other, so a timed-out subtask would be marked as expired at the orchestrator level while its subprocess continued running freely.

### Fix Applied

Connected the timeout handler to the stop mechanism so that when a subtask timeout fires, it immediately invokes the same termination path used by explicit stops:

1. On timeout expiry, the handler now calls the subtask's stop/kill function directly (same function used for `/stop` propagation).
2. `SIGTERM` is sent to the subtask subprocess, with a short grace period followed by `SIGKILL` if the process does not exit cleanly.
3. The subtask row is updated to `status = 'timeout'` (distinct from `'cancelled'`) so the orchestrator can distinguish user-initiated stops from timeout-triggered stops in logs and retries.
4. A timeout notification is surfaced to the user confirming the subtask was stopped.

### Notes

- Prior to the fix, long-running subtasks could accumulate silently after timeouts, exhausting API budget.
- The `'timeout'` status is treated as non-retryable by default; the mission orchestrator will not automatically re-queue a timed-out subtask without explicit configuration.

---

## No Retry Logic on Agent Task Failures

**Date:** 2026-03-16

### What Happened

When an agent task failed mid-execution (due to a transient error, network blip, or subprocess crash), the orchestrator made no attempt to retry. The task was silently dropped -- no retry, no error notification to the user, no status update in the DB. From the user's perspective, the task just disappeared with no feedback.

### Root Cause

The task dispatch loop had no retry mechanism. On any thrown error, the catch block logged the failure and exited the task handler immediately. There was no retry counter, no backoff strategy, and no distinction between transient failures (retriable) and permanent failures (not retriable). All errors were treated as terminal.

### Fix Applied

Added a configurable retry wrapper around task execution:

1. Tasks are now attempted up to `MAX_RETRIES` times (default: 3) before being marked as permanently failed.
2. Retries use exponential backoff (1s, 2s, 4s) to avoid hammering a degraded dependency.
3. Transient errors (network timeouts, subprocess non-zero exits) trigger retries; logic errors and explicit cancellations do not.
4. After exhausting retries, the task is marked `status = 'failed'` in the DB and the user receives a Telegram notification with the error summary.

---
