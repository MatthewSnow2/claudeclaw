#!/usr/bin/env python3
"""
Image Diversity Reporter -- Analyze prompt history and suggest fresh directions.

Reads the image_prompts table from starscream_analytics.db and reports on
prompt diversity, repeated patterns, and suggests new visual directions.

Usage:
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 image_diversity.py
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 image_diversity.py --last 20
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 image_diversity.py --suggest --topic "Healthcare AI"

Returns:
  Human-readable diversity report to stdout.
  JSON mode with --json flag.
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# --- Config ---
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
DB_PATH = STORE_DIR / "starscream_analytics.db"

# Visual element categories for analysis
COLOR_WORDS = {
    "blue", "red", "green", "purple", "coral", "indigo", "teal", "orange",
    "gold", "silver", "white", "black", "navy", "cyan", "magenta", "amber",
    "emerald", "crimson", "violet",
}

STYLE_WORDS = {
    "abstract", "geometric", "futuristic", "minimal", "photorealistic",
    "isometric", "flat", "3d", "watercolor", "sketch", "neon", "holographic",
    "vintage", "retro", "modern", "corporate", "cinematic", "editorial",
}

SUBJECT_WORDS = {
    "robot", "network", "circuit", "brain", "data", "dashboard", "factory",
    "warehouse", "hospital", "worker", "agent", "pipeline", "flow", "chart",
    "graph", "node", "gear", "cog", "screen", "interface", "hand", "eye",
    "globe", "city", "building", "cloud", "server", "chip", "processor",
}

# Alternative visual directions to suggest
FRESH_DIRECTIONS = [
    "Paper-cut layered illustration style with warm earth tones",
    "Monochrome blueprint/schematic aesthetic with white lines on deep blue",
    "Collage-style mixing photography textures with vector overlays",
    "Soft watercolor gradients with hand-drawn line elements",
    "Bold pop-art style with halftone dots and primary colors",
    "Minimalist iconographic style, single object on clean background",
    "Isometric 3D scene with pastel colors and soft shadows",
    "Dark mode dashboard aesthetic with accent color highlights",
    "Nature-tech hybrid: organic forms merging with digital patterns",
    "Vintage infographic style with muted retro color palette",
    "Glass morphism effect with frosted translucent layers",
    "Topographic/contour map style with gradient line work",
]


def analyze_prompts(db: sqlite3.Connection, limit: int = 10) -> dict:
    """Analyze recent prompts for diversity patterns."""
    rows = db.execute(
        """SELECT id, created_at, topic, prompt_text, model_used, diversity_score,
                  qa_score, qa_passed
           FROM image_prompts
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    if not rows:
        return {
            "total_prompts": 0,
            "analysis": "No prompts logged yet.",
            "color_freq": {},
            "style_freq": {},
            "subject_freq": {},
            "topic_freq": {},
            "avg_diversity": 0.0,
            "avg_qa": 0.0,
            "qa_pass_rate": 0.0,
        }

    # Extract frequency data
    all_words = []
    topics = []
    diversity_scores = []
    qa_scores = []
    qa_passed_count = 0

    for row in rows:
        prompt_words = set(row[3].lower().split())
        all_words.extend(prompt_words)
        if row[2]:
            topics.append(row[2])
        if row[5]:
            diversity_scores.append(row[5])
        if row[6]:
            qa_scores.append(row[6])
        if row[7]:
            qa_passed_count += 1

    word_set = set(all_words)

    color_freq = Counter(w for w in all_words if w in COLOR_WORDS)
    style_freq = Counter(w for w in all_words if w in STYLE_WORDS)
    subject_freq = Counter(w for w in all_words if w in SUBJECT_WORDS)
    topic_freq = Counter(topics)

    # Identify overused elements
    overused_colors = [c for c, count in color_freq.most_common(3) if count >= limit * 0.4]
    overused_styles = [s for s, count in style_freq.most_common(3) if count >= limit * 0.4]
    overused_subjects = [s for s, count in subject_freq.most_common(3) if count >= limit * 0.4]

    # Identify unused elements
    unused_colors = sorted(COLOR_WORDS - word_set)
    unused_styles = sorted(STYLE_WORDS - word_set)
    unused_subjects = sorted(SUBJECT_WORDS - word_set)

    return {
        "total_prompts": len(rows),
        "color_freq": dict(color_freq.most_common()),
        "style_freq": dict(style_freq.most_common()),
        "subject_freq": dict(subject_freq.most_common()),
        "topic_freq": dict(topic_freq.most_common()),
        "overused_colors": overused_colors,
        "overused_styles": overused_styles,
        "overused_subjects": overused_subjects,
        "unused_colors": unused_colors[:5],
        "unused_styles": unused_styles[:5],
        "unused_subjects": unused_subjects[:5],
        "avg_diversity": round(sum(diversity_scores) / len(diversity_scores), 2) if diversity_scores else 0.0,
        "avg_qa": round(sum(qa_scores) / len(qa_scores), 1) if qa_scores else 0.0,
        "qa_pass_rate": round(qa_passed_count / len(rows) * 100, 1) if rows else 0.0,
    }


