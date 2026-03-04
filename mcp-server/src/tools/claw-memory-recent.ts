import { getRecentMemoryVectors } from '../services/index.js';
import type { ToolResult } from '../types/index.js';
import { logger } from '../utils/index.js';

export const clawMemoryRecentTool = {
  name: 'claw_memory_recent',
  description:
    'Retrieve the most recently accessed ClaudeClaw memory vectors. ' +
    'Optionally filter by chat_id, sector, or category. ' +
    'Does not require Ollama.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      limit: { type: 'number', description: 'Max results to return (default: 10)' },
      chat_id: { type: 'string', description: 'Filter to a specific chat ID' },
      sector: { type: 'string', description: 'Filter by sector (e.g., semantic, episodic)' },
      category: {
        type: 'string',
        description: 'Filter by category: decision, preference, project_state, action_item, technical_detail, person_info, insight',
      },
    },
    required: [],
  },
};

export async function executeClawMemoryRecent(
  args: Record<string, unknown>,
): Promise<ToolResult> {
  try {
    const limit = (args.limit as number) ?? 10;
    const chatId = args.chat_id as string | undefined;
    const sector = args.sector as string | undefined;
    const category = args.category as string | undefined;

    const results = getRecentMemoryVectors(limit, chatId, sector, category);

    if (results.length === 0) {
      return { content: [{ type: 'text', text: 'No recent memory vectors found.' }] };
    }

    const lines = results.map((v) => {
      const cat = v.category ? ` [${v.category}]` : '';
      let tags = '';
      if (v.tags) {
        try { tags = ` tags:${JSON.parse(v.tags).join(',')}`; } catch { /* ignore */ }
      }
      let people = '';
      if (v.people) {
        try { people = ` people:${JSON.parse(v.people).join(',')}`; } catch { /* ignore */ }
      }
      const date = new Date(v.accessed_at * 1000).toISOString().split('T')[0];
      const actionFlag = v.is_action_item ? ' [ACTION]' : '';
      return `- **${v.content}**${cat}${actionFlag}${tags}${people} (accessed: ${date}, confidence: ${(v.confidence ?? 1).toFixed(2)})`;
    });

    const filters = [chatId && `chat:${chatId}`, category && `category:${category}`, sector && `sector:${sector}`].filter(Boolean).join(', ');
    const filterLabel = filters ? ` (${filters})` : '';

    const output = `## Recent Memories${filterLabel}\n\n${lines.join('\n')}\n\n_${results.length} results_`;
    return { content: [{ type: 'text', text: output }] };

  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error('claw_memory_recent failed', { error: msg });
    return { content: [{ type: 'text', text: `Error: ${msg}` }], isError: true };
  }
}
