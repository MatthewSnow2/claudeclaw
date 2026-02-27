import crypto from 'crypto';

import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';

import { STORE_DIR } from './config.js';

let db: Database.Database;

function createSchema(database: Database.Database): void {
  database.exec(`
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
      id          TEXT PRIMARY KEY,
      prompt      TEXT NOT NULL,
      schedule    TEXT NOT NULL,
      next_run    INTEGER NOT NULL,
      last_run    INTEGER,
      last_result TEXT,
      status      TEXT NOT NULL DEFAULT 'active',
      created_at  INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON scheduled_tasks(status, next_run);

    CREATE TABLE IF NOT EXISTS sessions (
      chat_id   TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS memories (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id     TEXT NOT NULL,
      topic_key   TEXT,
      content     TEXT NOT NULL,
      sector      TEXT NOT NULL DEFAULT 'semantic',
      salience    REAL NOT NULL DEFAULT 1.0,
      created_at  INTEGER NOT NULL,
      accessed_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_memories_chat ON memories(chat_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_memories_sector ON memories(chat_id, sector);

    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
      content,
      content=memories,
      content_rowid=id
    );

    CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
      INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
    END;

    CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
    END;

    CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
      INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
    END;

    CREATE TABLE IF NOT EXISTS dispatch_queue (
      id TEXT PRIMARY KEY,
      chat_id TEXT NOT NULL,
      prompt TEXT NOT NULL,
      worker_type TEXT NOT NULL,
      status TEXT DEFAULT 'queued',
      result TEXT,
      session_id TEXT,
      created_at INTEGER NOT NULL,
      started_at INTEGER,
      completed_at INTEGER,
      error TEXT,
      notified INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_queue(status);
    CREATE INDEX IF NOT EXISTS idx_dispatch_worker ON dispatch_queue(worker_type, status);

    CREATE TABLE IF NOT EXISTS conversation_log (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id     TEXT NOT NULL,
      session_id  TEXT,
      role        TEXT NOT NULL,
      content     TEXT NOT NULL,
      created_at  INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_convo_log_chat ON conversation_log(chat_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS token_usage (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id         TEXT NOT NULL,
      session_id      TEXT,
      input_tokens    INTEGER NOT NULL DEFAULT 0,
      output_tokens   INTEGER NOT NULL DEFAULT 0,
      cache_read      INTEGER NOT NULL DEFAULT 0,
      cost_usd        REAL NOT NULL DEFAULT 0,
      did_compact     INTEGER NOT NULL DEFAULT 0,
      created_at      INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_token_usage_chat ON token_usage(chat_id, created_at DESC);

    CREATE TABLE IF NOT EXISTS processed_messages (
      message_id  INTEGER PRIMARY KEY,
      created_at  INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS memory_vectors (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id         TEXT NOT NULL,
      content         TEXT NOT NULL,
      source_type     TEXT NOT NULL DEFAULT 'extraction',
      embedding       BLOB NOT NULL,
      salience        REAL NOT NULL DEFAULT 1.0,
      created_at      INTEGER NOT NULL,
      accessed_at     INTEGER NOT NULL,
      source_log_ids  TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_memvec_chat ON memory_vectors(chat_id);

    CREATE TABLE IF NOT EXISTS extraction_state (
      chat_id         TEXT PRIMARY KEY,
      last_log_id     INTEGER NOT NULL DEFAULT 0,
      last_run_at     INTEGER NOT NULL,
      facts_total     INTEGER NOT NULL DEFAULT 0
    );
  `);
}

export function initDatabase(): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('busy_timeout = 5000');
  createSchema(db);
}

/** @internal - for tests only. Creates a fresh in-memory database. */
export function _initTestDatabase(): void {
  db = new Database(':memory:');
  db.pragma('journal_mode = WAL');
  createSchema(db);
}

export function getSession(chatId: string): string | undefined {
  const row = db
    .prepare('SELECT session_id FROM sessions WHERE chat_id = ?')
    .get(chatId) as { session_id: string } | undefined;
  return row?.session_id;
}

export function setSession(chatId: string, sessionId: string): void {
  db.prepare(
    'INSERT OR REPLACE INTO sessions (chat_id, session_id, updated_at) VALUES (?, ?, ?)',
  ).run(chatId, sessionId, new Date().toISOString());
}

export function clearSession(chatId: string): void {
  db.prepare('DELETE FROM sessions WHERE chat_id = ?').run(chatId);
}

