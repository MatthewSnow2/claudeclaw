import { query } from '@anthropic-ai/claude-agent-sdk';

import { getArcadeMcpConfig, isArcadeConfigured } from './arcade-config.js';
import { PROJECT_ROOT } from './config.js';
import { readLocalEnvFile } from './env.js';
import { logger } from './logger.js';
import * as telemetry from './telemetry.js';

export interface AgentResult {
  text: string | null;
  newSessionId: string | undefined;
}

/**
 * Minimum interval between progress updates sent to Telegram (ms).
 * Prevents message spam during rapid tool use.
 */
const PROGRESS_MIN_INTERVAL_MS = 15_000;

/**
 * Generate a human-readable summary of a tool invocation.
 * Returns null for tools that shouldn't surface as progress (internal/noisy).
 */
function describeToolUse(
  toolName: string,
  input: Record<string, unknown> | undefined,
): string | null {
  switch (toolName) {
    case 'Bash': {
      const cmd = input?.['command'] as string | undefined;
      if (cmd) {
        const short = cmd.length > 80 ? cmd.slice(0, 80) + '...' : cmd;
        return `Running: ${short}`;
      }
      return 'Running command...';
    }
    case 'Read': {
      const fp = input?.['file_path'] as string | undefined;
      if (fp) return `Reading ${fp.split('/').pop()}`;
      return 'Reading file...';
    }
    case 'Write': {
      const fp = input?.['file_path'] as string | undefined;
      if (fp) return `Writing ${fp.split('/').pop()}`;
      return 'Writing file...';
    }
    case 'Edit': {
      const fp = input?.['file_path'] as string | undefined;
      if (fp) return `Editing ${fp.split('/').pop()}`;
      return 'Editing file...';
    }
    case 'Grep':
    case 'Glob':
      return 'Searching codebase...';
    case 'WebSearch': {
      const q = input?.['query'] as string | undefined;
      if (q) return `Searching: ${q.slice(0, 60)}`;
      return 'Searching the web...';
    }
    case 'WebFetch':
      return 'Fetching web content...';
    case 'Task':
      return 'Launching sub-agent...';
    case 'TodoWrite':
    case 'ToolSearch':
      return null; // Internal, skip
    default:
      if (toolName.startsWith('mcp__arcade__')) {
        const parts = toolName.replace('mcp__arcade__', '').split('_');
        const provider = parts[0];
        const action = parts.slice(1).join(' ');
        return `${provider}: ${action}`;
      }
      return null;
  }
}

// Concurrency limiter: only 1 Claude subprocess at a time to avoid rate limit
// collisions with interactive Claude Code sessions.
const MAX_CONCURRENT_AGENTS = 1;
let activeAgentCalls = 0;

// Retry config for transient API errors (529 overloaded, 503 service unavailable)
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 10_000; // 10s, 20s, 40s

function isRetryableError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return msg.includes('529') || msg.includes('overloaded') || msg.includes('503');
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * A minimal AsyncIterable that yields a single user message then closes.
 * This is the format the Claude Agent SDK expects for its `prompt` parameter.
 * The SDK drives the agentic loop internally (tool use, multi-step reasoning)
 * and surfaces a final `result` event when done.
 */
async function* singleTurn(text: string): AsyncGenerator<{
  type: 'user';
  message: { role: 'user'; content: string };
  parent_tool_use_id: null;
  session_id: string;
}> {
  yield {
    type: 'user',
    message: { role: 'user', content: text },
    parent_tool_use_id: null,
    session_id: '',
  };
}

/**
 * Run a single user message through Claude Code and return the result.
 *
 * Uses `resume` to continue the same session across Telegram messages,
 * giving Claude persistent context without re-sending history.
 *
 * Auth: The SDK spawns the `claude` CLI subprocess which reads OAuth auth
 * from ~/.claude/ automatically (the same auth used in the terminal).
 * No explicit token needed if Mark is already logged in via `claude login`.
 * Optionally override with CLAUDE_CODE_OAUTH_TOKEN in .env.
 *
 * @param message    The user's text (may include transcribed voice prefix)
 * @param sessionId  Claude Code session ID to resume, or undefined for new session
 * @param onTyping   Called every TYPING_REFRESH_MS while waiting — sends typing action to Telegram
 * @param onProgress Optional callback to send intermediate status updates to the user
 */
export async function runAgent(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
): Promise<AgentResult> {
  if (activeAgentCalls >= MAX_CONCURRENT_AGENTS) {
    logger.warn({ activeAgentCalls }, 'Agent concurrency limit reached');
    return {
      text: 'Already processing another request. Try again in a moment.',
      newSessionId: sessionId,
    };
  }

  activeAgentCalls++;
  try {
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        return await runAgentInner(message, sessionId, onTyping, onProgress);
      } catch (err) {
        if (attempt < MAX_RETRIES && isRetryableError(err)) {
          const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
          logger.warn(
            { attempt: attempt + 1, maxRetries: MAX_RETRIES, delayMs: delay },
            'API overloaded, retrying...',
          );
          if (onProgress) {
            await onProgress(`API busy, retrying in ${delay / 1000}s...`).catch(() => {});
          }
          await sleep(delay);
          continue;
        }
        throw err;
      }
    }
    // Unreachable but TypeScript needs it
    throw new Error('Retry loop exhausted');
  } finally {
    activeAgentCalls--;
  }
}

