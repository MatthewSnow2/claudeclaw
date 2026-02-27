#!/usr/bin/env python3
"""
Inbox Triage Agent - L5 Morning Briefing Consolidator
Collects actionable items from GitHub, Linear, Late API, and Metroplex.
Sends a prioritized Telegram briefing before the morning report.

Sources:
  1. GitHub - notifications, PRs with review requests (via gh CLI)
  2. Linear - assigned issues, recent updates (via REST API)
  3. Late API - unread social inbox messages
  4. Metroplex - stuck builds, circuit breaker halts, queue state

Usage:
  python3 inbox_triage.py              # Normal run
  python3 inbox_triage.py --dry-run    # Print but don't send

Cron:
  45 7 * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/inbox_triage.py >> /tmp/inbox_triage.log 2>&1
"""
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ENV_FILE = Path(os.path.expanduser("~/.env.shared"))
METROPLEX_DB = Path("/home/apexaipc/projects/metroplex/data/metroplex.db")


def load_env() -> dict[str, str]:
    """Load API keys from ~/.env.shared."""
    keys = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            keys[key] = val
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "LINEAR_API_KEY", "LATE_API_KEY"):
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


# --- Source collectors ---

def collect_github() -> list[dict]:
    """Collect GitHub notifications and review requests via gh CLI."""
    items = []

    # Notifications
    notif_json = run("gh api notifications --jq '.[] | {subject: .subject.title, type: .subject.type, reason: .reason, repo: .repository.full_name}' 2>/dev/null")
    if notif_json:
        for line in notif_json.strip().split("\n"):
            if not line.strip():
                continue
            try:
                n = json.loads(line)
                reason = n.get("reason", "")
                if reason in ("review_requested", "assign", "mention", "security_alert"):
                    items.append({
                        "source": "GITHUB",
                        "priority": 1 if reason == "review_requested" else 2,
                        "text": f"{n.get('subject', 'Unknown')}",
                        "detail": f"{n.get('repo', '')} ({reason})",
                    })
            except json.JSONDecodeError:
                continue

    # PRs needing review (direct check)
    pr_json = run("gh search prs --review-requested=@me --state=open --json title,repository,url --limit 5 2>/dev/null")
    if pr_json:
        try:
            prs = json.loads(pr_json)
            for pr in prs:
                repo = pr.get("repository", {}).get("name", "")
                title = pr.get("title", "")[:60]
                items.append({
                    "source": "GITHUB",
                    "priority": 1,
                    "text": f"PR review: {title}",
                    "detail": repo,
                })
        except json.JSONDecodeError:
            pass

    return items


def collect_linear(api_key: str) -> list[dict]:
    """Collect assigned Linear issues via GraphQL API."""
    items = []
    if not api_key:
        return items

    query = """
    query {
      viewer {
        assignedIssues(filter: { state: { type: { in: ["started", "unstarted"] } } }, first: 10) {
          nodes {
            identifier
            title
            state { name }
            priority
            updatedAt
          }
        }
      }
    }
    """

    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.linear.app/graphql",
        data=payload,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Linear API error: {e}", file=sys.stderr)
        return items

    issues = (data.get("data", {}).get("viewer", {})
              .get("assignedIssues", {}).get("nodes", []))

    for issue in issues:
        identifier = issue.get("identifier", "")
        title = issue.get("title", "")[:50]
        state = issue.get("state", {}).get("name", "")
        priority = issue.get("priority", 4)

        items.append({
            "source": "LINEAR",
            "priority": max(1, min(priority, 3)),
            "text": f"{identifier}: {title}",
            "detail": state,
        })

    return items


