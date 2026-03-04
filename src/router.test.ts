import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./llm-backends.js', () => ({
  callGemini: vi.fn().mockResolvedValue({ text: 'gemini response', backend: 'gemini', model: 'test-model' }),
  callPerplexity: vi.fn().mockResolvedValue({ text: 'perplexity response', backend: 'perplexity', model: 'sonar' }),
  callOllama: vi.fn().mockResolvedValue({ text: 'ollama response', backend: 'ollama', model: 'qwen' }),
  callOpenAI: vi.fn().mockResolvedValue({ text: 'openai response', backend: 'openai', model: 'gpt-4o' }),
}));

vi.mock('./agent.js', () => ({
  runAgent: vi.fn().mockResolvedValue({ text: 'claude response', newSessionId: 'test-session' }),
}));

vi.mock('./telemetry.js', () => ({
  emit: vi.fn(),
}));

vi.mock('./logger.js', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

import { isClaude, routeMessage } from './router.js';
import { callGemini, callPerplexity } from './llm-backends.js';
import { runAgent } from './agent.js';

describe('isClaude (prefix routing)', () => {
  it('returns true for messages with no prefix', () => {
    expect(isClaude('hello world')).toBe(true);
  });

  it('returns true for @claude prefix', () => {
    expect(isClaude('@claude do something')).toBe(true);
  });

  it('returns false for @gemini prefix', () => {
    expect(isClaude('@gemini what is 2+2')).toBe(false);
  });

  it('returns false for @research prefix', () => {
    expect(isClaude('@research latest AI news')).toBe(false);
  });

  it('returns false for @perplexity prefix', () => {
    expect(isClaude('@perplexity search for something')).toBe(false);
  });

  it('returns false for @ollama prefix', () => {
    expect(isClaude('@ollama private question')).toBe(false);
  });

  it('returns false for @local prefix', () => {
    expect(isClaude('@local private question')).toBe(false);
  });

  it('returns false for @gpt prefix', () => {
    expect(isClaude('@gpt explain something')).toBe(false);
  });

  it('returns false for unknown @prefix (another bot)', () => {
    expect(isClaude('@somebot do something')).toBe(false);
  });
});

describe('routeMessage', () => {
  const onTyping = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('routes default messages to claude (runAgent)', async () => {
    const result = await routeMessage('hello', 'hello with context', 'session-1', onTyping);
    expect(result).not.toBeNull();
    expect(result!.backend).toBe('claude');
    expect(result!.text).toBe('claude response');
    expect(result!.newSessionId).toBe('test-session');
    expect(runAgent).toHaveBeenCalledWith('hello with context', 'session-1', onTyping, undefined);
  });

  it('routes @gemini prefix to callGemini', async () => {
    const result = await routeMessage('@gemini what is AI', '@gemini what is AI', undefined, onTyping);
    expect(result).not.toBeNull();
    expect(result!.text).toBe('gemini response');
    expect(callGemini).toHaveBeenCalledWith('what is AI');
  });

  it('routes @perplexity prefix to callPerplexity', async () => {
    const result = await routeMessage('@perplexity latest news', '@perplexity latest news', undefined, onTyping);
    expect(result).not.toBeNull();
    expect(result!.text).toBe('perplexity response');
    expect(callPerplexity).toHaveBeenCalledWith('latest news');
  });

  it('returns null for unknown @prefix (ignore)', async () => {
    const result = await routeMessage('@somebot do stuff', '@somebot do stuff', undefined, onTyping);
    expect(result).toBeNull();
  });
});
