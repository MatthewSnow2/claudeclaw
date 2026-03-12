/**
 * Dispatch Worker
 * Polls the dispatch_queue for tasks matching its worker type and executes them.
 * Each worker runs as a separate pm2 process with its own MAX_CONCURRENT_AGENTS=1.
 *
 * Usage:
 *   node dist/worker.js --type starscream
 *   node dist/worker.js --type default
 *   node dist/worker.js --type ravage
 *   node dist/worker.js --type soundwave
 *   node dist/worker.js --type astrotrain
 */

import path from 'path';

import { runAgent } from './agent.js';
import { PROJECT_ROOT } from './config.js';
import {
  claimTask,
  completeTask,
  failTask,
  initDatabase,
  resetStaleTasks,
  type WorkerType,
} from './db.js';
import { logger } from './logger.js';
import * as telemetry from './telemetry.js';

const POLL_INTERVAL_MS = 5_000; // 5 seconds
const STALE_RESET_INTERVAL_MS = 60_000; // 1 minute

const VALID_WORKER_TYPES: Set<string> = new Set([
  'starscream',
  'ravage',
  'soundwave',
  'astrotrain',
  'default',
]);

/**
 * Map worker types to their persona directories.
 * Each persona has its own CLAUDE.md with specialized instructions.
 * ALL workers (including 'default') use workers/<type>/ so they load
 * the worker-specific CLAUDE.md first. This prevents the default worker
 * from reading the main CLAUDE.md's Telegram bot personality and
 * attempting to send messages to Telegram directly.
 */
function getWorkerCwd(workerType: WorkerType): string {
  const personaDir = path.resolve(PROJECT_ROOT, 'workers', workerType);
  return personaDir;
}

function parseArgs(): WorkerType {
  const args = process.argv.slice(2);
  const typeIndex = args.indexOf('--type');

  if (typeIndex === -1 || typeIndex + 1 >= args.length) {
    console.error('Usage: node dist/worker.js --type <starscream|ravage|soundwave|astrotrain|default>');
    process.exit(1);
  }

  const workerType = args[typeIndex + 1];
  if (!VALID_WORKER_TYPES.has(workerType)) {
    console.error(`Invalid worker type: ${workerType}`);
    console.error(`Valid types: ${[...VALID_WORKER_TYPES].join(', ')}`);
    process.exit(1);
  }

  return workerType as WorkerType;
}

async function processTask(workerType: WorkerType): Promise<boolean> {
  const task = claimTask(workerType);
  if (!task) return false;

  const cwd = getWorkerCwd(workerType);
  logger.info(
    { taskId: task.id, workerType, promptLen: task.prompt.length, cwd },
    'Claimed task',
  );

  const startTime = Date.now();

  try {
    const result = await runAgent(
      task.prompt,
      task.session_id ?? undefined, // Resume from chat session if available
      () => {}, // No typing indicator (no Telegram context)
      undefined, // No progress callback
      cwd, // Worker-specific CWD for persona CLAUDE.md
    );

    const text = result.text?.trim() || 'Task completed with no output.';
    completeTask(task.id, text, result.newSessionId);

    const elapsed = Math.round((Date.now() - startTime) / 1000);
    logger.info(
      { taskId: task.id, workerType, elapsed },
      'Task completed',
    );

    telemetry.emit({
      timestamp: new Date().toISOString(),
      event_type: 'dispatch_task_completed',
      task_id: task.id,
      worker_type: workerType,
      success: true,
      latency_ms: Date.now() - startTime,
    });

    return true;
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    failTask(task.id, errorMsg);

    logger.error(
      { err, taskId: task.id, workerType },
      'Task failed',
    );

    telemetry.emit({
      timestamp: new Date().toISOString(),
      event_type: 'dispatch_task_completed',
      task_id: task.id,
      worker_type: workerType,
      success: false,
      latency_ms: Date.now() - startTime,
    });

    return true; // We processed a task (even though it failed)
  }
}

async function mainLoop(workerType: WorkerType): Promise<void> {
  logger.info({ workerType, pollIntervalMs: POLL_INTERVAL_MS }, 'Worker starting');

  // Periodically reset stale tasks (stuck in 'running' > 10min)
  setInterval(() => {
    const reset = resetStaleTasks(600);
    if (reset > 0) {
      logger.warn({ reset }, 'Reset stale dispatch tasks');
    }
  }, STALE_RESET_INTERVAL_MS);

  // Main poll loop
  while (true) {
    try {
      const processed = await processTask(workerType);
      if (!processed) {
        // No task available, wait before polling again
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      // If we processed a task, immediately check for another
    } catch (err) {
      logger.error({ err }, 'Unexpected error in worker loop');
      // Wait before retrying to avoid tight error loops
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS * 2));
    }
  }
}

// Entry point
const workerType = parseArgs();
initDatabase();
mainLoop(workerType).catch((err) => {
  logger.fatal({ err }, 'Worker crashed');
  process.exit(1);
});
