import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./env.js', () => ({
  readEnvFile: vi.fn(),
}));

vi.mock('./logger.js', () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
}));

import { callGemini, callPerplexity, callOpenAI } from './llm-backends.js';
import { readEnvFile } from './env.js';

const mockReadEnvFile = vi.mocked(readEnvFile);

describe('callGemini', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('throws when no API key is configured', async () => {
    mockReadEnvFile.mockReturnValue({});
    await expect(callGemini('test')).rejects.toThrow('GEMINI_API_KEY not configured');
  });
});

describe('callPerplexity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('throws when no API key is configured', async () => {
    mockReadEnvFile.mockReturnValue({});
    await expect(callPerplexity('test')).rejects.toThrow('PERPLEXITY_API_KEY not configured');
  });
});

describe('callOpenAI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('throws when no API key is configured', async () => {
    mockReadEnvFile.mockReturnValue({});
    await expect(callOpenAI('test')).rejects.toThrow('OPENAI_API_KEY not configured');
  });
});