async function runAgentInner(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
): Promise<AgentResult> {
  // Read auth overrides from LOCAL .env only (not ~/.env.shared).
  // ANTHROPIC_API_KEY in ~/.env.shared would override Max plan OAuth with API billing.
  // These are only needed if you want to explicitly override which account is used.
  const secrets = readLocalEnvFile(['CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_API_KEY']);

  const sdkEnv: Record<string, string | undefined> = { ...process.env };

  // Remove nesting guard: PM2 may inherit CLAUDECODE / CLAUDE_CODE_ENTRYPOINT
  // from the shell that originally started the process. The subprocess is
  // independent and must not be blocked by the nested-session check.
  delete sdkEnv.CLAUDECODE;
  delete sdkEnv.CLAUDE_CODE_ENTRYPOINT;

  if (secrets.CLAUDE_CODE_OAUTH_TOKEN) {
    sdkEnv.CLAUDE_CODE_OAUTH_TOKEN = secrets.CLAUDE_CODE_OAUTH_TOKEN;
  }
  if (secrets.ANTHROPIC_API_KEY) {
    sdkEnv.ANTHROPIC_API_KEY = secrets.ANTHROPIC_API_KEY;
  }

  // Build mcpServers config — Arcade provides Linear/GitHub/Slack tools
  const mcpServers: Record<string, { command: string; args: string[] }> = {};
  if (isArcadeConfigured()) {
    mcpServers['arcade'] = getArcadeMcpConfig();
    logger.info('Arcade MCP server configured');
  }

  let newSessionId: string | undefined;
  let resultText: string | null = null;
  let lastProgressTime = 0;

  // Refresh typing indicator on an interval while Claude works.
  // Telegram's "typing..." action expires after ~5s.
  const typingInterval = setInterval(onTyping, 4000);

  try {
    logger.info(
      { sessionId: sessionId ?? 'new', messageLen: message.length },
      'Starting agent query',
    );

    for await (const event of query({
      prompt: singleTurn(message),
      options: {
        // cwd = ea-claude project root so Claude Code loads our CLAUDE.md
        cwd: PROJECT_ROOT,

        // Resume the previous session for this chat (persistent context)
        resume: sessionId,

        // 'project' loads CLAUDE.md from cwd; 'user' loads ~/.claude/skills/ and user settings
        settingSources: ['project', 'user'],

        // Skip all permission prompts — this is Mark's personal bot on his own Mac
        permissionMode: 'bypassPermissions',
        allowDangerouslySkipPermissions: true,

        // Pass secrets to the subprocess without polluting our own process.env
        env: sdkEnv,

        // Arcade MCP: Linear, GitHub, Slack tools (empty if keys not configured)
        mcpServers,
      },
    })) {
      const ev = event as Record<string, unknown>;

      if (ev['type'] === 'system' && ev['subtype'] === 'init') {
        newSessionId = ev['session_id'] as string;
        logger.info({ newSessionId }, 'Session initialized');
      }

      // Surface tool-use events as progress updates to Telegram.
      // Rate-limited to avoid spamming the chat.
      if (onProgress && ev['type'] === 'assistant') {
        const msg = ev['message'] as Record<string, unknown> | undefined;
        const content = msg?.['content'] as Array<Record<string, unknown>> | undefined;
        if (content) {
          for (const block of content) {
            if (block['type'] === 'tool_use') {
              const toolName = block['name'] as string;
              const toolInput = block['input'] as Record<string, unknown> | undefined;
              const summary = describeToolUse(toolName, toolInput);

              telemetry.emit({
                timestamp: new Date().toISOString(),
                event_type: 'tool_used',
                tool_name: toolName,
                tool_summary: summary ?? undefined,
              });

              const now = Date.now();
              if (now - lastProgressTime >= PROGRESS_MIN_INTERVAL_MS) {
                if (summary) {
                  lastProgressTime = now;
                  logger.debug({ toolName, summary }, 'Sending progress update');
                  await onProgress(summary).catch(() => {});
                }
              }
            }
          }
        }
      }

      if (ev['type'] === 'result') {
        resultText = (ev['result'] as string | null | undefined) ?? null;
        logger.info(
          { hasResult: !!resultText, subtype: ev['subtype'] },
          'Agent result received',
        );
      }
    }
  } catch (err) {
    // The SDK throws when the Claude Code subprocess exits with non-zero,
    // even after emitting a valid result. If we already captured the result,
    // log the exit error but don't propagate it.
    if (resultText !== null) {
      logger.warn(
        { err: err instanceof Error ? err.message : err },
        'Agent process exited with error after delivering result (ignored)',
      );
    } else {
      throw err;
    }
  } finally {
    clearInterval(typingInterval);
  }

  return { text: resultText, newSessionId };
}
