#!/usr/bin/env python3
"""
Watchdog Agent - L5 Observation Layer
Monitors all ecosystem services and alerts on state transitions.
Standalone Python, zero external deps, runs on cron every 15 minutes.

Checks:
  1. PM2 processes (ea-claude, workers)
  2. Systemd services (metroplex)
  3. Dashboard HTTP server (port 8080)
  4. Dashboard report freshness (latest.json mtime)
  5. Metroplex spin detection (same patch re-processed)
  6. Cron pipeline health (research-agents, ideaforge logs)
  7. Disk usage (partitions > 90%)
  8. Dispatch queue stuck tasks

Alert throttling: same condition won't re-alert within 2 hours.

Cron:
  */15 * * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/watchdog.py >> /tmp/watchdog.log 2>&1
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# Paths
PROJECTS_DIR = Path("/home/apexaipc/projects")
STORE_DIR = PROJECTS_DIR / "claudeclaw" / "store"
STATE_FILE = STORE_DIR / "watchdog_state.json"
LATEST_JSON = PROJECTS_DIR / "claudeclaw" / "dashboard" / "reports" / "latest.json"
METROPLEX_DB = PROJECTS_DIR / "metroplex" / "data" / "metroplex.db"
CLAUDECLAW_DB = STORE_DIR / "claudeclaw.db"
ENV_FILE = Path(os.path.expanduser("~/.env.shared"))

# Throttle: don't re-alert same condition within this many seconds
THROTTLE_SECONDS = 7200  # 2 hours

# Cron log paths to check freshness
CRON_LOGS = {
    "research-agents": Path("/var/log/research-agents/pipeline.log"),
    "ideaforge": Path("/var/log/ideaforge/pipeline.log"),
}
CRON_MAX_AGE_HOURS = 26  # Alert if log older than 26h


def run(cmd: str, timeout: int = 10) -> str:
    """Run a shell command, return stdout or empty string."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def load_env() -> tuple[str, str]:
    """Load Telegram credentials from ~/.env.shared."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        return token, chat_id

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key == "TELEGRAM_BOT_TOKEN":
                token = val
            elif key == "TELEGRAM_CHAT_ID":
                chat_id = val
    return token, chat_id


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send Telegram message. Returns True on success."""
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    """Load last-alert timestamps from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"alerts": {}}


def save_state(state: dict):
    """Save state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def should_alert(state: dict, key: str) -> bool:
    """Check if we should alert for this condition (throttle check)."""
    alerts = state.get("alerts", {})
    last = alerts.get(key, 0)
    now = datetime.now().timestamp()
    return (now - last) > THROTTLE_SECONDS


def record_alert(state: dict, key: str):
    """Record that we alerted for this condition."""
    if "alerts" not in state:
        state["alerts"] = {}
    state["alerts"][key] = datetime.now().timestamp()


def clear_alert(state: dict, key: str):
    """Clear alert state when condition resolves."""
    if "alerts" in state and key in state["alerts"]:
        del state["alerts"][key]


# --- Checks ---

def check_pm2() -> list[dict]:
    """Check PM2 processes."""
    issues = []
    pm2_out = run("pm2 jlist 2>/dev/null")
    if not pm2_out:
        issues.append({"key": "pm2_down", "msg": "PM2 not responding or no processes", "level": "error"})
        return issues

    try:
        procs = json.loads(pm2_out)
    except json.JSONDecodeError:
        issues.append({"key": "pm2_parse", "msg": "PM2 output not valid JSON", "level": "error"})
        return issues

    proc_map = {p.get("name", ""): p.get("pm2_env", {}).get("status", "unknown") for p in procs}

    # Check ea-claude
    ea_status = proc_map.get("ea-claude", "not found")
    if ea_status != "online":
        issues.append({"key": "ea_claude_down", "msg": f"ea-claude: {ea_status}", "level": "error"})

    # Check workers (if they exist)
    for name in ["ea-claude-default", "ea-claude-starscream"]:
        if name in proc_map and proc_map[name] != "online":
            issues.append({"key": f"{name}_down", "msg": f"{name}: {proc_map[name]}", "level": "warning"})

    return issues


