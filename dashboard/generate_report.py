#!/usr/bin/env python3
"""
Dashboard Report Generator
Produces structured JSON from live system state for the Data Dashboard.
Called by scheduled tasks (morning 0800, evening 1600).

Usage:
  python3 generate_report.py              # Generates report + updates latest.json
  python3 generate_report.py --type morning
  python3 generate_report.py --type evening
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path("/home/apexaipc/projects")
DASHBOARD_DIR = Path(__file__).parent
REPORTS_DIR = DASHBOARD_DIR / "reports"
PIPELINE_FILE = PROJECTS_DIR / "claudeclaw" / "PIPELINE.md"
TIMELINE_FILE = REPORTS_DIR / "timeline.json"

# Projects to check for git status
GIT_PROJECTS = [
    "claudeclaw", "ultra-magnus", "yce-harness", "metroplex",
    "ideaforge", "research-agents", "st-factory", "perceptor",
    "sky-lynx", "gen-ui-dashboard",
]

# Services to health-check
SERVICES = {
    "EA-Claude (Data)": {"check": "pm2", "name": "ea-claude"},
    "Metroplex": {"check": "systemd", "name": "metroplex"},
    "HTTP Server": {"check": "port", "port": 8080},
}


def run(cmd, timeout=10):
    """Run a shell command, return stdout or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def check_service_health():
    """Check all monitored services."""
    items = []

    # PM2 processes
    pm2_out = run("pm2 jlist 2>/dev/null")
    pm2_procs = {}
    if pm2_out:
        try:
            for proc in json.loads(pm2_out):
                pm2_procs[proc.get("name", "")] = proc.get("pm2_env", {}).get("status", "unknown")
        except json.JSONDecodeError:
            pass

    # Systemd services
    def systemd_status(name):
        out = run(f"systemctl is-active {name} 2>/dev/null")
        return out.strip()

    # Port checks
    def port_open(port):
        out = run(f"lsof -i :{port} -t 2>/dev/null")
        return bool(out.strip())

    for label, cfg in SERVICES.items():
        if cfg["check"] == "pm2":
            status_str = pm2_procs.get(cfg["name"], "not found")
            if status_str == "online":
                items.append({"text": label, "detail": "Running via pm2", "status": "ok"})
            elif status_str == "not found":
                items.append({"text": label, "detail": "Not found in pm2 process list", "status": "error"})
            else:
                items.append({"text": label, "detail": f"Status: {status_str}", "status": "warning"})

        elif cfg["check"] == "systemd":
            st = systemd_status(cfg["name"])
            if st == "active":
                items.append({"text": label, "detail": "systemd service active", "status": "ok"})
            elif st == "inactive":
                items.append({"text": label, "detail": "systemd service inactive", "status": "warning"})
            else:
                items.append({"text": label, "detail": f"systemd status: {st}", "status": "error"})

        elif cfg["check"] == "port":
            if port_open(cfg["port"]):
                items.append({"text": label, "detail": f"Listening on port {cfg['port']}", "status": "ok"})
            else:
                items.append({"text": label, "detail": f"Nothing on port {cfg['port']}", "status": "error"})

    # Cron checks
    cron_out = run("crontab -l 2>/dev/null")
    if "research" in cron_out.lower():
        items.append({"text": "Research Agents (cron)", "detail": "Cron entry found", "status": "ok"})
    else:
        items.append({"text": "Research Agents (cron)", "detail": "No cron entry found", "status": "warning"})

    if "sky-lynx" in cron_out.lower() or "sky_lynx" in cron_out.lower():
        items.append({"text": "Sky-Lynx (cron)", "detail": "Cron entry found", "status": "ok"})
    else:
        items.append({"text": "Sky-Lynx (cron)", "detail": "No cron entry found", "status": "warning"})

    return {"title": "Service Health", "items": items}


