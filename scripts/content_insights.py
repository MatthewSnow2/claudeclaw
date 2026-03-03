#!/usr/bin/env python3
"""
Content Insights Analyzer -- Starscream Intelligence Layer
Analyzes LinkedIn post performance and produces actionable insights.
Designed for cron -- runs after starscream_analytics.py.

Usage:
  python3 content_insights.py              # Full analysis
  python3 content_insights.py --dry-run    # Print insights, don't store
  python3 content_insights.py --summary    # Print latest insights

Cron (run 5 min after analytics):
  5 18 * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/content_insights.py >> /tmp/content_insights.log 2>&1
"""
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
ANALYTICS_DB = STORE_DIR / "starscream_analytics.db"

MIN_POSTS_THRESHOLD = 5

# Common LinkedIn content topics to detect in content_preview
TOPIC_KEYWORDS = {
    "AI/ML": [
        "ai", "machine learning", "gpt", "llm", "neural",
        "deep learning", "artificial intelligence",
    ],
    "Leadership": [
        "leadership", "team", "management", "culture", "hire", "hiring",
    ],
    "Startup": [
        "startup", "founder", "venture", "fundraise", "pivot", "mvp",
    ],
    "Career": [
        "career", "interview", "resume", "job", "promotion",
    ],
    "Tech": [
        "code", "coding", "software", "engineering", "developer", "api", "cloud",
    ],
    "Personal": [
        "i learned", "my experience", "story", "journey", "reflection",
    ],
    "How-To": [
        "how to", "steps to", "guide", "tutorial", "tips",
    ],
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TIME_BUCKETS = {
    "morning": (6, 12),
    "afternoon": (12, 18),
    "evening": (18, 24),
    "night": (0, 6),
}


def init_insights_table(db: sqlite3.Connection):
    """Create content_insights table with the spec schema.

    Drops the old schema if column layout doesn't match.
    """
    # Check if existing table has the new schema
    cols = {
        row[1]
        for row in db.execute("PRAGMA table_info(content_insights)").fetchall()
    }
    expected = {"id", "analysis_date", "insight_type", "metric_name",
                "metric_value", "detail_json", "created_at"}

    if cols and cols != expected:
        # Old schema present -- drop and recreate
        db.execute("DROP TABLE IF EXISTS content_insights")
        db.commit()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS content_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_date TEXT NOT NULL,
            insight_type TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL DEFAULT 0.0,
            detail_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_insights_date
            ON content_insights(analysis_date);
        CREATE INDEX IF NOT EXISTS idx_insights_type
            ON content_insights(insight_type);
    """)


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    """Check if a table exists in the database."""
    row = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row[0] > 0


def get_posts(db: sqlite3.Connection) -> list[dict]:
    """Fetch latest snapshot per post from post_metrics."""
    if not table_exists(db, "post_metrics"):
        return []

    rows = db.execute("""
        SELECT id, content_preview, published_at, likes, comments,
               shares, impressions, clicks, engagement_rate, raw_json
        FROM post_metrics
        WHERE collected_at = (
            SELECT MAX(collected_at) FROM post_metrics pm2
            WHERE pm2.id = post_metrics.id
        )
        ORDER BY engagement_rate DESC
    """).fetchall()

    posts = []
    for r in rows:
        raw = {}
        try:
            raw = json.loads(r[9]) if r[9] else {}
        except (json.JSONDecodeError, TypeError):
            pass

        full_content = raw.get("content", raw.get("text", ""))
        posts.append({
            "id": r[0],
            "content_preview": r[1] or "",
            "full_content": full_content,
            "published_at": r[2] or "",
            "likes": r[3] or 0,
            "comments": r[4] or 0,
            "shares": r[5] or 0,
            "impressions": r[6] or 0,
            "clicks": r[7] or 0,
            "engagement_rate": r[8] or 0.0,
        })

    return posts


def detect_topic(text: str) -> str:
    """Detect topic from content text using keyword matching."""
    lower = text.lower()
    scores: dict[str, int] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > 0:
            scores[topic] = count

    if not scores:
        return "Other"
    return max(scores, key=scores.get)


def detect_opening_pattern(text: str) -> str:
    """Categorize the opening pattern of a post."""
    text = text.strip().lower()
    if not text:
        return "statement"

    # Check how-to first (before question, since "how to" starts with "how")
    if text.startswith(("how to", "step", "guide", "tip")):
        return "how-to"

    question_starters = (
        "how ", "what ", "why ", "when ", "where ", "who ",
        "which ", "is ", "are ", "do ", "does ", "can ", "should ",
    )
    if text.startswith(question_starters):
        return "question"

    if any(c.isdigit() for c in text[:20]):
        return "statistic"

    if text.startswith(("i ", "my ", "we ", "our ")):
        return "personal"

    return "statement"


def get_content_length(post: dict) -> int:
    """Get best available content length for a post."""
    content = post.get("full_content", "")
    if not content:
        content = post.get("content_preview", "")
    return len(content)


def parse_published_dt(published_at: str) -> datetime | None:
    """Parse published_at string to datetime, handling common formats."""
    if not published_at:
        return None
    try:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def analyze_topic_ranking(posts: list[dict]) -> list[dict]:
    """1. Topic Ranking by Engagement Rate."""
    topic_data: dict[str, dict] = defaultdict(
        lambda: {"rates": [], "impressions": 0, "examples": []}
    )

    for post in posts:
        text = post["full_content"] or post["content_preview"]
        topic = detect_topic(text)
        topic_data[topic]["rates"].append(post["engagement_rate"])
        topic_data[topic]["impressions"] += post["impressions"]
        if len(topic_data[topic]["examples"]) < 2:
            preview = (post["content_preview"] or "")[:60]
            topic_data[topic]["examples"].append(preview)

    results = []
    for topic, data in topic_data.items():
        rates = data["rates"]
        avg = sum(rates) / len(rates) if rates else 0.0
        results.append({
            "insight_type": "topic_ranking",
            "metric_name": topic,
            "metric_value": round(avg, 4),
            "detail": {
                "post_count": len(rates),
                "total_impressions": data["impressions"],
                "examples": data["examples"],
            },
        })

    results.sort(key=lambda x: x["metric_value"], reverse=True)
    return results


def analyze_post_length(posts: list[dict]) -> list[dict]:
    """2. Optimal Post Length Correlation."""
    buckets: dict[str, list[dict]] = {
        "short": [],
        "medium": [],
        "long": [],
    }

    for post in posts:
        length = get_content_length(post)
        rate = post["engagement_rate"]
        entry = {"rate": rate, "length": length}

        if length < 100:
            buckets["short"].append(entry)
        elif length <= 300:
            buckets["medium"].append(entry)
        else:
            buckets["long"].append(entry)

    results = []
    labels = {
        "short": "< 100 chars",
        "medium": "100-300 chars",
        "long": "300+ chars",
    }
    for bucket_name, entries in buckets.items():
        if not entries:
            continue
        avg = sum(e["rate"] for e in entries) / len(entries)
        avg_len = sum(e["length"] for e in entries) / len(entries)
        results.append({
            "insight_type": "post_length",
            "metric_name": bucket_name,
            "metric_value": round(avg, 4),
            "detail": {
                "post_count": len(entries),
                "label": labels[bucket_name],
                "avg_char_count": round(avg_len),
            },
        })

    results.sort(key=lambda x: x["metric_value"], reverse=True)
    return results


def analyze_opening_patterns(posts: list[dict]) -> list[dict]:
    """3. Best Performing Opening Patterns."""
    pattern_data: dict[str, dict] = defaultdict(
        lambda: {"rates": [], "examples": []}
    )

    for post in posts:
        text = post["full_content"] or post["content_preview"]
        first50 = text[:50] if text else ""
        pattern = detect_opening_pattern(first50)
        pattern_data[pattern]["rates"].append(post["engagement_rate"])
        if len(pattern_data[pattern]["examples"]) < 2:
            pattern_data[pattern]["examples"].append(first50[:60])

    results = []
    for pattern, data in pattern_data.items():
        rates = data["rates"]
        avg = sum(rates) / len(rates) if rates else 0.0
        results.append({
            "insight_type": "opening_pattern",
            "metric_name": pattern,
            "metric_value": round(avg, 4),
            "detail": {
                "post_count": len(rates),
                "examples": data["examples"],
            },
        })

    results.sort(key=lambda x: x["metric_value"], reverse=True)
    return results


def analyze_day_of_week(posts: list[dict]) -> list[dict]:
    """4. Day-of-Week Performance."""
    day_data: dict[str, list[float]] = defaultdict(list)

    for post in posts:
        dt = parse_published_dt(post["published_at"])
        if dt is None:
            continue
        day_name = DAY_NAMES[dt.weekday()]
        day_data[day_name].append(post["engagement_rate"])

    results = []
    for day in DAY_NAMES:
        rates = day_data.get(day, [])
        avg = sum(rates) / len(rates) if rates else 0.0
        results.append({
            "insight_type": "day_of_week",
            "metric_name": day,
            "metric_value": round(avg, 4),
            "detail": {
                "post_count": len(rates),
            },
        })

    return results


def analyze_time_of_day(posts: list[dict]) -> list[dict]:
    """5. Time-of-Day Performance."""
    bucket_data: dict[str, list[float]] = defaultdict(list)

    for post in posts:
        dt = parse_published_dt(post["published_at"])
        if dt is None:
            continue
        hour = dt.hour
        for bucket_name, (start, end) in TIME_BUCKETS.items():
            if start <= hour < end:
                bucket_data[bucket_name].append(post["engagement_rate"])
                break

    results = []
    for bucket_name in ["morning", "afternoon", "evening", "night"]:
        rates = bucket_data.get(bucket_name, [])
        avg = sum(rates) / len(rates) if rates else 0.0
        start, end = TIME_BUCKETS[bucket_name]
        results.append({
            "insight_type": "time_of_day",
            "metric_name": bucket_name,
            "metric_value": round(avg, 4),
            "detail": {
                "post_count": len(rates),
                "hour_range": f"{start}-{end}",
            },
        })

    return results


def analyze_engagement_velocity(db: sqlite3.Connection) -> list[dict]:
    """6. Engagement Velocity from content_decay data."""
    if not table_exists(db, "content_decay"):
        return []

    count = db.execute("SELECT COUNT(*) FROM content_decay").fetchone()[0]
    if count == 0:
        return []

    # Get all posts with decay data
    post_ids = [
        r[0] for r in db.execute(
            "SELECT DISTINCT post_id FROM content_decay"
        ).fetchall()
    ]

    if len(post_ids) < 2:
        return []

    # Calculate velocity stats per post
    velocities = []
    for pid in post_ids:
        rows = db.execute("""
            SELECT hours_since_publish, cumulative_engagement, cumulative_impressions
            FROM content_decay
            WHERE post_id = ?
            ORDER BY hours_since_publish
        """, (pid,)).fetchall()

        if len(rows) < 2:
            continue

        # Engagement at 24h mark (or closest)
        eng_24h = 0.0
        for r in rows:
            if r[0] <= 24:
                eng_24h = r[1]

        total_eng = rows[-1][1]
        total_hours = rows[-1][0] or 1
        avg_velocity = total_eng / total_hours if total_hours > 0 else 0.0

        velocities.append({
            "post_id": pid,
            "engagement_24h": eng_24h,
            "total_engagement": total_eng,
            "total_hours": total_hours,
            "avg_velocity": avg_velocity,
        })

    if not velocities:
        return []

    # Split into top half and bottom half by total engagement
    velocities.sort(key=lambda x: x["total_engagement"], reverse=True)
    mid = len(velocities) // 2
    top_half = velocities[:mid] if mid > 0 else velocities
    bottom_half = velocities[mid:] if mid > 0 else []

    results = []

    top_avg_vel = sum(v["avg_velocity"] for v in top_half) / len(top_half) if top_half else 0.0
    results.append({
        "insight_type": "engagement_velocity",
        "metric_name": "top_performers",
        "metric_value": round(top_avg_vel, 4),
        "detail": {
            "post_count": len(top_half),
            "avg_engagement_24h": round(
                sum(v["engagement_24h"] for v in top_half) / len(top_half), 2
            ) if top_half else 0,
        },
    })

    if bottom_half:
        bot_avg_vel = sum(v["avg_velocity"] for v in bottom_half) / len(bottom_half)
        results.append({
            "insight_type": "engagement_velocity",
            "metric_name": "bottom_performers",
            "metric_value": round(bot_avg_vel, 4),
            "detail": {
                "post_count": len(bottom_half),
                "avg_engagement_24h": round(
                    sum(v["engagement_24h"] for v in bottom_half) / len(bottom_half), 2
                ),
            },
        })

    return results


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_insights(db: sqlite3.Connection, today: str, all_insights: list[dict]):
    """Store computed insights. Idempotent: replaces today's data."""
    now = datetime.now().isoformat()

    # Clear today's insights for idempotent re-run
    db.execute("DELETE FROM content_insights WHERE analysis_date = ?", (today,))

    for item in all_insights:
        db.execute(
            """INSERT INTO content_insights
               (analysis_date, insight_type, metric_name, metric_value, detail_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                today,
                item["insight_type"],
                item["metric_name"],
                item["metric_value"],
                json.dumps(item.get("detail", {})),
                now,
            ),
        )

    db.commit()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def build_summary(db: sqlite3.Connection | None = None) -> str:
    """Build Telegram-friendly summary from latest stored insights.

    Can be called by starscream_analytics.py or independently.
    """
    if db is None:
        if not ANALYTICS_DB.exists():
            return "No analytics DB found."
        db = sqlite3.connect(str(ANALYTICS_DB))
        close_db = True
    else:
        close_db = False

    try:
        if not table_exists(db, "content_insights"):
            return "No insights data yet. Run content_insights.py first."

        # Check schema matches
        cols = {
            row[1]
            for row in db.execute("PRAGMA table_info(content_insights)").fetchall()
        }
        if "analysis_date" not in cols:
            return "Insights table has old schema. Run content_insights.py to upgrade."

        # Get latest analysis date
        row = db.execute(
            "SELECT MAX(analysis_date) FROM content_insights"
        ).fetchone()
        if not row or not row[0]:
            return "No insights stored yet."

        latest_date = row[0]
        now = datetime.now()
        lines = [f"Content Insights -- {now.strftime('%a %b %d')}\n"]

        # Topic ranking
        topics = db.execute("""
            SELECT metric_name, metric_value, detail_json
            FROM content_insights
            WHERE analysis_date = ? AND insight_type = 'topic_ranking'
            ORDER BY metric_value DESC
            LIMIT 5
        """, (latest_date,)).fetchall()

        if topics:
            lines.append("Top Topics by Engagement:")
            for i, t in enumerate(topics, 1):
                detail = json.loads(t[2]) if t[2] else {}
                count = detail.get("post_count", 0)
                lines.append(f"  {i}. {t[0]}: {t[1]:.1f}% ({count} posts)")

        # Best posting window (combine day_of_week + time_of_day)
        best_day = db.execute("""
            SELECT metric_name, metric_value
            FROM content_insights
            WHERE analysis_date = ? AND insight_type = 'day_of_week'
                AND metric_value > 0
            ORDER BY metric_value DESC
            LIMIT 2
        """, (latest_date,)).fetchall()

        best_time = db.execute("""
            SELECT metric_name, metric_value
            FROM content_insights
            WHERE analysis_date = ? AND insight_type = 'time_of_day'
                AND metric_value > 0
            ORDER BY metric_value DESC
            LIMIT 1
        """, (latest_date,)).fetchone()

        if best_day or best_time:
            lines.append("\nBest Posting Window:")
            if best_day and best_time:
                days = "/".join(d[0][:3] for d in best_day)
                time_name = best_time[0]
                bucket_range = TIME_BUCKETS.get(time_name, (0, 24))
                lines.append(f"  {days} {time_name}s ({bucket_range[0]}-{bucket_range[1]})")
            elif best_day:
                days = "/".join(d[0][:3] for d in best_day)
                lines.append(f"  {days}")

        # Opening patterns
        openings = db.execute("""
            SELECT metric_name, metric_value
            FROM content_insights
            WHERE analysis_date = ? AND insight_type = 'opening_pattern'
                AND metric_value > 0
            ORDER BY metric_value DESC
            LIMIT 1
        """, (latest_date,)).fetchone()

        if openings:
            lines.append(f"\nOpening That Works:")
            lines.append(f"  {openings[0].title()}s: {openings[1]:.1f}% avg engagement")

        # Post length
        lengths = db.execute("""
            SELECT metric_name, metric_value, detail_json
            FROM content_insights
            WHERE analysis_date = ? AND insight_type = 'post_length'
                AND metric_value > 0
            ORDER BY metric_value DESC
            LIMIT 1
        """, (latest_date,)).fetchone()

        if lengths:
            detail = json.loads(lengths[2]) if lengths[2] else {}
            label = detail.get("label", lengths[0])
            lines.append(f"\nPost Length Sweet Spot:")
            lines.append(f"  {lengths[0].title()} ({label}): {lengths[1]:.1f}% avg")

        return "\n".join(lines)

    finally:
        if close_db:
            db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_analysis(dry_run: bool = False) -> dict:
    """Run full content analysis pipeline."""
    if not ANALYTICS_DB.exists():
        print("Analytics DB not found. Run starscream_analytics.py first.")
        return {}

    db = sqlite3.connect(str(ANALYTICS_DB))
    init_insights_table(db)

    posts = get_posts(db)
    post_count = len(posts)
    print(f"Found {post_count} posts in post_metrics.")

    if post_count < MIN_POSTS_THRESHOLD:
        print(f"Need at least {MIN_POSTS_THRESHOLD} posts for meaningful insights. "
              f"Have {post_count}. Skipping analysis.")
        db.close()
        return {"status": "insufficient_data", "post_count": post_count}

    today = datetime.now().strftime("%Y-%m-%d")
    all_insights: list[dict] = []

    # 1. Topic ranking
    topic_results = analyze_topic_ranking(posts)
    all_insights.extend(topic_results)
    print(f"  Topics detected: {len(topic_results)}")

    # 2. Post length correlation
    length_results = analyze_post_length(posts)
    all_insights.extend(length_results)
    print(f"  Length buckets: {len(length_results)}")

    # 3. Opening patterns
    opening_results = analyze_opening_patterns(posts)
    all_insights.extend(opening_results)
    print(f"  Opening patterns: {len(opening_results)}")

    # 4. Day of week
    day_results = analyze_day_of_week(posts)
    all_insights.extend(day_results)
    active_days = sum(1 for d in day_results if d["detail"]["post_count"] > 0)
    print(f"  Days with data: {active_days}/7")

    # 5. Time of day
    time_results = analyze_time_of_day(posts)
    all_insights.extend(time_results)
    active_times = sum(1 for t in time_results if t["detail"]["post_count"] > 0)
    print(f"  Time buckets with data: {active_times}/4")

    # 6. Engagement velocity
    velocity_results = analyze_engagement_velocity(db)
    all_insights.extend(velocity_results)
    if velocity_results:
        print(f"  Velocity segments: {len(velocity_results)}")
    else:
        print("  Velocity: no content_decay data")

    if dry_run:
        print("\n--- DRY RUN: Insights ---")
        for item in all_insights:
            print(f"  [{item['insight_type']}] {item['metric_name']}: "
                  f"{item['metric_value']:.4f}")
        print(f"\nTotal insights: {len(all_insights)}")
        print("\n--- Summary ---")
        # Store temporarily for summary generation
        store_insights(db, today, all_insights)
        print(build_summary(db))
        # Roll back by clearing (dry run should not persist)
        db.execute("DELETE FROM content_insights WHERE analysis_date = ?", (today,))
        db.commit()
    else:
        store_insights(db, today, all_insights)
        print(f"Stored {len(all_insights)} insights for {today}")

    db.close()
    return {
        "status": "ok",
        "post_count": post_count,
        "insight_count": len(all_insights),
        "analysis_date": today,
    }


def print_latest_summary():
    """Print the most recent stored insights summary."""
    summary = build_summary()
    print(summary)


def main():
    dry_run = "--dry-run" in sys.argv
    summary_only = "--summary" in sys.argv

    if summary_only:
        print_latest_summary()
        return

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now().isoformat()}] Running content insights analysis...")
    result = run_analysis(dry_run=dry_run)

    status = result.get("status", "")
    if status == "insufficient_data":
        print(f"Waiting for more data ({result.get('post_count', 0)}/{MIN_POSTS_THRESHOLD} posts).")
    elif status == "ok":
        print(f"Done. {result.get('post_count', 0)} posts, "
              f"{result.get('insight_count', 0)} insights generated.")


if __name__ == "__main__":
    main()