def suggest_direction(analysis: dict, topic: str = "") -> list[str]:
    """Suggest fresh visual directions based on analysis."""
    suggestions = []

    # Suggest unused colors
    if analysis.get("unused_colors"):
        colors = ", ".join(analysis["unused_colors"][:3])
        suggestions.append(f"Try unused color palette: {colors}")

    # Suggest unused styles
    if analysis.get("unused_styles"):
        styles = ", ".join(analysis["unused_styles"][:3])
        suggestions.append(f"Try unused visual style: {styles}")

    # Warn about overuse
    if analysis.get("overused_colors"):
        colors = ", ".join(analysis["overused_colors"])
        suggestions.append(f"Overused colors (avoid): {colors}")

    if analysis.get("overused_styles"):
        styles = ", ".join(analysis["overused_styles"])
        suggestions.append(f"Overused styles (vary): {styles}")

    # Add fresh directions
    import random
    random.seed(datetime.now().day)  # Consistent per day, changes daily
    fresh = random.sample(FRESH_DIRECTIONS, min(2, len(FRESH_DIRECTIONS)))
    for direction in fresh:
        suggestions.append(f"Fresh direction: {direction}")

    return suggestions


def format_report(analysis: dict, suggestions: list[str]) -> str:
    """Format analysis as a human-readable report."""
    lines = [
        "# Image Diversity Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Analyzing last {analysis['total_prompts']} prompts",
        "",
    ]

    if analysis["total_prompts"] == 0:
        lines.append("No prompts logged yet. Generate some images first!")
        return "\n".join(lines)

    # Scores
    lines.append("## Quality Metrics")
    lines.append(f"- Average diversity score: {analysis['avg_diversity']}")
    lines.append(f"- Average QA score: {analysis['avg_qa']}")
    lines.append(f"- QA pass rate: {analysis['qa_pass_rate']}%")
    lines.append("")

    # Topic distribution
    if analysis["topic_freq"]:
        lines.append("## Topic Distribution")
        for topic, count in analysis["topic_freq"].items():
            lines.append(f"  {topic}: {count}")
        lines.append("")

    # Visual patterns
    if analysis["color_freq"]:
        lines.append("## Color Usage")
        for color, count in list(analysis["color_freq"].items())[:8]:
            bar = "#" * count
            lines.append(f"  {color:12s} {bar} ({count})")
        lines.append("")

    if analysis["style_freq"]:
        lines.append("## Style Usage")
        for style, count in list(analysis["style_freq"].items())[:8]:
            bar = "#" * count
            lines.append(f"  {style:16s} {bar} ({count})")
        lines.append("")

    # Suggestions
    if suggestions:
        lines.append("## Suggestions")
        for s in suggestions:
            lines.append(f"  - {s}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Image Diversity Reporter",
    )
    parser.add_argument("--last", "-n", type=int, default=10,
                        help="Number of recent prompts to analyze (default: 10)")
    parser.add_argument("--topic", "-t", default="",
                        help="Topic context for suggestions")
    parser.add_argument("--suggest", "-s", action="store_true",
                        help="Include fresh direction suggestions")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON instead of human-readable text")

    args = parser.parse_args()

    db = sqlite3.connect(str(DB_PATH))

    # Check if table exists
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='image_prompts'"
    ).fetchone()

    if not tables:
        if args.json:
            print(json.dumps({"error": "image_prompts table does not exist yet"}))
        else:
            print("No image_prompts table yet. Run generate_starscream_image.py first.")
        db.close()
        return

    analysis = analyze_prompts(db, args.last)
    suggestions = suggest_direction(analysis, args.topic) if args.suggest else []

    if args.json:
        output = {**analysis, "suggestions": suggestions}
        print(json.dumps(output, indent=2))
    else:
        report = format_report(analysis, suggestions)
        print(report)

    db.close()


if __name__ == "__main__":
    main()