// ── Message Dedup ───────────────────────────────────────────────────
// SQLite-backed dedup survives PM2 restarts (unlike the old in-memory Map).
// Telegram re-delivers pending updates after a 409 conflict restart,
// so we need persistent tracking to avoid processing the same message twice.

const DEDUP_TTL_SECONDS = 600; // 10 minutes — well beyond Telegram's retry window

export function isMessageProcessed(messageId: number): boolean {
  const row = db
    .prepare('SELECT 1 FROM processed_messages WHERE message_id = ?')
    .get(messageId);
  return !!row;
}

export function markMessageProcessed(messageId: number): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    'INSERT OR IGNORE INTO processed_messages (message_id, created_at) VALUES (?, ?)',
  ).run(messageId, now);
}

export function pruneProcessedMessages(): void {
  const cutoff = Math.floor(Date.now() / 1000) - DEDUP_TTL_SECONDS;
  db.prepare('DELETE FROM processed_messages WHERE created_at < ?').run(cutoff);
}

// ── Memory ──────────────────────────────────────────────────────────

export interface Memory {
  id: number;
  chat_id: string;
  topic_key: string | null;
  content: string;
  sector: string;
  salience: number;
  created_at: number;
  accessed_at: number;
}

export function saveMemory(
  chatId: string,
  content: string,
  sector = 'semantic',
  topicKey?: string,
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO memories (chat_id, content, sector, topic_key, created_at, accessed_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(chatId, content, sector, topicKey ?? null, now, now);
}

export function searchMemories(
  chatId: string,
  query: string,
  limit = 3,
): Memory[] {
  // Sanitize for FTS5: strip special chars, add * for prefix matching
  const sanitized = query
    .replace(/[""]/g, '"')
    .replace(/[^\w\s]/g, '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => `"${w}"*`)
    .join(' ');

  if (!sanitized) return [];

  return db
    .prepare(
      `SELECT memories.* FROM memories
       JOIN memories_fts ON memories.id = memories_fts.rowid
       WHERE memories_fts MATCH ? AND memories.chat_id = ?
       ORDER BY rank
       LIMIT ?`,
    )
    .all(sanitized, chatId, limit) as Memory[];
}

export function getRecentMemories(chatId: string, limit = 5): Memory[] {
  return db
    .prepare(
      'SELECT * FROM memories WHERE chat_id = ? ORDER BY accessed_at DESC LIMIT ?',
    )
    .all(chatId, limit) as Memory[];
}

export function touchMemory(id: number): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    'UPDATE memories SET accessed_at = ?, salience = MIN(salience + 0.1, 5.0) WHERE id = ?',
  ).run(now, id);
}

export function decayMemories(): void {
  const oneDayAgo = Math.floor(Date.now() / 1000) - 86400;
  db.prepare(
    'UPDATE memories SET salience = salience * 0.98 WHERE created_at < ?',
  ).run(oneDayAgo);
  db.prepare('DELETE FROM memories WHERE salience < 0.1').run();
}

// ── Scheduled Tasks ──────────────────────────────────────────────────

export interface ScheduledTask {
  id: string;
  prompt: string;
  schedule: string;
  next_run: number;
  last_run: number | null;
  last_result: string | null;
  status: 'active' | 'paused';
  created_at: number;
}

export function createScheduledTask(
  id: string,
  prompt: string,
  schedule: string,
  nextRun: number,
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO scheduled_tasks (id, prompt, schedule, next_run, status, created_at)
     VALUES (?, ?, ?, ?, 'active', ?)`,
  ).run(id, prompt, schedule, nextRun, now);
}

export function getDueTasks(): ScheduledTask[] {
  const now = Math.floor(Date.now() / 1000);
  return db
    .prepare(
      `SELECT * FROM scheduled_tasks WHERE status = 'active' AND next_run <= ? ORDER BY next_run`,
    )
    .all(now) as ScheduledTask[];
}

export function getAllScheduledTasks(): ScheduledTask[] {
  return db
    .prepare('SELECT * FROM scheduled_tasks ORDER BY created_at DESC')
    .all() as ScheduledTask[];
}

export function updateTaskAfterRun(
  id: string,
  nextRun: number,
  result: string,
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `UPDATE scheduled_tasks SET last_run = ?, next_run = ?, last_result = ? WHERE id = ?`,
  ).run(now, nextRun, result.slice(0, 500), id);
}

export function deleteScheduledTask(id: string): void {
  db.prepare('DELETE FROM scheduled_tasks WHERE id = ?').run(id);
}

export function pauseScheduledTask(id: string): void {
  db.prepare(`UPDATE scheduled_tasks SET status = 'paused' WHERE id = ?`).run(id);
}

export function resumeScheduledTask(id: string): void {
  db.prepare(`UPDATE scheduled_tasks SET status = 'active' WHERE id = ?`).run(id);
}

// ── Dispatch Queue ──────────────────────────────────────────────────

export type WorkerType = 'starscream' | 'ravage' | 'soundwave' | 'astrotrain' | 'default';
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface DispatchTask {
  id: string;
  chat_id: string;
  prompt: string;
  worker_type: WorkerType;
  status: TaskStatus;
  result: string | null;
  session_id: string | null;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  error: string | null;
  notified: number;
}

export function enqueueTask(
  chatId: string,
  prompt: string,
  workerType: WorkerType,
): string {
  const id = crypto.randomUUID();
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO dispatch_queue (id, chat_id, prompt, worker_type, status, created_at)
     VALUES (?, ?, ?, ?, 'queued', ?)`,
  ).run(id, chatId, prompt, workerType, now);
  return id;
}

