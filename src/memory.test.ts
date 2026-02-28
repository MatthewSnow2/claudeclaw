import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./db.js', () => ({
  searchMemories: vi.fn(),
  getRecentMemories: vi.fn(),
  getMemoryVectors: vi.fn().mockReturnValue([]),
  touchMemory: vi.fn(),
  touchMemoryVector: vi.fn(),
  saveMemory: vi.fn(),
  decayMemories: vi.fn(),
  decayMemoryVectors: vi.fn(),
  logConversationTurn: vi.fn(),
  pruneConversationLog: vi.fn(),
}));

import {
  buildMemoryContext,
  saveConversationTurn,
  runDecaySweep,
} from './memory.js';

import {
  searchMemories,
  getRecentMemories,
  touchMemory,
  saveMemory,
  decayMemories,
  decayMemoryVectors,
  logConversationTurn,
  pruneConversationLog,
} from './db.js';

const mockSearchMemories = vi.mocked(searchMemories);
const mockGetRecentMemories = vi.mocked(getRecentMemories);
const mockTouchMemory = vi.mocked(touchMemory);
const mockSaveMemory = vi.mocked(saveMemory);
const mockDecayMemories = vi.mocked(decayMemories);
const mockDecayMemoryVectors = vi.mocked(decayMemoryVectors);
const mockLogConversationTurn = vi.mocked(logConversationTurn);
const mockPruneConversationLog = vi.mocked(pruneConversationLog);

describe('buildMemoryContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns empty string when no memories found', async () => {
    mockSearchMemories.mockReturnValue([]);
    mockGetRecentMemories.mockReturnValue([]);

    const result = await buildMemoryContext('chat1', 'hello');
    expect(result).toBe('');
  });

  it('returns formatted string when FTS results exist', async () => {
    mockSearchMemories.mockReturnValue([
      {
        id: 1,
        chat_id: 'chat1',
        topic_key: null,
        content: 'I like pizza',
        sector: 'semantic',
        salience: 1.0,
        created_at: 100,
        accessed_at: 100,
      },
    ]);
    mockGetRecentMemories.mockReturnValue([]);

    const result = await buildMemoryContext('chat1', 'pizza');
    expect(result).toContain('[Memory context]');
    expect(result).toContain('I like pizza');
    expect(result).toContain('semantic');
    expect(result).toContain('[End memory context]');
  });

  it('returns formatted string when recent memories exist', async () => {
    mockSearchMemories.mockReturnValue([]);
    mockGetRecentMemories.mockReturnValue([
      {
        id: 2,
        chat_id: 'chat1',
        topic_key: null,
        content: 'Recent thought',
        sector: 'episodic',
        salience: 1.0,
        created_at: 100,
        accessed_at: 200,
      },
    ]);

    const result = await buildMemoryContext('chat1', 'anything');
    expect(result).toContain('Recent thought');
    expect(result).toContain('episodic');
  });

  it('deduplicates between FTS and recent results', async () => {
    const sharedMemory = {
      id: 1,
      chat_id: 'chat1',
      topic_key: null,
      content: 'shared memory',
      sector: 'semantic',
      salience: 1.0,
      created_at: 100,
      accessed_at: 100,
    };

    mockSearchMemories.mockReturnValue([sharedMemory]);
    mockGetRecentMemories.mockReturnValue([sharedMemory]);

    const result = await buildMemoryContext('chat1', 'shared');
    // Should only appear once
    const occurrences = result.split('shared memory').length - 1;
    expect(occurrences).toBe(1);
  });

  it('touches (boosts salience of) returned memories', async () => {
    mockSearchMemories.mockReturnValue([
      {
        id: 10,
        chat_id: 'chat1',
        topic_key: null,
        content: 'mem1',
        sector: 'semantic',
        salience: 1.0,
        created_at: 100,
        accessed_at: 100,
      },
    ]);
    mockGetRecentMemories.mockReturnValue([
      {
        id: 20,
        chat_id: 'chat1',
        topic_key: null,
        content: 'mem2',
        sector: 'episodic',
        salience: 1.0,
        created_at: 100,
        accessed_at: 200,
      },
    ]);

    await buildMemoryContext('chat1', 'test');
    expect(mockTouchMemory).toHaveBeenCalledWith(10);
    expect(mockTouchMemory).toHaveBeenCalledWith(20);
    expect(mockTouchMemory).toHaveBeenCalledTimes(2);
  });

  it('handles empty user message gracefully', async () => {
    mockSearchMemories.mockReturnValue([]);
    mockGetRecentMemories.mockReturnValue([]);

    const result = await buildMemoryContext('chat1', '');
    expect(result).toBe('');
  });

  it('handles short user message gracefully', async () => {
    mockSearchMemories.mockReturnValue([]);
    mockGetRecentMemories.mockReturnValue([]);

    const result = await buildMemoryContext('chat1', 'hi');
    expect(result).toBe('');
  });
});

describe('saveConversationTurn', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('logs both user and assistant messages to conversation_log', () => {
    saveConversationTurn('chat1', 'I prefer TypeScript over JavaScript always', 'Noted.', 'sess1');
    expect(mockLogConversationTurn).toHaveBeenCalledWith('chat1', 'user', 'I prefer TypeScript over JavaScript always', 'sess1');
    expect(mockLogConversationTurn).toHaveBeenCalledWith('chat1', 'assistant', 'Noted.', 'sess1');
  });

  it('logs without sessionId when not provided', () => {
    saveConversationTurn('chat1', 'Hello there', 'Hi.');
    expect(mockLogConversationTurn).toHaveBeenCalledWith('chat1', 'user', 'Hello there', undefined);
    expect(mockLogConversationTurn).toHaveBeenCalledWith('chat1', 'assistant', 'Hi.', undefined);
  });

  it('does NOT call saveMemory (Phase 7 handles extraction)', () => {
    saveConversationTurn('chat1', 'I prefer TypeScript over JavaScript always', 'Noted.');
    expect(mockSaveMemory).not.toHaveBeenCalled();
  });
});

describe('runDecaySweep', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls decayMemories, decayMemoryVectors, and pruneConversationLog', () => {
    runDecaySweep();
    expect(mockDecayMemories).toHaveBeenCalledOnce();
    expect(mockDecayMemoryVectors).toHaveBeenCalledOnce();
    expect(mockPruneConversationLog).toHaveBeenCalledWith(500);
  });
});
