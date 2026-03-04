#!/usr/bin/env python3
"""
Content Insights Analyzer - L5 Content Intelligence for Starscream
Analyzes post performance across topic, length, opener style, and timing
to produce actionable "what works" insights.

Reads from:
  - starscream_analytics.db (post_metrics, best_time_analysis, content_decay, posting_frequency)
  - claudeclaw.db (posted_content for topic mapping)

Writes to:
  - starscream_analytics.db (content_insights table)

Usage:
  python3 content_insights.py              # Full analysis, store results
  python3 content_insights.py --dry-run    # Print results, don't store
  python3 content_insights.py --json       # Output JSON to stdout (for report generator)

Cron (chain after starscream_analytics.py):
  5 18 * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/content_insights.py >> /tmp/content_insights.log 2>&1
"""
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# --- Config ---
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
ANALYTICS_DB_PATH = STORE_DIR / "starscream_analytics.db"
CLAUDECLAW_DB_PATH = STORE_DIR / "claudeclaw.db"

DEFAULT_PERIOD_DAYS = 30


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_insights_table(db: sqlite3.Connection) -> None:
    """Create the content_insights table if it does not exist.

    Schema uses TEXT primary key (UUID), stores each insight_type as a single
    JSON blob in data_json, with a confidence score and period_days.

    If a table with an incompatible schema already exists, it is dropped and
    recreated so the script stays idempotent across schema migrations.
    """
    # Detect stale schema and drop if columns don't match
    existing_cols = {
        row[1]
        for row in db.execute("PRAGMA table_info(content_insights)").fetchall()
    }
    expected_cols = {"id", "generated_at", "insight_type", "data_json",
                     "period_days", "confidence"}

    if existing_cols and existing_cols != expected_cols:
        db.execute("DROP TABLE IF EXISTS content_insights")
        db.commit()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS content_insights (
            id TEXT PRIMARY KEY,
            generated_at TEXT NOT NULL,
            insight_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            period_days INTEGER DEFAULT 30,
            confidence REAL DEFAULT 0.0
        );

        CREATE INDEX IF NOT EXISTS idx_content_insights_type
            ON content_insights(insight_type);
        CREATE INDEX IF NOT EXISTS idx_content_insights_generated
            ON content_insights(generated_at);
    """)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def confidence_from_count(count: int, min_threshold: int = 3,
                          strong_threshold: int = 15) -> float:
    """Calculate a confidence score between 0.0 and 1.0 based on sample size.

    Ranges:
      0 samples                    -> 0.0
      1 to min_threshold-1         -> 0.0 to 0.3 (linear)
      min_threshold to strong      -> 0.3 to 0.8 (linear)
      above strong_threshold       -> 0.8 to 1.0 (diminishing returns)
    """
    if count <= 0:
        return 0.0
    if count < min_threshold:
        return round(0.3 * (count / min_threshold), 2)
    if count <= strong_threshold:
        return round(
            0.3 + 0.5 * ((count - min_threshold) / (strong_threshold - min_threshold)),
            2,
        )
    # Diminishing returns above strong_threshold
    return round(min(1.0, 0.8 + 0.2 * (1 - 1 / (count - strong_threshold + 1))), 2)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_post_data(analytics_db: sqlite3.Connection,
                   claudeclaw_db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Load and join post_metrics with posted_content topic data.

    Uses the most recent snapshot per post from post_metrics. Joins on
    late_post_id (posted_content) = id (post_metrics), with a fallback to
    content-snippet similarity matching when IDs do not align.

    Returns a list of dicts with merged fields. Returns an empty list when
    post_metrics has no rows.
    """
    # Check table exists
    has_table = analytics_db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='post_metrics'"
    ).fetchone()[0]
    if not has_table:
        return []

    # Fetch latest snapshot per post
    metrics_rows = analytics_db.execute("""
        SELECT pm.id, pm.content_preview, pm.published_at,
               pm.likes, pm.comments, pm.shares, pm.impressions,
               pm.clicks, pm.engagement_rate, pm.raw_json
        FROM post_metrics pm
        INNER JOIN (
            SELECT id, MAX(collected_at) AS latest
            FROM post_metrics
            GROUP BY id
        ) latest_snap ON pm.id = latest_snap.id
                      AND pm.collected_at = latest_snap.latest
        ORDER BY pm.published_at DESC
    """).fetchall()

    # Fetch posted_content for topic mapping
    content_rows = claudeclaw_db.execute("""
        SELECT late_post_id, topic, title_snippet, content_hash
        FROM posted_content
    """).fetchall()

    # Build lookup by late_post_id
    topic_by_id: dict[str, dict[str, Any]] = {}
    for row in content_rows:
        if row[0]:
            topic_by_id[row[0]] = {
                "topic": row[1] or "Unknown",
                "title_snippet": row[2] or "",
                "content_hash": row[3] or "",
            }

    posts: list[dict[str, Any]] = []
    for row in metrics_rows:
        post_id = row[0]
        content_preview = row[1] or ""
        published_at = row[2] or ""

        # Extract full content from raw_json when available
        full_content = ""
        try:
            raw = json.loads(row[9]) if row[9] else {}
            full_content = raw.get("content", raw.get("text", ""))
        except (json.JSONDecodeError, TypeError):
            pass

        # Topic: try exact ID match first
        topic_info = topic_by_id.get(post_id, {})
        topic = topic_info.get("topic", "Unknown")

        # Fallback: fuzzy match on content snippet
        if topic == "Unknown" and content_preview:
            preview_lower = content_preview.lower()[:50]
            for _pid, info in topic_by_id.items():
                snippet_lower = (info.get("title_snippet") or "").lower()[:50]
                if snippet_lower and preview_lower and (
                    snippet_lower in preview_lower or preview_lower in snippet_lower
                ):
                    topic = info["topic"]
                    break

        posts.append({
            "id": post_id,
            "content_preview": content_preview,
            "full_content": full_content or content_preview,
            "published_at": published_at,
            "likes": row[3] or 0,
            "comments": row[4] or 0,
            "shares": row[5] or 0,
            "impressions": row[6] or 0,
            "clicks": row[7] or 0,
            "engagement_rate": row[8] or 0.0,
            "topic": topic,
        })

    return posts


