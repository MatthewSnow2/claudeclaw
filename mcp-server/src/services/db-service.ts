import Database from 'better-sqlite3';

import { getConfig } from '../config.js';
import type { MemoryRow, MemoryVectorRow } from '../types/index.js';
import { logger } from '../utils/index.js';

let db: Database.Database | null = null;
let hasMetadataColumns = false;

/** Lazy read-only DB connection. Opens on first query. */
function getDb(): Database.Database {
  if (db) return db;

  const { dbPath } = getConfig();
  logger.info(`Opening database (read-only): ${dbPath}`);

  db = new Database(dbPath, { readonly: true, fileMustExist: true });
  db.pragma('busy_timeout = 5000');

  // Check if metadata columns exist (migration may not have run yet)
  const cols = db.prepare("PRAGMA table_info('memory_vectors')").all() as Array<{ name: string }>;
  const colNames = new Set(cols.map(c => c.name));
  hasMetadataColumns = colNames.has('category') && colNames.has('tags') && colNames.has('people');

  if (!hasMetadataColumns) {
    logger.warn('memory_vectors metadata columns not found -- structured queries will return defaults');
  }

  return db;
}

export function closeDb(): void {
  if (db) {
    db.close();
    db = null;
  }
}

/** Fill in default metadata fields for rows from a pre-migration DB. */
function normalizeVectorRow(row: Record<string, unknown>): MemoryVectorRow {
  return {
    id: row.id as number,
    chat_id: row.chat_id as string,
    content: row.content as string,
    source_type: row.source_type as string,
    embedding: row.embedding as Buffer,
    salience: row.salience as number,
    created_at: row.created_at as number,
    accessed_at: row.accessed_at as number,
    source_log_ids: (row.source_log_ids as string | null) ?? null,
    category: (row.category as MemoryVectorRow['category']) ?? null,
    tags: (row.tags as string | null) ?? null,
    people: (row.people as string | null) ?? null,
    is_action_item: (row.is_action_item as number) ?? 0,
    confidence: (row.confidence as number) ?? 1.0,
  };
}

// ── Memory Vectors (semantic search candidates) ────────────────────

export function getAllMemoryVectors(chatId?: string): MemoryVectorRow[] {
  const d = getDb();
  const rows = chatId
    ? d.prepare('SELECT * FROM memory_vectors WHERE chat_id = ?').all(chatId)
    : d.prepare('SELECT * FROM memory_vectors').all();
  return (rows as Array<Record<string, unknown>>).map(normalizeVectorRow);
}

export function getRecentMemoryVectors(limit: number, chatId?: string, _sector?: string, category?: string): MemoryVectorRow[] {
  const d = getDb();
  const conditions: string[] = [];
  const params: unknown[] = [];

  if (chatId) {
    conditions.push('chat_id = ?');
    params.push(chatId);
  }
  if (category && hasMetadataColumns) {
    conditions.push('category = ?');
    params.push(category);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  params.push(limit);

  const rows = d.prepare(`SELECT * FROM memory_vectors ${where} ORDER BY accessed_at DESC LIMIT ?`).all(...params);
  return (rows as Array<Record<string, unknown>>).map(normalizeVectorRow);
}

// ── Memories (FTS5 keyword search) ────────────────────────────────

export function searchMemoriesFts(query: string, limit: number): MemoryRow[] {
  const d = getDb();
  // Sanitize for FTS5
  const sanitized = query
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[^\w\s]/g, '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => `"${w}"*`)
    .join(' ');

  if (!sanitized) return [];

  return d.prepare(
    `SELECT memories.* FROM memories
     JOIN memories_fts ON memories.id = memories_fts.rowid
     WHERE memories_fts MATCH ?
     ORDER BY rank
     LIMIT ?`,
  ).all(sanitized, limit) as MemoryRow[];
}

// ── Stats ──────────────────────────────────────────────────────────

export interface MemoryStats {
  totalMemories: number;
  totalVectors: number;
  totalConversationTurns: number;
  categoryDistribution: Record<string, number>;
  actionItemCount: number;
  chatIds: string[];
  lastExtractionRun: number | null;
  totalFactsExtracted: number;
}

export function getMemoryStats(): MemoryStats {
  const d = getDb();

  const totalMemories = (d.prepare('SELECT COUNT(*) as c FROM memories').get() as { c: number }).c;
  const totalVectors = (d.prepare('SELECT COUNT(*) as c FROM memory_vectors').get() as { c: number }).c;
  const totalConversationTurns = (d.prepare('SELECT COUNT(*) as c FROM conversation_log').get() as { c: number }).c;

  // Category distribution (only if metadata columns exist)
  let categoryDistribution: Record<string, number> = {};
  let actionItemCount = 0;

  if (hasMetadataColumns) {
    const catRows = d.prepare(
      `SELECT COALESCE(category, 'uncategorized') as cat, COUNT(*) as c FROM memory_vectors GROUP BY category`,
    ).all() as Array<{ cat: string; c: number }>;

    for (const row of catRows) {
      categoryDistribution[row.cat] = row.c;
    }

    actionItemCount = (d.prepare('SELECT COUNT(*) as c FROM memory_vectors WHERE is_action_item = 1').get() as { c: number }).c;
  } else {
    categoryDistribution = { uncategorized: totalVectors };
  }

  const chatIds = (d.prepare('SELECT DISTINCT chat_id FROM memories UNION SELECT DISTINCT chat_id FROM memory_vectors').all() as Array<{ chat_id: string }>)
    .map(r => r.chat_id);

  // Extraction state
  const extRow = d.prepare('SELECT MAX(last_run_at) as last_run, SUM(facts_total) as total FROM extraction_state').get() as { last_run: number | null; total: number | null } | undefined;

  return {
    totalMemories,
    totalVectors,
    totalConversationTurns,
    categoryDistribution,
    actionItemCount,
    chatIds,
    lastExtractionRun: extRow?.last_run ?? null,
    totalFactsExtracted: extRow?.total ?? 0,
  };
}
