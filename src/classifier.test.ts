import { describe, it, expect } from 'vitest';
import { classifyMessage } from './classifier.js';

describe('classifyMessage', () => {
  // ── Quick patterns ──────────────────────────────────────────────

  it('classifies bot commands as quick', () => {
    expect(classifyMessage('/start')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
    expect(classifyMessage('/help')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
    expect(classifyMessage('convolife')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
  });

  it('classifies greetings as quick', () => {
    expect(classifyMessage('hello')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
    expect(classifyMessage('thanks!')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
  });

  it('classifies short questions as quick', () => {
    expect(classifyMessage('what time is it?')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
    expect(classifyMessage('who built this?')).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
  });

  // ── Worker routing ──────────────────────────────────────────────

  it('routes LinkedIn posts to starscream', () => {
    const result = classifyMessage('write a LinkedIn post about AI agents');
    expect(result).toEqual({ isLong: true, workerType: 'starscream', modelTier: 'sonnet' });
  });

  it('routes coding tasks to ravage', () => {
    const result = classifyMessage('build the new auth module');
    expect(result).toEqual({ isLong: true, workerType: 'ravage', modelTier: 'sonnet' });
  });

  it('routes research tasks to soundwave', () => {
    const result = classifyMessage('research the competitor landscape');
    expect(result).toEqual({ isLong: true, workerType: 'soundwave', modelTier: 'sonnet' });
  });

  it('routes deploy tasks to ravage', () => {
    const result = classifyMessage('deploy the service to production');
    expect(result).toEqual({ isLong: true, workerType: 'ravage', modelTier: 'sonnet' });
  });

  // ── Multi-agent composition (Phase D) ──────────────────────────

  it('dispatches multi-topic messages to multiple workers', () => {
    // "build" matches ravage, "LinkedIn post" matches starscream, "research" matches soundwave
    const result = classifyMessage('build a LinkedIn post and research competitors');
    expect(result.isLong).toBe(true);
    expect(result.multiWorker).toEqual(['starscream', 'ravage', 'soundwave']);
    expect(result.workerType).toBe('starscream'); // Primary = first match
  });

  it('keeps multi-topic discussions without long indicators inline', () => {
    // No action verbs, just mentions two domains
    const result = classifyMessage('LinkedIn and competitor data look fine');
    expect(result.isLong).toBe(false);
  });

  // ── Long conversational guard (the classifier fix) ─────────────

  it('keeps long discussions about workers inline (the duplicate bug case)', () => {
    // This is the exact bug case: a long conversational message that mentions
    // a worker name but is a discussion, not a command.
    const msg =
      'Was the intention for Starscream to create two different posts because that\'s ' +
      "what I have pending: two posts? They're both scheduled. They look good and we'll " +
      'move forward with it but I want to know if this was the plan or if we\'re still ' +
      'dealing with the duplicate conversation issue still? This duplicate issue, I think ' +
      "this might actually be a classifier issue. I don't think this is the same as the " +
      'duplicate message we were seeing before.';
    const result = classifyMessage(msg);
    expect(result.isLong).toBe(false);
    expect(result.workerType).toBe('default');
  });

  it('keeps questions about workers inline', () => {
    const msg =
      'Is the task Ravage is working on still in progress? I want to check on the ' +
      'deployment status. The last time Ravage ran a deploy it took about 15 minutes ' +
      "and I want to know if we're past that window yet.";
    const result = classifyMessage(msg);
    expect(result.isLong).toBe(false);
  });

  it('keeps meta-discussion with "supposed to" inline', () => {
    const msg =
      'Soundwave was supposed to generate a research report but I do not think it ran. ' +
      'Can you check the dispatch queue and let me know what happened? I want to know ' +
      'the intention behind the scheduled task configuration.';
    const result = classifyMessage(msg);
    expect(result.isLong).toBe(false);
  });

  it('keeps messages starting with question words inline', () => {
    const msg =
      'Why did Starscream post twice today? The duplicate posts are causing confusion ' +
      'on LinkedIn and I need to understand the root cause. Please investigate the ' +
      'classifier and scheduler to find the issue.';
    const result = classifyMessage(msg);
    expect(result.isLong).toBe(false);
  });

  // ── Imperative commands WITH worker name still dispatch ────────

  it('dispatches imperative commands that name a worker', () => {
    const msg =
      'Starscream, write a LinkedIn post about how AI agents are changing healthcare ' +
      'supply chains. Focus on the bottom-up worker perspective, not the executive ' +
      'top-down narrative that everyone else is pushing.';
    const result = classifyMessage(msg);
    expect(result.isLong).toBe(true);
    expect(result.workerType).toBe('starscream');
  });

  // ── Backtick escape (agent name references) ────────────────────

  it('does not route to an agent when its name is in backticks', () => {
    // "Rename the `Starscream` card" -- talking ABOUT Starscream, not commanding it
    const result = classifyMessage('Rename the `Starscream` card on the dashboard');
    expect(result.workerType).not.toBe('starscream');
  });

  it('does not route when multiple agent names are in backticks', () => {
    const result = classifyMessage('Build a comparison between `Ravage` and `Soundwave` efficiency');
    // "build" triggers long indicator + ravage route, but since both names
    // are in backticks, only the bare "build" should route (to ravage via action verb)
    expect(result.workerType).toBe('ravage');
    expect(result.multiWorker).toBeUndefined(); // No multi-topic since names stripped
  });

  it('still routes when agent name is NOT in backticks', () => {
    const result = classifyMessage('Starscream, write a post about AI');
    expect(result.isLong).toBe(true);
    expect(result.workerType).toBe('starscream');
  });

  it('routes correctly when only some names are escaped', () => {
    // Commanding Ravage but referencing Starscream
    const result = classifyMessage('Build a new card for `Starscream` on the dashboard');
    expect(result.isLong).toBe(true);
    expect(result.workerType).toBe('ravage'); // "build" routes to ravage
  });

  // ── Edge cases ─────────────────────────────────────────────────

  it('handles empty string', () => {
    const result = classifyMessage('');
    expect(result.isLong).toBe(false);
  });

  it('handles @prefix stripping', () => {
    const result = classifyMessage('@claude what time is it?');
    expect(result.isLong).toBe(false);
  });

  it('short imperative commands dispatch normally', () => {
    const result = classifyMessage('fix the auth bug');
    expect(result).toEqual({ isLong: true, workerType: 'ravage', modelTier: 'sonnet' });
  });

  it('messages with no long indicators stay inline', () => {
    const result = classifyMessage('I like pizza');
    expect(result).toEqual({ isLong: false, workerType: 'default', modelTier: 'sonnet' });
  });

  // ── Model Tiering ─────────────────────────────────────────────

  it('assigns opus tier for architecture tasks', () => {
    const result = classifyMessage('architect the new microservices platform');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('opus');
  });

  it('assigns opus tier for security audits', () => {
    const result = classifyMessage('audit the security of our API endpoints');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('opus');
  });

  it('assigns opus tier for comprehensive reviews', () => {
    const result = classifyMessage('comprehensive review of the codebase');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('opus');
  });

  it('assigns haiku tier for formatting tasks that hit long indicators', () => {
    // "refactor" hits LONG_INDICATORS, "format" hits HAIKU_INDICATORS
    const result = classifyMessage('refactor and reformat the config module');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('haiku');
  });

  it('assigns haiku tier when explicitly requested', () => {
    const result = classifyMessage('fix the typo in auth module, use haiku');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('haiku');
  });

  it('respects explicit "use opus" override', () => {
    const result = classifyMessage('build the login page, use opus');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('opus');
  });

  it('respects explicit "use haiku" override', () => {
    const result = classifyMessage('fix the typo in the readme, use haiku');
    expect(result.isLong).toBe(true);
    expect(result.modelTier).toBe('haiku');
  });

  it('defaults to sonnet for standard tasks', () => {
    const result = classifyMessage('build the new auth module');
    expect(result.modelTier).toBe('sonnet');
  });
});
