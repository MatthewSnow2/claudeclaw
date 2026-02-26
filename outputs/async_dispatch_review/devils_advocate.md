# Devil's Advocate: EA-Claude Async Dispatch

## Domain
Adversarial Analysis

## Files Reviewed

**Blueprint & Analysis:**
- `/home/apexaipc/projects/claudeclaw/BLUEPRINT-async-dispatch.md` (full blueprint, 172 lines)
- `/home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/orchestrator_analysis.md` (orchestrator findings)

**Source Files (complete reads):**
- `/home/apexaipc/projects/claudeclaw/src/bot.ts` (592 lines -- message handling, formatting, dedup)
- `/home/apexaipc/projects/claudeclaw/src/agent.ts` (329 lines -- Claude subprocess, concurrency guard, retry)
- `/home/apexaipc/projects/claudeclaw/src/router.ts` (172 lines -- @prefix multi-LLM routing)
- `/home/apexaipc/projects/claudeclaw/src/memory.ts` (79 lines -- memory context build, conversation save)
- `/home/apexaipc/projects/claudeclaw/src/scheduler.ts` (107 lines -- cron task execution)
- `/home/apexaipc/projects/claudeclaw/src/db.ts` (237 lines -- SQLite schema, session/memory/task CRUD)
- `/home/apexaipc/projects/claudeclaw/src/index.ts` (179 lines -- pm2 entry, PID lock, 409 recovery)
- `/home/apexaipc/projects/claudeclaw/src/config.ts` (47 lines -- env loading, path resolution)
- `/home/apexaipc/projects/claudeclaw/src/telemetry.ts` (90 lines -- JSONL event emitter)
- `/home/apexaipc/projects/claudeclaw/src/env.ts` (74 lines -- .env parsing, shared secrets fallback)
- `/home/apexaipc/projects/claudeclaw/ecosystem.config.cjs` (22 lines -- current pm2 config, single process)
- `/home/apexaipc/projects/claudeclaw/package.json` (dependencies, scripts)

**Test files confirmed present:** bot.test.ts, memory.test.ts, db.test.ts, env.test.ts, voice.test.ts, media.test.ts

---

## Findings

### 1. SQLite Is the Wrong Abstraction for a Multi-Process Task Queue

**Assumption challenged:** "Queue backend: SQLite (same as existing db.ts, simple, no new deps)"

**Why it might be wrong:** SQLite with WAL mode supports concurrent readers, but writers serialize. Every task claim is a write. Every status update is a write. Every result write is a write. With 4 processes polling on intervals (3 workers every 5s, 1 result-poller every 10s), that's roughly 40 write-competitive transactions per minute just from polling overhead. The real problem is not throughput -- it's the failure mode. When a writer hits `SQLITE_BUSY`, better-sqlite3 throws synchronously. The current `db.ts` (line 69) sets `journal_mode = WAL` but sets NO `busy_timeout`. Zero. That means any concurrent write attempt gets an immediate throw, not a retry.

**Severity:** Critical

**What happens if we're wrong:** Workers will see `SQLITE_BUSY` exceptions that manifest as uncaught errors. The pm2 error handling doesn't exist yet -- there's no try/catch around the claim operation in the blueprint. Tasks could be double-claimed (two workers both SELECT the same row before either UPDATEs it) or permanently orphaned. Under the blueprint's "stale task" recovery (reset `running` tasks after 10 minutes), this means a minimum 10-minute delay before any failed claim gets retried.

**Suggested mitigation:** Add `db.pragma('busy_timeout = 5000')` after WAL mode. Use `UPDATE dispatch_queue SET status = 'running', started_at = ? WHERE id = (SELECT id FROM dispatch_queue WHERE status = 'queued' AND worker_type = ? ORDER BY created_at LIMIT 1) RETURNING *` as an atomic claim. This is a single statement -- SQLite's implicit transaction makes it atomic. No separate SELECT-then-UPDATE race window.

---

