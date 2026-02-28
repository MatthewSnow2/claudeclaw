#!/usr/bin/env python3
"""
Semantic Memory Extraction -- Phase 7b
Extracts structured facts from conversation logs via Qwen (local Ollama),
embeds them via nomic-embed-text, and stores in memory_vectors table.

Architecture:
  conversation_log -> Qwen extraction -> nomic embedding -> memory_vectors

Runs every 30 minutes on cron. Zero external deps (stdlib only).

Cron:
  */30 * * * * /usr/bin/python3 /home/apexaipc/projects/claudeclaw/scripts/extract_memories.py >> /tmp/extract_memories.log 2>&1
"""

import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

# Paths
STORE_DIR = Path("/home/apexaipc/projects/claudeclaw/store")
DB_PATH = STORE_DIR / "claudeclaw.db"

# Ollama config
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
EXTRACTION_MODEL = "qwen2.5:7b-instruct"
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIMS = 768

# Processing config
BATCH_SIZE = 20  # conversation_log rows per batch
MAX_FACTS_PER_BATCH = 20  # safety cap on extracted facts

EXTRACTION_PROMPT = """Extract important facts from this conversation. Output a JSON array of strings.
Focus on: decisions made, user preferences, project state changes, action items, technical details, names/dates/numbers.
Each fact must be self-contained (understandable without conversation context).
Keep facts concise -- one sentence each.
Return [] if nothing worth remembering.

Conversation:
{conversation}"""

DRY_RUN = "--dry-run" in sys.argv


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def ollama_available() -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def call_qwen(prompt: str) -> Optional[str]:
    """Call Qwen via Ollama chat API. Returns raw response text or None on failure."""
    payload = json.dumps({
        "model": EXTRACTION_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 1024},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        log(f"Qwen call failed: {e}")
        return None


def embed_text(text: str) -> Optional[bytes]:
    """Embed text via nomic-embed-text. Returns raw bytes (768 floats) or None."""
    payload = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": text,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            embeddings = data.get("embeddings", [])
            if not embeddings or len(embeddings[0]) != EMBEDDING_DIMS:
                log(f"Unexpected embedding dims: {len(embeddings[0]) if embeddings else 0}")
                return None
            # Pack as little-endian float32 array (matches TypeScript Buffer.readFloatLE)
            return struct.pack(f"<{EMBEDDING_DIMS}f", *embeddings[0])
    except (urllib.error.URLError, OSError, json.JSONDecodeError, struct.error) as e:
        log(f"Embedding failed: {e}")
        return None


def parse_facts(raw: str) -> list[str]:
    """Parse JSON array of fact strings from Qwen response. Robust against markdown fences."""
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            # Handle nested arrays: [[...]] -> [...]
            if parsed and isinstance(parsed[0], list):
                parsed = parsed[0]
            return [str(f).strip() for f in parsed if isinstance(f, str) and f.strip()][:MAX_FACTS_PER_BATCH]
    except json.JSONDecodeError:
        pass

    # Fallback: try to find JSON array within the text
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], list):
                    parsed = parsed[0]
                return [str(f).strip() for f in parsed if isinstance(f, str) and f.strip()][:MAX_FACTS_PER_BATCH]
        except json.JSONDecodeError:
            pass

    log(f"Failed to parse facts from Qwen response: {text[:200]}")
    return []


# Patterns that indicate tool-echo spam or bot noise (mirrors bot.ts isToolEcho)
SPAM_PATTERNS: list[re.Pattern] = [
    re.compile(r"^Running: .+$"),
    re.compile(r"^(Reading|Writing|Editing) \S+$"),
    re.compile(r"^Searching (codebase|the web)\.\.\.\s*$"),
    re.compile(r"^Searching: .+$"),
    re.compile(r"^Fetching web content\.\.\.\s*$"),
    re.compile(r"^Launching sub-agent\.\.\.\s*$"),
    re.compile(r"^Done\.$"),
    re.compile(r"^[A-Z][a-z]+: [A-Z][a-zA-Z ]+$"),
    re.compile(r"^Worker process output\b"),
    re.compile(r"^Standing by\b"),
    re.compile(r"^Worker \w+ completed\b"),
    re.compile(r"^Context window: \d+%"),
]


def is_spam(content: str) -> bool:
    """Check if a message is tool-echo spam or bot noise."""
    trimmed = content.strip()
    if len(trimmed) < 5:
        return True
    if len(trimmed) > 200:
        return False
    return any(p.search(trimmed) for p in SPAM_PATTERNS)


