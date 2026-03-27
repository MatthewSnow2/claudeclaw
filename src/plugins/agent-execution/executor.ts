/**
 * Agent Execution Engine — runs agents with scoped tools via the Agent SDK.
 *
 * Replaces CMD's CLI subprocess approach with SDK-native execution.
 * Uses query() with tools, maxTurns, and systemPrompt options for isolation.
 */

import { query } from '@anthropic-ai/claude-agent-sdk';

import { readEnvFile } from '../../env.js';
import { logger } from '../../logger.js';
import type { UsageInfo } from '../../agent.js';
import type { ExecutorRequest, ExecutorResult } from './types.js';

/**
 * Execute an agent with scoped tools and constraints via the Agent SDK.
 *
 * This is the replacement for both:
 * - EAC's prompt-inject path (runAgent with prepended CLAUDE.md)
 * - CMD's CLI subprocess path (spawn claude with --allowedTools)
 *
 * The SDK handles tool scoping, max turns, and MCP server isolation natively.
 */
export async function executeWithEngine(
  request: ExecutorRequest,
): Promise<ExecutorResult> {
  const { agentId, prompt, cwd, systemPrompt, model, execution, abortController } = request;
  const start = Date.now();

  logger.info(
    { agentId, mode: execution.mode, tools: execution.tools, maxTurns: execution.maxTurns },
    'Execution engine: starting agent',
  );

  request.onProgress?.(`Running ${agentId} (scoped execution)...`);

  // Build tool list — add Agent tool if canSpawnSubAgents
  const tools = [...execution.tools];
  if (execution.canSpawnSubAgents && !tools.includes('Agent')) {
    tools.push('Agent');
  }

  // Build MCP server specs for SDK
  const mcpServers: string[] = [];
  // SDK accepts AgentMcpServerSpec which can be string (server name) or config object.
  // For now we pass the server configs as additional MCP if present.
  // TODO: When SDK supports McpServerConfigForProcessTransport in options.mcpServers,
  // pass the full config objects here.

  // Auth: same pattern as agent.ts — strip ANTHROPIC_API_KEY, use OAuth
  const secrets = readEnvFile(['CLAUDE_CODE_OAUTH_TOKEN']);
  const sdkEnv: Record<string, string | undefined> = { ...process.env };
  delete sdkEnv.ANTHROPIC_API_KEY;
  if (secrets.CLAUDE_CODE_OAUTH_TOKEN) {
    sdkEnv.CLAUDE_CODE_OAUTH_TOKEN = secrets.CLAUDE_CODE_OAUTH_TOKEN;
  }

  // Inject MCP server env vars into the subprocess environment
  for (const serverConfig of Object.values(execution.mcpServers)) {
    if (serverConfig.env) {
      Object.assign(sdkEnv, serverConfig.env);
    }
  }

  // Build system prompt with preset + append pattern
  // This preserves Claude Code's built-in tool instructions while injecting agent persona
  const systemPromptConfig = systemPrompt
    ? { type: 'preset' as const, preset: 'claude_code' as const, append: systemPrompt }
    : undefined;

  let resultText: string | null = null;
  let lastAssistantText: string | null = null;
  let usage: UsageInfo | null = null;
  let didCompact = false;
  let preCompactTokens: number | null = null;
  let lastCallCacheRead = 0;
  let lastCallInputTokens = 0;

  // Set up timeout via abort controller
  const timeoutAbort = new AbortController();
  const timer = setTimeout(() => timeoutAbort.abort(), execution.timeout);

  // Link caller's abort to our timeout abort
  const onCallerAbort = () => timeoutAbort.abort();
  abortController?.signal.addEventListener('abort', onCallerAbort);

  try {
    for await (const event of query({
      prompt,
      options: {
        cwd,
        tools,
        maxTurns: execution.maxTurns,
        systemPrompt: systemPromptConfig,
        permissionMode: 'bypassPermissions',
        allowDangerouslySkipPermissions: true,
        persistSession: false,
        settingSources: [],
        env: sdkEnv,
        abortController: timeoutAbort,
        ...(model ? { model } : {}),
      },
    })) {
      const ev = event as Record<string, unknown>;

      // Track session init
      if (ev['type'] === 'system' && ev['subtype'] === 'init') {
        logger.info({ agentId, sessionId: ev['session_id'] }, 'Execution engine: session init');
      }

      // Detect compaction
      if (ev['type'] === 'system' && ev['subtype'] === 'compact_boundary') {
        didCompact = true;
        const meta = ev['compact_metadata'] as { trigger: string; pre_tokens: number } | undefined;
        preCompactTokens = meta?.pre_tokens ?? null;
      }

      // Track per-call usage and capture assistant text
      if (ev['type'] === 'assistant') {
        const msg = ev['message'] as Record<string, unknown> | undefined;
        const msgUsage = msg?.['usage'] as Record<string, number> | undefined;
        if (msgUsage?.['cache_read_input_tokens']) {
          lastCallCacheRead = msgUsage['cache_read_input_tokens'];
        }
        if (msgUsage?.['input_tokens']) {
          lastCallInputTokens = msgUsage['input_tokens'];
        }

        const content = msg?.['content'] as Array<{ type: string; text?: string; name?: string }> | undefined;
        if (content) {
          const textParts = content.filter((b) => b.type === 'text' && b.text).map((b) => b.text!);
          if (textParts.length > 0) {
            lastAssistantText = textParts.join('');
          }

          // Report tool use progress
          if (request.onProgress) {
            for (const block of content) {
              if (block.type === 'tool_use' && block.name) {
                request.onProgress(`${agentId}: ${block.name}`);
              }
            }
          }
        }
      }

      // Capture result
      if (ev['type'] === 'result') {
        resultText = (ev['result'] as string | null | undefined) ?? null;

        const evUsage = ev['usage'] as Record<string, number> | undefined;
        if (evUsage) {
          usage = {
            inputTokens: evUsage['input_tokens'] ?? 0,
            outputTokens: evUsage['output_tokens'] ?? 0,
            cacheReadInputTokens: evUsage['cache_read_input_tokens'] ?? 0,
            totalCostUsd: (ev['total_cost_usd'] as number) ?? 0,
            didCompact,
            preCompactTokens,
            lastCallCacheRead,
            lastCallInputTokens,
          };
        }

        logger.info(
          { agentId, hasResult: !!resultText, costUsd: usage?.totalCostUsd },
          'Execution engine: agent completed',
        );
      }
    }
  } catch (err) {
    if (timeoutAbort.signal.aborted) {
      const durationMs = Date.now() - start;
      logger.warn({ agentId, durationMs }, 'Execution engine: agent aborted/timed out');
      return { text: null, usage, aborted: true, durationMs };
    }
    throw err;
  } finally {
    clearTimeout(timer);
    abortController?.signal.removeEventListener('abort', onCallerAbort);
  }

  const durationMs = Date.now() - start;
  request.onProgress?.(`${agentId} completed (${Math.round(durationMs / 1000)}s)`);

  return {
    text: resultText || lastAssistantText,
    usage,
    durationMs,
  };
}