### 2. Context Amnesia: Workers Cannot Answer Follow-Up Questions

**Assumption challenged:** "Workers don't share sessions with Data. Each dispatched task gets a fresh Claude session."

**Why it might be wrong:** This breaks the conversational contract Matthew has with the bot. Current flow: Matthew asks something, Claude responds within the same session, Matthew asks a follow-up. The session continuity means Claude remembers what it just did. With dispatch: Matthew says "research competitor pricing for XYZ." Soundwave runs it. Result comes back via the poller. Now Matthew says "expand on the third point." Data has no idea what the third point was -- it wasn't in Data's session. The memory system (`saveConversationTurn`, memory.ts line 58) only saves the user's original message and the response if it goes through `handleMessage()`. The result-poller bypass means:

1. The dispatched prompt is saved nowhere in the memory system.
2. The worker's response is saved nowhere in the memory system.
3. Data's Claude session has no knowledge of what the worker did.

**Severity:** Critical

**What happens if we're wrong:** Matthew will ask "what did you find?" and Data will say "I don't know what you're referring to." This will happen on the first real use and immediately erode trust in the system. The whole point of a Chief of Staff is maintaining context across interactions.

**Suggested mitigation:** When the result-poller delivers a result, it must also call `saveConversationTurn(chatId, originalPrompt, workerResult)`. Additionally, the result should be injected into Data's memory context so Claude can reference it. Consider adding a `dispatch_results` memory sector with higher salience to ensure recent async results appear in the memory context window.

---

### 3. The Classifier Will Misclassify Constantly and There Is No Recovery Path

**Assumption challenged:** "Classification by keywords" -- Contains "LinkedIn" -> starscream, Contains "code" -> ravage, etc.

**Why it might be wrong:** The keyword approach has fatal ambiguity problems:

- "Check my code review on LinkedIn" -- matches both `starscream` (LinkedIn) and `ravage` (code, review). Which wins? Blueprint doesn't specify priority order.
- "Can you quickly check if the PR was merged?" -- keyword "PR" triggers `ravage`, but this is a 5-second GitHub API call. It should run inline. The classifier would dispatch it to the queue, adding 15-20 seconds of unnecessary latency (5s poll + 10s result-poll).
- "Summarize this" + a 200-page PDF attachment -- no keyword match for any worker. Goes to `default`. But could it run inline? No way to know without reading the attachment first.
- The 30-second heuristic is ungrounded. Where did 30 seconds come from? The codebase has no historical duration tracking. It's a guess.

The real failure mode is **false-positive dispatch**: a quick task gets routed to the queue. Instead of a 3-second inline response, the user waits 5s (worker poll) + 3s (execution) + 10s (result poll) = 18 seconds. That's 6x slower for a false positive. Users will notice immediately.

**Severity:** Critical

**What happens if we're wrong:** The bot becomes slower for a significant percentage of messages. Matthew will quickly learn to say "run this inline" or stop using it. The 30-second threshold is meaningless without data -- some Claude tasks take 5 seconds, others take 5 minutes, and the message text alone is a poor predictor.

**Suggested mitigation:**
1. Start conservative: ONLY dispatch messages that explicitly contain async intent ("build me X", "write a PR for Y", "research and write up Z"). Default to inline for everything else.
2. Add a `/dispatch` command so Matthew can manually dispatch. Let the user tell you, don't guess.
3. If classification must be automated, use Claude itself (a fast Haiku call) to classify -- but acknowledge this adds ~1-2s latency to every message.
4. Track actual durations and build the classifier from real data in Phase 3, not Phase 1.

---

### 4. pm2 Restarts Will Destroy In-Flight Work With No Recovery

**Assumption challenged:** "Worker crash: pm2 auto-restart. Unclaimed tasks (status='running' for >10min) get reset to 'queued'."

**Why it might be wrong:** When pm2 sends SIGTERM to a worker, the worker's Claude subprocess (spawned via the Agent SDK) is a child process. The SDK's `query()` function (agent.ts line 232) drives an async iterator over a subprocess. SIGTERM to the worker Node.js process will:

1. Kill the worker process.
2. The Claude subprocess may or may not receive SIGTERM (depends on process group handling).
3. If the subprocess was 25 minutes into a 30-minute coding task, all that work is lost.
4. The task stays in `running` status for up to 10 minutes before the stale-task recovery resets it to `queued`.
5. The task is then re-executed from scratch. The previous 25 minutes of work are completely wasted.

The current `index.ts` graceful shutdown (lines 104-111) calls `bot.stop()` which cleanly shuts down the Telegram long-poll. But there's no equivalent for "wait for the current Claude subprocess to finish." The Agent SDK's `query()` doesn't support cancellation -- it's a for-await-of loop.

**Severity:** Warning

**What happens if we're wrong:** Long tasks (the exact tasks this system is designed for) are the most vulnerable to restart-induced loss. A coding task that generates files on disk might leave partial state. A research task loses all accumulated context. The 10-minute stale recovery window means the user sees silence for 10+ minutes before the task even re-queues.

**Suggested mitigation:**
1. Workers must handle SIGTERM by setting a flag that prevents claiming new tasks, then waiting for the current subprocess to finish (with a timeout, say 60s).
2. Reduce the stale-task timeout to 2 minutes (not 10) -- better to re-run quickly than to wait.
3. Consider writing partial results to the queue periodically (a "heartbeat" update to `started_at`) so the stale detector can distinguish between "worker is alive but working" and "worker crashed."

---

### 5. The Complexity Is Not Justified by the Workload

**Assumption challenged:** "Is the complexity worth it?"

**Why it might be wrong:** Let's count what this blueprint adds:
- 1 new database table with multi-process access patterns
- 1 classifier module
- 1 result-poller module
- 1 generic worker loop
- 3 worker-specific CLAUDE.md files
- pm2 ecosystem expansion from 1 process to 4
- Stale task recovery mechanism
- Memory system integration for async results
- Telemetry event extensions
- New test coverage for all of the above

That's roughly 500-800 lines of new code and 200+ lines of modifications to existing files. For a **personal bot used by one person**.

Meanwhile, the actual problem statement is: "When a long task comes in, the bot blocks until completion." How often does this actually happen? Matthew sends a long task, and a second message arrives during execution. The second message hits the `MAX_CONCURRENT_AGENTS` guard and gets "Already processing another request. Try again in a moment." That's it. That's the entire user-facing impact.

The simpler alternative: increase `MAX_CONCURRENT_AGENTS` to 2. The Claude Max plan likely supports 2 concurrent sessions. The Agent SDK spawns subprocesses, so they don't share memory. The retry logic already handles 529 overload. Total code change: change the number 1 to 2 on line 80 of agent.ts. One character.

Or: use an in-process async queue. When a message comes in and the agent is busy, push it to a queue. When the agent finishes, pop the next item. The user gets "Message queued, I'll get to it after the current task." No new processes, no SQLite contention, no stale task recovery, no result-poller.

**Severity:** Critical (architectural over-engineering)

**What happens if we're wrong:** 2-3 weeks of development time for a feature that could be 80% solved in 15 minutes. The added complexity creates new failure modes (SQLite contention, context amnesia, classifier errors, pm2 restart issues) that didn't exist before. Each of those failure modes needs its own mitigation, which adds more code, which adds more failure modes.

**Suggested mitigation:**
1. Start with `MAX_CONCURRENT_AGENTS = 2` and an in-process message queue. Ship it in an hour.
2. Measure: how often does Matthew actually send concurrent requests? Log it. If it's less than 5 times per day, stop here.
3. Only graduate to multi-process workers when the data proves the simple solution is insufficient.

---

### 6. Three Named Workers Is Premature Persona Optimization

**Assumption challenged:** "3 named workers (Starscream, Ravage, Soundwave)" with distinct specialties.

