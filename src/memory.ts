import http from 'http';

import {
  decayMemories,
  decayMemoryVectors,
  getMemoryVectors,
  getRecentMemories,
  logConversationTurn,
  pruneConversationLog,
  searchMemories,
  touchMemory,
  touchMemoryVector,
} from './db.js';
import { logger } from './logger.js';

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
 * Build a compact memory context string to prepend to the user's message.
 * Uses 3-layer progressive disclosure:
 *   Layer 1: FTS5 keyword search against user message -> top 3 results
 *   Layer 2: Vector similarity search via nomic-embed-text -> top 3 results (threshold > 0.3)
 *   Layer 3: Most recent 5 memories (recency)
 *   Deduplicates across all layers.
 *
 * Graceful degradation: if Ollama is down, Layer 2 is silently skipped.
 * Returns empty string if no memories exist for this chat.
 */
export async function buildMemoryContext(
  chatId: string,
  userMessage: string,
): Promise<string> {
  const seenIds = new Set<number>();       // dedup within memories table (by row id)
  const seenContent = new Set<string>();   // cross-table dedup (by normalized content)
  const lines: string[] = [];

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
    lines.push(`- ${mem.content} (${mem.sector})`);
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
          lines.push(`- ${v.content} (${label})`);
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
    lines.push(`- ${mem.content} (${mem.sector})`);
  }

  if (lines.length === 0) return '';

  return `[Memory context]\n${lines.join('\n')}\n[End memory context]`;
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
