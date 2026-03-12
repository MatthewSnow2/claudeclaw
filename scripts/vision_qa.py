#!/usr/bin/env python3
"""
Vision QA -- Validate generated images before posting.

Uses Claude's vision API to evaluate image quality, relevance, and catch
common generation failures (bad anatomy, text artifacts, uncanny valley).

Usage:
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 vision_qa.py \
    --image /path/to/image.png \
    --topic "AI Agents" \
    --description "Abstract visualization of autonomous AI agents coordinating tasks"

Returns:
  JSON to stdout: {"passed": true/false, "score": 0-100, "issues": [...], "summary": "..."}
  Exit code 0 = passed, 1 = error, 2 = failed QA

Can also update the image_prompts table if --prompt-id is provided.
"""

import argparse
import base64
import json
import mimetypes
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- Config ---
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
DB_PATH = STORE_DIR / "starscream_analytics.db"
ENV_FILE = Path.home() / ".env.shared"

# QA thresholds
PASS_THRESHOLD = 60  # Minimum score to pass QA (out of 100)

QA_SYSTEM_PROMPT = """You are an image quality assurance reviewer for LinkedIn posts.
Evaluate the image on these criteria and return ONLY valid JSON (no markdown, no code fences):

1. **Technical Quality** (0-25): Resolution clarity, no artifacts, no blurriness, proper rendering
2. **Anatomy/Realism** (0-25): If humans or body parts are visible, check for distortion, extra fingers, warped faces, uncanny valley. If abstract/no humans, give full marks.
3. **Relevance** (0-25): Does the image match the stated topic and description? Would it make sense alongside a LinkedIn post about this topic?
4. **Professional Aesthetic** (0-25): Is it visually appealing for a professional social media post? Good composition, appropriate colors, not cluttered?

Return this exact JSON structure:
{
  "technical_quality": <0-25>,
  "anatomy_realism": <0-25>,
  "relevance": <0-25>,
  "professional_aesthetic": <0-25>,
  "total_score": <0-100>,
  "passed": <true if total >= 60>,
  "issues": ["list of specific problems found, if any"],
  "summary": "One-sentence overall assessment"
}"""


def encode_image(image_path: Path) -> tuple[str, str]:
    """Read and base64-encode an image file. Returns (base64_data, mime_type)."""
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if mime_type is None:
        # Default based on extension
        ext = image_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mime_type = mime_map.get(ext, "image/png")

    image_data = image_path.read_bytes()
    b64_data = base64.standard_b64encode(image_data).decode("utf-8")
    return b64_data, mime_type


def run_vision_qa(
    image_path: Path,
    topic: str,
    description: str,
) -> dict:
    """Run vision QA on an image using Claude. Returns the QA result dict."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    b64_data, mime_type = encode_image(image_path)

    user_message = (
        f"Topic: {topic}\n"
        f"Description: {description}\n\n"
        "Please evaluate this image for use in a LinkedIn post about the above topic."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=QA_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": user_message,
                        },
                    ],
                }
            ],
        )

        # Parse the response
        response_text = response.content[0].text.strip()

        # Handle potential markdown code fences
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (code fences)
            response_text = "\n".join(lines[1:-1])

        result = json.loads(response_text)

        # Ensure required fields
        result.setdefault("passed", result.get("total_score", 0) >= PASS_THRESHOLD)
        result.setdefault("issues", [])
        result.setdefault("summary", "No summary provided")

        return result

    except json.JSONDecodeError as e:
        print(f"Error parsing Claude response as JSON: {e}", file=sys.stderr)
        print(f"Raw response: {response_text}", file=sys.stderr)
        return {
            "total_score": 0,
            "passed": False,
            "issues": ["Failed to parse QA response"],
            "summary": f"QA evaluation error: {e}",
        }
    except Exception as e:
        print(f"Error calling Claude vision API: {e}", file=sys.stderr)
        return {
            "total_score": 0,
            "passed": False,
            "issues": [f"API error: {str(e)}"],
            "summary": f"Vision QA failed: {e}",
        }


def update_prompt_qa(db_path: Path, prompt_id: int, score: float, passed: bool):
    """Update the image_prompts table with QA results."""
    try:
        db = sqlite3.connect(str(db_path))
        db.execute(
            "UPDATE image_prompts SET qa_score = ?, qa_passed = ? WHERE id = ?",
            (score, 1 if passed else 0, prompt_id),
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"Warning: Could not update prompt record: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Vision QA -- Validate images before posting",
    )
    parser.add_argument("--image", "-i", required=True, type=Path, help="Path to image file")
    parser.add_argument("--topic", "-t", default="", help="Post topic")
    parser.add_argument("--description", "-d", default="", help="Image description/prompt used")
    parser.add_argument("--prompt-id", type=int, default=None,
                        help="image_prompts row ID to update with QA results")
    parser.add_argument("--threshold", type=int, default=PASS_THRESHOLD,
                        help=f"Minimum score to pass (default: {PASS_THRESHOLD})")

    args = parser.parse_args()

    if not args.image.exists():
        print(f"Error: Image not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    # Load env
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    # Run QA
    result = run_vision_qa(args.image, args.topic, args.description)

    # Override pass threshold if custom
    if args.threshold != PASS_THRESHOLD:
        result["passed"] = result.get("total_score", 0) >= args.threshold

    # Update DB if prompt ID provided
    if args.prompt_id is not None:
        update_prompt_qa(
            DB_PATH,
            args.prompt_id,
            result.get("total_score", 0),
            result.get("passed", False),
        )

    # Output JSON result
    print(json.dumps(result, indent=2))

    # Exit code: 0 = passed, 2 = failed QA
    sys.exit(0 if result.get("passed", False) else 2)


if __name__ == "__main__":
    main()
