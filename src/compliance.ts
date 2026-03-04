/**
 * Compliance Scoring — Phase B1 of CF V5 Feature Adoption
 *
 * Scores worker task results on a 0.0-1.0 scale based on quality signals.
 * Pure function, no LLM calls. Runs synchronously in the result-poller
 * before deciding whether to post, re-dispatch, or send for review.
 */

import type { DispatchTask } from './db.js';

/** Minimum result length to avoid penalizing intentionally short responses. */
const MIN_LENGTH_THRESHOLD = 80;

/** Maximum score contribution from any single check (normalized). */
const MAX_CHECK_WEIGHT = 0.25;

interface ScoreBreakdown {
  score: number;
  checks: Array<{ name: string; passed: boolean; weight: number }>;
  issues: string[];
}

/**
 * Score a completed task result for quality.
 *
 * Checks are worker-type-aware:
 * - All workers: length, coherence (not truncated/error dump)
 * - ravage (coding): mentions files, code blocks, or test results
 * - soundwave (research): cites sources, structured sections
 * - starscream (social): has post-like structure, within length norms
 * - default/astrotrain: general quality checks only
 */
export function scoreResult(task: DispatchTask): ScoreBreakdown {
  const result = task.result ?? '';
  const checks: ScoreBreakdown['checks'] = [];
  const issues: string[] = [];

  // ── Universal checks (all workers) ───────────────────────────

  // 1. Minimum length: result should be substantive
  const hasMinLength = result.length >= MIN_LENGTH_THRESHOLD;
  checks.push({ name: 'min_length', passed: hasMinLength, weight: 0.20 });
  if (!hasMinLength) issues.push(`Result too short (${result.length} chars, min ${MIN_LENGTH_THRESHOLD})`);

  // 2. Not an error dump: result shouldn't be mostly stack traces
  const errorSignals = (result.match(/\b(Error|FATAL|Traceback|panic|FAILED)\b/gi) || []).length;
  const isNotErrorDump = errorSignals < 5;
  checks.push({ name: 'not_error_dump', passed: isNotErrorDump, weight: 0.15 });
  if (!isNotErrorDump) issues.push(`Result looks like an error dump (${errorSignals} error signals)`);

  // 3. Not truncated: result shouldn't end mid-sentence
  const trimmed = result.trimEnd();
  const endsCleanly = /[.!?:)\]`"'}\d]$/.test(trimmed) || trimmed.endsWith('```') || trimmed.length < 50;
  checks.push({ name: 'not_truncated', passed: endsCleanly, weight: 0.10 });
  if (!endsCleanly) issues.push('Result appears truncated');

  // 4. Has structure: paragraphs, lists, or sections
  const hasStructure = result.includes('\n') || result.length < 200;
  checks.push({ name: 'has_structure', passed: hasStructure, weight: 0.10 });
  if (!hasStructure) issues.push('Result is a single unstructured block');

  // ── Worker-specific checks ───────────────────────────────────

  switch (task.worker_type) {
    case 'ravage': {
      // Coding tasks should reference files or include code
      const hasCodeSignals =
        /```[\s\S]*```/.test(result) ||
        /\.(ts|js|py|rs|go|css|html|json|yaml|toml|sql)\b/.test(result) ||
        /\b(function|class|const|let|var|def|import|export|return)\b/.test(result);
      checks.push({ name: 'code_signals', passed: hasCodeSignals, weight: MAX_CHECK_WEIGHT });
      if (!hasCodeSignals) issues.push('Coding task output has no code references');

      // Should mention test results or at least acknowledge testing
      const hasTestSignals =
        /\b(test|spec|assert|expect|passing|failing|✓|✗|PASS|FAIL)\b/i.test(result) ||
        /\b(verified|confirmed|checked)\b/i.test(result);
      checks.push({ name: 'test_signals', passed: hasTestSignals, weight: 0.20 });
      if (!hasTestSignals) issues.push('No testing signals in coding output');
      break;
    }

    case 'soundwave': {
      // Research should cite sources or have structured sections
      const hasCitations =
        /https?:\/\//.test(result) ||
        /\b(source|reference|according to|study|report|data shows)\b/i.test(result);
      checks.push({ name: 'citations', passed: hasCitations, weight: MAX_CHECK_WEIGHT });
      if (!hasCitations) issues.push('Research output lacks citations or source references');

      // Should have sections/headers
      const hasSections =
        /^#{1,3}\s/m.test(result) ||
        /\*\*[^*]+\*\*/.test(result) ||
        /^\d+\.\s/m.test(result);
      checks.push({ name: 'sections', passed: hasSections, weight: 0.20 });
      if (!hasSections) issues.push('Research output lacks structured sections');
      break;
    }

    case 'starscream': {
      // Social posts should be within LinkedIn's ideal range
      const wordCount = result.split(/\s+/).length;
      const goodLength = wordCount >= 30 && wordCount <= 500;
      checks.push({ name: 'post_length', passed: goodLength, weight: MAX_CHECK_WEIGHT });
      if (!goodLength) issues.push(`Post length (${wordCount} words) outside ideal range (30-500)`);

      // Should have engagement hooks (questions, calls to action)
      const hasHooks = /\?/.test(result) || /\b(comment|share|thoughts|agree|disagree|what do you)\b/i.test(result);
      checks.push({ name: 'engagement_hooks', passed: hasHooks, weight: 0.20 });
      if (!hasHooks) issues.push('Social post lacks engagement hooks');
      break;
    }

    default: {
      // Generic workers: just check the result is actionable
      const isActionable = result.length >= MIN_LENGTH_THRESHOLD * 2;
      checks.push({ name: 'actionable', passed: isActionable, weight: MAX_CHECK_WEIGHT });
      if (!isActionable) issues.push('Output may not be substantive enough');
      break;
    }
  }

  // ── Calculate weighted score ─────────────────────────────────

  const totalWeight = checks.reduce((sum, c) => sum + c.weight, 0);
  const earnedWeight = checks
    .filter((c) => c.passed)
    .reduce((sum, c) => sum + c.weight, 0);

  const score = totalWeight > 0 ? Math.round((earnedWeight / totalWeight) * 100) / 100 : 0;

  return { score, checks, issues };
}

/**
 * Threshold below which a task gets re-dispatched instead of posted.
 */
export const RE_DISPATCH_THRESHOLD = 0.35;

/**
 * Threshold above which a task qualifies for the reviewer gate
 * (if enabled). Tasks between RE_DISPATCH_THRESHOLD and this
 * value are posted directly without review.
 */
export const REVIEW_THRESHOLD = 0.60;
