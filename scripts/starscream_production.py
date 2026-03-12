#!/usr/bin/env python3
"""
Starscream Production Pipeline -- Image gen, QA, upload, and scheduling.

Separated from Starscream's writing workflow. Takes a post text and image brief,
handles all production steps: diversity check, Gemini image gen, vision QA,
Imgur upload, and Late API scheduling.

Usage:
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 starscream_production.py \
    --post "Full post text here" \
    --image-brief "2-3 sentence image description" \
    --topic "AI Agents"

  # Dry run (skip scheduling):
  /home/apexaipc/projects/claudeclaw/venv/bin/python3 starscream_production.py \
    --post "Post text" --image-brief "Image brief" --topic "Healthcare" --dry-run

Returns:
  JSON to stdout with results of each step.
  Exit code 0 = success, 1 = failure at any step.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.env.shared"))

VENV_PYTHON = "/home/apexaipc/projects/claudeclaw/venv/bin/python3"
SCRIPTS_DIR = Path("/home/apexaipc/projects/claudeclaw/scripts")
MEDIA_DIR = Path("/home/apexaipc/projects/claudeclaw/dashboard/media")
UPLOAD_SCRIPT = Path("/home/apexaipc/projects/claudeclaw/dashboard/upload_image.py")

LATE_API_BASE = "https://getlate.dev/api/v1"
LINKEDIN_ACCOUNT_ID = "69a62fa6dc8cab9432b3af43"


def run_script(script_path: str, args: list[str]) -> tuple[int, str, str]:
    """Run a Python script and return (exit_code, stdout, stderr)."""
    cmd = [VENV_PYTHON, script_path] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_diversity(topic: str) -> str | None:
    """Run diversity checker. Returns suggestions or None on failure."""
    code, out, err = run_script(
        str(SCRIPTS_DIR / "image_diversity.py"),
        ["--suggest", "--topic", topic],
    )
    if code != 0:
        print(f"Diversity check failed (exit {code}): {err}", file=sys.stderr)
        return None
    return out


def generate_image(prompt: str, topic: str) -> str | None:
    """Generate image via Gemini. Returns file path or None."""
    code, out, err = run_script(
        str(SCRIPTS_DIR / "generate_starscream_image.py"),
        ["--prompt", prompt, "--topic", topic, "--check-diversity"],
    )
    if code == 2:
        print(f"Diversity fail. Retrying without diversity check.", file=sys.stderr)
        code, out, err = run_script(
            str(SCRIPTS_DIR / "generate_starscream_image.py"),
            ["--prompt", prompt, "--topic", topic],
        )
    if code != 0:
        print(f"Image generation failed (exit {code}): {err}", file=sys.stderr)
        return None
    # Script prints the output path
    for line in out.splitlines():
        if line.strip().endswith(".png") or line.strip().endswith(".webp"):
            return line.strip()
    return out.splitlines()[-1].strip() if out else None


def run_vision_qa(image_path: str, topic: str, description: str) -> dict | None:
    """Run vision QA. Returns result dict or None."""
    code, out, err = run_script(
        str(SCRIPTS_DIR / "vision_qa.py"),
        ["--image", image_path, "--topic", topic, "--description", description],
    )
    if code not in (0, 2):
        print(f"Vision QA error (exit {code}): {err}", file=sys.stderr)
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"Vision QA returned non-JSON: {out}", file=sys.stderr)
        return None


def upload_to_imgur(image_path: str) -> str | None:
    """Upload image to Imgur. Returns URL or None."""
    code, out, err = run_script(str(UPLOAD_SCRIPT), [image_path])
    if code != 0:
        print(f"Imgur upload failed (exit {code}): {err}", file=sys.stderr)
        return None
    # Script prints the URL
    for line in out.splitlines():
        if line.startswith("http"):
            return line.strip()
    return None


def schedule_post(content: str, image_url: str, api_key: str) -> dict | None:
    """Schedule via Late API, 30min from now."""
    schedule_time = datetime.now() + timedelta(minutes=30)
    payload = {
        "content": content,
        "scheduledFor": schedule_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "America/Chicago",
        "platforms": [{"platform": "linkedin", "accountId": LINKEDIN_ACCOUNT_ID}],
        "mediaItems": [{"type": "image", "url": image_url}],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{LATE_API_BASE}/posts",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Late API scheduling failed: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Starscream production pipeline")
    parser.add_argument("--post", required=True, help="Full post text")
    parser.add_argument("--image-brief", required=True, help="Image brief from Starscream")
    parser.add_argument("--topic", required=True, help="Topic name")
    parser.add_argument("--dry-run", action="store_true", help="Skip scheduling")
    args = parser.parse_args()

    api_key = os.environ.get("LATE_API_KEY", "")
    if not api_key and not args.dry_run:
        print("LATE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    results = {"steps": {}}

    # Step 1: Diversity check
    print("Step 1: Checking image diversity...")
    suggestions = check_diversity(args.topic)
    results["steps"]["diversity"] = {"suggestions": suggestions}

    # Step 2: Generate image using the brief as the prompt
    print("Step 2: Generating image...")
    image_path = generate_image(args.image_brief, args.topic)
    if not image_path:
        print("FAILED: Image generation failed. Aborting.", file=sys.stderr)
        results["steps"]["image_gen"] = {"status": "failed"}
        print(json.dumps(results, indent=2))
        sys.exit(1)
    results["steps"]["image_gen"] = {"status": "ok", "path": image_path}
    print(f"  Image saved: {image_path}")

    # Step 3: Vision QA
    print("Step 3: Running vision QA...")
    qa_result = run_vision_qa(image_path, args.topic, args.image_brief)
    if qa_result and not qa_result.get("passed", False):
        print(f"WARNING: Vision QA failed (score: {qa_result.get('score', '?')})")
        print(f"  Issues: {qa_result.get('issues', [])}")
        # Try once more with a note about the failures
        retry_brief = f"{args.image_brief}. Avoid: {', '.join(qa_result.get('issues', []))}"
        print("  Retrying image generation...")
        image_path2 = generate_image(retry_brief, args.topic)
        if image_path2:
            qa_result2 = run_vision_qa(image_path2, args.topic, retry_brief)
            if qa_result2 and qa_result2.get("passed", False):
                image_path = image_path2
                qa_result = qa_result2
                print(f"  Retry passed (score: {qa_result2.get('score', '?')})")
            else:
                print("  Retry also failed QA. Using best available image.")
    results["steps"]["vision_qa"] = qa_result or {"status": "skipped"}

    # Step 4: Upload to Imgur
    print("Step 4: Uploading to Imgur...")
    imgur_url = upload_to_imgur(image_path)
    if not imgur_url:
        print("FAILED: Imgur upload failed. Aborting.", file=sys.stderr)
        results["steps"]["imgur"] = {"status": "failed"}
        print(json.dumps(results, indent=2))
        sys.exit(1)
    results["steps"]["imgur"] = {"status": "ok", "url": imgur_url}
    print(f"  Imgur URL: {imgur_url}")

    # Step 5: Schedule via Late API
    if args.dry_run:
        print("Step 5: DRY RUN -- skipping Late API scheduling")
        results["steps"]["scheduling"] = {"status": "dry_run"}
    else:
        print("Step 5: Scheduling via Late API (30min out)...")
        late_result = schedule_post(args.post, imgur_url, api_key)
        if not late_result:
            print("FAILED: Late API scheduling failed.", file=sys.stderr)
            results["steps"]["scheduling"] = {"status": "failed"}
            print(json.dumps(results, indent=2))
            sys.exit(1)
        results["steps"]["scheduling"] = {"status": "scheduled", "response": late_result}
        print("  Scheduled for 30min from now.")

    results["status"] = "complete"
    results["image_url"] = imgur_url
    print("\nProduction pipeline complete.")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
