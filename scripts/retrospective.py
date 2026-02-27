#!/usr/bin/env python3
"""
Retrospective Agent - L5 Weekly Cross-Cutting Analysis
Runs Sunday 8pm (before Sky-Lynx at 2am). Collects metrics from all ecosystem
components and produces a structured weekly retrospective.

Data Sources:
  1. Starscream analytics DB - post performance, engagement trends
  2. Metroplex DB - build success/fail, triage throughput, cycle counts
  3. IdeaForge DB - idea pipeline flow (signals -> ideas -> builds)
  4. ST Factory - recommendation status, patch status
  5. Git logs - commit velocity across all projects

Output:
  - JSON report at /home/apexaipc/projects/st-factory/data/weekly_retrospective.json
  - Telegram summary

Usage:
  python3 retrospective.py              # Normal run
  python3 retrospective.py --dry-run    # Print but don't store or send

Cron:
  0 20 * * 0 /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/retrospective.py >> /tmp/retrospective.log 2>&1
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Paths ---
ENV_FILE = Path(os.path.expanduser("~/.env.shared"))
PROJECTS_DIR = Path("/home/apexaipc/projects")
STARSCREAM_DB = PROJECTS_DIR / "claudeclaw" / "store" / "starscream_analytics.db"
METROPLEX_DB = PROJECTS_DIR / "metroplex" / "data" / "metroplex.db"
IDEAFORGE_DB = PROJECTS_DIR / "ideaforge" / "data" / "ideaforge.db"
STFACTORY_DB = PROJECTS_DIR / "st-factory" / "data" / "persona_metrics.db"
OUTPUT_DIR = PROJECTS_DIR / "st-factory" / "data"
OUTPUT_FILE = OUTPUT_DIR / "weekly_retrospective.json"

GIT_PROJECTS = [
    "claudeclaw", "ultra-magnus", "yce-harness", "metroplex",
    "ideaforge", "research-agents", "st-factory", "perceptor",
    "sky-lynx", "gen-ui-dashboard",
]


def load_env() -> dict[str, str]:
    """Load API keys from ~/.env.shared."""
    keys = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            keys[key.strip()] = val.strip().strip('"').strip("'")
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(k):
            keys[k] = os.environ[k]
    return keys


def run(cmd: str, timeout: int = 15) -> str:
    """Run shell command, return stdout."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception:
        return ""


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    """Send Telegram message."""
    import urllib.error
    import urllib.request
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


def safe_query(db_path: Path, query: str, params: tuple = ()) -> list:
    """Safe DB query that returns empty list on any error."""
    if not db_path.exists():
        return []
    try:
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
        rows = db.execute(query, params).fetchall()
        db.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"DB error ({db_path.name}): {e}", file=sys.stderr)
        return []


# --- Data Collectors ---

def collect_starscream_metrics(cutoff: str) -> dict:
    """Collect Starscream content analytics for the week."""
    metrics = {"posts": 0, "total_likes": 0, "total_comments": 0,
               "total_impressions": 0, "avg_engagement": 0.0,
               "follower_delta": 0, "top_post": None}

    if not STARSCREAM_DB.exists():
        return metrics

    # Post metrics this week
    posts = safe_query(
        STARSCREAM_DB,
        """SELECT content_preview, likes, comments, impressions, engagement_rate
           FROM post_metrics WHERE collected_at > ?
           GROUP BY id HAVING collected_at = MAX(collected_at)
           ORDER BY engagement_rate DESC""",
        (cutoff,)
    )

    if posts:
        metrics["posts"] = len(posts)
        metrics["total_likes"] = sum(p.get("likes", 0) for p in posts)
        metrics["total_comments"] = sum(p.get("comments", 0) for p in posts)
        metrics["total_impressions"] = sum(p.get("impressions", 0) for p in posts)
        rates = [p.get("engagement_rate", 0) for p in posts if p.get("engagement_rate", 0) > 0]
        metrics["avg_engagement"] = round(sum(rates) / len(rates), 2) if rates else 0.0
        metrics["top_post"] = posts[0].get("content_preview", "")[:60] if posts else None

    # Follower delta
    followers = safe_query(
        STARSCREAM_DB,
        "SELECT total_followers FROM follower_metrics ORDER BY collected_at DESC LIMIT 7"
    )
    if len(followers) >= 2:
        metrics["follower_delta"] = followers[0].get("total_followers", 0) - followers[-1].get("total_followers", 0)

    return metrics


