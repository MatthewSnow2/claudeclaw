#!/usr/bin/env python3
"""
Semantic Memory Extraction -- Phase 7c (Structured Metadata)
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
from typing import Any, Optional

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

# Valid categories for structured extraction
VALID_CATEGORIES = {
    "decision", "preference", "project_state", "action_item",
    "technical_detail", "person_info", "insight",
}

EXTRACTION_PROMPT = """Extract important facts from this conversation. Output a JSON array of objects.

Each object must have exactly these fields:
- "content": string (one self-contained sentence)
- "category": one of: decision, preference, project_state, action_item, technical_detail, person_info, insight
- "tags": array of 1-3 short topic strings
- "people": array of person names mentioned ([] if none)
- "is_action_item": true or false
- "confidence": number from 0.1 to 1.0

Example output:
[
  {{"content": "Matthew decided to use Railway for deployment instead of Vercel", "category": "decision", "tags": ["deployment", "railway"], "people": ["Matthew"], "is_action_item": false, "confidence": 0.9}},
  {{"content": "Need to update the CI pipeline to run mypy before pytest", "category": "action_item", "tags": ["ci", "testing"], "people": [], "is_action_item": true, "confidence": 0.8}}
]

Return [] if nothing worth remembering.

Conversation:
{conversation}"""

DRY_RUN = "--dry-run" in sys.argv

# Parse failure tracking
_parse_failures = 0


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
        "options": {"temperature": 0.1, "num_predict": 2048},
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


def _normalize_memory_object(obj: Any) -> Optional[dict]:
    """Validate and normalize a single memory object from Qwen output.
    Returns a normalized dict or None if invalid."""
    # Handle plain string fallback (backward compatibility)
    if isinstance(obj, str):
        text = obj.strip()
        if not text:
            return None
        return {
            "content": text,
            "category": "insight",
            "tags": [],
            "people": [],
            "is_action_item": False,
            "confidence": 0.8,
        }

    if not isinstance(obj, dict):
        return None

    content = obj.get("content")
    if not isinstance(content, str) or not content.strip():
        return None

    # Normalize category
    category = obj.get("category", "insight")
    if not isinstance(category, str) or category not in VALID_CATEGORIES:
        category = "insight"

    # Normalize tags (cap at 5)
    tags = obj.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if isinstance(t, str) and str(t).strip()][:5]

    # Normalize people
    people = obj.get("people", [])
    if not isinstance(people, list):
        people = []
    people = [str(p).strip() for p in people if isinstance(p, str) and str(p).strip()]

    # Normalize is_action_item
    is_action_item = bool(obj.get("is_action_item", False))

    # Normalize confidence (clamp 0.0-1.0)
    confidence = obj.get("confidence", 1.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 1.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "content": content.strip(),
        "category": category,
        "tags": tags,
        "people": people,
        "is_action_item": is_action_item,
        "confidence": confidence,
    }


def _extract_json_array(text: str) -> Optional[list]:
    """Try to extract a JSON array from text, handling markdown fences and partial JSON."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Direct parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            # Handle nested arrays: [[...]] -> [...]
            if parsed and isinstance(parsed[0], list):
                parsed = parsed[0]
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: find JSON array within text
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                if parsed and isinstance(parsed[0], list):
                    parsed = parsed[0]
                return parsed
        except json.JSONDecodeError:
            pass

    return None


def parse_memory_objects(raw: str) -> list[dict]:
    """Parse JSON array of memory objects from Qwen response.
    Handles structured objects, plain strings (backward compat), markdown fences, and partial JSON."""
    global _parse_failures

    parsed = _extract_json_array(raw)
    if parsed is None:
        _parse_failures += 1
        log(f"Failed to parse memory objects from Qwen response (failures: {_parse_failures}): {raw[:200]}")
        return []

    results = []
    for item in parsed:
        normalized = _normalize_memory_object(item)
        if normalized:
            results.append(normalized)
        if len(results) >= MAX_FACTS_PER_BATCH:
            break

    return results


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure memory_vectors has metadata columns. Safety net for when cron fires before bot restart."""
    cursor = conn.execute("PRAGMA table_info('memory_vectors')")
    existing = {row[1] for row in cursor.fetchall()}

    additions = [
        ("category", "TEXT"),
        ("tags", "TEXT"),
        ("people", "TEXT"),
        ("is_action_item", "INTEGER NOT NULL DEFAULT 0"),
        ("confidence", "REAL NOT NULL DEFAULT 1.0"),
    ]

    for col, typedef in additions:
        if col not in existing:
            conn.execute(f"ALTER TABLE memory_vectors ADD COLUMN {col} {typedef}")
            log(f"  Migration: added column {col} to memory_vectors")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memvec_category ON memory_vectors(chat_id, category)"
    )
    conn.commit()


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
        # Ensure schema has metadata columns (safety net)
        ensure_schema(conn)

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
                    memory_objects = parse_memory_objects(raw_response)
                    log(f"[DRY RUN] Extracted {len(memory_objects)} structured facts:")
                    for mo in memory_objects:
                        log(f"  - [{mo['category']}] {mo['content']} (conf={mo['confidence']}, tags={mo['tags']})")
                continue

            # Call Qwen for extraction
            prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
            raw_response = call_qwen(prompt)

            if raw_response is None:
                log(f"Qwen extraction failed for chat {chat_id}, skipping batch")
                continue

            memory_objects = parse_memory_objects(raw_response)
            log(f"Extracted {len(memory_objects)} structured facts from chat {chat_id}")

            # Embed and store each fact
            source_ids = ",".join(str(r["id"]) for r in rows_as_dicts)
            stored = 0

            for mo in memory_objects:
                embedding = embed_text(mo["content"])
                if embedding is None:
                    log(f"  Embedding failed for fact: {mo['content'][:80]}")
                    continue

                now = int(time.time())
                conn.execute(
                    """INSERT INTO memory_vectors
                       (chat_id, content, source_type, embedding, salience, created_at, accessed_at, source_log_ids,
                        category, tags, people, is_action_item, confidence)
                       VALUES (?, ?, 'extraction', ?, 1.0, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        chat_id,
                        mo["content"],
                        embedding,
                        now,
                        now,
                        source_ids,
                        mo["category"],
                        json.dumps(mo["tags"]),
                        json.dumps(mo["people"]),
                        1 if mo["is_action_item"] else 0,
                        mo["confidence"],
                    ),
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
            log(f"  Stored {stored}/{len(memory_objects)} facts, watermark -> {max_id}")

        log(f"Extraction complete: {total_facts} new facts across {len(chat_ids)} chats")
        if _parse_failures > 0:
            log(f"WARNING: {_parse_failures} parse failures during this run")

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