**Why it might be wrong:** The worker specialization is based on predicted future workload, not observed patterns. Starscream (social media, LinkedIn) -- how often does Matthew actually ask the bot to do LinkedIn tasks? Soundwave (research, HIL coaching) -- the ST Factory/Metroplex integration doesn't exist yet. These workers are being designed for workflows that aren't built.

Each idle worker is a Node.js process consuming ~50-80MB of RAM, polling SQLite every 5 seconds, accomplishing nothing. On a 32GB machine that also runs pm2, Claude Code interactive sessions, and potentially yce-harness processes, memory is not infinite.

More importantly: the worker-per-specialty model means if Matthew sends 3 coding tasks in a row, Ravage processes them sequentially (maxConcurrent: 1) while Starscream and Soundwave sit idle. No load balancing.

**Severity:** Warning

**What happens if we're wrong:** Wasted RAM, wasted polling cycles, artificial bottleneck on the most-used worker type. Matthew asks "why is my coding task queued when I can see Starscream is doing nothing?"

**Suggested mitigation:** Start with 1 generic worker. No specialization. It claims any task type. If workload data later shows that specialization improves results (not just sounds cool), add workers then. A generic pool of N workers with round-robin claiming is simpler and more resilient than fixed-specialty allocation.

---

### 7. The Result-Poller Creates a Ghost Conversation

**Assumption challenged:** "Data polls results -> sends to Telegram"

**Why it might be wrong:** The current bot (bot.ts) has a tight coupling between incoming messages and outgoing replies via the grammY `ctx.reply()` pattern. The `ctx` object carries the message thread, reply-to metadata, chat context, and formatting. The result-poller has none of this.

When the poller sends a result via `bot.api.sendMessage()`, it arrives as a new message -- not as a reply to the original message. If Matthew has sent 5 messages since dispatching the task, the result appears at the bottom of the chat with no visual connection to what triggered it. There's no reply-to-message-id. There's no thread.

Also: the result-poller needs the bot instance. But the bot is created inside `main()` in index.ts and is local to the 409 retry loop. Each retry creates a NEW bot. The scheduler handles this with `botApiRef.current` (index.ts line 86), but the result-poller would need the same mutable reference pattern. The blueprint doesn't address this.

And there's a bigger problem: the `dispatch_queue` schema has no `message_id` column. Without the original Telegram message ID, the poller cannot reply-to the triggering message. It can only send a floating message that Matthew must manually connect to the original request.

**Severity:** Warning

**What happens if we're wrong:** Matthew gets disorienting out-of-context messages. "Here are the research findings..." with no indication of what was asked. If 3 tasks complete near-simultaneously, he gets 3 back-to-back messages with no context about which request each corresponds to. The UX degrades from "chief of staff" to "random facts dispenser."

**Suggested mitigation:**
1. Add `message_id INTEGER` to the dispatch_queue schema. Store the Telegram message_id of the triggering message.
2. Result-poller uses `reply_to_message_id` when sending results so they thread in the chat.
3. Prefix each result with context: "Re: [original prompt truncated to 60 chars]"

---

### 8. Claude Max Plan Rate Limits Are Undocumented and Assumed

**Assumption challenged:** "Each worker spawns Claude subprocesses on Max plan OAuth. No API billing unless explicitly overridden."

**Why it might be wrong:** The blueprint assumes the Claude Max plan supports 4+ concurrent Claude Code sessions from the same OAuth credential. This assumption is untested. Anthropic's rate limits for Max plan sessions are not publicly documented per-seat, and they can change without notice.

Currently, the system runs 1 Claude Code subprocess at a time (agent.ts line 80) specifically because of this uncertainty: "Concurrency limiter: only 1 Claude subprocess at a time to avoid rate limit collisions with interactive Claude Code sessions." The comment explicitly acknowledges the risk.

If 4 processes each spawn a Claude subprocess, and Anthropic's backend sees 4 concurrent sessions from the same account, any of these could happen:
- Hard rejection (429 rate limit) on sessions 2-4
- Queuing on Anthropic's side (adding latency, but not failing)
- Degraded model quality (smaller model, less reasoning) under high concurrency
- Account flag for abuse

