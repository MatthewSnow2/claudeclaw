import { getAllMemoryVectors, embedQuery, cosineSimilarity } from '../services/index.js';
import type { ToolResult } from '../types/index.js';
import { logger } from '../utils/index.js';

export const clawMemorySearchTool = {
  name: 'claw_memory_search',
  description:
    'Semantic similarity search over ClaudeClaw extracted memory vectors. ' +
    'Embeds the query via Ollama nomic-embed-text and returns the most similar memories. ' +
    'Requires Ollama to be running. Gracefully degrades if unavailable.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      query: { type: 'string', description: 'The search query to embed and compare' },
      limit: { type: 'number', description: 'Max results to return (default: 5)' },
      threshold: { type: 'number', description: 'Minimum cosine similarity threshold (default: 0.3)' },
      chat_id: { type: 'string', description: 'Filter to a specific chat ID (optional)' },
    },
    required: ['query'],
  },
};

export async function executeClawMemorySearch(
  args: Record<string, unknown>,
): Promise<ToolResult> {
  try {
    const query = args.query as string;
    const limit = (args.limit as number) ?? 5;
    const threshold = (args.threshold as number) ?? 0.3;
    const chatId = args.chat_id as string | undefined;

    if (!query) {
      return { content: [{ type: 'text', text: 'Error: query is required' }], isError: true };
    }

    // Embed the query
    const queryEmbedding = await embedQuery(query);
    if (!queryEmbedding) {
      return {
        content: [{
          type: 'text',
          text: '**Ollama unavailable** -- semantic search requires Ollama with nomic-embed-text. ' +
            'Try `claw_memory_keyword` for keyword-based search instead.',
        }],
      };
    }

    const vectors = getAllMemoryVectors(chatId);
    if (vectors.length === 0) {
      return { content: [{ type: 'text', text: 'No memory vectors found.' }] };
    }

    // Score and filter
    const scored = vectors
      .map((v) => {
        const score = cosineSimilarity(queryEmbedding, v.embedding);
        const adjustedScore = v.confidence != null ? score * v.confidence : score;
        return { ...v, score, adjustedScore };
      })
      .filter((v) => v.score >= threshold)
      .sort((a, b) => b.adjustedScore - a.adjustedScore)
      .slice(0, limit);

    if (scored.length === 0) {
      return { content: [{ type: 'text', text: `No memories found above similarity threshold ${threshold}.` }] };
    }

    // Format output
    const lines = scored.map((v) => {
      const cat = v.category ? ` [${v.category}]` : '';
      let tags = '';
      if (v.tags) {
        try { tags = ` tags:${JSON.parse(v.tags).join(',')}`; } catch { /* ignore */ }
      }
      let people = '';
      if (v.people) {
        try { people = ` people:${JSON.parse(v.people).join(',')}`; } catch { /* ignore */ }
      }
      const date = new Date(v.created_at * 1000).toISOString().split('T')[0];
      return `- **${v.content}**${cat}${tags}${people} (score: ${v.adjustedScore.toFixed(3)}, date: ${date})`;
    });

    const output = `## Semantic Search: "${query}"\n\n${lines.join('\n')}\n\n_${scored.length} results from ${vectors.length} total vectors_`;
    return { content: [{ type: 'text', text: output }] };

  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error('claw_memory_search failed', { error: msg });
    return { content: [{ type: 'text', text: `Error: ${msg}` }], isError: true };
  }
}
