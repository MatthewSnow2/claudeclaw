# Agent Team Prompt: EA-Claude Async Dispatch Blueprint Review

Create an agent team to review and approve the EA-Claude Async Dispatch Blueprint for implementation readiness.

The blueprint describes a migration from a blocking single-session Telegram bot architecture to an async worker dispatch system using SQLite queue, message classification, pm2 worker processes (Starscream, Ravage, Soundwave), and a result poller. The goal is to unblock the bot during long-running tasks and enable specialized parallel workers.

The blueprint is at /home/apexaipc/projects/claudeclaw/BLUEPRINT-async-dispatch.md.

The existing codebase is at /home/apexaipc/projects/claudeclaw/src/ with key files:
- bot.ts (Grammy Telegram bot, message handling, dedup cache)
- agent.ts (Claude Agent SDK query(), MAX_CONCURRENT_AGENTS=1, retry logic)
- scheduler.ts (cron task runner, idempotent init, polls every 60s)
- index.ts (pm2 entry point, 409 conflict recovery, PID lock)
- router.ts (multi-LLM @prefix routing: claude, gemini, perplexity, ollama)
- memory.ts (FTS5 search + recency, context injection)
- db.ts (SQLite database, sessions, memories, scheduled tasks)
- config.ts (env loading, Telegram tokens, voice keys)

Constraints:
- Must use SQLite (same as existing db.ts, no new database dependencies)
- Must work with Claude Max plan OAuth (no API billing unless explicitly overridden)
- Must not break existing interactive message flow (quick responses stay inline)
- Must integrate with existing memory system (workers may need context)
- pm2 manages all processes; no Docker, no Kubernetes
- Workers must not collide on API rate limits with each other or with Data (the main bot)

This is a two-phase operation:

PHASE 1 -- Orchestrator Analysis (must complete before Phase 2):

Spawn 1 teammate:

1. Blueprint Analyst -- Read the entire blueprint AND the existing codebase (bot.ts, agent.ts, scheduler.ts, index.ts, router.ts, memory.ts, db.ts). Produce:
   - A domain map: what areas of expertise does this blueprint cover?
   - For each domain, specify:
     * Domain name (e.g., "Queue Architecture", "Concurrency", "Process Management", "Codebase Integration")
     * Why this domain needs review (what's at stake if we get it wrong)
     * Key questions a specialist should answer
     * Specific sections of the blueprint AND existing code to focus on
   - A recommended team composition: which specialist agents to spawn
   - Dependencies between specialists (who should go first?)
   - Initial flag: are there any obvious gaps or contradictions in the blueprint?
   Save analysis to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/orchestrator_analysis.md. This must complete before Phase 2 begins.

PHASE 2 -- Specialist Review Team:

Using the Orchestrator's analysis, spawn the recommended specialists. At minimum, the team MUST include these four (the Orchestrator may add more):

2. Architecture Reviewer -- Evaluate the queue-based dispatch architecture for:
   - SQLite as a task queue (is this the right choice given concurrency needs?)
   - Worker polling pattern (5s intervals, claiming mechanism, stale task recovery)
   - Result poller design (10s polling, notification flow back to Telegram)
   - Component boundaries between classifier, queue, workers, and poller
   - Whether the 4-phase implementation order makes sense
   - Single points of failure and recovery paths
   Save to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/architecture_review.md.

3. Concurrency Specialist -- Evaluate race conditions and process isolation:
   - SQLite WAL mode under concurrent writes from multiple pm2 workers
   - Task claiming: can two workers claim the same task? (SELECT ... WHERE status='queued' LIMIT 1 is not atomic)
   - Rate limit collision between workers + Data bot + scheduled tasks (all hitting Claude API)
   - Session isolation: workers get fresh sessions but Data maintains conversational session
   - What happens when a worker crashes mid-task? (status='running' timeout + reset)
   - pm2 restart behavior and its interaction with the queue
   Save to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/concurrency_review.md.

4. Codebase Integration Reviewer -- Map the blueprint to the existing code and identify:
   - Exact changes needed in bot.ts (where does classification happen? before or after router?)
   - How does dispatch interact with the existing memory system? (workers need context?)
   - Does the classifier need access to session state to make good quick/long decisions?
   - How does the result-poller coexist with the existing scheduler? (both poll on intervals)
   - What happens to @prefix routing (router.ts) for dispatched tasks? (gemini/perplexity stay inline?)
   - Is the existing dedup cache in bot.ts sufficient, or do dispatched tasks need their own dedup?
   - What code from agent.ts can be reused in worker.ts vs what needs to be refactored?
   Save to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/integration_review.md.

5. Devil's Advocate -- Find reasons this architecture could fail. Challenge the blueprint's assumptions:
   - "SQLite is fine for a task queue" -- is it? What happens at 50 concurrent writes?
   - "Workers don't need shared sessions" -- but what if Matthew asks a follow-up about a dispatched task?
   - "Classification by keywords" -- what about ambiguous messages? "check my LinkedIn" (quick lookup or full audit?)
   - "pm2 manages everything" -- pm2 restarts kill in-flight Claude subprocesses. What's the blast radius?
   - Is the complexity worth it? Could a simpler solution (just increase MAX_CONCURRENT_AGENTS to 2-3) solve 80% of the problem?
   - What's the user experience during the transition? Will Matthew get confused about which "agent" did what?
   Save contrarian analysis to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/devils_advocate.md.

Each specialist should:
   - Read the Orchestrator's analysis to understand their assignment
   - Read the full blueprint AND relevant source files from /home/apexaipc/projects/claudeclaw/src/
   - Produce a structured review:
     * Domain: [their domain]
     * Files Reviewed: [list of blueprint sections and source files]
     * Findings: [numbered list with severity: Critical/Warning/Suggestion]
     * Missing Elements: [what should be in the blueprint but isn't]
     * Recommendations: [specific, actionable improvements -- include code snippets where helpful]
   - Be specific: reference line numbers, function names, and exact code paths

After all specialists complete:
   - Cross-reference findings for contradictions (e.g., Architecture says "polling is fine" but Concurrency says "polling creates race conditions")
   - Identify gaps: domains the Orchestrator flagged but no specialist covered
   - Rank all findings by severity
   - Produce a consolidated review with:
     * Executive summary (3-5 sentences)
     * Critical issues (must fix before implementation)
     * Warnings (should fix, implementation may proceed with caution)
     * Suggestions (nice to have, can be deferred)
     * Blueprint modifications: specific edits to BLUEPRINT-async-dispatch.md (if any)
     * Overall assessment: APPROVE / REVISE / RETHINK
   Save to /home/apexaipc/projects/claudeclaw/outputs/async_dispatch_review/consolidated_review.md