The retry logic (agent.ts lines 83-95) uses exponential backoff with no jitter. If all 4 processes hit a 529 simultaneously, they all retry at exactly the same times (10s, 20s, 40s), causing a thundering herd that re-triggers the overload.

**Severity:** Warning

**What happens if we're wrong:** All workers fail simultaneously and retry in sync, creating a sustained overload pattern. Tasks fail after MAX_RETRIES (3) and get marked as `failed`. The user sees multiple "task failed" messages. The system is worse than the current single-agent approach because at least the single agent works reliably.

**Suggested mitigation:**
1. Before building any of this, test concurrent session limits. Spawn 2 Claude Code subprocesses from the same machine with Max plan OAuth and observe the behavior.
2. Add jitter to retry delays: `delay * (1 + Math.random() * 0.5)` to prevent thundering herd.
3. Implement a global rate limiter (shared via SQLite or filesystem) so processes coordinate rather than compete.

---

### 9. The Scheduler Is a Time Bomb Waiting to Collide

**Assumption challenged:** The blueprint doesn't address the scheduler path at all.

**Why it might be wrong:** The scheduler (scheduler.ts line 59) calls `runAgent()` directly. It runs in the same process as Data. When a scheduled task fires, it blocks Data's agent slot (`MAX_CONCURRENT_AGENTS = 1`). If Matthew sends a message while a scheduled task is running, he gets "Already processing another request."

The blueprint proposes adding 3 workers to handle long tasks, but doesn't mention the scheduler at all. The scheduler is responsible for the morning report, which is potentially the longest-running task in the system (it aggregates data from multiple sources). So the most blocking task in the system is the one that ISN'T routed through the new dispatch system.

Options:
1. Scheduler routes through dispatch_queue: Good, but requires modifying scheduler.ts to insert tasks instead of calling runAgent(). Who classifies scheduled tasks? They don't have user messages with keywords.
2. Scheduler stays as-is: Defeats the purpose. The morning report blocks Data for 2-5 minutes every day at 9am, which is exactly when Matthew is most likely to be sending messages.

**Severity:** Warning

**What happens if we're wrong:** Matthew builds this whole dispatch system, and the most annoying blocking case (morning report at 9am) still blocks the bot. He'll notice on day 1.

**Suggested mitigation:** Phase 1 must include routing scheduled tasks through the dispatch queue. The scheduler should insert into `dispatch_queue` with `worker_type = 'soundwave'` (or 'default') instead of calling `runAgent()`.

---

### 10. The Codebase Is Not Ready for This Level of Surgery

**Assumption challenged:** "The existing codebase is ready for this"

**Why it might be wrong:** Look at what this codebase has already survived:
- The 409 conflict recovery loop (index.ts lines 72-171) is 100 lines of hard-won battle scars. It took multiple iterations to get the timing right (the comment "KEY FIX: Initial delay must be >= 35s" on line 77 tells a story of painful debugging).
- The `botApiRef.current` pattern (index.ts line 86) exists because a simpler approach failed -- "Previous approach used a closure over a local var that never updated."
- The scheduler had a duplicate-interval bug that required explicit tracking (scheduler.ts lines 17-22).
- The message dedup cache (bot.ts lines 28-49) exists because of edge cases in the 409 retry cycle.

Every one of these is a lesson learned through production failures. The codebase is stabilized through scar tissue, not through architectural clarity. Adding multi-process coordination, a task queue, a classifier, a result-poller, and worker lifecycle management increases the surface area for these kinds of hard-to-debug production issues by at least 4x.

The test suite covers bot formatting, memory operations, db CRUD, and env parsing -- but there are NO tests for the 409 recovery flow, NO tests for the scheduler's concurrency behavior, NO tests for what happens when runAgent is called while another is running. The critical paths are untested. Adding more critical paths without first testing the existing ones is accumulating risk.

