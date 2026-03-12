#!/usr/bin/env python3
"""
Starscream Image Generator -- Gemini-powered image generation for LinkedIn posts.

Replaces the HF Z-Image Turbo MCP tool with Gemini Flash for better anatomy,
higher quality, and more consistent results.

Usage:
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 generate_starscream_image.py \
    --prompt "Your image prompt here" \
    --topic "AI Agents" \
    --output /path/to/output.png

  # With diversity check (reads recent prompts, suggests adjustments):
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 generate_starscream_image.py \
    --prompt "Your image prompt here" \
    --topic "AI Agents" \
    --check-diversity

Returns:
  Prints the output file path on success.
  Logs the prompt to the image_prompts table in starscream_analytics.db.
  Exit code 0 on success, 1 on failure.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Config ---
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
MEDIA_DIR = Path("/home/apexaipc/projects/claudeclaw/dashboard/media")
DB_PATH = STORE_DIR / "starscream_analytics.db"
ENV_FILE = Path.home() / ".env.shared"

# Gemini model for image generation
# Flash is fast + cheap; Pro is higher quality but slower
MODEL_MAP = {
    "flash": "gemini-3.1-flash-image-preview",
    "pro": "gemini-3.1-pro-image-preview",
}
DEFAULT_MODEL = "flash"

MAX_RETRIES = 3
DEFAULT_ASPECT_RATIO = "16:9"  # LinkedIn landscape
DEFAULT_SIZE = "2K"


def init_prompt_table(db: sqlite3.Connection):
    """Create the image_prompts table if it doesn't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS image_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            topic TEXT,
            prompt_text TEXT NOT NULL,
            model_used TEXT NOT NULL,
            output_path TEXT,
            diversity_score REAL DEFAULT 0.0,
            qa_score REAL DEFAULT 0.0,
            qa_passed INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_image_prompts_created
            ON image_prompts(created_at)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_image_prompts_topic
            ON image_prompts(topic)
    """)
    db.commit()


def log_prompt(
    db: sqlite3.Connection,
    topic: str,
    prompt_text: str,
    model_used: str,
    output_path: str | None = None,
    diversity_score: float = 0.0,
) -> int:
    """Log an image prompt to the database. Returns the row ID."""
    now = datetime.now().isoformat()
    cursor = db.execute(
        """INSERT INTO image_prompts
           (created_at, topic, prompt_text, model_used, output_path, diversity_score)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (now, topic, prompt_text, model_used, output_path, diversity_score),
    )
    db.commit()
    return cursor.lastrowid


