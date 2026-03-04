# Command Center Dashboard -- Setup Guide

> A live operational dashboard for your ClaudeClaw deployment. Shows your agents, dispatch queue, memory system, scheduled tasks, and whatever else you want to track -- all in one browser tab.

---

## What You're Building

The Command Center is a single-page web dashboard served from your ClaudeClaw machine. It reads live data from your ClaudeClaw SQLite database and PM2 processes, generates a JSON report, and renders it as a multi-tab HTML dashboard.

**What it looks like:**

- **Agents tab** -- shows each PM2 process (your workers), their status, uptime, memory usage, queue depth, and an efficiency donut chart per agent
- **Operations tab** -- summary stats (commits, open items, blockers, services online), a weekly progress chart, service health checks, and a drag-to-reorder work priority list
- **Soundwave / HLL tab** -- memory system stats (extraction coverage, growth rate), recent memories, decision log, session stats
- **Strategy tab** -- idea evaluation history, pass/fail/override breakdown, focus rate tracking

You don't need all four tabs. Most people start with Agents + Operations and add the rest later.

**How it works:**

```
[Python report generator]  -->  reports/latest.json  -->  [HTML dashboard reads JSON]
       |                                                        |
  Queries PM2, SQLite DB                              Served via Python HTTP server
  Runs on a schedule (cron/PM2)                       Accessed from any browser on LAN
```

---

## Prerequisites

You need:

1. **ClaudeClaw running** -- the Telegram bot, with its SQLite database at `store/claudeclaw.db`
2. **PM2 installed** -- `npm install -g pm2` (you probably already have this)
3. **Python 3.11+** -- for the report generator and HTTP server
4. **Node 20+** -- you already have this if ClaudeClaw is running

---

## Step 1: Create the Dashboard Directory

Inside your ClaudeClaw project root, create:

```
your-claudeclaw/
  dashboard/
    index.html          <-- the dashboard UI
    generate_report.py  <-- the report generator
    reports/            <-- where JSON reports get written
    media/
      avatars/          <-- agent avatar images (optional)
```

```bash
cd /path/to/your/claudeclaw
mkdir -p dashboard/reports dashboard/media/avatars
```

---

## Step 2: Generate Your Dashboard with Claude Code

The easiest way to get your Command Center running is to give Claude Code the prompt from **PROMPT.md** (included in this guide). That prompt will:

1. Ask you a few questions about your setup (agent names, what tabs you want, what projects you track)
2. Generate a customized `dashboard/index.html`
3. Generate a customized `dashboard/generate_report.py`
4. Set up the PM2 HTTP server entry
5. Test everything

**To use it:**

```
1. Open Claude Code in your ClaudeClaw project directory
2. Paste the contents of PROMPT.md
3. Answer the questions it asks
4. Review and approve the generated files
```

If you'd rather build it by hand, read on.

---

## Step 3: The Report Generator (generate_report.py)

This is the brain of the dashboard. It's a Python script that:

- Queries `pm2 jlist` for process status
- Queries your ClaudeClaw SQLite database for dispatch queue stats, token usage, memories, scheduled tasks
- Optionally checks other data sources (other project databases, git repos, services)
- Writes a JSON file to `dashboard/reports/latest.json`

### What you need to customize

**Agent mapping** -- Tell it which PM2 process names map to which agent identities:

```python
PM2_TO_AGENT = {
    "ea-claude": {"agent_id": "main", "role": "Coordinator"},
    "ea-claude-default": {"agent_id": "worker-1", "role": "General Worker"},
    # Add your workers here. Match the PM2 app names from your ecosystem.config.cjs
}
```

**Database path** -- Point it at your ClaudeClaw database:

```python
CLAUDECLAW_DB = Path("/path/to/your/claudeclaw/store/claudeclaw.db")
```

**Service health checks** -- Define what services to monitor:

```python
SERVICES = {
    "ClaudeClaw (Main)": {"check": "pm2", "name": "ea-claude"},
    "Dashboard HTTP": {"check": "port", "port": 8080},
    # Add your own services here
}
```

**Project tracking** (optional) -- If you want git commit stats:

```python
GIT_PROJECTS = ["claudeclaw", "my-other-project"]
```

### Core functions the report generator needs

At minimum, your report generator should produce JSON like this:

```json
{
  "timestamp": "2026-03-02T15:00:00",
  "tabs": {
    "agents": {
      "pm2_processes": [...],
      "queue_stats": {...},
      "scheduled_tasks": [...]
    },
    "operations": {
      "service_health": [...],
      "commits_this_week": 0,
      "open_items": 0
    }
  },
  "sections": {
    "service_health": { "title": "Service Health", "items": [...] },
    "pipeline": { "title": "Pipeline Status", "items": [...] }
  }
}
```

