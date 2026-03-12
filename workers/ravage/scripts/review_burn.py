#!/home/apexaipc/projects/claudeclaw/venv/bin/python
"""
Code Review Burn Tracker.

Queries hive_mind for pr_review events and reports cost trends.
Designed to be called by Ravage or Data when checking review spend.

Usage:
    python review_burn.py                # Last 7 days
    python review_burn.py --days 30      # Last 30 days
    python review_burn.py --detail       # Show individual reviews
"""

import argparse
import sqlite3
import time
from pathlib import Path

STORE_DIR = Path(__file__).resolve().parents[3] / "store"
DB_PATH = STORE_DIR / "claudeclaw.db"


def get_review_burn(days: int = 7, detail: bool = False) -> str:
    if not DB_PATH.exists():
        return "DB not found. No review data."

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cutoff = int(time.time()) - (days * 86400)

    try:
        # Aggregate stats
        row = conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(cost_usd), 0) as total_cost "
            "FROM hive_mind WHERE event_type = 'pr_review' AND created_at >= ?",
            (cutoff,),
        ).fetchone()

        count = row["cnt"]
        total_cost = row["total_cost"]

        if count == 0:
            return f"No PR reviews in the last {days} days."

        avg_cost = total_cost / count if count > 0 else 0

        lines = [
            f"PR Review Burn ({days}d)",
            f"  Reviews: {count}",
            f"  Total cost: ${total_cost:.4f}",
            f"  Avg cost/review: ${avg_cost:.4f}",
        ]

        # Daily breakdown
        daily = conn.execute(
            "SELECT date(created_at, 'unixepoch') as day, COUNT(*) as cnt, "
            "SUM(cost_usd) as cost FROM hive_mind "
            "WHERE event_type = 'pr_review' AND created_at >= ? "
            "GROUP BY day ORDER BY day DESC",
            (cutoff,),
        ).fetchall()

        if daily:
            lines.append(f"\n  Daily breakdown:")
            for d in daily:
                lines.append(f"    {d['day']}: {d['cnt']} reviews, ${d['cost']:.4f}")

        # Detail view
        if detail:
            reviews = conn.execute(
                "SELECT summary, detail, cost_usd, created_at FROM hive_mind "
                "WHERE event_type = 'pr_review' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 20",
                (cutoff,),
            ).fetchall()

            if reviews:
                lines.append(f"\n  Recent reviews:")
                for r in reviews:
                    lines.append(f"    ${r['cost_usd']:.4f} | {r['summary']}")

        return "\n".join(lines)

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Review burn tracker")
    parser.add_argument("--days", type=int, default=7, help="Lookback period")
    parser.add_argument("--detail", action="store_true", help="Show individual reviews")
    args = parser.parse_args()

    print(get_review_burn(args.days, args.detail))


if __name__ == "__main__":
    main()
