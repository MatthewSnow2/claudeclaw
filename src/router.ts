import { runAgent, type AgentResult } from './agent.js';

import { callGemini, callOllama, callOpenAI, callPerplexity } from './llm-backends.js';
import { logger } from './logger.js';
import * as telemetry from './telemetry.js';

export interface RouteResult {
  text: string;
  backend: string;
  newSessionId?: string;
}

type Backend = 'claude' | 'gemini' | 'perplexity' | 'ollama' | 'openai' | 'ignore';

interface ParsedMessage {
  backend: Backend;
  message: string;
}

const PREFIX_MAP: Record<string, Backend> = {
  '@claude': 'claude',
  '@data': 'claude',
  '@m2ai_data_bot': 'claude',
  '@gemini': 'gemini',
  '@research': 'perplexity',
  '@perplexity': 'perplexity',
  '@ollama': 'ollama',
  '@local': 'ollama',
  '@private': 'ollama',
  '@gpt': 'openai',
};

/**
 * Parse the @prefix from a message and determine which backend to route to.
 * Default (no prefix) routes to Claude Code.
 */
function parsePrefix(raw: string): ParsedMessage {
  const trimmed = raw.trimStart();
  const match = trimmed.match(/^(@\w+)\s+/);

  if (match) {
    const prefix = match[1].toLowerCase();
    const backend = PREFIX_MAP[prefix];
    if (backend) {
      return {
        backend,
        message: trimmed.slice(match[0].length),
      };
    }
    // Message starts with an @mention we don't own (e.g. @m2ai_chad_bot).
    // In group chats this is directed at another bot — don't intercept it.
    return { backend: 'ignore', message: '' };
  }

  return { backend: 'claude', message: raw };
}

/**
 * Route an incoming message to the appropriate backend.
 * Returns null if the message should be ignored (e.g. @mention for another bot).
 *
 * @param originalMessage  The raw user message (used for @prefix detection)
 * @param fullMessage      The message enriched with memory context (sent to Claude)
 * @param sessionId        Claude Code session ID to resume
 * @param onTyping         Typing indicator callback
 * @param onProgress       Optional callback to send intermediate status updates to the user
 */
export async function routeMessage(
  originalMessage: string,
  fullMessage: string,
  sessionId: string | undefined,
  onTyping: () => void,
  onProgress?: (msg: string) => Promise<void>,
): Promise<RouteResult | null> {
  const { backend, message } = parsePrefix(originalMessage);

  if (backend === 'ignore') {
    logger.info('Ignoring message directed at another bot');
    return null;
  }

  logger.info({ backend, messageLen: message.length }, 'Routing message');

  telemetry.emit({
    timestamp: new Date().toISOString(),
    event_type: 'message_routed',
    backend,
    message_length: message.length,
  });

  const startTime = Date.now();

  switch (backend) {
    case 'claude': {
      const result: AgentResult = await runAgent(
        fullMessage,
        sessionId,
        onTyping,
        onProgress,
      );
      const text = result.text?.trim() || 'Done.';
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'agent_completed',
        backend: 'claude',
        latency_ms: Date.now() - startTime,
        success: true,
        response_length: text.length,
        session_id: result.newSessionId,
      });
      return {
        text,
        backend: 'claude',
        newSessionId: result.newSessionId,
      };
    }

    case 'gemini': {
      const result = await callGemini(message);
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'agent_completed',
        backend: `gemini (${result.model})`,
        latency_ms: Date.now() - startTime,
        success: true,
        response_length: result.text.length,
      });
      return { text: result.text, backend: `gemini (${result.model})` };
    }

    case 'perplexity': {
      const result = await callPerplexity(message);
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'agent_completed',
        backend: `perplexity (${result.model})`,
        latency_ms: Date.now() - startTime,
        success: true,
        response_length: result.text.length,
      });
      return { text: result.text, backend: `perplexity (${result.model})` };
    }

    case 'ollama': {
      const result = await callOllama(message);
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'agent_completed',
        backend: `ollama (${result.model})`,
        latency_ms: Date.now() - startTime,
        success: true,
        response_length: result.text.length,
      });
      return { text: result.text, backend: `ollama (${result.model})` };
    }

    case 'openai': {
      const result = await callOpenAI(message);
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'agent_completed',
        backend: `openai (${result.model})`,
        latency_ms: Date.now() - startTime,
        success: true,
        response_length: result.text.length,
      });
      return { text: result.text, backend: `openai (${result.model})` };
    }

  }
}
