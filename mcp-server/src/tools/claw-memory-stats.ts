import { getMemoryStats } from '../services/index.js';
import type { ToolResult } from '../types/index.js';
import { logger } from '../utils/index.js';

export const clawMemoryStatsTool = {
  name: 'claw_memory_stats',
  description:
    'Get aggregate statistics about ClaudeClaw memory: total counts, ' +
    'category distributions, action items, extraction pipeline status. ' +
    'Does not require Ollama.',
  inputSchema: {
    type: 'object' as const,
    properties: {},
    required: [],
  },
};

export async function executeClawMemoryStats(
  _args: Record<string, unknown>,
): Promise<ToolResult> {
  try {
    const stats = getMemoryStats();

    const catLines = Object.entries(stats.categoryDistribution)
      .sort(([, a], [, b]) => b - a)
      .map(([cat, count]) => `  - ${cat}: ${count}`);

    const lastRun = stats.lastExtractionRun
      ? new Date(stats.lastExtractionRun * 1000).toISOString()
      : 'never';

    const output = [
      '## ClaudeClaw Memory Stats',
      '',
      `| Metric | Value |`,
      `|--------|-------|`,
      `| Total memories (FTS) | ${stats.totalMemories} |`,
      `| Total vectors | ${stats.totalVectors} |`,
      `| Conversation turns | ${stats.totalConversationTurns} |`,
      `| Action items | ${stats.actionItemCount} |`,
      `| Total facts extracted | ${stats.totalFactsExtracted} |`,
      `| Last extraction run | ${lastRun} |`,
      `| Active chats | ${stats.chatIds.length} |`,
      '',
      '### Category Distribution',
      catLines.length > 0 ? catLines.join('\n') : '  _(no categories yet)_',
    ].join('\n');

    return { content: [{ type: 'text', text: output }] };

  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error('claw_memory_stats failed', { error: msg });
    return { content: [{ type: 'text', text: `Error: ${msg}` }], isError: true };
  }
}