def check_metroplex() -> list[dict]:
    """Check Metroplex systemd service."""
    issues = []
    status = run("systemctl --user is-active metroplex 2>/dev/null")
    if status != "active":
        issues.append({"key": "metroplex_down", "msg": f"Metroplex service: {status or 'unknown'}", "level": "error"})
    return issues


def check_dashboard() -> list[dict]:
    """Check dashboard HTTP server and report freshness."""
    issues = []

    # Port 8080
    port_check = run("lsof -i :8080 -t 2>/dev/null")
    if not port_check:
        issues.append({"key": "dashboard_port", "msg": "Dashboard HTTP (port 8080) not responding", "level": "error"})

    # Report freshness
    if LATEST_JSON.exists():
        mtime = LATEST_JSON.stat().st_mtime
        age_min = (datetime.now().timestamp() - mtime) / 60
        if age_min > 35:
            issues.append({
                "key": "report_stale",
                "msg": f"Dashboard report is {age_min:.0f}min old (should refresh every 30min)",
                "level": "warning"
            })
    else:
        issues.append({"key": "report_missing", "msg": "latest.json does not exist", "level": "error"})

    return issues


def check_spin_detection() -> list[dict]:
    """Check for Metroplex spin loops (same patch re-processed many times)."""
    issues = []
    if not METROPLEX_DB.exists():
        return issues

    try:
        db = sqlite3.connect(str(METROPLEX_DB))
        cursor = db.cursor()

        # Check if patch_applications table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patch_applications'")
        if not cursor.fetchone():
            db.close()
            return issues

        # Count recent repeated patch applications (last 50)
        cursor.execute("""
            SELECT patch_id, status, COUNT(*) as cnt
            FROM patch_applications
            GROUP BY patch_id, status
            HAVING cnt > 5
            ORDER BY cnt DESC
            LIMIT 3
        """)
        for row in cursor.fetchall():
            patch_id, status, cnt = row
            if status == "skipped" and cnt > 10:
                issues.append({
                    "key": f"spin_{patch_id}",
                    "msg": f"Patch {patch_id} processed {cnt}x (status: {status}) - possible spin loop",
                    "level": "warning"
                })
        db.close()
    except Exception as e:
        issues.append({"key": "metroplex_db_error", "msg": f"Metroplex DB check failed: {str(e)[:80]}", "level": "warning"})

    return issues


def check_cron_health() -> list[dict]:
    """Check cron pipeline log freshness."""
    issues = []
    for name, log_path in CRON_LOGS.items():
        if log_path.exists():
            mtime = log_path.stat().st_mtime
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            if age_hours > CRON_MAX_AGE_HOURS:
                issues.append({
                    "key": f"cron_{name}_stale",
                    "msg": f"{name} log is {age_hours:.0f}h old (expected daily)",
                    "level": "warning"
                })
        # Don't alert if log doesn't exist -- cron may not be set up yet
    return issues


def check_disk() -> list[dict]:
    """Check disk usage."""
    issues = []
    try:
        usage = shutil.disk_usage("/")
        pct = (usage.used / usage.total) * 100
        if pct > 90:
            issues.append({
                "key": "disk_root",
                "msg": f"Root partition at {pct:.1f}% ({usage.free // (1024**3)}GB free)",
                "level": "error" if pct > 95 else "warning"
            })
        # Also check /home if it's a separate partition
        home_usage = shutil.disk_usage("/home")
        if home_usage.total != usage.total:
            home_pct = (home_usage.used / home_usage.total) * 100
            if home_pct > 90:
                issues.append({
                    "key": "disk_home",
                    "msg": f"/home at {home_pct:.1f}% ({home_usage.free // (1024**3)}GB free)",
                    "level": "error" if home_pct > 95 else "warning"
                })
    except Exception:
        pass
    return issues