**Severity:** Warning

**What happens if we're wrong:** Weeks of debugging multi-process edge cases. Ghost messages, lost tasks, zombie workers, SQLite lock contention that only manifests under specific timing conditions. Each bug will be 10x harder to reproduce than the 409 bug was, because it involves multiple processes.

**Suggested mitigation:**
1. Before building the dispatch system, add integration tests for the scheduler + agent interaction.
2. Add a `busy_timeout` to SQLite.
3. Consider whether the 409 recovery loop can be simplified first -- it's the most complex part of the codebase and it will interact with the new multi-process architecture in unpredictable ways.

---

### 11. No Cancellation, No Visibility, No Control

**Assumption challenged:** The blueprint provides no user-facing task management.

**Why it might be wrong:** Once a task is dispatched, Matthew has zero control:
- No way to cancel a running task.
- No way to see what's queued.
- No way to see what's running.
- No way to re-prioritize.
- No way to know if a worker is dead.

The ACK message says "Got it. Dispatched to Ravage. I'll report back when done." But what if 20 minutes pass with no result? Is Ravage dead? Is the task still running? Did it fail silently? The only recourse is `pm2 logs ea-claude-ravage` in a terminal -- which defeats the purpose of a Telegram bot.

**Severity:** Warning

**What happens if we're wrong:** Matthew will not trust the system. He'll send the same request twice because he's not sure the first one is being processed. This creates duplicate tasks in the queue with no dedup mechanism. (The message dedup in bot.ts tracks Telegram `message_id`, but if Matthew manually re-types the request, it gets a new `message_id`.)

**Suggested mitigation:**
1. `/tasks` command -- list queued and running tasks with worker assignment and age.
2. `/cancel <id>` command -- mark a task as cancelled, kill the worker's subprocess if possible.
3. Periodic heartbeat: workers update `started_at` every 60 seconds. The poller checks for stale heartbeats and proactively notifies "Task X appears stuck."

---

## The "Do Nothing" Alternative

The simplest change that gets 80% of the benefit:

### Option A: Increase MAX_CONCURRENT_AGENTS to 2 (1 line change)

```typescript
// agent.ts line 80
const MAX_CONCURRENT_AGENTS = 2;
```

Why this works: The actual problem is that Matthew's second message gets bounced while the first is processing. Allowing 2 concurrent Claude subprocesses means he can send a quick follow-up while a long task runs. The Claude Max plan very likely supports 2 concurrent sessions. The retry logic already handles 529 overload gracefully.

Risk: If the Max plan doesn't support 2 concurrent sessions, one will fail with a 529 and retry. That's the current behavior for free -- no new code needed.

Effort: 5 minutes.

### Option B: In-Process Async Queue (50 lines of code)

```typescript
// New: queue.ts
const taskQueue: Array<{ chatId: string; message: string; resolve: Function }> = [];
let processing = false;

export function enqueueTask(chatId: string, message: string): Promise<string> {
  return new Promise((resolve) => {
    taskQueue.push({ chatId, message, resolve });
    if (!processing) processNext();
  });
}

async function processNext() {
  if (taskQueue.length === 0) { processing = false; return; }
  processing = true;
  const task = taskQueue.shift()!;
  // Send "queued" message to user
  // Run agent
  // Send result
  // processNext() recursively
}
```

Why this works: Tasks queue in-memory. Matthew gets "Your message is queued (position 2)." Tasks run sequentially. No SQLite contention, no multi-process coordination, no pm2 expansion. Zero new dependencies.

Risk: Queue is lost on restart. But tasks are just Telegram messages -- Matthew can re-send. For a personal bot with 10-20 messages per day, this is fine.

Effort: 2-3 hours.

### Option C: Route Scheduled Tasks Only (targeted fix)

If the morning report blocking Data at 9am is the real pain point, route ONLY scheduled tasks through a single worker process. Don't touch interactive messages at all.

```
Data (inline) -- handles all interactive messages
Worker (pm2)  -- handles ONLY scheduled tasks
```