def format_turns(rows: list[dict]) -> str:
    """Format conversation_log rows into readable conversation text.
    Filters out spam/tool-echo messages before sending to Qwen."""
    lines = []
    skipped = 0
    for row in rows:
        role = row["role"].upper()
        content = row["content"]
        if is_spam(content):
            skipped += 1
            continue
        # Truncate very long messages to keep Qwen's context manageable
        if len(content) > 1000:
            content = content[:1000] + "... [truncated]"
        lines.append(f"{role}: {content}")
    if skipped:
        log(f"  Filtered {skipped} spam/noise messages from batch")
    return "\n\n".join(lines)


def run_extraction():
    """Main extraction loop."""
    if not ollama_available():
        log("Ollama not running -- skipping extraction")
        return

    if not DB_PATH.exists():
        log(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")

    try:
        # Get all chat_ids that have conversation_log entries
        chat_ids = [
            row["chat_id"]
            for row in conn.execute("SELECT DISTINCT chat_id FROM conversation_log").fetchall()
        ]

        if not chat_ids:
            log("No conversation logs to process")
            return

        total_facts = 0

        for chat_id in chat_ids:
            # Get watermark for this chat
            wm_row = conn.execute(
                "SELECT last_log_id, facts_total FROM extraction_state WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

            last_log_id = wm_row["last_log_id"] if wm_row else 0
            facts_total = wm_row["facts_total"] if wm_row else 0

            # Fetch new conversation_log entries above watermark
            rows = conn.execute(
                """SELECT id, role, content FROM conversation_log
                   WHERE chat_id = ? AND id > ?
                   ORDER BY id ASC LIMIT ?""",
                (chat_id, last_log_id, BATCH_SIZE),
            ).fetchall()

            if not rows:
                continue

            rows_as_dicts = [dict(r) for r in rows]
            max_id = max(r["id"] for r in rows_as_dicts)
            conversation_text = format_turns(rows_as_dicts)

            log(f"Processing chat {chat_id}: {len(rows_as_dicts)} turns (log IDs {last_log_id + 1}..{max_id})")

            # If all messages were filtered as spam, advance watermark without calling Qwen
            if not conversation_text.strip():
                log(f"  All {len(rows_as_dicts)} turns were spam -- advancing watermark to {max_id}")
                now = int(time.time())
                conn.execute(
                    """INSERT OR REPLACE INTO extraction_state
                       (chat_id, last_log_id, last_run_at, facts_total)
                       VALUES (?, ?, ?, ?)""",
                    (chat_id, max_id, now, facts_total),
                )
                conn.commit()
                continue

            if DRY_RUN:
                log(f"[DRY RUN] Would send {len(conversation_text)} chars to Qwen")
                # Still call Qwen in dry run to show what would be extracted
                prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
                raw_response = call_qwen(prompt)
                if raw_response:
                    facts = parse_facts(raw_response)
                    log(f"[DRY RUN] Extracted {len(facts)} facts:")
                    for f in facts:
                        log(f"  - {f}")
                continue

            # Call Qwen for extraction
            prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
            raw_response = call_qwen(prompt)

            if raw_response is None:
                log(f"Qwen extraction failed for chat {chat_id}, skipping batch")
                continue

            facts = parse_facts(raw_response)
            log(f"Extracted {len(facts)} facts from chat {chat_id}")

            # Embed and store each fact
            source_ids = ",".join(str(r["id"]) for r in rows_as_dicts)
            stored = 0

            for fact in facts:
                embedding = embed_text(fact)
                if embedding is None:
                    log(f"  Embedding failed for fact: {fact[:80]}")
                    continue

                now = int(time.time())
                conn.execute(
                    """INSERT INTO memory_vectors
                       (chat_id, content, source_type, embedding, salience, created_at, accessed_at, source_log_ids)
                       VALUES (?, ?, 'extraction', ?, 1.0, ?, ?, ?)""",
                    (chat_id, fact, embedding, now, now, source_ids),
                )
                stored += 1

            # Update watermark
            facts_total += stored
            now = int(time.time())
            conn.execute(
                """INSERT OR REPLACE INTO extraction_state
                   (chat_id, last_log_id, last_run_at, facts_total)
                   VALUES (?, ?, ?, ?)""",
                (chat_id, max_id, now, facts_total),
            )

            conn.commit()
            total_facts += stored
            log(f"  Stored {stored}/{len(facts)} facts, watermark -> {max_id}")

        log(f"Extraction complete: {total_facts} new facts across {len(chat_ids)} chats")

    except Exception as e:
        log(f"Extraction error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    log("=" * 60)
    log("Semantic memory extraction starting" + (" [DRY RUN]" if DRY_RUN else ""))
    run_extraction()
    log("Done")
