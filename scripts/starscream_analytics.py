#!/usr/bin/env python3
"""
Starscream Analytics Collector - L5 Content Feedback Loop
Collects LinkedIn analytics from Late API, stores in SQLite, sends daily summary.
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
ENV_FILE = Path(os.path.expanduser("~/.env.shared"))

LATE_API_BASE = "https://getlate.dev/api/v1"
LINKEDIN_ACCOUNT_ID = "69307d78f43160a0bc999f1a"


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
    return keys


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
            return json.loads(resp.read().decode("utf-8"))
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
            clicks INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0.0,
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


def collect_post_analytics(db: sqlite3.Connection, api_key: str) -> list[dict]:
    """Fetch post analytics from Late API and store."""
    data = late_api_get(f"/analytics?accountId={LINKEDIN_ACCOUNT_ID}", api_key)
    if not data:
        return []

    now = datetime.now().isoformat()
    posts = data if isinstance(data, list) else data.get("posts", data.get("data", []))

    stored = []
    for post in posts:
        post_id = post.get("id") or post.get("postId") or ""
        if not post_id:
            continue

        content = post.get("content", post.get("text", ""))[:100]
        published = post.get("publishedAt", post.get("createdAt", ""))
        likes = post.get("likes", post.get("reactions", 0)) or 0
        comments = post.get("comments", 0) or 0
        shares = post.get("shares", post.get("reposts", 0)) or 0
        impressions = post.get("impressions", post.get("views", 0)) or 0
        clicks = post.get("clicks", 0) or 0

        engagement = 0.0
        if impressions > 0:
            engagement = ((likes + comments + shares + clicks) / impressions) * 100

        db.execute(
            """INSERT OR REPLACE INTO post_metrics
               (id, collected_at, content_preview, published_at,
                likes, comments, shares, impressions, clicks,
                engagement_rate, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (post_id, now, content, published,
             likes, comments, shares, impressions, clicks,
             round(engagement, 2), json.dumps(post)),
        )
        stored.append({
            "id": post_id, "content": content[:50],
            "likes": likes, "comments": comments, "impressions": impressions,
            "engagement": round(engagement, 2),
        })

    db.commit()
    return stored


def collect_follower_analytics(db: sqlite3.Connection, api_key: str) -> dict | None:
    """Fetch follower analytics from Late API and store."""
    data = late_api_get(f"/analytics/followers?accountId={LINKEDIN_ACCOUNT_ID}", api_key)
    if not data:
        return None

    now = datetime.now().isoformat()
    total = data.get("totalFollowers", data.get("total", 0)) or 0
    new_24h = data.get("newFollowers", data.get("gained", 0)) or 0

    db.execute(
        """INSERT OR REPLACE INTO follower_metrics
           (collected_at, total_followers, new_followers_24h, raw_json)
           VALUES (?, ?, ?, ?)""",
        (now, total, new_24h, json.dumps(data)),
    )
    db.commit()
    return {"total": total, "new_24h": new_24h}


def collect_aggregate(db: sqlite3.Connection, api_key: str) -> dict | None:
    """Fetch aggregate analytics from Late API and store daily summary."""
    data = late_api_get(
        f"/analytics/linkedin/aggregate?accountId={LINKEDIN_ACCOUNT_ID}", api_key
    )
    if not data:
        return None

    today = datetime.now().strftime("%Y-%m-%d")

    total_posts = data.get("totalPosts", 0) or 0
    total_likes = data.get("totalLikes", data.get("totalReactions", 0)) or 0
    total_comments = data.get("totalComments", 0) or 0
    total_shares = data.get("totalShares", data.get("totalReposts", 0)) or 0
    total_impressions = data.get("totalImpressions", data.get("totalViews", 0)) or 0
    avg_engagement = data.get("averageEngagementRate", 0.0) or 0.0

    # Get latest follower count
    follower_row = db.execute(
        "SELECT total_followers FROM follower_metrics ORDER BY collected_at DESC LIMIT 1"
    ).fetchone()
    follower_count = follower_row[0] if follower_row else 0

    db.execute(
        """INSERT OR REPLACE INTO daily_aggregate
           (date, total_posts, total_likes, total_comments, total_shares,
            total_impressions, avg_engagement_rate, follower_count, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (today, total_posts, total_likes, total_comments, total_shares,
         total_impressions, avg_engagement, follower_count, json.dumps(data)),
    )
    db.commit()
    return {
        "posts": total_posts, "likes": total_likes, "comments": total_comments,
        "impressions": total_impressions, "engagement": round(avg_engagement, 2),
        "followers": follower_count,
    }


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
        lines.append("<b>Today's Summary</b>")
        lines.append(f"  Posts: {agg[1]} | Likes: {agg[2]} | Comments: {agg[3]}")
        lines.append(f"  Impressions: {agg[5]} | Engagement: {agg[6]:.1f}%")
        lines.append(f"  Followers: {agg[7]}")
    else:
        lines.append("No aggregate data for today")

    # Top 3 recent posts by engagement
    top_posts = db.execute(
        """SELECT content_preview, likes, comments, impressions, engagement_rate
           FROM post_metrics
           WHERE collected_at > ?
           GROUP BY id
           HAVING collected_at = MAX(collected_at)
           ORDER BY engagement_rate DESC
           LIMIT 3""",
        ((now - timedelta(days=7)).isoformat(),)
    ).fetchall()

    if top_posts:
        lines.append("\n<b>Top Posts (7d)</b>")
        for i, p in enumerate(top_posts, 1):
            preview = (p[0] or "")[:40]
            lines.append(f"  {i}. {preview}...")
            lines.append(f"     {p[1]} likes, {p[2]} comments, {p[3]} views ({p[4]:.1f}%)")

    # Follower trend (last 7 days)
    follower_history = db.execute(
        """SELECT collected_at, total_followers FROM follower_metrics
           ORDER BY collected_at DESC LIMIT 7"""
    ).fetchall()

    if len(follower_history) >= 2:
        latest = follower_history[0][1]
        oldest = follower_history[-1][1]
        delta = latest - oldest
        direction = "+" if delta >= 0 else ""
        lines.append(f"\n<b>Follower Trend</b>: {direction}{delta} over last {len(follower_history)} snapshots")

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

    # Collect all data
    posts = collect_post_analytics(db, api_key)
    followers = collect_follower_analytics(db, api_key)
    aggregate = collect_aggregate(db, api_key)

    print(f"  Posts collected: {len(posts)}")
    print(f"  Followers: {followers}")
    print(f"  Aggregate: {aggregate}")

    if dry_run:
        print("\n=== DRY RUN - Summary ===")
        print(build_summary(db))
        db.close()
        return

    # Send summary
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