Each `item` in a section follows this shape:

```json
{
  "text": "Short title",
  "detail": "Longer description (shown on expand)",
  "status": "ok | warning | error | info"
}
```

---

## Step 4: The Dashboard HTML (index.html)

The HTML file is a self-contained single-page app. No build step, no bundler. It uses:

- **Chart.js** (loaded from CDN) for donut charts and timeline graphs
- **Inter + JetBrains Mono** fonts (loaded from Google Fonts)
- **Pure CSS** for the layout, cards, tabs, and responsive grid
- **Vanilla JavaScript** for data loading and rendering

### How it works

1. On load, fetches `reports/latest.json` (and optionally `reports/timeline.json`)
2. Parses the JSON and dispatches to per-tab render functions
3. Auto-refreshes every 30 seconds
4. Shows a live/stale/error indicator based on report age

### Key customization points

**Tabs** -- The tab bar is just HTML buttons. Remove tabs you don't want:

```html
<nav class="tab-bar">
  <button class="tab-btn active" data-tab="overview">Agents</button>
  <button class="tab-btn" data-tab="operations">Operations</button>
  <!-- Remove or add tabs as needed -->
</nav>
```

**Color scheme** -- All colors are CSS variables at the top of the `<style>` block:

```css
:root {
  --bg: #FAFBFC;        /* Page background */
  --card: #FFFFFF;       /* Card background */
  --accent: #E8735A;     /* Brand color (salmon/coral) */
  --ok: #10B981;         /* Green (healthy) */
  --warning: #F59E0B;    /* Yellow (needs attention) */
  --error: #EF4444;      /* Red (broken) */
  --info: #6366F1;       /* Purple (informational) */
}
```

Change `--accent` to match your brand. Everything else follows from it.

**Title** -- In the header:

```html
<h1><span>EAC</span> Command Center</h1>
```

Change "EAC" and "Command Center" to whatever you want.

**Agent cards** -- The agent grid renders from the `pm2_processes` array in your report JSON. Each agent gets:
- A status dot (green/red/yellow)
- Name and role
- An optional avatar image (from `media/avatars/`)
- An efficiency donut chart
- Stats line: uptime, memory, queue count

**Agent avatars** -- Drop images into `dashboard/media/avatars/` named `{agent_id}.webp` (or `.png`). The dashboard looks for them at `media/avatars/{agent_id}.webp`. If missing, it shows a default icon.

---

## Step 5: Serve It

Add an entry to your `ecosystem.config.cjs` (or create one) to serve the dashboard:

```javascript
{
  name: 'my-dashboard',
  script: 'python3',
  args: '-m http.server 8080 --bind 0.0.0.0',
  cwd: __dirname + '/dashboard',
  interpreter: 'none',
  restart_delay: 3000,
  max_restarts: 10,
  min_uptime: 30000,
}
```

Then:

```bash
pm2 start ecosystem.config.cjs
```

Access from any browser on your network at `http://YOUR_IP:8080/`

---

## Step 6: Schedule Report Generation

The dashboard needs `reports/latest.json` to be fresh. You have two options:

### Option A: Cron job (simplest)

```bash
# Run every 5 minutes
crontab -e
# Add:
*/5 * * * * cd /path/to/your/claudeclaw && python3 dashboard/generate_report.py
```

### Option B: PM2 cron

Add another PM2 app that runs the generator on an interval:

```javascript
{
  name: 'report-generator',
  script: 'python3',
  args: 'dashboard/generate_report.py',
  cwd: __dirname,
  interpreter: 'none',
  cron_restart: '*/5 * * * *',
  autorestart: false,
}
```

### Option C: Scheduled task in ClaudeClaw

Tell your bot: "Every 5 minutes, run the dashboard report generator"

It will create a scheduled task that runs `python3 dashboard/generate_report.py` on a cron.

---

## Step 7: Customize Your Tabs

### Tab: Agents (recommended for everyone)

Shows your PM2 fleet. Requires:
- `pm2 jlist` access
- `dispatch_queue` table in your ClaudeClaw DB (comes standard)

### Tab: Operations (recommended)

Shows service health, commit stats, and a priority work list. Requires:
- Service health check definitions in generate_report.py
- Optional: git repos to count commits from

### Tab: Memory / HLL (optional)

Shows your memory system stats. Requires:
- `memories` table in your ClaudeClaw DB (comes standard)
- `conversation_log` table (comes standard)
- `token_usage` table (comes standard)