def collect_metroplex_metrics(cutoff: str) -> dict:
    """Collect Metroplex build/triage metrics for the week."""
    metrics = {"cycles": 0, "triage_approved": 0, "triage_rejected": 0,
               "builds_completed": 0, "builds_failed": 0,
               "patches_applied": 0, "patches_skipped": 0}

    if not METROPLEX_DB.exists():
        return metrics

    # Cycles
    cycles = safe_query(
        METROPLEX_DB,
        "SELECT count(*) as cnt FROM cycles WHERE completed_at > ?",
        (cutoff,)
    )
    if cycles:
        metrics["cycles"] = cycles[0].get("cnt", 0)

    # Triage decisions
    triage = safe_query(
        METROPLEX_DB,
        """SELECT decision, count(*) as cnt FROM triage_decisions
           WHERE decided_at > ? GROUP BY decision""",
        (cutoff,)
    )
    for row in triage:
        if row.get("decision") == "approved":
            metrics["triage_approved"] = row.get("cnt", 0)
        elif row.get("decision") == "rejected":
            metrics["triage_rejected"] = row.get("cnt", 0)

    # Builds (queued_at is the timestamp column in build_jobs)
    builds = safe_query(
        METROPLEX_DB,
        """SELECT status, count(*) as cnt FROM build_jobs
           WHERE queued_at > ? GROUP BY status""",
        (cutoff,)
    )
    for row in builds:
        if row.get("status") == "completed":
            metrics["builds_completed"] = row.get("cnt", 0)
        elif row.get("status") == "failed":
            metrics["builds_failed"] = row.get("cnt", 0)

    # Patches
    patches = safe_query(
        METROPLEX_DB,
        """SELECT status, count(*) as cnt FROM patch_applications
           WHERE applied_at > ? GROUP BY status""",
        (cutoff,)
    )
    for row in patches:
        if row.get("status") == "applied":
            metrics["patches_applied"] = row.get("cnt", 0)
        elif row.get("status") == "skipped":
            metrics["patches_skipped"] = row.get("cnt", 0)

    return metrics


def collect_ideaforge_metrics(cutoff: str) -> dict:
    """Collect IdeaForge pipeline flow metrics."""
    metrics = {"signals_ingested": 0, "ideas_created": 0}

    if not IDEAFORGE_DB.exists():
        return metrics

    signals = safe_query(
        IDEAFORGE_DB,
        "SELECT count(*) as cnt FROM signals WHERE harvested_at > ?",
        (cutoff,)
    )
    if signals:
        metrics["signals_ingested"] = signals[0].get("cnt", 0)

    ideas = safe_query(
        IDEAFORGE_DB,
        "SELECT count(*) as cnt FROM ideas WHERE synthesized_at > ?",
        (cutoff,)
    )
    if ideas:
        metrics["ideas_created"] = ideas[0].get("cnt", 0)

    return metrics


def collect_stfactory_metrics(cutoff: str) -> dict:
    """Collect ST Factory recommendation and patch metrics."""
    metrics = {"recs_pending": 0, "recs_applied": 0,
               "patches_proposed": 0, "patches_applied": 0}

    if not STFACTORY_DB.exists():
        return metrics

    # Recommendations
    recs = safe_query(
        STFACTORY_DB,
        "SELECT status, count(*) as cnt FROM improvement_recommendations GROUP BY status"
    )
    for row in recs:
        if row.get("status") == "pending":
            metrics["recs_pending"] = row.get("cnt", 0)
        elif row.get("status") == "applied":
            metrics["recs_applied"] = row.get("cnt", 0)

    # Patches
    patches = safe_query(
        STFACTORY_DB,
        "SELECT status, count(*) as cnt FROM persona_patches GROUP BY status"
    )
    for row in patches:
        if row.get("status") == "proposed":
            metrics["patches_proposed"] = row.get("cnt", 0)
        elif row.get("status") == "applied":
            metrics["patches_applied"] = row.get("cnt", 0)

    return metrics