# ---------------------------------------------------------------------------
# Analysis: Topic Performance Ranking
# ---------------------------------------------------------------------------

def analyze_topic_performance(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank topics by average engagement rate.

    Returns a dict with:
      - rankings: list sorted by avg_engagement descending
      - total_posts_analyzed: int
      - confidence: float 0.0-1.0
    """
    topic_stats: dict[str, dict[str, Any]] = {}

    for post in posts:
        topic = post["topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {
                "total_engagement": 0.0,
                "count": 0,
                "best_engagement": 0.0,
                "best_post": "",
            }
        stats = topic_stats[topic]
        stats["total_engagement"] += post["engagement_rate"]
        stats["count"] += 1
        if post["engagement_rate"] > stats["best_engagement"]:
            stats["best_engagement"] = post["engagement_rate"]
            stats["best_post"] = post["content_preview"][:80]

    rankings = []
    for topic, stats in topic_stats.items():
        avg = stats["total_engagement"] / stats["count"] if stats["count"] > 0 else 0.0
        rankings.append({
            "topic": topic,
            "avg_engagement": round(avg, 2),
            "post_count": stats["count"],
            "best_post": stats["best_post"],
            "best_engagement": round(stats["best_engagement"], 2),
        })

    rankings.sort(key=lambda x: x["avg_engagement"], reverse=True)
    total_count = sum(s["count"] for s in topic_stats.values())
    return {
        "rankings": rankings,
        "total_posts_analyzed": total_count,
        "confidence": confidence_from_count(total_count),
    }


# ---------------------------------------------------------------------------
# Analysis: Post Length Correlation
# ---------------------------------------------------------------------------

def analyze_post_length(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze content_preview length vs engagement in three buckets.

    Buckets:
      - short: < 100 chars
      - medium: 100-200 chars
      - long: 200+ chars

    Returns a dict with:
      - buckets: list sorted by avg_engagement descending
      - total_posts_analyzed: int
      - confidence: float 0.0-1.0
    """
    buckets: dict[str, dict[str, Any]] = {
        "short": {"total_engagement": 0.0, "count": 0, "label": "<100 chars"},
        "medium": {"total_engagement": 0.0, "count": 0, "label": "100-200 chars"},
        "long": {"total_engagement": 0.0, "count": 0, "label": "200+ chars"},
    }

    for post in posts:
        length = len(post["content_preview"])
        if length < 100:
            bucket_key = "short"
        elif length <= 200:
            bucket_key = "medium"
        else:
            bucket_key = "long"

        buckets[bucket_key]["total_engagement"] += post["engagement_rate"]
        buckets[bucket_key]["count"] += 1

    results = []
    for bucket_key, data in buckets.items():
        avg = data["total_engagement"] / data["count"] if data["count"] > 0 else 0.0
        results.append({
            "bucket": bucket_key,
            "label": data["label"],
            "avg_engagement": round(avg, 2),
            "count": data["count"],
        })

    results.sort(key=lambda x: x["avg_engagement"], reverse=True)
    total_count = sum(b["count"] for b in buckets.values())
    return {
        "buckets": results,
        "total_posts_analyzed": total_count,
        "confidence": confidence_from_count(total_count),
    }


# ---------------------------------------------------------------------------
# Analysis: Opening Pattern Classification
# ---------------------------------------------------------------------------

def classify_opener(text: str) -> str:
    """Classify the opening pattern of a post into one of four categories.

    Categories:
      - question: starts with a question word or contains '?' in first 60 chars
      - stat: opens with a digit or currency/approximate prefix
      - contrarian: opens with a reframe, negation, or challenge
      - declarative: everything else (direct statement)
    """
    opener = text.strip()[:80].lower()
    if not opener:
        return "declarative"

    # Question: starts with question word or has early '?'
    question_starters = (
        "who ", "what ", "why ", "how ", "when ", "where ",
        "is ", "are ", "do ", "does ", "can ", "could ",
        "should ", "would ", "will ",
    )
    if any(opener.startswith(q) for q in question_starters) or "?" in opener[:60]:
        return "question"

    # Stat: opens with a digit or currency/approximate prefix
    if re.match(r"^[\$~]?\d", opener):
        return "stat"

    # Contrarian: negation, challenge, or reframe patterns
    contrarian_starters = (
        "most ", "nobody ", "no one ", "stop ", "forget ",
        "the problem ", "everyone ", "here's what ", "here is what ",
        "unpopular ", "hot take", "controversial",
        "the real ", "the dirty ", "the truth ",
        "you don't ", "you're not ", "you are not ",
    )
    if any(opener.startswith(c) for c in contrarian_starters):
        return "contrarian"

    return "declarative"


def analyze_opener_patterns(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Categorize opening patterns and rank by average engagement.

    Classifies each post opener into: question, stat, contrarian, declarative.

    Returns a dict with:
      - patterns: list sorted by avg_engagement descending, each with up to
        3 examples (selected by highest engagement)
      - total_posts_analyzed: int
      - confidence: float 0.0-1.0
    """
    pattern_stats: dict[str, dict[str, Any]] = {}

    for post in posts:
        text = post.get("full_content") or post.get("content_preview", "")
        pattern = classify_opener(text)
        if pattern not in pattern_stats:
            pattern_stats[pattern] = {
                "total_engagement": 0.0,
                "count": 0,
                "scored_examples": [],
            }
        stats = pattern_stats[pattern]
        stats["total_engagement"] += post["engagement_rate"]
        stats["count"] += 1
        stats["scored_examples"].append(
            (post["engagement_rate"], text[:60])
        )

    results = []
    for pattern, stats in pattern_stats.items():
        avg = stats["total_engagement"] / stats["count"] if stats["count"] > 0 else 0.0
        # Pick top 3 examples by engagement rate
        top_examples = sorted(
            stats["scored_examples"], key=lambda x: x[0], reverse=True
        )
        examples = [ex[1] for ex in top_examples[:3]]
        results.append({
            "pattern": pattern,
            "avg_engagement": round(avg, 2),
            "count": stats["count"],
            "examples": examples,
        })

    results.sort(key=lambda x: x["avg_engagement"], reverse=True)
    total_count = sum(s["count"] for s in pattern_stats.values())
    return {
        "patterns": results,
        "total_posts_analyzed": total_count,
        "confidence": confidence_from_count(total_count),
    }


# ---------------------------------------------------------------------------
# Analysis: Timing (Day-of-Week + Hour-of-Day)
# ---------------------------------------------------------------------------

def _parse_datetime(timestamp: str) -> datetime | None:
    """Try parsing a timestamp string in common ISO formats.

    Handles Z suffix, +00:00, space separators, and fractional seconds.
    Returns a naive datetime or None if unparseable.
    """
    if not timestamp:
        return None

    cleaned = timestamp.replace("+00:00", "").replace("Z", "").replace(" ", "T")

    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    # Last resort: first 19 characters
    try:
        return datetime.strptime(cleaned[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def analyze_timing(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze engagement by day-of-week and hour-of-day.

    Parses published_at timestamps and computes average engagement for each
    day (Monday-Sunday) and each hour (0-23) independently.

    Returns a dict with:
      - best_day, worst_day: str day names or "N/A"
      - best_hour: int (0-23) or -1 if no data
      - by_day: list of day results sorted by engagement
      - by_hour: list of hour results sorted by engagement
      - posts_with_timestamps: int
      - confidence: float 0.0-1.0
    """
    day_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    day_stats: dict[int, dict[str, float]] = {}
    hour_stats: dict[int, dict[str, float]] = {}

    parsed_count = 0
    for post in posts:
        dt = _parse_datetime(post.get("published_at", ""))
        if not dt:
            continue

        parsed_count += 1
        dow = dt.weekday()  # 0=Monday
        hour = dt.hour

        if dow not in day_stats:
            day_stats[dow] = {"total": 0.0, "count": 0.0}
        day_stats[dow]["total"] += post["engagement_rate"]
        day_stats[dow]["count"] += 1

        if hour not in hour_stats:
            hour_stats[hour] = {"total": 0.0, "count": 0.0}
        hour_stats[hour]["total"] += post["engagement_rate"]
        hour_stats[hour]["count"] += 1

    # Day-of-week results
    day_results = []
    for dow in range(7):
        if dow in day_stats and day_stats[dow]["count"] > 0:
            avg = day_stats[dow]["total"] / day_stats[dow]["count"]
            day_results.append({
                "day": day_names[dow],
                "day_index": dow,
                "avg_engagement": round(avg, 2),
                "count": int(day_stats[dow]["count"]),
            })
    day_results.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # Hour-of-day results
    hour_results = []
    for hour in range(24):
        if hour in hour_stats and hour_stats[hour]["count"] > 0:
            avg = hour_stats[hour]["total"] / hour_stats[hour]["count"]
            hour_results.append({
                "hour": hour,
                "avg_engagement": round(avg, 2),
                "count": int(hour_stats[hour]["count"]),
            })
    hour_results.sort(key=lambda x: x["avg_engagement"], reverse=True)

    best_day = day_results[0]["day"] if day_results else "N/A"
    worst_day = day_results[-1]["day"] if day_results else "N/A"
    best_hour = hour_results[0]["hour"] if hour_results else -1

    return {
        "best_day": best_day,
        "worst_day": worst_day,
        "best_hour": best_hour,
        "by_day": day_results,
        "by_hour": hour_results,
        "posts_with_timestamps": parsed_count,
        "confidence": confidence_from_count(parsed_count),
    }


# ---------------------------------------------------------------------------
# Analysis: Overall Summary with Recommendations
# ---------------------------------------------------------------------------

def build_overall_summary(topic_data: dict[str, Any],
                          length_data: dict[str, Any],
                          opener_data: dict[str, Any],
                          timing_data: dict[str, Any]) -> dict[str, Any]:
    """Combine all analyses into an actionable summary with top 3 recommendations.

    Recommendations are prioritized: timing > opener style > length > topic.
    Confidence is the average of all sub-analysis confidences.

    Returns a dict with:
      - recommendations: list of up to 3 actionable strings
      - generated_at: ISO timestamp
      - total_posts_analyzed: int
      - confidence: float 0.0-1.0
      - breakdown: per-analysis confidence scores
    """
    recommendations: list[str] = []

    # 1. Timing recommendation
    if timing_data["best_day"] != "N/A" and timing_data["best_hour"] >= 0:
        hour_label = f"{timing_data['best_hour']}:00"
        recommendations.append(
            f"Post on {timing_data['best_day']}s around {hour_label} "
            f"for highest engagement"
        )
    elif timing_data["best_day"] != "N/A":
        recommendations.append(
            f"Post on {timing_data['best_day']}s for highest engagement"
        )

    # 2. Opener recommendation
    if opener_data.get("patterns"):
        best_pattern = opener_data["patterns"][0]
        if best_pattern["count"] >= 2:
            recommendations.append(
                f"Use {best_pattern['pattern']} openers "
                f"(avg {best_pattern['avg_engagement']}% engagement)"
            )

    # 3. Length recommendation
    if length_data.get("buckets"):
        best_bucket = length_data["buckets"][0]
        if best_bucket["count"] >= 2:
            recommendations.append(
                f"Keep posts {best_bucket['label']} "
                f"({best_bucket['bucket']} length, "
                f"avg {best_bucket['avg_engagement']}% engagement)"
            )

    # 4. Topic recommendation (fill remaining slot)
    if len(recommendations) < 3 and topic_data.get("rankings"):
        top_topic = topic_data["rankings"][0]
        if top_topic["post_count"] >= 2:
            recommendations.append(
                f"Double down on '{top_topic['topic']}' content "
                f"(avg {top_topic['avg_engagement']}% engagement)"
            )

    recommendations = recommendations[:3]

    # Fallback when no data available
    if not recommendations:
        recommendations.append(
            "Not enough data yet. Keep posting and check back after "
            "5+ published posts."
        )

    # Overall confidence: average of sub-analysis confidences
    confidences = [
        topic_data.get("confidence", 0.0),
        length_data.get("confidence", 0.0),
        opener_data.get("confidence", 0.0),
        timing_data.get("confidence", 0.0),
    ]
    avg_confidence = sum(confidences) / len(confidences)

    return {
        "recommendations": recommendations,
        "generated_at": datetime.now().isoformat(),
        "total_posts_analyzed": topic_data.get("total_posts_analyzed", 0),
        "confidence": round(avg_confidence, 2),
        "breakdown": {
            "topic_confidence": topic_data.get("confidence", 0.0),
            "length_confidence": length_data.get("confidence", 0.0),
            "opener_confidence": opener_data.get("confidence", 0.0),
            "timing_confidence": timing_data.get("confidence", 0.0),
        },
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_insights(db: sqlite3.Connection, insights: dict[str, dict[str, Any]],
                   period_days: int) -> int:
    """Write all insight results to the content_insights table.

    Inserts one row per insight_type with a fresh UUID as primary key.
    Returns the number of rows inserted.
    """
    now = datetime.now().isoformat()
    count = 0

    for insight_type, data in insights.items():
        row_id = str(uuid.uuid4())
        confidence = data.get("confidence", 0.0)
        db.execute(
            """INSERT INTO content_insights
               (id, generated_at, insight_type, data_json, period_days, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (row_id, now, insight_type, json.dumps(data, default=str),
             period_days, confidence),
        )
        count += 1

    db.commit()
    return count


# ---------------------------------------------------------------------------
# Text report formatting
# ---------------------------------------------------------------------------

def format_text_report(insights: dict[str, dict[str, Any]]) -> str:
    """Format insights as a human-readable text report for terminal output."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("CONTENT INSIGHTS REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)

    # --- Topic Rankings ---
    topic = insights.get("topic_ranking", {})
    rankings = topic.get("rankings", [])
    lines.append(
        f"\n--- Topic Performance "
        f"({topic.get('total_posts_analyzed', 0)} posts) ---"
    )
    if rankings:
        for i, r in enumerate(rankings, 1):
            lines.append(
                f"  {i}. {r['topic']}: {r['avg_engagement']}% avg "
                f"({r['post_count']} posts, best: {r['best_engagement']}%)"
            )
    else:
        lines.append("  No topic data available")

    # --- Length Correlation ---
    length = insights.get("length_correlation", {})
    buckets = length.get("buckets", [])
    lines.append("\n--- Post Length vs Engagement ---")
    if buckets:
        for b in buckets:
            bar = (
                "#" * min(20, int(b["avg_engagement"] * 2))
                if b["avg_engagement"] > 0 else "-"
            )
            lines.append(
                f"  {b['bucket']:>8s} ({b['label']:>12s}): "
                f"{b['avg_engagement']}% avg [{b['count']} posts] {bar}"
            )
    else:
        lines.append("  No length data available")

    # --- Opener Analysis ---
    opener = insights.get("opener_analysis", {})
    patterns = opener.get("patterns", [])
    lines.append("\n--- Opening Pattern Analysis ---")
    if patterns:
        for p in patterns:
            lines.append(
                f"  {p['pattern']:>12s}: "
                f"{p['avg_engagement']}% avg ({p['count']} posts)"
            )
            for ex in p.get("examples", [])[:2]:
                lines.append(f'               "{ex}..."')
    else:
        lines.append("  No opener data available")

    # --- Timing Analysis ---
    timing = insights.get("timing_analysis", {})
    ts_count = timing.get("posts_with_timestamps", 0)
    lines.append(f"\n--- Timing Analysis ({ts_count} posts with timestamps) ---")
    if timing.get("best_day") and timing["best_day"] != "N/A":
        lines.append(f"  Best day:  {timing['best_day']}")
        lines.append(f"  Worst day: {timing['worst_day']}")
        if timing.get("best_hour", -1) >= 0:
            lines.append(f"  Best hour: {timing['best_hour']}:00")
        by_day = timing.get("by_day", [])
        if by_day:
            lines.append("  By day:")
            for d in by_day:
                bar = (
                    "#" * min(15, int(d["avg_engagement"] * 2))
                    if d["avg_engagement"] > 0 else "-"
                )
                lines.append(
                    f"    {d['day']:>10s}: {d['avg_engagement']}% "
                    f"({d['count']} posts) {bar}"
                )
    else:
        lines.append("  No timing data available")

    # --- Summary & Recommendations ---
    summary = insights.get("overall_summary", {})
    recs = summary.get("recommendations", [])
    lines.append(f"\n{'=' * 60}")
    lines.append("RECOMMENDATIONS")
    lines.append("=" * 60)
    for i, rec in enumerate(recs, 1):
        lines.append(f"  {i}. {rec}")
    conf = summary.get("confidence", 0.0)
    lines.append(f"\nOverall confidence: {conf:.0%}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_analysis(period_days: int = DEFAULT_PERIOD_DAYS) -> dict[str, dict[str, Any]]:
    """Execute all analyses and return the full insights dict.

    Opens both databases, loads joined post data, runs each analysis
    function, and returns the combined results keyed by insight_type.
    Gracefully returns empty-data insights when tables are empty.
    """
    analytics_db = sqlite3.connect(str(ANALYTICS_DB_PATH))
    claudeclaw_db = sqlite3.connect(str(CLAUDECLAW_DB_PATH))

    try:
        posts = load_post_data(analytics_db, claudeclaw_db)
    finally:
        claudeclaw_db.close()
        analytics_db.close()

    topic_data = analyze_topic_performance(posts)
    length_data = analyze_post_length(posts)
    opener_data = analyze_opener_patterns(posts)
    timing_data = analyze_timing(posts)
    summary_data = build_overall_summary(
        topic_data, length_data, opener_data, timing_data,
    )

    return {
        "topic_ranking": topic_data,
        "length_correlation": length_data,
        "opener_analysis": opener_data,
        "timing_analysis": timing_data,
        "overall_summary": summary_data,
    }


def main() -> None:
    """Entry point. Handles --dry-run and --json CLI flags."""
    dry_run = "--dry-run" in sys.argv
    json_mode = "--json" in sys.argv

    STORE_DIR.mkdir(parents=True, exist_ok=True)

    if not ANALYTICS_DB_PATH.exists():
        print(
            f"Analytics database not found: {ANALYTICS_DB_PATH}",
            file=sys.stderr,
        )
        print(
            "Run starscream_analytics.py first to initialize it.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not CLAUDECLAW_DB_PATH.exists():
        print(
            f"ClaudeClaw database not found: {CLAUDECLAW_DB_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[{datetime.now().isoformat()}] Running content insights analysis...")

    insights = run_analysis()

    post_count = insights.get("topic_ranking", {}).get("total_posts_analyzed", 0)
    print(f"  Posts analyzed: {post_count}")

    # JSON output mode: dump and exit
    if json_mode:
        print(json.dumps(insights, indent=2, default=str))
        return

    # Text report to stdout
    report = format_text_report(insights)
    print(report)

    if dry_run:
        print("[DRY RUN] Results not stored to database.")
        return

    # Store results
    db = sqlite3.connect(str(ANALYTICS_DB_PATH))
    init_insights_table(db)
    rows_stored = store_insights(db, insights, DEFAULT_PERIOD_DAYS)
    db.close()

    print(f"Stored {rows_stored} insight rows to {ANALYTICS_DB_PATH}")


if __name__ == "__main__":
    main()