export function claimTask(workerType: WorkerType): DispatchTask | undefined {
  const now = Math.floor(Date.now() / 1000);
  // Atomic claim via transaction: prevents race conditions when multiple
  // worker processes poll simultaneously.
  const claimTx = db.transaction(() => {
    const task = db
      .prepare(
        `SELECT * FROM dispatch_queue
         WHERE worker_type = ? AND status = 'queued'
         ORDER BY created_at ASC
         LIMIT 1`,
      )
      .get(workerType) as DispatchTask | undefined;

    if (!task) return undefined;

    db.prepare(
      `UPDATE dispatch_queue SET status = 'running', started_at = ? WHERE id = ?`,
    ).run(now, task.id);

    return { ...task, status: 'running' as const, started_at: now };
  });

  return claimTx();
}

export function completeTask(id: string, result: string): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `UPDATE dispatch_queue SET status = 'completed', result = ?, completed_at = ? WHERE id = ?`,
  ).run(result, now, id);
}

export function failTask(id: string, error: string): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `UPDATE dispatch_queue SET status = 'failed', error = ?, completed_at = ? WHERE id = ?`,
  ).run(error, now, id);
}

export function getPendingResults(): DispatchTask[] {
  return db
    .prepare(
      `SELECT * FROM dispatch_queue
       WHERE status IN ('completed', 'failed') AND notified = 0
       ORDER BY completed_at ASC`,
    )
    .all() as DispatchTask[];
}

export function markNotified(id: string): void {
  db.prepare(
    `UPDATE dispatch_queue SET notified = 1 WHERE id = ?`,
  ).run(id);
}

export function resetStaleTasks(timeoutSeconds: number = 600): number {
  const cutoff = Math.floor(Date.now() / 1000) - timeoutSeconds;
  const result = db.prepare(
    `UPDATE dispatch_queue SET status = 'queued', started_at = NULL
     WHERE status = 'running' AND started_at < ?`,
  ).run(cutoff);
  return result.changes;
}

// ── Conversation Log ──────────────────────────────────────────────────

export interface ConversationTurn {
  id: number;
  chat_id: string;
  session_id: string | null;
  role: string;
  content: string;
  created_at: number;
}