Useful if you use the memory system heavily and want visibility into what's being stored, extraction coverage, and salience scores.

### Tab: Strategy (optional)

Shows idea evaluation history (Christensen filter). Requires:
- `christensen_log` table in your ClaudeClaw DB
- Only useful if you've set up the Christensen filter in your CLAUDE.md

### Tab: Pipeline (optional)

Shows project pipeline items. Requires:
- `pipeline_items` table in your ClaudeClaw DB
- Only useful if you track work items through a pipeline

### Adding your own tab

1. Add a `<button>` to the tab bar with a unique `data-tab` value
2. Add a `<div class="tab-content" id="tab-yourtab">` with your HTML
3. Add a `renderYourTab()` function in the `<script>` block
4. Have your report generator produce the data your tab needs in `latest.json`

---

## The Data Your ClaudeClaw DB Already Has

If you're running standard ClaudeClaw, your SQLite database at `store/claudeclaw.db` already has these tables that the dashboard can read:

| Table | What it holds | Dashboard use |
|-------|--------------|---------------|
| `dispatch_queue` | Async task queue (queued/running/completed/failed) | Agent queue stats, completed counts, avg duration |
| `scheduled_tasks` | Cron-based scheduled tasks | Scheduled tasks list |
| `token_usage` | API token tracking (input/output/cache, cost) | Token spend stats, cost tracking |
| `memories` | Conversation memory with FTS5 | Memory count, recent memories, salience stats |
| `conversation_log` | Full conversation history | Turn counts, session stats |
| `sessions` | Chat ID to session ID mapping | Session tracking |
| `christensen_log` | Idea evaluations | Strategy tab (if you use it) |
| `pipeline_items` | Work items | Pipeline tab (if you use it) |

You don't need external databases. The dashboard can be fully powered by what ClaudeClaw already stores.

---

## Common Customization Questions

### "I only have 1 worker, not 5"

That's fine. Most people start with just the main bot (`ea-claude`) and maybe one worker. The agent grid scales to whatever you have. Just update `PM2_TO_AGENT` in the report generator to match your actual PM2 apps.

### "I don't use PM2"

If you run ClaudeClaw with `npm run dev` or `systemd` instead of PM2:
- Skip the PM2 process status section
- The report generator can still query your SQLite DB
- Replace `pm2 jlist` with whatever process monitoring you have (or skip the agent grid)

### "I want dark mode"

Change the CSS variables:

```css
:root {
  --bg: #0F172A;
  --card: #1E293B;
  --text: #F1F5F9;
  --text-secondary: #94A3B8;
  --border: #334155;
}
```

### "I want it accessible from the internet"

Don't expose port 8080 directly. Use a reverse proxy (nginx, Caddy) with HTTPS and basic auth. The dashboard has no built-in authentication.

### "Can I run the report generator from a different machine?"

Yes, but it needs:
- SSH access to run `pm2 jlist` on the ClaudeClaw host
- Access to the SQLite database file
- Write access to the `dashboard/reports/` directory

Simplest approach: run everything on the same machine.

---

## File Reference

| File | Purpose | Customize? |
|------|---------|------------|
| `dashboard/index.html` | Dashboard UI | Yes -- tabs, colors, title, agent card layout |
| `dashboard/generate_report.py` | Report generator | Yes -- agent mapping, DB path, services, projects |
| `dashboard/reports/latest.json` | Generated report (auto) | No -- generated file |
| `dashboard/reports/timeline.json` | Historical timeline (auto) | No -- generated file |
| `dashboard/media/avatars/*.webp` | Agent avatar images | Yes -- your own images |
| `ecosystem.config.cjs` | PM2 config | Yes -- add dashboard HTTP server entry |

---

## Troubleshooting

**Dashboard shows "connecting..." forever**
- Check that `reports/latest.json` exists: `ls dashboard/reports/latest.json`
- Run the report generator manually: `python3 dashboard/generate_report.py`
- Check the HTTP server is running: `curl http://localhost:8080/reports/latest.json`

**"stale" indicator (yellow)**
- The report is older than 2 minutes. Your cron/PM2 report generator may have stopped.
- Check: `pm2 logs report-generator` or `cat /var/log/syslog | grep generate_report`

**Agent cards show "unknown" status**
- PM2 process names in your report generator don't match your `ecosystem.config.cjs`
- Run `pm2 jlist | jq '.[].name'` to see actual process names

**Charts not rendering**
- Check browser console for Chart.js errors
- Ensure CDN is reachable: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`

**Database locked errors in report generator**
- SQLite can lock during writes. The generator uses `timeout=5` to wait.
- If persistent, check for long-running queries from other processes.
