import type { WorkerType } from './db.js';

export interface Classification {
  isLong: boolean;
  workerType: WorkerType;
}

/**
 * Quick-path patterns: messages that should be handled inline (< 30s).
 * These are checked first. If any match, the message is classified as quick.
 */
const QUICK_PATTERNS: RegExp[] = [
  // Bot commands and special commands
  /^\/\w+/,
  /^convolife$/i,
  /^checkpoint$/i,

  // Status checks and simple lookups
  /^what('?s| is) (the )?(status|time|date|weather)/i,
  /^(hi|hey|hello|yo|sup|thanks|thank you|ok|okay|got it|cool|nice|good)\s*[.!?]?$/i,

  // Short questions (under 60 chars, no action verbs)
  /^(who|what|where|when|why|how|is|are|do|does|did|can|could|will|would|should)\b.{0,55}\?$/i,

  // Memory recall
  /^(remember|recall|what did (i|we)|last time)/i,

  // Simple lookups
  /^(show|list|get) (my )?(tasks|schedule|memories|sessions)/i,

  // Conversational / meta
  /^(convolife|checkpoint|status|ping)\b/i,
];

/**
 * Worker routing rules. Order matters: first match wins.
 * Each entry maps keyword patterns to a worker type.
 */
const WORKER_ROUTES: Array<{ patterns: RegExp[]; worker: WorkerType }> = [
  // Starscream: social media, LinkedIn, content scheduling
  {
    worker: 'starscream',
    patterns: [
      /\blinkedin\b/i,
      /\b(social media|social post)\b/i,
      /\bschedule\s+(a\s+)?post\b/i,
      /\b(write|draft|create)\s+(a\s+)?(post|tweet|thread|article)\b/i,
      /\bstarscream\b/i,
      /\bcontent\s+(calendar|strategy|plan)\b/i,
    ],
  },

  // Ravage: coding, GitHub, builds, deploys
  {
    worker: 'ravage',
    patterns: [
      /\b(build|code|implement|refactor|fix|debug|patch)\b/i,
      /\b(commit|push|merge|rebase|cherry.?pick)\b/i,
      /\bgithub\b/i,
      /\b(pull request|PR|pr)\b/i,
      /\bdeploy\b/i,
      /\b(write|add|create|update)\s+(a\s+)?(function|class|module|component|test|feature|endpoint|api|script)\b/i,
      /\bravage\b/i,
      /\b(npm|pip|cargo|docker)\b/i,
      /\b(migrate|migration|schema)\b/i,
    ],
  },

  // Soundwave: research, analysis, reports, pipeline work
  {
    worker: 'soundwave',
    patterns: [
      /\b(research|investigate|analyze|analyse)\b/i,
      /\breview\s+(the\s+)?pipeline\b/i,
      /\bmorning\s+report\b/i,
      /\b(market|competitor|industry)\s+(research|analysis|report)\b/i,
      /\bsoundwave\b/i,
      /\b(deep\s+dive|comprehensive|thorough)\s+(review|analysis|report)\b/i,
      /\bwrite\s+(a\s+)?(report|analysis|brief|summary|review)\b/i,
    ],
  },
];

/**
 * Long-task indicators: if a message matches any of these and didn't
 * match a quick pattern, it gets dispatched to a worker.
 */
const LONG_INDICATORS: RegExp[] = [
  // Explicit action verbs that imply multi-step work
  /\b(build|create|implement|write|develop|design|architect|scaffold)\b/i,
  /\b(review|audit|analyze|research|investigate)\b/i,
  /\b(refactor|rewrite|migrate|upgrade|overhaul)\b/i,
  /\b(deploy|release|ship|publish)\b/i,
  /\b(fix|debug|troubleshoot|diagnose)\b/i,

  // Slide deck / presentation
  /\b(slide\s*deck|presentation|pitch\s*deck)\b/i,

  // Multi-file / project-scope work
  /\bacross\s+(all|the|every)\b/i,
  /\b(entire|whole)\s+(project|codebase|repo)\b/i,

  // Explicit dispatch requests
  /\bdispatch\b/i,
];

/**
 * Classify an incoming message as quick (inline) or long (dispatch to worker).
 *
 * Classification flow:
 * 1. If the message matches a quick pattern, return quick.
 * 2. If the message matches a long indicator, route to the appropriate worker.
 * 3. If no pattern matches, default to quick (inline).
 */
export function classifyMessage(text: string): Classification {
  const trimmed = text.trim();

  // Strip @prefix for classification (routing already handled by router.ts)
  const stripped = trimmed.replace(/^@\w+\s+/, '');

  // 1. Check quick patterns first
  for (const pattern of QUICK_PATTERNS) {
    if (pattern.test(stripped)) {
      return { isLong: false, workerType: 'default' };
    }
  }

  // 2. Check if this looks like a long task
  const isLong = LONG_INDICATORS.some((p) => p.test(stripped));

  if (!isLong) {
    // Short message with no long indicators: handle inline
    return { isLong: false, workerType: 'default' };
  }

  // 3. Route to the appropriate worker
  for (const route of WORKER_ROUTES) {
    for (const pattern of route.patterns) {
      if (pattern.test(stripped)) {
        return { isLong: true, workerType: route.worker };
      }
    }
  }

  // Long task but no specific worker match: use default
  return { isLong: true, workerType: 'default' };
}
