#!/usr/bin/env python3
"""
Starscream Analytics Collector - L5 Content Feedback Loop
Collects LinkedIn analytics from Late API, stores in SQLite, sends daily summary.
Generates a performance brief for Starscream's content feedback loop.
Designed for cron -- no Claude/LLM dependency.

Usage:
  python3 starscream_analytics.py              # Normal run
  python3 starscream_analytics.py --dry-run    # Print data, don't store or send
  python3 starscream_analytics.py --summary    # Just print latest summary

Cron:
  0 18 * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/starscream_analytics.py >> /tmp/starscream_analytics.log 2>&1
"""
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
DB_PATH = STORE_DIR / "starscream_analytics.db"
BRIEF_PATH = STORE_DIR / "starscream_performance_brief.md"
ENV_FILE = Path(os.path.expanduser("~/.env.shared"))

LATE_API_BASE = "https://getlate.dev/api/v1"
LINKEDIN_ACCOUNT_ID = "69a62fa6dc8cab9432b3af43"


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
            if key in ("LATE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                keys[key] = val
    # Env vars override file
    for k in ("LATE_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if os.environ.get(k):
            keys[k] = os.environ[k]
    # Strip whitespace from all values (prevents auth failures)
    return {k: v.strip() for k, v in keys.items()}


def late_api_get(endpoint: str, api_key: str) -> dict | None:
    """GET request to Late API. Returns parsed JSON or None on failure."""
    url = f"{LATE_API_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            if body.startswith("<!DOCTYPE") or body.startswith("<html"):
                print(f"Late API returned HTML ({endpoint}), skipping", file=sys.stderr)
                return None
            return json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Late API error ({endpoint}): {e}", file=sys.stderr)
        return None


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


def init_db(db: sqlite3.Connection):
    """Create analytics tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS post_metrics (
            id TEXT,
            collected_at TEXT NOT NULL,
            platform TEXT DEFAULT 'linkedin',
            content_preview TEXT,
            published_at TEXT,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0,
            platform_url TEXT,
            raw_json TEXT,
            PRIMARY KEY (id, collected_at)
        );

        CREATE TABLE IF NOT EXISTS follower_metrics (
            collected_at TEXT PRIMARY KEY,
            total_followers INTEGER DEFAULT 0,
            new_followers_24h INTEGER DEFAULT 0,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_aggregate (
            date TEXT PRIMARY KEY,
            total_posts INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            avg_engagement_rate REAL DEFAULT 0.0,
            follower_count INTEGER DEFAULT 0,
            raw_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_post_metrics_published
            ON post_metrics(published_at);
    """)


# --- Collectors (use only verified Late API endpoints) ---


def collect_post_analytics(db: sqlite3.Connection, api_key: str) -> list[dict]:
    """Fetch post analytics from GET /analytics?accountId=... and store."""
    data = late_api_get(f"/analytics?accountId={LINKEDIN_ACCOUNT_ID}", api_key)
    if not data:
        return []

    now = datetime.now().isoformat()
    posts = data.get("posts", [])

    stored = []
    for post in posts:
        post_id = post.get("_id", "")
        if not post_id:
            continue

        content = post.get("content", "")[:200]
        published = post.get("publishedAt", "")
        analytics = post.get("analytics", {})
        platform_url = post.get("platformPostUrl", "")

        likes = analytics.get("likes", 0) or 0
        comments = analytics.get("comments", 0) or 0
        shares = analytics.get("shares", 0) or 0
        impressions = analytics.get("impressions", 0) or 0
        reach = analytics.get("reach", 0) or 0
        clicks = analytics.get("clicks", 0) or 0
        saves = analytics.get("saves", 0) or 0
        engagement_rate = analytics.get("engagementRate", 0.0) or 0.0

        db.execute(
            """INSERT OR REPLACE INTO post_metrics
               (id, collected_at, content_preview, published_at,
                likes, comments, shares, impressions, reach, clicks, saves,
                engagement_rate, platform_url, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (post_id, now, content, published,
             likes, comments, shares, impressions, reach, clicks, saves,
             round(engagement_rate, 2), platform_url, json.dumps(post)),
        )
        stored.append({
            "id": post_id, "content": content[:60],
            "likes": likes, "comments": comments, "shares": shares,
            "impressions": impressions, "reach": reach,
            "engagement": round(engagement_rate, 2),
        })

    db.commit()
    return stored


def collect_follower_analytics(db: sqlite3.Connection, api_key: str) -> dict | None:
    """Extract follower count from GET /accounts and store."""
    data = late_api_get("/accounts", api_key)
    if not data:
        return None

    accounts = data.get("accounts", [])
    account = next(
        (a for a in accounts if a.get("_id") == LINKEDIN_ACCOUNT_ID), None
    )
    if not account:
        return None

    now = datetime.now().isoformat()
    total = account.get("followersCount", 0) or 0

    # Calculate new followers since last snapshot
    prev = db.execute(
        "SELECT total_followers FROM follower_metrics ORDER BY collected_at DESC LIMIT 1"
    ).fetchone()
    new_24h = total - prev[0] if prev else 0

    db.execute(
        """INSERT OR REPLACE INTO follower_metrics
           (collected_at, total_followers, new_followers_24h, raw_json)
           VALUES (?, ?, ?, ?)""",
        (now, total, new_24h, json.dumps(account)),
    )
    db.commit()
    return {"total": total, "new_24h": new_24h}


def compute_daily_aggregate(db: sqlite3.Connection, follower_count: int) -> dict | None:
    """Compute daily aggregate from stored post_metrics (no API call needed)."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Get latest snapshot of each post from the most recent collection
    latest_collection = db.execute(
        "SELECT MAX(collected_at) FROM post_metrics"
    ).fetchone()
    if not latest_collection or not latest_collection[0]:
        return None

    rows = db.execute(
        """SELECT COUNT(*), SUM(likes), SUM(comments), SUM(shares),
                  SUM(impressions), AVG(engagement_rate)
           FROM post_metrics
           WHERE collected_at = ?""",
        (latest_collection[0],),
    ).fetchone()

    if not rows or rows[0] == 0:
        return None

    total_posts, total_likes, total_comments, total_shares, total_impressions, avg_eng = rows

    db.execute(
        """INSERT OR REPLACE INTO daily_aggregate
           (date, total_posts, total_likes, total_comments, total_shares,
            total_impressions, avg_engagement_rate, follower_count, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (today, total_posts, total_likes or 0, total_comments or 0,
         total_shares or 0, total_impressions or 0,
         round(avg_eng or 0.0, 2), follower_count,
         json.dumps({"computed_from": "post_metrics", "collection": latest_collection[0]})),
    )
    db.commit()
    return {
        "posts": total_posts,
        "likes": total_likes or 0,
        "comments": total_comments or 0,
        "shares": total_shares or 0,
        "impressions": total_impressions or 0,
        "engagement": round(avg_eng or 0.0, 2),
        "followers": follower_count,
    }


# --- Summary & Performance Brief ---


def build_summary(db: sqlite3.Connection) -> str:
    """Build a Telegram-friendly analytics summary."""
    now = datetime.now()
    lines = [f"<b>Starscream Analytics -- {now.strftime('%a %b %d')}</b>\n"]

    # Today's aggregate
    today = now.strftime("%Y-%m-%d")
    agg = db.execute(
        "SELECT * FROM daily_aggregate WHERE date = ?", (today,)
    ).fetchone()
    if agg:
        lines.append("<b>Summary</b>")
        lines.append(f"  Posts: {agg[1]} | Likes: {agg[2]} | Comments: {agg[3]}")
        lines.append(f"  Impressions: {agg[5]} | Engagement: {agg[6]:.1f}%")
        lines.append(f"  Followers: {agg[7]}")
    else:
        # Fallback: show latest aggregate from any day
        agg = db.execute(
            "SELECT * FROM daily_aggregate ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if agg:
            lines.append(f"<b>Latest Summary ({agg[0]})</b>")
            lines.append(f"  Posts: {agg[1]} | Likes: {agg[2]} | Comments: {agg[3]}")
            lines.append(f"  Impressions: {agg[5]} | Engagement: {agg[6]:.1f}%")
            lines.append(f"  Followers: {agg[7]}")
        else:
            lines.append("No aggregate data yet")

    # All posts ranked by engagement (latest snapshot per post)
    posts = db.execute(
        """SELECT id, content_preview, likes, comments, shares,
                  impressions, reach, engagement_rate, published_at, platform_url
           FROM post_metrics
           WHERE collected_at = (SELECT MAX(collected_at) FROM post_metrics)
           ORDER BY engagement_rate DESC"""
    ).fetchall()

    if posts:
        lines.append(f"\n<b>Post Performance ({len(posts)} posts)</b>")
        for i, p in enumerate(posts, 1):
            preview = (p[1] or "")[:50]
            lines.append(f"  {i}. {preview}...")
            lines.append(
                f"     {p[5]} impr | {p[6]} reach | {p[2]} likes | "
                f"{p[3]} comments | {p[4]} shares | {p[7]:.1f}%"
            )

    # Follower trend
    follower_history = db.execute(
        """SELECT collected_at, total_followers FROM follower_metrics
           ORDER BY collected_at DESC LIMIT 7"""
    ).fetchall()

    if len(follower_history) >= 2:
        latest = follower_history[0][1]
        oldest = follower_history[-1][1]
        delta = latest - oldest
        direction = "+" if delta >= 0 else ""
        lines.append(
            f"\n<b>Follower Trend</b>: {latest} total "
            f"({direction}{delta} over {len(follower_history)} snapshots)"
        )
    elif follower_history:
        lines.append(f"\n<b>Followers</b>: {follower_history[0][1]}")

    return "\n".join(lines)


def build_performance_brief(db: sqlite3.Connection) -> str:
    """Generate a Markdown performance brief for Starscream's content loop."""
    now = datetime.now()
    lines = [
        "# Starscream Performance Brief",
        f"Auto-generated: {now.strftime('%Y-%m-%d %H:%M')} CST",
        "",
        "Read this before generating new content. Use these insights to pick topics and adjust style.",
        "",
    ]

    # Get latest snapshot of all posts
    posts = db.execute(
        """SELECT id, content_preview, likes, comments, shares,
                  impressions, reach, engagement_rate, published_at
           FROM post_metrics
           WHERE collected_at = (SELECT MAX(collected_at) FROM post_metrics)
           ORDER BY engagement_rate DESC"""
    ).fetchall()

    if not posts:
        lines.append("## No Data Yet")
        lines.append("No posts have been tracked. Keep posting and check back after the next analytics run.")
        return "\n".join(lines)

    # Overall stats
    total_impressions = sum(p[5] for p in posts)
    total_likes = sum(p[2] for p in posts)
    total_comments = sum(p[3] for p in posts)
    avg_engagement = sum(p[7] for p in posts) / len(posts) if posts else 0

    follower_row = db.execute(
        "SELECT total_followers FROM follower_metrics ORDER BY collected_at DESC LIMIT 1"
    ).fetchone()
    followers = follower_row[0] if follower_row else 0

    lines.append("## Account Overview")
    lines.append(f"- Posts tracked: {len(posts)}")
    lines.append(f"- Total impressions: {total_impressions}")
    lines.append(f"- Total likes: {total_likes} | Comments: {total_comments}")
    lines.append(f"- Average engagement rate: {avg_engagement:.1f}%")
    lines.append(f"- Followers: {followers}")
    lines.append("")

    # Top performers
    lines.append("## Top Performing Posts")
    for i, p in enumerate(posts[:3], 1):
        preview = (p[1] or "")[:80]
        lines.append(f"### {i}. ({p[7]:.1f}% engagement, {p[5]} impressions)")
        lines.append(f"> {preview}...")
        lines.append(f"- Likes: {p[2]} | Comments: {p[3]} | Shares: {p[4]} | Reach: {p[6]}")
        lines.append("")

    # Bottom performers (if more than 3 posts)
    if len(posts) > 3:
        lines.append("## Lowest Performing Posts")
        for i, p in enumerate(posts[-2:], 1):
            preview = (p[1] or "")[:80]
            lines.append(f"### {i}. ({p[7]:.1f}% engagement, {p[5]} impressions)")
            lines.append(f"> {preview}...")
            lines.append(f"- Likes: {p[2]} | Comments: {p[3]} | Shares: {p[4]} | Reach: {p[6]}")
            lines.append("")

    # Topic analysis (infer topic from content preview keywords)
    topic_map = {
        "healthcare": ["healthcare", "hospital", "nurse", "patient", "clinical", "ehr", "medical", "bedside"],
        "supply chain": ["supply chain", "scm", "procurement", "logistics", "shipment", "inventory", "warehouse"],
        "ai security": ["security", "audit", "observability", "vulnerability", "forensic", "kill switch", "compliance"],
        "ai agents": ["agent", "autonomous", "agentic", "level 5", "dark factory", "automation"],
        "m2ai / personal": ["m2ai", "snow-town", "st metro", "my ", "i built", "i shipped", "this week"],
    }

    topic_stats: dict[str, list[dict]] = {}
    for p in posts:
        content_lower = (p[1] or "").lower()
        matched = False
        for topic, keywords in topic_map.items():
            if any(kw in content_lower for kw in keywords):
                topic_stats.setdefault(topic, []).append({
                    "engagement": p[7], "impressions": p[5], "likes": p[2],
                })
                matched = True
                break
        if not matched:
            topic_stats.setdefault("other", []).append({
                "engagement": p[7], "impressions": p[5], "likes": p[2],
            })

    if topic_stats:
        lines.append("## Topic Performance")
        lines.append("| Topic | Posts | Avg Engagement | Avg Impressions | Total Likes |")
        lines.append("|-------|-------|---------------|-----------------|-------------|")
        ranked = sorted(
            topic_stats.items(),
            key=lambda x: sum(p["engagement"] for p in x[1]) / len(x[1]),
            reverse=True,
        )
        for topic, stats in ranked:
            avg_eng = sum(s["engagement"] for s in stats) / len(stats)
            avg_imp = sum(s["impressions"] for s in stats) / len(stats)
            total_l = sum(s["likes"] for s in stats)
            lines.append(f"| {topic} | {len(stats)} | {avg_eng:.1f}% | {avg_imp:.0f} | {total_l} |")
        lines.append("")

    # Content insights
    lines.append("## Content Guidance")

    if posts and posts[0][7] > 0:
        best = posts[0]
        best_preview = (best[1] or "")[:60]
        lines.append(f"- **Best performing content** starts with: \"{best_preview}...\"")

    # Check what engagement patterns work
    posts_with_likes = [p for p in posts if p[2] > 0]
    posts_without_likes = [p for p in posts if p[2] == 0]
    if posts_with_likes and posts_without_likes:
        avg_imp_liked = sum(p[5] for p in posts_with_likes) / len(posts_with_likes)
        avg_imp_unliked = sum(p[5] for p in posts_without_likes) / len(posts_without_likes)
        lines.append(
            f"- Posts with likes avg {avg_imp_liked:.0f} impressions vs "
            f"{avg_imp_unliked:.0f} for posts without"
        )

    # Posting time analysis (from published_at timestamps)
    hour_stats: dict[int, list[float]] = {}
    for p in posts:
        pub = p[8]
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                # Convert UTC to CST (UTC-6)
                cst_hour = (dt.hour - 6) % 24
                hour_stats.setdefault(cst_hour, []).append(p[7])
            except (ValueError, AttributeError):
                pass

    if hour_stats:
        best_hour = max(hour_stats.items(), key=lambda x: sum(x[1]) / len(x[1]))
        lines.append(f"- Best posting hour (CST): {best_hour[0]}:00 ({sum(best_hour[1]) / len(best_hour[1]):.1f}% avg engagement)")

    # Follower growth trend
    follower_history = db.execute(
        """SELECT collected_at, total_followers FROM follower_metrics
           ORDER BY collected_at DESC LIMIT 14"""
    ).fetchall()

    if len(follower_history) >= 2:
        latest = follower_history[0][1]
        oldest = follower_history[-1][1]
        delta = latest - oldest
        days = max(1, (datetime.fromisoformat(follower_history[0][0]) -
                       datetime.fromisoformat(follower_history[-1][0])).days)
        rate = delta / days if days > 0 else 0
        direction = "+" if delta >= 0 else ""
        lines.append(f"- Follower growth: {direction}{delta} ({direction}{rate:.1f}/day)")

    lines.append("")
    lines.append("## Action Items for Next Post")
    if ranked:
        best_topic = ranked[0][0]
        worst_topic = ranked[-1][0] if len(ranked) > 1 else None
        lines.append(f"- **Lean into**: {best_topic} (highest engagement)")
        if worst_topic and worst_topic != best_topic:
            lines.append(f"- **Rethink approach for**: {worst_topic} (lowest engagement)")
    lines.append("- Check if posts with questions vs. declarative closers perform differently")
    lines.append("- Monitor reach-to-impression ratio for algorithm signal strength")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv
    summary_only = "--summary" in sys.argv

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    init_db(db)

    if summary_only:
        print(build_summary(db))
        db.close()
        return

    env = load_env()
    api_key = env.get("LATE_API_KEY", "")
    if not api_key:
        print("Missing LATE_API_KEY in ~/.env.shared", file=sys.stderr)
        sys.exit(1)

    print(f"[{datetime.now().isoformat()}] Collecting Starscream analytics...")

    # Collect from Late API (only verified endpoints)
    posts = collect_post_analytics(db, api_key)
    followers = collect_follower_analytics(db, api_key)
    follower_count = followers["total"] if followers else 0

    # Compute aggregate locally from stored post data
    aggregate = compute_daily_aggregate(db, follower_count)

    print(f"  Posts collected: {len(posts)}")
    print(f"  Followers: {followers}")
    print(f"  Aggregate: {aggregate}")

    # Generate performance brief for Starscream feedback loop
    brief = build_performance_brief(db)
    BRIEF_PATH.write_text(brief)
    print(f"  Performance brief written to {BRIEF_PATH}")

    if dry_run:
        print("\n=== DRY RUN - Summary ===")
        print(build_summary(db))
        print("\n=== Performance Brief ===")
        print(brief)
        db.close()
        return

    # Send summary to Telegram
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        summary = build_summary(db)
        if len(summary) > 4000:
            summary = summary[:3997] + "..."
        if send_telegram(token, chat_id, summary):
            print("Analytics summary sent to Telegram")
        else:
            print("Failed to send summary", file=sys.stderr)
    else:
        print("No Telegram credentials, printing summary:")
        print(build_summary(db))

    db.close()


if __name__ == "__main__":
    main()