def update_prompt_record(
    db: sqlite3.Connection,
    row_id: int,
    output_path: str | None = None,
    qa_score: float | None = None,
    qa_passed: bool | None = None,
):
    """Update an existing prompt record with generation results."""
    updates = []
    params = []
    if output_path is not None:
        updates.append("output_path = ?")
        params.append(output_path)
    if qa_score is not None:
        updates.append("qa_score = ?")
        params.append(qa_score)
    if qa_passed is not None:
        updates.append("qa_passed = ?")
        params.append(1 if qa_passed else 0)
    if updates:
        params.append(row_id)
        db.execute(
            f"UPDATE image_prompts SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        db.commit()


def check_diversity(db: sqlite3.Connection, prompt_text: str, topic: str) -> dict:
    """Check prompt diversity against recent history.

    Returns:
        dict with keys: score (0.0-1.0), warnings (list of str), suggestions (list of str)
        Higher score = more diverse (good).
    """
    # Get last 10 prompts
    rows = db.execute(
        """SELECT prompt_text, topic FROM image_prompts
           ORDER BY created_at DESC LIMIT 10"""
    ).fetchall()

    if not rows:
        return {"score": 1.0, "warnings": [], "suggestions": []}

    warnings = []
    suggestions = []

    # Extract keywords from current prompt
    current_words = set(prompt_text.lower().split())
    # Remove common stopwords
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "that", "this", "these", "those", "it", "its",
    }
    current_keywords = current_words - stopwords

    # Check keyword overlap with recent prompts
    overlap_scores = []
    for row_prompt, row_topic in rows:
        row_words = set(row_prompt.lower().split()) - stopwords
        if not row_words or not current_keywords:
            continue
        overlap = len(current_keywords & row_words) / max(len(current_keywords), 1)
        overlap_scores.append(overlap)

    avg_overlap = sum(overlap_scores) / len(overlap_scores) if overlap_scores else 0

    # Check topic repetition
    recent_topics = [r[1] for r in rows if r[1]]
    if topic and recent_topics:
        topic_count = sum(1 for t in recent_topics[:5] if t and t.lower() == topic.lower())
        if topic_count >= 3:
            warnings.append(
                f"Topic '{topic}' used {topic_count}/5 recent posts. Consider a different topic."
            )

    # Check for repeated visual elements
    visual_keywords = {
        "blue", "purple", "coral", "indigo", "gradient", "glow", "neon",
        "circuit", "network", "neural", "abstract", "geometric", "futuristic",
        "dark", "light", "bright", "minimal", "holographic",
    }
    current_visual = current_keywords & visual_keywords
    all_recent_visual = set()
    for row_prompt, _ in rows:
        row_words = set(row_prompt.lower().split()) - stopwords
        all_recent_visual |= (row_words & visual_keywords)

    repeated_visuals = current_visual & all_recent_visual
    if len(repeated_visuals) >= 3:
        warnings.append(
            f"Reusing visual elements: {', '.join(sorted(repeated_visuals))}. "
            "Try different colors/styles."
        )
        # Suggest alternatives
        unused = visual_keywords - all_recent_visual
        if unused:
            suggestions.append(f"Try these unused visual elements: {', '.join(sorted(list(unused)[:5]))}")

    # Calculate diversity score
    # 1.0 = fully diverse, 0.0 = completely repetitive
    diversity_score = max(0.0, 1.0 - avg_overlap)
    if warnings:
        diversity_score *= 0.7  # Penalize for warnings

    if diversity_score < 0.4:
        warnings.append(
            f"Low diversity score ({diversity_score:.2f}). "
            "The prompt is too similar to recent ones."
        )
        suggestions.append("Use different metaphors, colors, and compositions.")

    return {
        "score": round(diversity_score, 2),
        "warnings": warnings,
        "suggestions": suggestions,
    }