def check_pipeline():
    """Parse PIPELINE.md for active tasks and their status."""
    items = []
    if not PIPELINE_FILE.exists():
        return {"title": "Pipeline Status", "items": [{"text": "PIPELINE.md not found", "detail": "", "status": "error"}]}

    content = PIPELINE_FILE.read_text()
    lines = content.split("\n")

    current_section = ""
    for line in lines:
        stripped = line.strip()

        # Track section headers
        if stripped.startswith("## PRIORITY"):
            current_section = stripped
        elif stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            current_section = stripped

        # Skip closed/parked sections
        if "PARKED" in current_section or "CLOSED" in current_section:
            continue

        # Grab checkbox items
        if stripped.startswith("- [x]"):
            task = stripped[6:].strip()
            # Only include recently completed (skip if too old)
            items.append({"text": task[:80], "detail": current_section, "status": "ok"})
        elif stripped.startswith("- [ ]"):
            task = stripped[6:].strip()
            items.append({"text": task[:80], "detail": current_section, "status": "warning"})

    # Pipeline view: recent completions + high-priority open items only
    open_items = [i for i in items if i["status"] != "ok"]
    recent_done = [i for i in items if i["status"] == "ok"][-3:]

    # Limit open to P1/P2 only (skip P3 detail -- that goes in Unfinished)
    p1_p2_open = [i for i in open_items if "PRIORITY 1" in i["detail"] or "PRIORITY 2" in i["detail"]]
    p3_summary = len([i for i in open_items if "PRIORITY 3" in i["detail"] or "continued" in i["detail"]])

    result_items = recent_done + p1_p2_open
    if p3_summary > 0:
        result_items.append({"text": f"{p3_summary} items in Priority 3 pipeline", "detail": "See Unfinished Business section", "status": "info"})

    return {"title": "Pipeline Status", "items": result_items}


def check_activity():
    """Check recent git activity across projects."""
    items = []
    cutoff = datetime.now() - timedelta(days=7)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    for proj in GIT_PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not (proj_dir / ".git").exists():
            continue

        # Get last commit
        log = run(f"git -C {proj_dir} log -1 --format='%h|%s|%ar' 2>/dev/null")
        if not log:
            continue

        parts = log.split("|", 2)
        if len(parts) == 3:
            sha, msg, ago = parts
            # Count commits this week
            count = run(f"git -C {proj_dir} rev-list --count --since='{cutoff_str}' HEAD 2>/dev/null")
            count = count if count else "0"

            status = "ok" if int(count) > 0 else "info"
            items.append({
                "text": f"{proj}: {msg[:50]}",
                "detail": f"{sha} ({ago}) -- {count} commits this week",
                "status": status
            })

    items.sort(key=lambda x: x["status"] != "ok")
    return {"title": "Recent Activity", "items": items}


def check_uncommitted():
    """Check for uncommitted changes across projects."""
    items = []

    for proj in GIT_PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not (proj_dir / ".git").exists():
            continue

        status = run(f"git -C {proj_dir} status --porcelain 2>/dev/null")
        if status:
            lines = status.strip().split("\n")
            modified = len([l for l in lines if l.startswith(" M") or l.startswith("M ")])
            untracked = len([l for l in lines if l.startswith("??")])
            staged = len([l for l in lines if l[0] in "AMDRC" and l[0] != "?"])

            parts = []
            if modified: parts.append(f"{modified} modified")
            if untracked: parts.append(f"{untracked} untracked")
            if staged: parts.append(f"{staged} staged")

            sev = "warning" if modified + staged > 0 else "info"
            items.append({
                "text": f"{proj}: {', '.join(parts)}",
                "detail": "\n".join(lines[:5]),
                "status": sev
            })

    if not items:
        items.append({"text": "All repos clean", "detail": "", "status": "ok"})

    return {"title": "Uncommitted Changes", "items": items}


def get_priorities():
    """Extract priority items from PIPELINE.md (open tasks in P1/P2)."""
    items = []
    if not PIPELINE_FILE.exists():
        return {"title": "Priorities", "items": []}

    content = PIPELINE_FILE.read_text()
    in_priority = False
    section_name = ""

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("## PRIORITY 1") or stripped.startswith("## PRIORITY 2"):
            in_priority = True
            section_name = stripped
        elif stripped.startswith("## PRIORITY 3") or stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            in_priority = False

        if in_priority and stripped.startswith("- [ ]"):
            task = stripped[6:].strip()
            items.append({
                "text": task[:80],
                "detail": section_name,
                "status": "warning"
            })

    return {"title": "Priorities", "items": items}


