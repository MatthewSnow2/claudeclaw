import { query } from '@anthropic-ai/claude-agent-sdk';

import { getArcadeMcpConfig, isArcadeConfigured } from './arcade-config.js';
import { PROJECT_ROOT } from './config.js';
import { readLocalEnvFile } from './env.js';
import { logger } from './logger.js';

export interface AgentResult {
  text: string | null;
  newSessionId: string | undefined;
}

// Concurrency limiter: only 1 Claude subprocess at a time to avoid rate limit
// collisions with interactive Claude Code sessions.
const MAX_CONCURRENT_AGENTS = 1;
let activeAgentCalls = 0;

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
 * @param message   The user's text (may include transcribed voice prefix)
 * @param sessionId Claude Code session ID to resume, or undefined for new session
 * @param onTyping  Called every TYPING_REFRESH_MS while waiting — sends typing action to Telegram
 */
export async function runAgent(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
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
    return await runAgentInner(message, sessionId, onTyping);
  } finally {
    activeAgentCalls--;
  }
}

async function runAgentInner(
  message: string,
  sessionId: string | undefined,
  onTyping: () => void,
): Promise<AgentResult> {
  // Read auth overrides from LOCAL .env only (not ~/.env.shared).
  // ANTHROPIC_API_KEY in ~/.env.shared would override Max plan OAuth with API billing.
  // These are only needed if you want to explicitly override which account is used.
  const secrets = readLocalEnvFile(['CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_API_KEY']);

  const sdkEnv: Record<string, string | undefined> = { ...process.env };
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
        // cwd = claudeclaw project root so Claude Code loads our CLAUDE.md
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
