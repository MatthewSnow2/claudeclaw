import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { closeDb } from './services/index.js';
import {
  clawMemorySearchTool,
  executeClawMemorySearch,
  clawMemoryKeywordTool,
  executeClawMemoryKeyword,
  clawMemoryRecentTool,
  executeClawMemoryRecent,
  clawMemoryStatsTool,
  executeClawMemoryStats,
} from './tools/index.js';
import type { ToolResult } from './types/index.js';
import { logger } from './utils/index.js';

const server = new Server(
  { name: 'claudeclaw-memory', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

const TOOLS = [
  clawMemorySearchTool,
  clawMemoryKeywordTool,
  clawMemoryRecentTool,
  clawMemoryStatsTool,
];

const toolExecutors: Record<
  string,
  (args: Record<string, unknown>) => Promise<ToolResult>
> = {
  claw_memory_search: executeClawMemorySearch,
  claw_memory_keyword: executeClawMemoryKeyword,
  claw_memory_recent: executeClawMemoryRecent,
  claw_memory_stats: executeClawMemoryStats,
};

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const executor = toolExecutors[name];

  if (!executor) {
    return {
      content: [{ type: 'text' as const, text: `Unknown tool: ${name}` }],
      isError: true,
    };
  }

  try {
    return await executor(args ?? {});
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    logger.error(`Tool ${name} failed`, { error: msg });
    return {
      content: [{ type: 'text' as const, text: `Tool failed: ${msg}` }],
      isError: true,
    };
  }
});

async function main(): Promise<void> {
  logger.info('ClaudeClaw Memory MCP server starting');
  const transport = new StdioServerTransport();
  await server.connect(transport);
  logger.info('Server connected via stdio');
}

// Clean up on exit
process.on('SIGINT', () => {
  closeDb();
  process.exit(0);
});
process.on('SIGTERM', () => {
  closeDb();
  process.exit(0);
});

main().catch((error) => {
  logger.error('Fatal error', { error: String(error) });
  process.exit(1);
});
