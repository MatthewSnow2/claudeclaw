# ClaudeClaw

> Your Claude Code CLI, running as a personal Telegram bot on your own machine.

ClaudeClaw is not a chatbot wrapper. It's a bridge that lets the Claude Agent SDK spawn the actual `claude` CLI subprocess on your Mac or server, then pipes the result back to your Telegram chat. Because it runs the real Claude Code process, every skill you have installed in `~/.claude/skills/` works automatically -- no configuration, no syncing, no duplicating anything. Send a voice note, get a spoken response. Drop a PDF, get it processed. Set a recurring task, get a Telegram message every Monday at 9am.

---

## What You Get

- **Full Claude Code in your pocket** -- the same agent that runs in your terminal, accessible from your phone
- **All your global skills auto-loaded** -- `/gmail`, `/todo`, `/linkedin-post`, `/agent-browser`, everything in `~/.claude/skills/`
- **Voice in, voice out** -- Groq Whisper STT (free tier) + ElevenLabs TTS for spoken interaction
- **Photo and document handling** -- send a photo or file, Claude reads and processes it
- **SQLite memory with FTS5 search** -- keyword-matched recall plus recency layer, with salience decay
- **Cron-based scheduler** -- recurring autonomous tasks that fire and message you with results
- **Session resumption** -- Claude Code sessions persist across messages so context carries forward
- **Single-user locked** -- hardcoded to one Telegram chat ID, no multi-tenant attack surface
- **Background service** -- setup wizard installs a launchd agent so it starts on login

---

## How It Works

```
Your Phone (Telegram)
        │
        │  text / voice / photo / document
        ▼
┌─────────────────────────────────────┐
│           ClaudeClaw                │
│   (Node.js · your Mac/server)      │
│                                     │
│  ┌──────────┐   ┌───────────────┐  │
│  │  Memory  │   │   Scheduler   │  │
│  │  SQLite  │   │   Cron jobs   │  │
│  │  + FTS5  │   │   (60s tick)  │  │
│  └──────────┘   └───────────────┘  │
│                                     │
│  Claude Agent SDK                   │
│    └─ claude CLI (subprocess)      │
│         ├─ CLAUDE.md (identity)    │
│         ├─ ~/.claude/skills/       │
│         ├─ MCP servers             │
│         └─ All tools               │
└─────────────────────────────────────┘
        │
        ├─ File system (Obsidian, local files)
        ├─ Web search + browser automation
        └─ Any MCP server in your Claude config
```

The key insight: ClaudeClaw uses `@anthropic-ai/claude-agent-sdk` to run the `claude` CLI as a subprocess, pointing it at your project directory so it loads `CLAUDE.md`. The `settingSources: ['project', 'user']` option means it also loads your user-level settings -- including every skill in `~/.claude/skills/`. The session ID is stored in SQLite and passed as `resume` on each call, so Claude Code carries context across messages without re-sending history.

---

## Prerequisites

