#!/usr/bin/env python3
"""
Send Dashboard Report via Telegram
Reads latest.json, formats a summary, and sends via Telegram Bot API.
Designed for cron -- no Claude/LLM dependency.

Usage:
  python3 send_report.py              # Auto-detect morning/evening by hour
  python3 send_report.py --morning    # Force morning report
  python3 send_report.py --evening    # Force evening report

Cron:
  0 8 * * *  /home/apexaipc/projects/claudeclaw/scripts/send_report.py
  0 16 * * * /home/apexaipc/projects/claudeclaw/scripts/send_report.py
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("/home/apexaipc/projects/claudeclaw/dashboard/reports")
LATEST_JSON = REPORTS_DIR / "latest.json"
GENERATE_SCRIPT = Path("/home/apexaipc/projects/claudeclaw/dashboard/generate_report.py")
ENV_FILE = Path(os.path.expanduser("~/.env.shared"))

STATUS_ICONS = {"ok": "+", "warning": "!", "error": "X", "info": "-"}


def load_env():
    """Load bot token and chat ID from ~/.env.shared."""
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
    """Send a message via Telegram Bot API. Returns True on success."""
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


def format_section(title: str, items: list[dict], max_items: int = 5) -> str:
    """Format a report section into plain text lines."""
    if not items:
        return ""

    lines = [f"<b>{title}</b>"]
    for item in items[:max_items]:
        icon = STATUS_ICONS.get(item.get("status", "info"), "-")
        text = item.get("text", "")
        detail = item.get("detail", "")
        line = f"  [{icon}] {text}"
        if detail and len(line) + len(detail) < 120:
            line += f" -- {detail}"
        lines.append(line)

    remaining = len(items) - max_items
    if remaining > 0:
        lines.append(f"  ... +{remaining} more")

    return "\n".join(lines)


def build_message(report: dict, report_type: str) -> str:
    """Build the full Telegram message from a report dict."""
    now = datetime.now()
    header = f"{'Morning' if report_type == 'morning' else 'Evening'} Report -- {now.strftime('%a %b %d, %H:%M')}"

    sections_order = [
        ("service_health", "Service Health", 8),
        ("priorities", "Priorities", 6),
        ("soundwave", "Operator Review", 6),
        ("pipeline", "Pipeline", 5),
        ("activity", "Recent Activity", 6),
        ("uncommitted", "Uncommitted Changes", 5),
    ]

    parts = [f"<b>{header}</b>\n"]

    sections = report.get("sections", {})
    for key, title, limit in sections_order:
        section = sections.get(key, {})
        items = section.get("items", [])
        formatted = format_section(title, items, max_items=limit)
        if formatted:
            parts.append(formatted)

    return "\n\n".join(parts)


def regenerate_report(report_type: str):
    """Run generate_report.py to produce a fresh latest.json."""
    try:
        subprocess.run(
            [sys.executable, str(GENERATE_SCRIPT), "--type", report_type],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        print(f"Report generation failed: {e}", file=sys.stderr)


def main():
    # Determine report type
    if "--morning" in sys.argv:
        report_type = "morning"
    elif "--evening" in sys.argv:
        report_type = "evening"
    else:
        report_type = "morning" if datetime.now().hour < 12 else "evening"

    # Regenerate the report first
    regenerate_report(report_type)

    # Load report
    if not LATEST_JSON.exists():
        print(f"No report at {LATEST_JSON}", file=sys.stderr)
        sys.exit(1)

    report = json.loads(LATEST_JSON.read_text())

    # Load credentials
    token, chat_id = load_env()
    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", file=sys.stderr)
        sys.exit(1)

    # Build and send
    message = build_message(report, report_type)

    # Telegram max message is 4096 chars
    if len(message) > 4000:
        message = message[:3997] + "..."

    if send_telegram(token, chat_id, message):
        print(f"{report_type.title()} report sent to Telegram")
    else:
        print("Failed to send report", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