export function logConversationTurn(
  chatId: string,
  role: 'user' | 'assistant',
  content: string,
  sessionId?: string,
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO conversation_log (chat_id, session_id, role, content, created_at)
     VALUES (?, ?, ?, ?, ?)`,
  ).run(chatId, sessionId ?? null, role, content, now);
}

export function getRecentConversation(
  chatId: string,
  limit = 20,
): ConversationTurn[] {
  return db
    .prepare(
      `SELECT * FROM conversation_log WHERE chat_id = ?
       ORDER BY created_at DESC LIMIT ?`,
    )
    .all(chatId, limit) as ConversationTurn[];
}

/**
 * Prune old conversation_log entries, keeping only the most recent N rows per chat.
 * Called alongside memory decay to prevent unbounded disk growth.
 */
export function pruneConversationLog(keepPerChat = 500): void {
  const chats = db
    .prepare('SELECT DISTINCT chat_id FROM conversation_log')
    .all() as Array<{ chat_id: string }>;

  const deleteStmt = db.prepare(`
    DELETE FROM conversation_log
    WHERE chat_id = ? AND id NOT IN (
      SELECT id FROM conversation_log
      WHERE chat_id = ?
      ORDER BY created_at DESC
      LIMIT ?
    )
  `);

  for (const chat of chats) {
    deleteStmt.run(chat.chat_id, chat.chat_id, keepPerChat);
  }
}

// ── Token Usage ──────────────────────────────────────────────────────

export function saveTokenUsage(
  chatId: string,
  sessionId: string | undefined,
  inputTokens: number,
  outputTokens: number,
  cacheRead: number,
  costUsd: number,
  didCompact: boolean,
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO token_usage (chat_id, session_id, input_tokens, output_tokens, cache_read, cost_usd, did_compact, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(chatId, sessionId ?? null, inputTokens, outputTokens, cacheRead, costUsd, didCompact ? 1 : 0, now);
}

export interface SessionTokenSummary {
  turns: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  lastCacheRead: number;
  totalCostUsd: number;
  compactions: number;
  firstTurnAt: number;
  lastTurnAt: number;
}

// ── Memory Vectors ──────────────────────────────────────────────────

export interface MemoryVector {
  id: number;
  chat_id: string;
  content: string;
  source_type: string;
  embedding: Buffer;
  salience: number;
  created_at: number;
  accessed_at: number;
  source_log_ids: string | null;
}

export function getMemoryVectors(chatId: string): MemoryVector[] {
  return db
    .prepare('SELECT * FROM memory_vectors WHERE chat_id = ?')
    .all(chatId) as MemoryVector[];
}

export function saveMemoryVector(
  chatId: string,
  content: string,
  embedding: Buffer,
  sourceLogIds?: string,
  sourceType = 'extraction',
): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT INTO memory_vectors (chat_id, content, source_type, embedding, salience, created_at, accessed_at, source_log_ids)
     VALUES (?, ?, ?, ?, 1.0, ?, ?, ?)`,
  ).run(chatId, content, sourceType, embedding, now, now, sourceLogIds ?? null);
}

export function touchMemoryVector(id: number): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    'UPDATE memory_vectors SET accessed_at = ?, salience = MIN(salience + 0.1, 5.0) WHERE id = ?',
  ).run(now, id);
}

export function decayMemoryVectors(): void {
  const oneDayAgo = Math.floor(Date.now() / 1000) - 86400;
  db.prepare(
    'UPDATE memory_vectors SET salience = salience * 0.98 WHERE created_at < ?',
  ).run(oneDayAgo);
  db.prepare('DELETE FROM memory_vectors WHERE salience < 0.1').run();
}

// ── Extraction State ────────────────────────────────────────────────

export function getExtractionWatermark(chatId: string): { lastLogId: number; factsTotal: number } {
  const row = db
    .prepare('SELECT last_log_id, facts_total FROM extraction_state WHERE chat_id = ?')
    .get(chatId) as { last_log_id: number; facts_total: number } | undefined;
  return row ? { lastLogId: row.last_log_id, factsTotal: row.facts_total } : { lastLogId: 0, factsTotal: 0 };
}

export function setExtractionWatermark(chatId: string, lastLogId: number, factsTotal: number): void {
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    `INSERT OR REPLACE INTO extraction_state (chat_id, last_log_id, last_run_at, facts_total)
     VALUES (?, ?, ?, ?)`,
  ).run(chatId, lastLogId, now, factsTotal);
}

export function getSessionTokenUsage(sessionId: string): SessionTokenSummary | null {
  const row = db
    .prepare(
      `SELECT
         COUNT(*)           as turns,
         SUM(input_tokens)  as totalInputTokens,
         SUM(output_tokens) as totalOutputTokens,
         SUM(cost_usd)      as totalCostUsd,
         SUM(did_compact)   as compactions,
         MIN(created_at)    as firstTurnAt,
         MAX(created_at)    as lastTurnAt
       FROM token_usage WHERE session_id = ?`,
    )
    .get(sessionId) as {
      turns: number;
      totalInputTokens: number;
      totalOutputTokens: number;
      totalCostUsd: number;
      compactions: number;
      firstTurnAt: number;
      lastTurnAt: number;
    } | undefined;

  if (!row || row.turns === 0) return null;

  // Get the most recent turn's cache_read -- that's the actual context window size
  const lastRow = db
    .prepare(
      `SELECT cache_read FROM token_usage
       WHERE session_id = ?
       ORDER BY created_at DESC LIMIT 1`,
    )
    .get(sessionId) as { cache_read: number } | undefined;

  return {
    turns: row.turns,
    totalInputTokens: row.totalInputTokens,
    totalOutputTokens: row.totalOutputTokens,
    lastCacheRead: lastRow?.cache_read ?? 0,
    totalCostUsd: row.totalCostUsd,
    compactions: row.compactions,
    firstTurnAt: row.firstTurnAt,
    lastTurnAt: row.lastTurnAt,
  };
}
