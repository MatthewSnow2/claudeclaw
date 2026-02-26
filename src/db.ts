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
  `);
}

export function initDatabase(): void {
  fs.mkdirSync(STORE_DIR, { recursive: true });
  const dbPath = path.join(STORE_DIR, 'claudeclaw.db');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
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

export type WorkerType = 'starscream' | 'ravage' | 'soundwave' | 'default';
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
  // Atomic claim: find oldest queued task for this worker type and set to running
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

  return { ...task, status: 'running', started_at: now };
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
