import { describe, it, expect } from 'vitest';
import { classifyMessage } from './classifier.js';

describe('classifyMessage', () => {
  // ── Quick patterns ──────────────────────────────────────────────

  it('classifies bot commands as quick', () => {
    expect(classifyMessage('/start')).toEqual({ isLong: false, workerType: 'default' });
    expect(classifyMessage('/help')).toEqual({ isLong: false, workerType: 'default' });
    expect(classifyMessage('convolife')).toEqual({ isLong: false, workerType: 'default' });
  });

  it('classifies greetings as quick', () => {
    expect(classifyMessage('hello')).toEqual({ isLong: false, workerType: 'default' });
    expect(classifyMessage('thanks!')).toEqual({ isLong: false, workerType: 'default' });
  });

  it('classifies short questions as quick', () => {
    expect(classifyMessage('what time is it?')).toEqual({ isLong: false, workerType: 'default' });
    expect(classifyMessage('who built this?')).toEqual({ isLong: false, workerType: 'default' });
  });

  // ── Worker routing ──────────────────────────────────────────────

  it('routes LinkedIn posts to starscream', () => {
    const result = classifyMessage('write a LinkedIn post about AI agents');
    expect(result).toEqual({ isLong: true, workerType: 'starscream' });
  });

  it('routes coding tasks to ravage', () => {
    const result = classifyMessage('build the new auth module');
    expect(result).toEqual({ isLong: true, workerType: 'ravage' });
  });

  it('routes research tasks to soundwave', () => {
    const result = classifyMessage('research the competitor landscape');
    expect(result).toEqual({ isLong: true, workerType: 'soundwave' });
  });

  it('routes deploy tasks to ravage', () => {
    const result = classifyMessage('deploy the service to production');
    expect(result).toEqual({ isLong: true, workerType: 'ravage' });
  });

  // ── Multi-topic guard ──────────────────────────────────────────

  it('keeps multi-topic messages inline', () => {
    const result = classifyMessage('build a LinkedIn post and research competitors');
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
    expect(result).toEqual({ isLong: true, workerType: 'ravage' });
  });

  it('messages with no long indicators stay inline', () => {
    const result = classifyMessage('I like pizza');
    expect(result).toEqual({ isLong: false, workerType: 'default' });
  });
});