def generate_image(
    prompt: str,
    model: str = DEFAULT_MODEL,
    output_path: Path | None = None,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    topic: str | None = None,
) -> Path:
    """Generate an image using Gemini. Returns the output file path."""
    # Prefer GOOGLE_API_KEY (paid tier), fall back to GEMINI_API_KEY
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Neither GOOGLE_API_KEY nor GEMINI_API_KEY found.", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    model_id = MODEL_MAP[model]

    # Default output path (includes topic slug to avoid same-day collisions)
    if output_path is None:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        if topic:
            slug = topic.lower().replace(" ", "-").replace("/", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-")[:30]
            output_path = MEDIA_DIR / f"starscream_{timestamp}_{slug}.png"
        else:
            output_path = MEDIA_DIR / f"starscream_{timestamp}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Enforce photorealistic style (safety net -- CLAUDE.md mandates this too)
    style_prefix = "Photorealistic, professional photography, natural lighting, 8K detail."
    if "photorealistic" not in prompt.lower():
        enhanced_prompt = f"{style_prefix} {prompt}"
    else:
        enhanced_prompt = prompt

    # Enhance prompt with aspect ratio hint
    if aspect_ratio:
        enhanced_prompt += f" Aspect ratio: {aspect_ratio}."

    config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            wait_time = 2 ** attempt
            print(f"Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})...",
                  file=sys.stderr)
            time.sleep(wait_time)

        try:
            response = client.models.generate_content(
                model=model_id,
                contents=types.Content(
                    parts=[types.Part.from_text(text=enhanced_prompt)]
                ),
                config=config,
            )

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        mime = part.inline_data.mime_type or "image/png"
                        ext = mime.split("/")[-1]
                        if ext == "jpeg":
                            ext = "jpg"

                        final_path = output_path.with_suffix(f".{ext}")
                        final_path.write_bytes(part.inline_data.data)
                        return final_path

            print("Error: No image data in Gemini response.", file=sys.stderr)
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        print(f"Model response: {part.text}", file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            error_msg = str(e)
            is_retryable = any(
                kw in error_msg.lower()
                for kw in ["overloaded", "429", "500", "503", "rate"]
            )

            if is_retryable and attempt < MAX_RETRIES - 1:
                last_error = e
                print(f"Model busy: {error_msg}", file=sys.stderr)
                continue

            # Fallback: if flash model exhausted, try pro before giving up
            is_quota_exhausted = "resource_exhausted" in error_msg.lower() or "quota" in error_msg.lower()
            if is_quota_exhausted and model_id != MODEL_MAP.get("pro"):
                fallback_id = MODEL_MAP.get("pro")
                if fallback_id:
                    print(f"Flash quota exhausted. Falling back to pro model ({fallback_id})...",
                          file=sys.stderr)
                    model_id = fallback_id
                    attempt = -1  # Reset retry counter for pro model
                    continue

            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)

    print(f"Error: All {MAX_RETRIES} attempts failed. Last error: {last_error}",
          file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Starscream Image Generator -- Gemini-powered LinkedIn images",
    )
    parser.add_argument("--prompt", "-p", required=True, help="Image generation prompt")
    parser.add_argument("--topic", "-t", default="", help="Post topic (for logging/diversity)")
    parser.add_argument(
        "--model", "-m", default=DEFAULT_MODEL, choices=list(MODEL_MAP.keys()),
        help=f"Gemini model variant (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output file path")
    parser.add_argument(
        "--aspect-ratio", "-a", default=DEFAULT_ASPECT_RATIO,
        choices=["1:1", "16:9", "9:16", "4:3", "3:4"],
        help=f"Aspect ratio (default: {DEFAULT_ASPECT_RATIO})",
    )
    parser.add_argument(
        "--check-diversity", action="store_true",
        help="Check prompt diversity against recent history before generating",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log and check diversity only, don't generate image",
    )

    args = parser.parse_args()

    # Load env
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    # Init DB
    db = sqlite3.connect(str(DB_PATH))
    init_prompt_table(db)

    # Diversity check
    if args.check_diversity:
        diversity = check_diversity(db, args.prompt, args.topic)
        print(f"Diversity score: {diversity['score']}", file=sys.stderr)
        if diversity["warnings"]:
            print("Warnings:", file=sys.stderr)
            for w in diversity["warnings"]:
                print(f"  - {w}", file=sys.stderr)
        if diversity["suggestions"]:
            print("Suggestions:", file=sys.stderr)
            for s in diversity["suggestions"]:
                print(f"  - {s}", file=sys.stderr)

        if diversity["score"] < 0.3:
            print(
                "DIVERSITY_FAIL: Prompt is too similar to recent images. "
                "Please revise the prompt.",
                file=sys.stderr,
            )
            # Still log it but flag it
            log_prompt(db, args.topic, args.prompt, args.model, diversity_score=diversity["score"])
            db.close()
            sys.exit(2)  # Exit code 2 = diversity failure

        diversity_score = diversity["score"]
    else:
        diversity_score = 0.0  # Not checked

    # Log prompt before generation
    row_id = log_prompt(
        db, args.topic, args.prompt, args.model, diversity_score=diversity_score,
    )

    if args.dry_run:
        print(f"DRY RUN: Prompt logged (id={row_id}), no image generated.")
        db.close()
        return

    # Generate image
    output = generate_image(
        prompt=args.prompt,
        model=args.model,
        output_path=args.output,
        aspect_ratio=args.aspect_ratio,
        topic=args.topic,
    )

    # Update record with output path
    update_prompt_record(db, row_id, output_path=str(output))
    db.close()

    # Print the output path (for Starscream to capture)
    print(str(output))


if __name__ == "__main__":
    main()