def collect_late_inbox(api_key: str) -> list[dict]:
    """Collect unread messages from Late API inbox."""
    items = []
    if not api_key:
        return items

    req = urllib.request.Request(
        "https://getlate.dev/api/v1/inbox?read=false&limit=10",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return items

    messages = data if isinstance(data, list) else data.get("messages", data.get("data", []))
    count = len(messages)

    if count > 0:
        items.append({
            "source": "LATE",
            "priority": 3,
            "text": f"{count} unread social message{'s' if count != 1 else ''}",
            "detail": "Check getlate.dev inbox",
        })

    return items


def collect_metroplex() -> list[dict]:
    """Check Metroplex for stuck builds, failed items, queue state."""
    items = []
    if not METROPLEX_DB.exists():
        return items

    try:
        db = sqlite3.connect(str(METROPLEX_DB))

        # Failed builds
        failed = db.execute(
            """SELECT title, source FROM priority_queue
               WHERE status = 'failed'
               ORDER BY completed_at DESC LIMIT 3"""
        ).fetchall()
        for row in failed:
            items.append({
                "source": "METROPLEX",
                "priority": 1,
                "text": f"Build failed: {(row[0] or '')[:40]}",
                "detail": f"Source: {row[1]}",
            })

        # Dispatched but potentially stuck
        dispatched = db.execute(
            """SELECT title, dispatched_at FROM priority_queue
               WHERE status = 'dispatched'
               ORDER BY dispatched_at ASC LIMIT 3"""
        ).fetchall()
        for row in dispatched:
            age = ""
            if row[1]:
                try:
                    dt = datetime.fromisoformat(row[1])
                    hours = (datetime.now() - dt).total_seconds() / 3600
                    if hours > 2:
                        age = f" ({hours:.0f}h stuck)"
                        items.append({
                            "source": "METROPLEX",
                            "priority": 2,
                            "text": f"Stuck build: {(row[0] or '')[:40]}",
                            "detail": f"Dispatched{age}",
                        })
                except Exception:
                    pass

        # Queue summary
        summary = db.execute(
            "SELECT status, count(*) FROM priority_queue GROUP BY status"
        ).fetchall()
        queue_parts = [f"{row[0]}: {row[1]}" for row in summary if row[1] > 0]
        if queue_parts:
            items.append({
                "source": "METROPLEX",
                "priority": 3,
                "text": f"Queue: {', '.join(queue_parts)}",
                "detail": "",
            })

        db.close()
    except Exception as e:
        items.append({
            "source": "METROPLEX",
            "priority": 3,
            "text": f"DB error: {str(e)[:50]}",
            "detail": "",
        })

    return items


def build_briefing(all_items: list[dict]) -> str:
    """Build a prioritized Telegram briefing."""
    now = datetime.now()
    day = now.strftime("%a %b %d")

    if not all_items:
        return f"<b>Inbox ({day})</b>\n\nAll clear. Nothing actionable."

    # Sort by priority (1=urgent, 3=low)
    all_items.sort(key=lambda x: x.get("priority", 3))

    lines = [f"<b>Inbox ({day}) -- {len(all_items)} items</b>\n"]

    for i, item in enumerate(all_items[:12], 1):
        source = item.get("source", "?")
        text = item.get("text", "")
        detail = item.get("detail", "")
        priority = item.get("priority", 3)

        marker = "!!" if priority == 1 else "!" if priority == 2 else "-"
        line = f"{marker} [{source}] {text}"
        if detail:
            line += f" -- {detail}"
        lines.append(line)

    remaining = len(all_items) - 12
    if remaining > 0:
        lines.append(f"\n+{remaining} more items")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    env = load_env()
    print(f"[{datetime.now().isoformat()}] Collecting inbox items...")

    all_items = []

    # Collect from all sources
    github_items = collect_github()
    all_items.extend(github_items)
    print(f"  GitHub: {len(github_items)} items")

    linear_items = collect_linear(env.get("LINEAR_API_KEY", ""))
    all_items.extend(linear_items)
    print(f"  Linear: {len(linear_items)} items")

    late_items = collect_late_inbox(env.get("LATE_API_KEY", ""))
    all_items.extend(late_items)
    print(f"  Late: {len(late_items)} items")

    metroplex_items = collect_metroplex()
    all_items.extend(metroplex_items)
    print(f"  Metroplex: {len(metroplex_items)} items")

    print(f"  Total: {len(all_items)} items")

    briefing = build_briefing(all_items)

    if dry_run:
        print("\n=== DRY RUN ===")
        print(briefing)
        return

    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")

    if token and chat_id:
        if len(briefing) > 4000:
            briefing = briefing[:3997] + "..."
        if send_telegram(token, chat_id, briefing):
            print("Inbox briefing sent to Telegram")
        else:
            print("Failed to send briefing", file=sys.stderr)
    else:
        print("No Telegram credentials, printing:")
        print(briefing)


if __name__ == "__main__":
    main()
