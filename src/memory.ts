import { promises as fsPromises } from 'fs';
import http from 'http';
import path from 'path';

import {
  decayMemories,
  decayMemoryVectors,
  getActiveTopic,
  getMemoryVectors,
  getRecentConversation,
  getRecentMemories,
  getSessionDirectives,
  logConversationTurn,
  pruneConversationLog,
  searchMemories,
  touchMemory,
  touchMemoryVector,
} from './db.js';
import { logger } from './logger.js';

// Perceptor config
const PERCEPTOR_INDEX_PATH = '/home/apexaipc/projects/perceptor/.perceptor/index.json';
const PERCEPTOR_MAX_RESULTS = 2;

// Ollama config for query-time embedding
const OLLAMA_BASE_URL = 'http://127.0.0.1:11434';
const EMBEDDING_MODEL = 'nomic-embed-text';
const EMBEDDING_DIMS = 768;
const SIMILARITY_THRESHOLD = 0.3;

/**
 * Embed text via Ollama nomic-embed-text.
 * Returns a Buffer of 768 little-endian float32s, or null if Ollama is down.
 * Typical latency: ~50ms.
 */
export function embedQuery(text: string): Promise<Buffer | null> {
  return new Promise((resolve) => {
    const payload = JSON.stringify({ model: EMBEDDING_MODEL, input: text });
    const url = new URL(`${OLLAMA_BASE_URL}/api/embed`);

    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        timeout: 10_000,
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          try {
            const data = JSON.parse(Buffer.concat(chunks).toString('utf-8'));
            const embeddings = data?.embeddings as number[][] | undefined;
            if (!embeddings || !embeddings[0] || embeddings[0].length !== EMBEDDING_DIMS) {
              resolve(null);
              return;
            }
            // Pack as little-endian float32 array (matches Python struct.pack('<768f'))
            const buf = Buffer.alloc(EMBEDDING_DIMS * 4);
            for (let i = 0; i < EMBEDDING_DIMS; i++) {
              buf.writeFloatLE(embeddings[0][i], i * 4);
            }
            resolve(buf);
          } catch {
            resolve(null);
          }
        });
      },
    );

    req.on('error', () => resolve(null));
    req.on('timeout', () => {
      req.destroy();
      resolve(null);
    });

    req.write(payload);
    req.end();
  });
}

/**
 * Compute cosine similarity between two embedding buffers.
 * Both must be little-endian float32 arrays of `dim` elements.
 */
export function cosineSimilarity(a: Buffer, b: Buffer, dim: number = EMBEDDING_DIMS): number {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < dim; i++) {
    const offset = i * 4;
    const va = a.readFloatLE(offset);
    const vb = b.readFloatLE(offset);
    dotProduct += va * vb;
    normA += va * va;
    normB += vb * vb;
  }

  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  if (denom === 0) return 0;
  return dotProduct / denom;
}

/**
 * Search Perceptor contexts by keyword matching against index metadata.
 * Returns top N matching context summaries. Filesystem-based, no MCP dependency.
 * Graceful degradation: returns [] if index is missing or unreadable.
 */
async function searchPerceptorContexts(
  query: string,
  limit: number = PERCEPTOR_MAX_RESULTS,
): Promise<Array<{ title: string; summary: string; score: number }>> {
  try {
    const raw = await fsPromises.readFile(PERCEPTOR_INDEX_PATH, 'utf-8');
    const index = JSON.parse(raw) as {
      contexts: Array<{
        title: string;
        summary: string;
        tags: string[];
        projects: string[];
        archived?: boolean;
      }>;
    };

    const queryLower = query.toLowerCase();
    const queryWords = queryLower.split(/\s+/).filter((w) => w.length > 3);

    const scored = index.contexts
      .filter((c) => !c.archived)
      .map((ctx) => {
        let score = 0;
        const titleLower = ctx.title.toLowerCase();
        const summaryLower = ctx.summary.toLowerCase();
        const tagsLower = ctx.tags.map((t) => t.toLowerCase());

        for (const word of queryWords) {
          if (titleLower.includes(word)) score += 0.4;
          if (summaryLower.includes(word)) score += 0.2;
          if (tagsLower.some((t) => t.includes(word))) score += 0.3;
        }
        // Normalize by word count so longer queries don't inflate scores
        if (queryWords.length > 0) score /= queryWords.length;

        return { title: ctx.title, summary: ctx.summary, score };
      })
      .filter((r) => r.score > 0.15)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    return scored;
  } catch (err) {
    logger.debug({ err }, 'Perceptor context search failed (graceful degradation)');
    return [];
  }
}

/**
 * Build a structured context string to prepend to the user's message.
 *
 * Context hierarchy (injected in this order for positional priority):
 *   Layer A: Active topic anchor (1-line summary of current discussion thread)
 *   Layer B: Session directives (explicit user instructions like "no Christensen filter")
 *   Layer C: Recent conversation turns (last 6 raw messages for thread continuity)
 *   Layer 1: FTS5 keyword search against user message -> top 3 results
 *   Layer 2: Vector similarity search via nomic-embed-text -> top 3 results (threshold > 0.3)
 *   Layer 3: Most recent 5 memories (recency)
 *   Layer 4: Perceptor cross-session contexts -> top 2 results
 *   Deduplicates across memory layers (1-4).
 *
 * Graceful degradation: if Ollama is down, Layer 2 is silently skipped.
 * If Perceptor index is missing, Layer 4 is silently skipped.
 * Returns empty string if no context exists for this chat.
 */