def collect_git_velocity(cutoff_str: str) -> dict:
    """Count commits across all projects in the last 7 days."""
    velocity = {}
    for proj in GIT_PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not (proj_dir / ".git").exists():
            continue
        count = run(f"git -C {proj_dir} rev-list --count --since='{cutoff_str}' HEAD 2>/dev/null")
        try:
            velocity[proj] = int(count)
        except ValueError:
            velocity[proj] = 0
    return velocity


def build_summary(report: dict) -> str:
    """Build Telegram-friendly weekly summary."""
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime("%b %d")
    lines = [f"<b>Weekly Retrospective ({week_start} - {now.strftime('%b %d')})</b>\n"]

    # Git velocity
    velocity = report.get("git_velocity", {})
    total_commits = sum(velocity.values())
    active = [f"{k}({v})" for k, v in velocity.items() if v > 0]
    lines.append(f"<b>Code</b>: {total_commits} commits across {len(active)} projects")
    if active:
        lines.append(f"  {', '.join(active[:6])}")

    # Starscream
    s = report.get("starscream", {})
    if s.get("posts", 0) > 0:
        lines.append(f"\n<b>Starscream</b>: {s['posts']} posts")
        lines.append(f"  {s.get('total_likes', 0)} likes, {s.get('total_comments', 0)} comments, {s.get('total_impressions', 0)} impressions")
        lines.append(f"  Avg engagement: {s.get('avg_engagement', 0):.1f}% | Followers: {'+' if s.get('follower_delta', 0) >= 0 else ''}{s.get('follower_delta', 0)}")

    # Metroplex
    m = report.get("metroplex", {})
    if m.get("cycles", 0) > 0:
        lines.append(f"\n<b>Metroplex</b>: {m['cycles']} cycles")
        lines.append(f"  Triage: {m.get('triage_approved', 0)} approved, {m.get('triage_rejected', 0)} rejected")
        lines.append(f"  Builds: {m.get('builds_completed', 0)} ok, {m.get('builds_failed', 0)} failed")
        lines.append(f"  Patches: {m.get('patches_applied', 0)} applied, {m.get('patches_skipped', 0)} skipped")

    # IdeaForge
    i = report.get("ideaforge", {})
    if i.get("signals_ingested", 0) > 0 or i.get("ideas_created", 0) > 0:
        lines.append(f"\n<b>IdeaForge</b>: {i.get('signals_ingested', 0)} signals, {i.get('ideas_created', 0)} ideas")

    # ST Factory
    f = report.get("st_factory", {})
    if any(f.values()):
        lines.append(f"\n<b>ST Factory</b>: {f.get('recs_pending', 0)} recs pending, {f.get('patches_proposed', 0)} patches proposed")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    now = datetime.now()
    cutoff = (now - timedelta(days=7)).isoformat()
    cutoff_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"[{now.isoformat()}] Generating weekly retrospective...")

    # Collect all metrics
    report = {
        "generated_at": now.isoformat(),
        "period": {"start": cutoff_date, "end": now.strftime("%Y-%m-%d")},
        "starscream": collect_starscream_metrics(cutoff),
        "metroplex": collect_metroplex_metrics(cutoff),
        "ideaforge": collect_ideaforge_metrics(cutoff),
        "st_factory": collect_stfactory_metrics(cutoff),
        "git_velocity": collect_git_velocity(cutoff_date),
    }

    summary = build_summary(report)

    if dry_run:
        print("\n=== DRY RUN ===")
        print(json.dumps(report, indent=2))
        print("\n=== SUMMARY ===")
        print(summary)
        return

    # Write JSON report for Sky-Lynx consumption
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2))
    print(f"Report written to {OUTPUT_FILE}")

    # Send Telegram summary
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")

    if token and chat_id:
        if len(summary) > 4000:
            summary = summary[:3997] + "..."
        if send_telegram(token, chat_id, summary):
            print("Weekly retro sent to Telegram")
        else:
            print("Failed to send retro", file=sys.stderr)
    else:
        print("No Telegram credentials, printing:")
        print(summary)


if __name__ == "__main__":
    main()