Effort: 1 day. Much less risk than the full blueprint.

---

## Missing Elements

### 1. No Load Testing or Capacity Model
The blueprint proposes 4 OS processes, each capable of spawning a Claude subprocess, on a machine that also runs interactive Claude Code sessions and potentially other projects. There is no resource budget. No measurement of: How much RAM does a Claude subprocess use? How much does a better-sqlite3 connection consume? What's the baseline memory usage of the existing ea-claude process? Without these numbers, the pm2 expansion is a bet that "32GB is enough." It probably is. But "probably" is not engineering.

### 2. No Rollback Plan
What if the dispatch system is deployed and breaks? How do you roll back to the current single-process architecture? The database schema change (adding dispatch_queue) is additive and safe. But the bot.ts changes (adding classification + dispatch) modify the core message handling path. If the classifier has a bug, EVERY message is affected, not just the ones meant for dispatch. There's no feature flag to disable dispatch without reverting code.

### 3. No Monitoring or Alerting
If all 3 workers are down, how does Matthew know? The bot will happily dispatch tasks to the queue and ACK them, but nothing will ever pick them up. The 10-minute stale recovery resets them to `queued`, and they get re-queued forever. The result-poller never finds completed tasks. Matthew is waiting indefinitely with no notification that anything is wrong.

### 4. The Telegram Bot Token Is Shared
Workers need to send progress or results to Telegram (or the result-poller does). All processes share the same `TELEGRAM_BOT_TOKEN`. Telegram's Bot API has rate limits (30 messages/second per chat, 20 messages/minute in groups). If a worker tries to send a result at the same time the poller does, they could hit Telegram's rate limit. More importantly: if any process calls `getUpdates()` or `setWebhook()`, it disrupts the main bot's long-poll connection, re-triggering the 409 conflict that took 100+ lines of code to handle.

### 5. Media Messages Are Ignored
The blueprint only discusses text messages. The current bot handles photos, documents, videos, and voice messages (bot.ts lines 404-583). Can a photo message be dispatched? "Analyze this screenshot and build a component from it" is clearly a long task with a photo attachment. The dispatch_queue schema stores only `prompt TEXT` -- there's no provision for media references, file paths, or binary attachments.

---

## Recommendations

**Verdict: REJECT the blueprint as written. Approve a reduced Phase 0.**

The blueprint solves a real problem (agent blocking) but proposes a solution whose complexity is 10x disproportionate to the problem's severity. The problem is "sometimes Matthew's second message gets bounced." The solution is "4 OS processes, a SQLite task queue, a keyword classifier, a result-poller, 3 specialized worker personas, and pm2 fleet management."

**What I would approve instead:**

**Phase 0 (ship this week):**
1. Change `MAX_CONCURRENT_AGENTS` from 1 to 2. Measure the impact for 2 weeks.
2. Route scheduled tasks to a separate worker process (1 worker, generic, no specialization). This is the most concrete pain point.
3. Add an in-process FIFO queue for interactive messages: if both agent slots are busy, queue the message and send "Got it, you're next in line."
4. Add duration telemetry: log actual execution time per message so the 30-second threshold has data behind it.

**Phase 1 (only if Phase 0 data justifies it):**
5. If data shows >10 daily cases of queueing, introduce 1 generic dispatch worker with SQLite queue. No classification -- everything dispatched goes to the same worker.
6. Add the result-poller with reply-to-message threading.
7. Add `/tasks` and `/cancel` commands.

**Phase 2 (only if Phase 1 data justifies it):**
8. Worker specialization (if worker performance data shows domain-specific CLAUDE.md improves output quality).
9. Automated classification (if override data from `/dispatch` shows consistent patterns).
10. Sky-Lynx integration.

The blueprint is sound in concept but should be built incrementally with data gates between phases, not shipped as a monolith. The risk of building all 4 phases before validating the first one is that you end up with a complex system solving a problem that could have been fixed with a one-line change.