export async function buildMemoryContext(
  chatId: string,
  userMessage: string,
): Promise<string> {
  const sections: string[] = [];

  // ── Layer A: Active topic anchor ──────────────────────────────────
  // Highest positional priority. Prevents system-prompt gravity from
  // pulling the model toward a default topic (e.g. ST Metro) when the
  // conversation is about something else entirely.
  const activeTopic = getActiveTopic(chatId);
  if (activeTopic) {
    sections.push(`[Active topic: ${activeTopic}]`);
  }

  // ── Layer B: Session directives ───────────────────────────────────
  // Explicit user instructions that persist within a session.
  // e.g. "no Christensen filter", "respond in bullet points"
  const directives = getSessionDirectives(chatId);
  if (directives.length > 0) {
    const directiveLines = directives.map((d) => `- ${d.directive}`).join('\n');
    sections.push(`[Session directives -- these are explicit user instructions, follow them]\n${directiveLines}\n[End session directives]`);
  }

  // ── Layer C: Recent conversation turns ────────────────────────────
  // Raw recency anchor: last 6 turns from conversation_log.
  // Provides thread continuity across sessions and after /respin.
  // Truncated to 250 chars per turn to keep context compact.
  const recentTurns = getRecentConversation(chatId, 6);
  if (recentTurns.length > 0) {
    const turnLines = recentTurns
      .reverse() // chronological order (getRecentConversation returns DESC)
      .map((t) => {
        const content = t.content.length > 250
          ? t.content.slice(0, 250) + '...'
          : t.content;
        return `[${t.role}]: ${content}`;
      })
      .join('\n');
    sections.push(`[Recent conversation]\n${turnLines}\n[End recent conversation]`);
  }

  // ── Layers 1-4: Memory context ────────────────────────────────────
  const seenIds = new Set<number>();       // dedup within memories table (by row id)
  const seenContent = new Set<string>();   // cross-table dedup (by normalized content)
  const memLines: string[] = [];

  /** Normalize content for cross-table dedup comparison. */
  const normalizeContent = (s: string): string => s.trim().toLowerCase();

  // Layer 1: FTS5 keyword search
  const searched = searchMemories(chatId, userMessage, 3);
  for (const mem of searched) {
    const key = normalizeContent(mem.content);
    if (seenContent.has(key)) continue;
    seenIds.add(mem.id);
    seenContent.add(key);
    touchMemory(mem.id);
    memLines.push(`- ${mem.content} (${mem.sector})`);
  }

  // Layer 2: Vector similarity search (graceful degradation if Ollama down)
  try {
    const queryEmbedding = await embedQuery(userMessage);
    if (queryEmbedding) {
      const vectors = getMemoryVectors(chatId);
      if (vectors.length > 0) {
        // Score all vectors and pick top 3 above threshold
        const scored = vectors
          .map((v) => ({
            ...v,
            score: cosineSimilarity(queryEmbedding, v.embedding),
          }))
          .filter((v) => v.score >= SIMILARITY_THRESHOLD)
          .sort((a, b) => b.score - a.score)
          .slice(0, 3);

        for (const v of scored) {
          const key = normalizeContent(v.content);
          if (seenContent.has(key)) continue;
          seenContent.add(key);
          touchMemoryVector(v.id);
          const label = v.category ? `vector:${v.category}` : 'vector';
          memLines.push(`- ${v.content} (${label})`);
        }
      }
    }
  } catch (err) {
    logger.debug({ err }, 'Vector search failed (graceful degradation)');
  }

  // Layer 3: Recent memories (deduplicated against Layer 1 by id AND content)
  const recent = getRecentMemories(chatId, 5);
  for (const mem of recent) {
    if (seenIds.has(mem.id)) continue;
    const key = normalizeContent(mem.content);
    if (seenContent.has(key)) continue;
    seenIds.add(mem.id);
    seenContent.add(key);
    touchMemory(mem.id);
    memLines.push(`- ${mem.content} (${mem.sector})`);
  }

  // Layer 4: Perceptor cross-session contexts (graceful degradation if index missing)
  try {
    const perceptorResults = await searchPerceptorContexts(userMessage);
    for (const ctx of perceptorResults) {
      const key = normalizeContent(ctx.summary);
      if (seenContent.has(key)) continue;
      seenContent.add(key);
      // Truncate summary to keep context compact
      const summary = ctx.summary.length > 200 ? ctx.summary.slice(0, 200) + '...' : ctx.summary;
      memLines.push(`- ${summary} (perceptor:${ctx.title.slice(0, 40)})`);
    }
  } catch (err) {
    logger.debug({ err }, 'Perceptor layer failed (graceful degradation)');
  }

  if (memLines.length > 0) {
    sections.push(`[Memory context]\n${memLines.join('\n')}\n[End memory context]`);
  }

  if (sections.length === 0) return '';

  return sections.join('\n\n');
}

/**
 * Log a conversation turn and persist to conversation_log.
 * Called AFTER Claude responds, with both user message and Claude's response.
 *
 * Memory extraction is handled by Phase 7 (extract_memories.py via Qwen),
 * which runs every 30 minutes on cron and produces higher-quality facts
 * than regex matching. This function only logs the raw conversation so
 * Phase 7 has material to work with.
 */
export function saveConversationTurn(
  chatId: string,
  userMessage: string,
  claudeResponse: string,
  sessionId?: string,
): void {
  // Log full conversation to conversation_log (for /respin and Phase 7 extraction)
  logConversationTurn(chatId, 'user', userMessage, sessionId);
  logConversationTurn(chatId, 'assistant', claudeResponse, sessionId);
}

/**
 * Run the daily decay sweep. Call once on startup and every 24h.
 * Also prunes old conversation_log entries and decays vector memories.
 */
export function runDecaySweep(): void {
  decayMemories();
  decayMemoryVectors();
  pruneConversationLog(500);
}
