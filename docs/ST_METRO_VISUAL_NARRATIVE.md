# ST Metro Ecosystem: The Complete Visual Narrative

*A non-technical guide to Matthew's fully autonomous software production system*

---

## What Is ST Metro?

ST Metro is a **self-improving software factory** that runs with zero human intervention. The human (Matthew) sets strategy and constraints. The system:
- Watches the market and research landscape for problems worth solving
- Synthesizes those problems into product ideas
- Automatically decides which ideas are worth building
- Builds them autonomously
- Observes the results and recommends improvements to itself
- The cycle repeats

**Named after**: The Transformers' Autobot city -- Metroplex. Each component is named after a Transformer character reflecting its role.

**Status (2026-02-25)**: The pipeline is **live and proven**. Signals flow from market research through idea synthesis through triage through autonomous builder. The system has shipped 1 MVP and continues running.

---

## The Big Picture

```
                         INPUTS                              PROCESSING                           OUTPUT
                    +--------------+
                    | Research     |     +------------+     +-----------+     +-------------+
  Internet ------->| Agents       |---->|            |---->|           |---->|             |
  (ArXiv, HN,      | (4 daily     |     | IdeaForge  |     | Metroplex |     | YCE Harness |----> GitHub
   GitHub trends)   | LLM workers) |     | (score &   |     | (triage & |     | (autonomous |      Vercel
                    +--------------+     | classify)  |     | dispatch) |     | multi-agent |      Railway
                                         +------------+     +-----------+     | engineer)   |
  Claude Desktop -->| idea-catcher |---->|            |          |            +-------------+
  (manual ideas)    | (MCP server) |     | Ultra-     |          |                  |
                    +--------------+     | Magnus     |          |                  |
                                         +------------+     +-----------+           |
                                              |             | ST Factory|<----------+
                    +--------------+          |             | (metrics  |     OutcomeRecords
  Matthew's ------->| Linear       |----------+             | & patches)|
  Strategy          | (backlog)    |                        +-----------+
                    +--------------+                             |
                                                            +-----------+
                                                            | Sky-Lynx  |
                                                            | (weekly   |---> Improvement
                                                            | analysis) |     Recommendations
                                                            +-----------+         |
                                                                 |                |
                                                            +-----------+         |
                                                            | Persona   |<--------+
                                                            | Academy   |
                                                            | (upgrade  |
                                                            | AI roles) |
                                                            +-----------+
                                                                 |
                                                                 +-----> Next cycle starts
                                                                         with smarter personas
```

---

## Act 1: The Scouts (Signal Ingestion)

Every day at 5 AM, four AI research agents wake up and scan the internet:

| Agent | What It Scans | LLM Used | Why Different LLM |
|-------|--------------|----------|-------------------|
| ArXiv Scanner | Academic papers on AI, ML, autonomy | Perplexity | Citation-rich, research-focused |
| Tool Monitor | GitHub trending repos, new frameworks | Gemini | Fast, broad coverage |
| Domain Watcher | Hacker News, industry forums | ChatGPT | Good at extracting sentiment |
| Idea Surfacer | Synthesizes all signals into ideas | Claude | Best at nuanced reasoning |

**Why different LLMs?** Anti-monoculture. If every agent used the same model, they'd have the same blind spots. Using 4 different LLMs ensures diverse perspectives.

**Output**: 50-100 research signals per day, normalized into a shared database (IdeaForge).

---

## Act 2: The Filter (IdeaForge + Triage)

Not every signal becomes an idea. Not every idea gets built.

**IdeaForge scores every idea on 5 dimensions:**
1. **Opportunity** -- How big is the market? (0-10)
2. **Problem Severity** -- How painful is this problem? (0-10)
3. **Feasibility** -- Can a solo dev build this in 2-4 weeks? (0-10)
4. **Why Now** -- Is the timing right? (0-10)
5. **Competition** -- Is the landscape favorable? (0-10)

**Then classifies:**
- **Tool** (cheap to build, quick value)
- **Agent** (medium complexity, AI-powered)
- **Product** (full product, needs sustained effort)
- **Dismiss** (not worth pursuing)

**Metroplex Triage Gate** then decides:
- Score >= 65/100? **Approved** -- queued for build
- Score < 65/100? **Rejected** or **Deferred**
- Already triaged? Skip (dedup filter prevents re-processing)

**Real example**: "Agent Supply Chain Scanner" scored 7.4/10 and was approved. "AI Agent Analytics Platform" scored 4.6/10 and was deferred.

---

## Act 3: The Builder (YCE Harness)

When Metroplex approves an idea, it dispatches to YCE Harness -- the autonomous software engineer.

YCE is not one agent. It's **five agents working in parallel**:

| Agent | Role | Model | Works In |
|-------|------|-------|----------|
| Orchestrator | Breaks spec into tasks, coordinates | Haiku (fast) | Main repo |
| Coding Agent | Writes features, TDD-style | Sonnet (smart) | Git worktree 1 |
| GitHub Agent | Commits, branches, PRs | Sonnet | Git worktree 2 |
| Linear Agent | Creates/updates issues | Sonnet | Main repo |
| QA Agent | Tests with Playwright | Sonnet | Git worktree 3 |

