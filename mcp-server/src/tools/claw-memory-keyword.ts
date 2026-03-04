import { searchMemoriesFts } from '../services/index.js';
import type { ToolResult } from '../types/index.js';
import { logger } from '../utils/index.js';

export const clawMemoryKeywordTool = {
  name: 'claw_memory_keyword',
  description:
    'FTS5 keyword search over ClaudeClaw memories. ' +
    'Searches the memories table using SQLite full-text search. ' +
    'Does not require Ollama -- works offline.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      query: { type: 'string', description: 'Keywords to search for' },
      limit: { type: 'number', description: 'Max results to return (default: 10)' },
    },
    required: ['query'],
  },
};

export async function executeClawMemoryKeyword(
  args: Record<string, unknown>,
): Promise<ToolResult> {
  try {
    const query = args.query as string;
    const limit = (args.limit as number) ?? 10;

    if (!query) {
      return { content: [{ type: 'text', text: 'Error: query is required' }], isError: true };
    }

    const results = searchMemoriesFts(query, limit);

    if (results.length === 0) {
      return { content: [{ type: 'text', text: `No keyword matches for "${query}".` }] };
    }

    const lines = results.map((m) => {
      const date = new Date(m.created_at * 1000).toISOString().split('T')[0];
      return `- **${m.content}** (${m.sector}, salience: ${m.salience.toFixed(2)}, date: ${date})`;
    });

    const output = `## Keyword Search: "${query}"\n\n${lines.join('\n')}\n\n_${results.length} results_`;
    return { content: [{ type: 'text', text: output }] };

  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error('claw_memory_keyword failed', { error: msg });
    return { content: [{ type: 'text', text: `Error: ${msg}` }], isError: true };
  }
}
