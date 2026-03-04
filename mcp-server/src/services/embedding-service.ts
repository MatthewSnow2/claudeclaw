import http from 'http';

import { getConfig } from '../config.js';
import { logger } from '../utils/index.js';

/**
 * Embed text via Ollama nomic-embed-text.
 * Returns a Buffer of 768 little-endian float32s, or null if Ollama is unavailable.
 * Duplicated from parent src/memory.ts (~60 lines, stable interface).
 */
export function embedQuery(text: string): Promise<Buffer | null> {
  const { ollamaBaseUrl, embeddingModel, embeddingDims } = getConfig();

  return new Promise((resolve) => {
    const payload = JSON.stringify({ model: embeddingModel, input: text });
    const url = new URL(`${ollamaBaseUrl}/api/embed`);

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
            if (!embeddings || !embeddings[0] || embeddings[0].length !== embeddingDims) {
              resolve(null);
              return;
            }
            const buf = Buffer.alloc(embeddingDims * 4);
            for (let i = 0; i < embeddingDims; i++) {
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
 * Both must be little-endian float32 arrays.
 */
export function cosineSimilarity(a: Buffer, b: Buffer, dim: number = 768): number {
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
