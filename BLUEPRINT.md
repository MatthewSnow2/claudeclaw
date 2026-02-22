# ClaudeClaw - Hybrid AI Chief of Staff

## Overview
ClaudeClaw ("Data") is a multi-LLM command center running as a Telegram bot, backed by Claude Code (Agent SDK) with @prefix routing to Gemini, Perplexity, Ollama, OpenAI, and Clawdbot.

## Phase Checklist

- [x] **Phase 1**: Clone, Configure, Run - .env with bot token and chat ID
- [x] **Phase 2**: CLAUDE.md Identity - Chief of Staff personality, routing docs, security rules
- [x] **Phase 3**: Multi-LLM Backend Integration
  - [x] 3a: `src/router.ts` - @prefix message routing
  - [x] 3b: `src/llm-backends.ts` - Gemini, Perplexity, Ollama, OpenAI backends
  - [x] 3c: `src/clawdbot-dispatch.ts` - HTTP dispatch to Clawdbot gateway
  - [x] 3d: `src/bot.ts` - Router integration, [backend] tags, error messages
  - [x] 3e: `src/env.ts` - ~/.env.shared fallback for secret loading
  - [x] 3f: `src/config.ts` - Clawdbot gateway config exports
- [x] **Phase 4**: Concurrency Safeguard - 1 concurrent Claude subprocess limit
- [x] **Phase 5**: Systemd Service - build, service file, enabled
- [x] **Phase 6**: Immediate Security
  - [x] Output redaction (redactSecrets function)
  - [x] CLAUDE.md security instructions
  - [ ] Auditd file monitoring (requires sudo - manual step)

## Up Next: Phase 7 — Bot-to-Bot Coordination via Linear

### Design

Linear serves as the shared work queue and coordination layer between Data and Chad.
Arcade MCP provides unified auth to Linear/GitHub/Slack for both bots.
Pattern proven in `yce-harness`: "Agents don't share memory. Pass information between them explicitly."

### Architecture

```
  Data (ClaudeClaw)                    Chad (Clawdbot)
       |                                    |
       |  Arcade MCP (Linear tools)         |  Arcade MCP (Linear tools)
       v                                    v
  +------------------------------------------+
  |          Linear Project (shared)         |
  |                                          |
  |  Issues = task queue                     |
  |  States = workflow (Todo→InProgress→Done)|
  |  Comments = signals + results            |
  |  META issue = global state & handoff     |
  |  Labels = ownership (#data, #chad)       |
  +------------------------------------------+
       |                                    |
       v                                    v
  Slack (via Arcade) — real-time notifications
  GitHub (via Arcade) — code artifacts linked to issues
```

### Implementation Steps

- [x] **7a: Arcade MCP for ClaudeClaw**
  - Add Arcade MCP config to ClaudeClaw (adapt `yce-harness/arcade_config.py` pattern)
  - Use `mcp-remote` stdio bridge (required for Claude SDK Task tool propagation)
  - Keys: `ARCADE_API_KEY`, `ARCADE_GATEWAY_SLUG`, `ARCADE_USER_ID` from `~/.env.shared`

- [ ] **7b: Shared Linear project**
  - Create a "Data + Chad Ops" Linear project (or reuse existing)
  - Convention: issues tagged `#data` or `#chad` for ownership
  - META issue: `[META] Bot Coordination Tracker` for global state
  - Comment-based signals: "Done — result: {summary}" triggers the other bot

- [ ] **7c: Clawdbot synchronous endpoint**
  - Replace fire-and-forget dispatch with request/response
  - Data can query Chad and get the answer back inline
  - Enables "second opinion" pattern without Linear overhead for quick queries

- [ ] **7d: Coordination patterns**
  - **Task handoff**: Data creates issue → Chad picks it up (or vice versa)
  - **Second opinion**: `@both` prefix — Data answers, dispatches to Chad, synthesizes both
  - **Pipeline**: Data does research → writes result to Linear → Chad implements
  - **Polling**: Each bot checks META issue for signals from the other

- [ ] **7e: Loop prevention & safety**
  - Max turns per coordination chain (e.g., 3 round-trips)
  - Cooldown between bot-to-bot interactions
  - Only Matthew can initiate coordination (no autonomous bot-to-bot without human trigger)
  - Dead letter queue: if a bot doesn't respond within timeout, notify Matthew via Telegram

### Reference Implementation
- `yce-harness/arcade_config.py` — Arcade MCP setup, tool definitions, mcp-remote bridge
- `yce-harness/client.py` — SDK client with Arcade MCP
- `yce-harness/agents/orchestrator.py` — Context routing between agents
- `yce-harness/prompts/orchestrator_prompt.md` — "Agents don't share memory" philosophy
- `yce-harness/linear_status.py` — Direct Linear API polling

---

## Deferred Items
- [ ] Separate Linux users per service
- [ ] Segment ~/.env.shared into per-service scoped files
- [ ] Remove bypassPermissions, implement scoped permission model
- [ ] Bash command denylist for sensitive file paths
- [ ] Input sanitization layer
- [ ] iptables rules
- [ ] Voice setup (Groq Whisper + ElevenLabs)
- [ ] Migrate cron jobs

## Architecture

### Current (Phases 1-6)
```
Matthew (Telegram) --> Data (ClaudeClaw) --> Claude Code (default)
                                        --> Gemini 2.0 Flash (@gemini)
                                        --> Perplexity Sonar (@research)
                                        --> Ollama local (@ollama/@local/@private)
                                        --> OpenAI GPT (@gpt)
                                        --> Clawdbot Gateway (@chad/@clawdbot)
```

### Target (Phase 7)
```
Matthew (Telegram)
   |            |
   v            v
  Data         Chad
   |            |
   +-----+------+
         |
    Linear (Arcade MCP)
    ├── Issues = task queue
    ├── Comments = signals
    ├── META = global state
    |
    +-- Slack (notifications)
    +-- GitHub (code artifacts)
```