def get_unfinished():
    """Get P3 items grouped by heading (not individual checkboxes)."""
    headings = {}
    if not PIPELINE_FILE.exists():
        return {"title": "Unfinished Business", "items": []}

    content = PIPELINE_FILE.read_text()
    in_p3 = False
    current_heading = ""

    for line in content.split("\n"):
        stripped = line.strip()

        if stripped.startswith("### ") and in_p3:
            current_heading = stripped[4:].strip()
            # Remove common suffixes like "(ACTIVE - ...)" for cleaner display
            clean = re.sub(r"\s*\(.*?\)\s*$", "", current_heading)
            if clean not in headings:
                headings[clean] = {"total": 0, "done": 0, "notes": []}

        if "PRIORITY 3" in stripped:
            in_p3 = True
        elif stripped.startswith("## PARKED") or stripped.startswith("## CLOSED"):
            in_p3 = False

        if in_p3 and current_heading:
            clean = re.sub(r"\s*\(.*?\)\s*$", "", current_heading)
            if stripped.startswith("- [ ]"):
                headings.get(clean, {}).get("total", 0)
                if clean in headings:
                    headings[clean]["total"] += 1
            elif stripped.startswith("- [x]"):
                if clean in headings:
                    headings[clean]["done"] += 1
                    headings[clean]["total"] += 1
            elif stripped.startswith("- Note:") or stripped.startswith("- **"):
                if clean in headings:
                    note = stripped.lstrip("- ").strip()
                    headings[clean]["notes"].append(note[:80])

    items = []
    for heading, data in headings.items():
        open_count = data["total"] - data["done"]
        if open_count == 0:
            continue  # Skip fully done headings
        progress = f"{data['done']}/{data['total']} done"
        note = data["notes"][0] if data["notes"] else ""
        items.append({
            "text": f"{heading} ({progress})",
            "detail": note,
            "status": "info" if data["done"] == 0 else "warning"
        })

    return {"title": "Unfinished Business", "items": items}


def update_timeline(completed_items):
    """Update timeline.json with today's completed count."""
    today = datetime.now().strftime("%Y-%m-%d")
    day_name = datetime.now().strftime("%a")

    timeline = {"weekly": [], "totals": {"week": 0}}
    if TIMELINE_FILE.exists():
        try:
            timeline = json.loads(TIMELINE_FILE.read_text())
        except json.JSONDecodeError:
            pass

    # Check if today already exists
    found = False
    for entry in timeline.get("weekly", []):
        if entry["date"] == today:
            entry["completed"] = completed_items
            found = True
            break

    if not found:
        timeline.setdefault("weekly", []).append({
            "date": today,
            "day": day_name,
            "completed": completed_items,
            "items": []
        })

    # Keep last 7 days
    timeline["weekly"] = timeline["weekly"][-7:]
    timeline["totals"]["week"] = sum(e["completed"] for e in timeline["weekly"])

    TIMELINE_FILE.write_text(json.dumps(timeline, indent=2))


def generate():
    """Generate full report."""
    report_type = "morning"
    if len(sys.argv) > 2 and sys.argv[1] == "--type":
        report_type = sys.argv[2]

    now = datetime.now()
    timestamp = now.isoformat()

    # Gather all sections
    service_health = check_service_health()
    pipeline = check_pipeline()
    activity = check_activity()
    uncommitted = check_uncommitted()
    priorities = get_priorities()
    unfinished = get_unfinished()

    report = {
        "timestamp": timestamp,
        "type": report_type,
        "sections": {
            "service_health": service_health,
            "pipeline": pipeline,
            "activity": activity,
            "uncommitted": uncommitted,
            "priorities": priorities,
            "unfinished": unfinished,
        }
    }

    # Count completed items for timeline
    ok_count = sum(
        1 for s in report["sections"].values()
        for i in s["items"]
        if i["status"] == "ok"
    )
    update_timeline(ok_count)

    # Write dated file
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H%M")
    dated_path = REPORTS_DIR / f"{date_str}_{hour_str}.json"
    dated_path.write_text(json.dumps(report, indent=2))

    # Write latest.json (always overwritten)
    latest_path = REPORTS_DIR / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2))

    print(f"Report written to {dated_path}")
    print(f"Latest updated at {latest_path}")

    return report


if __name__ == "__main__":
    generate()