def check_dispatch_queue() -> list[dict]:
    """Check for stuck tasks in dispatch queue."""
    issues = []
    if not CLAUDECLAW_DB.exists():
        return issues

    try:
        db = sqlite3.connect(str(CLAUDECLAW_DB))
        cursor = db.cursor()

        # Check if dispatch_queue table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dispatch_queue'")
        if not cursor.fetchone():
            db.close()
            return issues

        # Find tasks stuck in 'running' for > 10 minutes
        cursor.execute("""
            SELECT id, worker_type, prompt, claimed_at
            FROM dispatch_queue
            WHERE status = 'running'
            AND claimed_at IS NOT NULL
            AND (strftime('%s', 'now') - strftime('%s', claimed_at)) > 600
        """)
        for row in cursor.fetchall():
            task_id, worker_type, prompt, claimed_at = row
            issues.append({
                "key": f"dispatch_stuck_{task_id}",
                "msg": f"Dispatch task {task_id} ({worker_type}) stuck running since {claimed_at}",
                "level": "warning"
            })

        db.close()
    except Exception as e:
        # Don't fail watchdog over dispatch DB issues
        pass

    return issues


def check_stale_cycle() -> list[dict]:
    """Check if Metroplex is active but hasn't completed a cycle recently."""
    issues = []
    if not METROPLEX_DB.exists():
        return issues

    # Only check if Metroplex service is active
    status = run("systemctl --user is-active metroplex 2>/dev/null")
    if status != "active":
        return issues

    try:
        db = sqlite3.connect(str(METROPLEX_DB))
        cursor = db.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cycles'")
        if not cursor.fetchone():
            db.close()
            return issues

        cursor.execute("SELECT MAX(completed_at) FROM cycles")
        row = cursor.fetchone()
        if row and row[0]:
            last_cycle = datetime.fromisoformat(row[0])
            hours_ago = (datetime.now() - last_cycle).total_seconds() / 3600
            if hours_ago > 2:
                issues.append({
                    "key": "metroplex_stale_cycle",
                    "msg": f"Metroplex active but last cycle was {hours_ago:.1f}h ago",
                    "level": "warning"
                })
        db.close()
    except Exception:
        pass

    return issues


def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    now = datetime.now()
    state = load_state()

    # Run all checks
    all_issues = []
    all_issues.extend(check_pm2())
    all_issues.extend(check_metroplex())
    all_issues.extend(check_dashboard())
    all_issues.extend(check_spin_detection())
    all_issues.extend(check_stale_cycle())
    all_issues.extend(check_cron_health())
    all_issues.extend(check_disk())
    all_issues.extend(check_dispatch_queue())

    # Filter to only new/unthrottled alerts
    new_alerts = []
    for issue in all_issues:
        key = issue["key"]
        if force or should_alert(state, key):
            new_alerts.append(issue)
            if not dry_run:
                record_alert(state, key)

    # Clear alerts for conditions that resolved
    active_keys = {i["key"] for i in all_issues}
    for key in list(state.get("alerts", {}).keys()):
        if key not in active_keys:
            clear_alert(state, key)

    # Save state
    if not dry_run:
        state["last_run"] = now.isoformat()
        state["issues_found"] = len(all_issues)
        state["alerts_sent"] = len(new_alerts)
        save_state(state)

    # Log summary
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}[{now.isoformat()}] Watchdog: {len(all_issues)} issues, {len(new_alerts)} new alerts")
    for issue in all_issues:
        print(f"  [{issue['level']}] {issue['msg']}")

    if dry_run:
        if new_alerts:
            print(f"\n{len(new_alerts)} alerts would be sent:")
            for a in new_alerts:
                print(f"  -> {a['msg']}")
        return

    # Send alerts if any
    if new_alerts:
        token, chat_id = load_env()
        if not token or not chat_id:
            print("No Telegram credentials - can't send alerts", file=sys.stderr)
            return

        # Group by level
        errors = [a for a in new_alerts if a["level"] == "error"]
        warnings = [a for a in new_alerts if a["level"] == "warning"]

        lines = [f"<b>Watchdog Alert</b> ({now.strftime('%H:%M')})"]
        if errors:
            lines.append("")
            for a in errors:
                lines.append(f"!! {a['msg']}")
        if warnings:
            lines.append("")
            for a in warnings:
                lines.append(f"! {a['msg']}")

        message = "\n".join(lines)
        if len(message) > 4000:
            message = message[:3997] + "..."

        send_telegram(token, chat_id, message)


if __name__ == "__main__":
    main()
