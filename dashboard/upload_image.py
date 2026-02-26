#!/usr/bin/env python3
"""
Upload an image to Imgur for persistent public URLs.
Used by Starscream to get permanent image URLs for Late API posts.

Usage:
  python3 upload_image.py /path/to/image.webp
  python3 upload_image.py /path/to/image.png

Returns the public URL on stdout.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

IMGUR_CLIENT_ID = "546c25a59c58ad7"


def upload(image_path: str) -> str:
    """Upload image to Imgur, return public URL."""
    path = Path(image_path)

    # Convert webp to png if needed (broader compatibility)
    upload_path = image_path
    if path.suffix.lower() == ".webp":
        try:
            from PIL import Image
            png_path = path.with_suffix(".png")
            img = Image.open(image_path)
            img.save(str(png_path))
            upload_path = str(png_path)
        except ImportError:
            pass  # Upload webp directly if PIL not available

    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "https://api.imgur.com/3/image",
            "-H", f"Authorization: Client-ID {IMGUR_CLIENT_ID}",
            "-F", f"image=@{upload_path}",
        ],
        capture_output=True, text=True, timeout=30,
    )

    data = json.loads(result.stdout)
    if data.get("success"):
        return data["data"]["link"]
    else:
        raise RuntimeError(f"Imgur upload failed: {data}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 upload_image.py /path/to/image", file=sys.stderr)
        sys.exit(1)

    url = upload(sys.argv[1])
    print(url)