**Why parallel?** Each agent runs in an isolated git worktree. They don't block each other. The Coding Agent writes code while the Linear Agent tracks status and the GitHub Agent pushes commits.

**Output**: Feature branches with tests, merged into main, deployed to GitHub/Vercel/Railway.

---

## Act 4: The Loop (Sky-Lynx + Academy)

This is where ST Metro becomes more than a pipeline. It becomes a **learning system**.

Every Sunday at 2 AM, Sky-Lynx runs:

1. **Reads outcomes** -- What ideas were built? What failed? What shipped?
2. **Identifies patterns** -- "ArXiv signals produce higher-scoring ideas" or "Feasibility scores were too optimistic"
3. **Generates recommendations** -- Typed, structured improvements:
   - Voice adjustments ("Persona X should be more conservative")
   - Framework additions ("Add supply chain analysis to evaluator")
   - Constraint changes ("Reject ideas over $500K build cost")
   - CLAUDE.md updates ("Agent should check test coverage before shipping")

4. **Academy applies patches** -- Persona YAML files are updated automatically

**Next cycle**: All personas now reflect this week's learnings. Feasibility scoring is stricter. ArXiv signals get more weight. The system got smarter overnight.

**The key insight**: The system watches itself work. OutcomeRecords feed Sky-Lynx feeds Academy feeds the next cycle. No human retraining required.

---

## Act 5: The Coordinator (Metroplex)

Metroplex is the factory floor manager. It runs as a systemd service, cycling every 60 seconds:

**Three gates:**
1. **Triage Gate** -- Score and approve/reject ideas from IdeaForge
2. **Build Gate** -- Dispatch approved ideas to YCE Harness
3. **Patch Gate** -- Apply persona improvements from Sky-Lynx via Academy

**Safety guardrails:**
- **Circuit Breaker**: If a gate fails 3 times, it pauses (other gates keep running)
- **Per-Cycle Caps**: Max 3 ideas per cycle, max 5 patches per cycle
- **Schedule Windows**: Active 9 AM - 10 PM, Monday-Friday only
- **Kill switch**: One environment variable stops everything

---

## The Memory Layer (Perceptor)

How does the system remember conversations from weeks ago?

Perceptor is a context-sharing MCP server that syncs between Claude Desktop and Claude Code via GitHub:

1. Matthew has a conversation in Claude Desktop about enterprise AI adoption
2. Perceptor saves it as a tagged markdown file + pushes to GitHub
3. Next Claude Code session: `perceptor_load("enterprise-adoption-notes")` -- instant context recovery
4. No "what were we talking about last Tuesday?" moments

**5 tools**: `perceptor_list`, `perceptor_load`, `perceptor_save`, `perceptor_search`, `perceptor_sync`

---

## The Chief of Staff (Data / EA-Claude)

Data is the human interface to the entire ecosystem. Running as a Telegram bot on Matthew's workstation:

- **Multi-LLM routing**: @gemini, @research, @ollama, @gpt route to different backends
- **Full tool access**: Can SSH into hardware, manage files, run builds, access all MCP servers
- **Scheduled reports**: Morning briefing (9 AM), Evening review (4 PM)
- **Pipeline tracking**: Maintains PIPELINE.md with all open/closed/parked work
- **Memory**: Semantic and episodic memory with full-text search across sessions
- **Challenger Mode**: Applies Christensen filter to new ideas before executing

---

## Current Status

| Component | Status | What It Does |
|-----------|--------|-------------|
| Research Agents | Running (daily 5am) | 4 LLM agents scan internet for signals |
| IdeaForge | Running (daily 6am) | Score and classify ideas |
| Ultra-Magnus | Available | Manual idea-to-product pipeline |
| YCE Harness | Available | Autonomous multi-agent engineer |
| Metroplex | Running (systemd) | Triage, build dispatch, patching |
| ST Factory | Running | Metrics, contracts, outcome tracking |
| Sky-Lynx | Running (Sunday 2am) | Weekly analysis + improvement recs |
| Persona Academy | Available | Persona YAML management + patching |
| Perceptor | Running | Cross-session context memory |
| Data (EA-Claude) | Running (pm2) | Telegram bot, Chief of Staff |

**What's proven**: Signal ingestion through triage through approval. One idea went fully through the pipeline.

**What's next**: Build gate dispatching to YCE Harness. First fully autonomous idea-to-deployed-product cycle with zero human code or review.

---

## The Vision: Level 5 Autonomy

Based on Dan Shapiro's 5-level AI adoption framework and StrongDM's two constraints:
1. Code must not be written by humans
2. Code must not be reviewed by humans

ST Metro closes all human gates in the feedback loop:

```
Level 1: AI assists human coding (GitHub Copilot)
Level 2: AI writes code, human reviews (Claude Code)
Level 3: AI writes and reviews, human deploys (YCE Harness)
Level 4: AI writes, reviews, deploys, human monitors (Metroplex)
Level 5: AI writes, reviews, deploys, monitors, improves itself (ST Metro)
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
         WE ARE HERE (building toward full L5)
```

The ecosystem self-corrects: Sky-Lynx observes outcomes, generates recommendations, Academy upgrades personas, cycle repeats. The factory gets smarter every week without human intervention.

---

*Built by Matthew Snow / M2AI. Last updated: 2026-02-25.*
