# Command Center -- Claude Code Setup Prompt

> Copy everything below this line and paste it into Claude Code while in your ClaudeClaw project directory.

---

I want you to build a Command Center dashboard for my ClaudeClaw deployment. This is a single-page HTML dashboard that shows live operational data from my ClaudeClaw system.

Before you start building, ask me these questions one at a time. Wait for my answer before asking the next one.

## Questions to ask me:

1. **Agent names**: What PM2 process names are you running? (Run `pm2 jlist | jq '.[].name'` if you're not sure. The default ClaudeClaw setup has `ea-claude` plus worker processes like `ea-claude-default`, `ea-claude-starscream`, etc.)

2. **Agent identities**: For each PM2 process, what display name and role do you want on the dashboard? For example: "Data / Coordinator", "Ravage / Coding", "Soundwave / Research". Give me a name and a short role description for each.

3. **Dashboard title**: What do you want to call your dashboard? Default is "Command Center". Your name/brand for the header?

4. **Accent color**: Pick a brand color. Default is coral/salmon (#E8735A). Other popular options: blue (#3B82F6), purple (#8B5CF6), green (#10B981), or give me a hex code.

5. **Which tabs do you want?**
   - **Agents** (recommended) -- shows your PM2 fleet, dispatch queue stats, scheduled tasks
   - **Operations** (recommended) -- service health, weekly progress chart, priority work list
   - **Memory/HLL** (optional) -- memory system stats, recent memories, extraction progress
   - **Strategy** (optional) -- idea evaluation history (requires christensen_log table)
   - **Pipeline** (optional) -- project pipeline items (requires pipeline_items table)

6. **Extra data sources**: Do you have other SQLite databases or services you want the dashboard to monitor? (Other project databases, external APIs, git repos for commit tracking?)

7. **Port**: What port should the dashboard HTTP server run on? Default is 8080. Make sure it's not already in use.

8. **Access**: Will you access this from the same machine (localhost) or from another device on your network? If another device, what's the IP address of the machine running ClaudeClaw? (I need this so I give you the right URL.)

## After I answer your questions, build these files:

### 1. `dashboard/index.html`

A self-contained HTML file with:
- Inline CSS (no external stylesheets beyond Google Fonts)
- Chart.js loaded from CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`
- Fonts: Inter (body) + JetBrains Mono (stats/monospace)
- Tab navigation with URL hash support
- Auto-refresh every 30 seconds
- Live/stale/error indicator based on report age
- Responsive grid (3-col on desktop, 2-col on tablet, 1-col on mobile)
- Collapsible section cards
- Clean, minimal design using the accent color I chose

**Agents tab should include:**
- Summary stat cards (fleet size, online count, total queue depth, total completed 24h)
- Agent cards in a grid: status dot, name, role, avatar image (from `media/avatars/{agent_id}.webp`), efficiency donut chart, stats line (uptime | memory | queue count)
- Dispatch queue table (per worker: queued, running, done 24h, failed 24h, avg time)
- Scheduled tasks list

**Operations tab should include:**
- Summary stat cards (commits this week, open items, needs attention, services online)
- Service health section with status dots
- Weekly progress chart (Chart.js line chart from timeline.json)
- Priority work list (drag to reorder, checkboxes, saves to localStorage)
- Any additional sections from the report's `sections` object

**Memory tab (if selected) should include:**
- Memory count stat cards (total, semantic, episodic)
- Extraction progress bar
- Recent memories list (collapsible items with salience scores)
- Session stats (total turns, tokens per turn)

**Strategy tab (if selected) should include:**
- Summary stats (total evals, pass%, fail%, override%)
- Evaluation history (expandable cards with idea, outcome, reasoning, date)

### 2. `dashboard/generate_report.py`

A Python 3.11+ script that:
- Queries `pm2 jlist` for process status
- Queries my ClaudeClaw SQLite database for:
  - dispatch_queue stats (per worker_type: queued, running, completed 24h, failed 24h, avg duration)
  - scheduled_tasks list
  - token_usage summary (if Operations tab selected)
  - memories stats and recent entries (if Memory tab selected)
  - christensen_log entries (if Strategy tab selected)
  - pipeline_items (if Pipeline tab selected)
  - conversation_log stats (turn counts, session stats)
- Checks service health (PM2 processes, HTTP ports)
- Checks git repos for commit counts (if I listed any)
- Writes `dashboard/reports/latest.json`
- Optionally appends to `dashboard/reports/timeline.json` for the progress chart
- Uses my agent mapping (PM2 name -> agent_id + role)
- Has proper error handling (missing DB = skip, missing PM2 = skip, timeout = skip)
- Runs standalone: `python3 dashboard/generate_report.py`

Use these path constants at the top (I'll adjust them):
```python
CLAUDECLAW_DB = Path("store/claudeclaw.db")  # relative to project root
DASHBOARD_DIR = Path(__file__).parent
REPORTS_DIR = DASHBOARD_DIR / "reports"
```

### 3. Update `ecosystem.config.cjs`

Add a PM2 app entry for the HTTP server:
```javascript
{
  name: 'my-dashboard',
  script: 'python3',
  args: '-m http.server PORT --bind 0.0.0.0',
  cwd: __dirname + '/dashboard',
  interpreter: 'none',
  restart_delay: 3000,
  max_restarts: 10,
  min_uptime: 30000,
}
```

Use the port I specified.

### 4. Create directories

```bash
mkdir -p dashboard/reports dashboard/media/avatars
```

### 5. Test it

After generating the files:
1. Run the report generator once: `python3 dashboard/generate_report.py`
2. Verify `dashboard/reports/latest.json` was created
3. Start the HTTP server: `pm2 start ecosystem.config.cjs --only my-dashboard`
4. Tell me the URL to open in my browser

## Design requirements:

- The HTML must be a SINGLE FILE. All CSS inline in a `<style>` block. All JS inline in a `<script>` block.
- No build tools, no npm packages for the dashboard itself.
- Use CSS custom properties (`:root` variables) for all colors so the theme is easy to change later.
- Agent cards should be compact: 8px padding, 3px left border (color = status), 12px name font, 10px role/stats font.
- Status dots: 6px circles. Green = online, red = stopped, yellow = errored.
- Efficiency donut charts: 56px SVG with percentage label in the center.
- Cards should have subtle shadows and rounded corners (border-radius: 8-12px).
- The overall feel should be clean and professional -- think Vercel/Linear dashboard, not Bootstrap.
- Mobile-friendly: everything must work on a phone screen.

## What NOT to do:

- Don't hardcode any paths, agent names, or project names that are specific to someone else's setup. Use only what I tell you.
- Don't add authentication. This is a LAN-only dashboard.
- Don't use any Python web framework (Flask, FastAPI, etc.) for the dashboard server. Just `python3 -m http.server`.
- Don't create a backend API. The dashboard reads static JSON files, period.
- Don't install any Python packages. Use only stdlib (json, sqlite3, subprocess, pathlib, datetime).