1. Node.js 20 or later
2. Claude Code CLI installed and authenticated (`npm i -g @anthropic-ai/claude-code`, then `claude login`)
3. A Telegram account
4. A Telegram bot token from [@BotFather](https://t.me/botfather)
5. (Optional) A free Groq account for voice transcription
6. (Optional) An ElevenLabs account for voice responses

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/claudeclaw.git
cd claudeclaw

# 2. Install dependencies
npm install

# 3. Run the setup wizard
npm run setup

# 4. Edit CLAUDE.md to describe yourself and your skills
#    (this is the personality and context file -- make it yours)

# 5. Start ClaudeClaw
npm run dev
```

The setup wizard validates your bot token, walks you through getting your Telegram chat ID, configures voice keys if you want them, and offers to install a launchd service so it runs in the background automatically.

---

## Your Skills Work Automatically

This is the whole point. Any skill you have installed at `~/.claude/skills/` is available the moment ClaudeClaw starts -- because it runs the actual Claude Code CLI with your user settings loaded.

Send these directly to your bot:

```
/gmail check my inbox and summarize unread messages
/todo what's on my plate today
/linkedin-post write a post about the meeting I just had
/trend-pulse what's trending in AI agents this week
/agent-browser go to my Skool community and check DMs
/maestro run these five research tasks in parallel
```

Or just describe what you want in plain language. The `CLAUDE.md` file lists which skills exist and when to trigger them, so Claude invokes them automatically when relevant.

To add a new skill, drop it into `~/.claude/skills/` on your machine, add a line to the skills table in `CLAUDE.md`, and that's it. No restart needed for the next message.

---

## Setup Guide

### 1. Get a Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts to name your bot
4. Copy the token BotFather gives you

### 2. Run the Setup Wizard

```bash
npm run setup
```

The wizard:
- Checks your Node version and Claude CLI installation
- Validates your bot token against the Telegram API
- Walks you through getting your Telegram chat ID (start the bot, send `/chatid`)
- Asks for optional voice keys (Groq + ElevenLabs)
- Writes your `.env` file
- Offers to install a launchd background service on macOS

### 3. Configure Your Identity (CLAUDE.md)

`CLAUDE.md` is what makes ClaudeClaw yours instead of a generic bot. It's loaded by the Claude Code CLI on every session and defines the personality, context, and available tools.

Open it and fill in:

```markdown
# ClaudeClaw

You are [name], [your name]'s personal AI assistant, accessible via Telegram.

## Personality
[Describe how you want it to communicate. Direct? Casual? Formal?
What patterns should it never use? This shapes every response.]

## Who Is [Your Name]
[What you do, what context Claude needs to do useful work for you.
What projects are you running? What does your work actually look like?]

## Your Environment
- Obsidian vault: ~/path/to/your/vault
- This project lives at: ~/path/to/claudeclaw/

## Available Skills
| Skill         | Triggers                              |
|---------------|---------------------------------------|
| gmail         | emails, inbox, reply, send            |
| google-calendar | schedule, meeting, availability     |
| todo          | tasks, what's on my plate            |
| linkedin-post | LinkedIn post, write a post          |

## Message Format
[How should responses be formatted for Telegram?
Tight and readable? Long-form allowed? Voice note conventions?]
```

The more specific you are about who you are and what your environment looks like, the better it performs.

---

## Voice (Optional)

Voice requires two keys:

**Groq** (speech-to-text, free tier available):
```
GROQ_API_KEY=your_key_here
```
Get one at [console.groq.com](https://console.groq.com). Uses `whisper-large-v3`. The free tier handles real usage.

**ElevenLabs** (text-to-speech):
```
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id
```
Get one at [elevenlabs.io](https://elevenlabs.io). Clone your own voice and put the voice ID here.

Once configured:
- Send a Telegram voice note -- it gets transcribed and processed
- Run `/voice` in the chat to toggle spoken responses on or off
- When voice mode is on, Claude's responses come back as audio

---

## Scheduled Tasks

Tell Claude to create a task in natural language:

```
Every Monday at 9am, search for AI agent news from the past week and send me a summary

Every weekday at 8am, check my calendar and inbox and give me a briefing

First of every month, pull my Skool community stats and summarize engagement

Every 4 hours, check if any new consulting leads have come in via email
```

Claude creates the task by running:

```bash
node dist/schedule-cli.js create "PROMPT" "CRON"
```

The scheduler checks for due tasks every 60 seconds. When a task fires, it runs a fresh agent call and sends the result directly to your Telegram chat.

Manage tasks from the chat or directly:

```bash
node dist/schedule-cli.js list
node dist/schedule-cli.js pause <id>
node dist/schedule-cli.js resume <id>
node dist/schedule-cli.js delete <id>
```

**Cron reference:**

| Pattern | Meaning |
|---------|---------|
| `0 9 * * 1` | Every Monday at 9am |
| `0 8 * * 1-5` | Every weekday at 8am |
| `0 9 1 * *` | First of the month at 9am |
| `0 */4 * * *` | Every 4 hours |
| `0 18 * * 0` | Every Sunday at 6pm |

---

## Commands

| Command | What it does |
|---------|--------------|
| `/start` | Confirm the bot is online |
| `/chatid` | Get your Telegram chat ID (used during setup) |
| `/voice` | Toggle voice response mode on/off |
| `/memory` | Show recent memories stored for this chat |
| `/forget` | Clear the current session |
| `/newchat` | Start a fresh Claude Code session |
| `/gmail ...` | Invoke the gmail skill directly |
| `/todo ...` | Invoke the todo skill directly |
| Any text | Processed by Claude with full context |

Skill commands (any `/command` not in the list above) are passed through to Claude, which routes them to the matching skill.

---

## Other Channels

ClaudeClaw ships with Telegram. The pattern -- Claude Agent SDK as the core, a messaging channel on top, SQLite for state -- works across any channel.

**WhatsApp: [NanoClaw](https://github.com/qwibitai/nanoclaw)**
NanoClaw uses the same Agent SDK bridge for WhatsApp. Agents run in isolated Linux containers (Apple Container on macOS, Docker on Linux). Useful if you live in WhatsApp and want container-level isolation.

**Discord, Slack, and more: [OpenClaw](https://github.com/openclaw/openclaw)**
OpenClaw supports 10+ channels (Telegram, WhatsApp, Slack, Discord, iMessage, Signal, and more). More complexity, more channel adapters. See [Awesome OpenClaw](https://github.com/openclaw/awesome-openclaw) for the full ecosystem including hosting guides and the community.

**Minimal shell version: [TinyClaw](https://github.com/jlia0/tinyclaw)**
400 lines of shell, Claude Code + tmux. No Node, no dependencies.

The core idea in all of these is the same: the Claude Agent SDK spawns the `claude` subprocess with the right `cwd` and session options, and the channel is just the input/output layer. If you want to add another channel to ClaudeClaw, the `runAgent()` function in `src/agent.ts` is the only integration point you need.

---

## Running as a Background Service

### macOS (launchd)

The setup wizard handles this. To install manually:

```bash
# Copy the plist
cp claudeclaw.plist ~/Library/LaunchAgents/com.yourname.claudeclaw.plist

# Edit the plist to set correct paths for your machine
# Then load it
launchctl load ~/Library/LaunchAgents/com.yourname.claudeclaw.plist
```

Logs go to `/tmp/claudeclaw.log`:

```bash
tail -f /tmp/claudeclaw.log
```

### Linux (systemd)

Create `/etc/systemd/system/claudeclaw.service`:

```ini
[Unit]
Description=ClaudeClaw Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/claudeclaw
ExecStart=/usr/bin/node dist/index.js
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable claudeclaw
sudo systemctl start claudeclaw
sudo journalctl -u claudeclaw -f
```

### Windows (WSL2)

Use WSL2 and follow the Linux systemd steps above. Ensure your Claude Code auth (`~/.claude/`) is inside the WSL2 filesystem, not on the Windows mount.

---

## Memory System

ClaudeClaw uses three layers of context:

**1. Session resumption** -- Claude Code sessions persist across messages. The session ID is stored in SQLite and passed as `resume` to each agent call. Claude carries tool use history, context, and working memory without re-sending the full conversation.

**2. SQLite + FTS5 memory** -- Conversation turns are saved as memories with two sectors: `semantic` (things you say about yourself -- "I prefer", "remember", "I always") and `episodic` (general message content). Semantic memories decay slowly, episodic memories decay faster. Salience scores increase when a memory gets retrieved and decrease daily for memories that aren't accessed.

**3. Context injection** -- Before each message, a dual-layer search runs: FTS5 keyword search against your message (top 3 matches) plus the 5 most recently accessed memories. Results are prepended to the message as a `[Memory context]` block. The FTS5 index uses prefix matching so partial words still match.

Run `/memory` to see what's currently stored for your chat. Run `/forget` to clear the session and let memories decay naturally.

---

## Customizing Claudette

`CLAUDE.md` is the only file you need to touch to change behavior. The sections that matter most:

**Personality** -- Rules that apply to every response. Be specific. "No em dashes" is better than "be concise". "Don't narrate what you're about to do, just do it" changes behavior meaningfully.

**Who Is [You]** -- What you actually do. The more Claude knows about your work, the less you have to explain in each message. Include your projects, your workflow, what output you actually want.

**Environment** -- File paths that matter. Your Obsidian vault, your project directories, anything Claude should be able to find without being told.

**Available Skills** -- A table mapping skill names to natural language triggers. This is what teaches Claude to auto-invoke skills when you describe a task rather than explicitly calling them.

**Message Format** -- Telegram renders inconsistently. Tell Claude what you actually want: tight and readable, summary-first for long outputs, how to handle task lists.

Example personality rules that make a real difference:

```markdown
Rules you never break:
- No em dashes. Ever.
- No AI clichés. Never say "Certainly!", "Great question!", "I'd be happy to".
- Don't narrate what you're about to do. Just do it.
- If you don't know something, say so plainly.
- Match my energy -- if I'm casual, be casual back.
```

---

## Contributing

PRs welcome. Check the [issues](../../issues) for what's open.

If you build a skill that works well with ClaudeClaw, consider contributing it to the broader Claw ecosystem or opening an issue here so others can find it.

The `runAgent()` function in `src/agent.ts` is the integration seam for anyone adding a new channel or extending the agent behavior.

---

## License

MIT
