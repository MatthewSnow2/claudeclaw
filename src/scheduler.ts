import { CronExpressionParser } from 'cron-parser';

import { ALLOWED_CHAT_ID } from './config.js';
import {
  enqueueTask,
  getDueTasks,
  updateTaskAfterRun,
  type WorkerType,
} from './db.js';
import { logger } from './logger.js';
import * as telemetry from './telemetry.js';

type Sender = (text: string) => Promise<void>;

let sender: Sender;

/**
 * Track the scheduler interval so we can clear it on re-init.
 * Without this, each 409 retry loop spawns a NEW parallel interval,
 * leading to N concurrent schedulers all firing runDueTasks().
 */
let schedulerInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Map scheduled task prompts to worker types.
 * Uses keyword matching similar to classifier.ts but for known scheduled tasks.
 */
function routeToWorker(prompt: string): WorkerType {
  const lower = prompt.toLowerCase();
  if (
    lower.includes('starscream') ||
    lower.includes('linkedin') ||
    lower.includes('social') ||
    (lower.includes('schedule') && lower.includes('post'))
  ) {
    return 'starscream';
  }
  if (
    lower.includes('build') ||
    lower.includes('deploy') ||
    lower.includes('ravage')
  ) {
    return 'ravage';
  }
  if (
    lower.includes('research') ||
    lower.includes('analyze') ||
    lower.includes('report') ||
    lower.includes('soundwave')
  ) {
    return 'soundwave';
  }
  if (
    lower.includes('astrotrain') ||
    lower.includes('supply chain') ||
    lower.includes('scm') ||
    lower.includes('dsp') ||
    (lower.includes('simulation') && lower.includes('procurement'))
  ) {
    return 'astrotrain';
  }
  return 'default';
}

/**
 * Initialise the scheduler. Safe to call multiple times (idempotent).
 * Clears any previous interval before creating a new one.
 * @param send  Function that sends a message to Mark's Telegram chat.
 */
export function initScheduler(send: Sender): void {
  if (!ALLOWED_CHAT_ID) {
    logger.warn('ALLOWED_CHAT_ID not set — scheduler will not send results');
  }
  sender = send;

  // Clear previous interval to prevent duplicate schedulers on 409 retry
  if (schedulerInterval) {
    clearInterval(schedulerInterval);
    logger.info('Cleared previous scheduler interval');
  }

  schedulerInterval = setInterval(() => void runDueTasks(), 60_000);
  logger.info('Scheduler started (checking every 60s)');
}

/**
 * Check for due tasks and dispatch them to the appropriate worker queue.
 * This is non-blocking: tasks are enqueued and picked up by worker processes.
 * Results are delivered back to Telegram via result-poller.ts.
 */
async function runDueTasks(): Promise<void> {
  const tasks = getDueTasks();
  if (tasks.length === 0) return;

  logger.info({ count: tasks.length }, 'Dispatching due scheduled tasks');

  for (const task of tasks) {
    const workerType = routeToWorker(task.prompt);

    logger.info(
      { taskId: task.id, workerType, prompt: task.prompt.slice(0, 60) },
      'Dispatching scheduled task to worker queue',
    );

    try {
      // Enqueue to dispatch_queue -- a worker process will pick it up
      const dispatchId = enqueueTask(ALLOWED_CHAT_ID, task.prompt, workerType);

      // Notify the user that the task was dispatched
      try {
        await sender(
          `Scheduled task dispatched to ${workerType}: "${task.prompt.slice(0, 60)}${task.prompt.length > 60 ? '...' : ''}"`,
        );
      } catch {
        // Don't fail dispatch over notification
      }

      // Update next run time immediately (don't wait for worker completion)
      const nextRun = computeNextRun(task.schedule);
      updateTaskAfterRun(task.id, nextRun, `Dispatched as ${dispatchId}`);

      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'scheduled_task_dispatched',
        task_id: task.id,
        dispatch_id: dispatchId,
        worker_type: workerType,
        prompt_preview: task.prompt.slice(0, 80),
      });

      logger.info(
        { taskId: task.id, dispatchId, workerType, nextRun },
        'Task dispatched, next run scheduled',
      );
    } catch (err) {
      logger.error({ err, taskId: task.id }, 'Failed to dispatch scheduled task');
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      telemetry.emit({
        timestamp: new Date().toISOString(),
        event_type: 'error',
        error_source: 'scheduler',
        error_message: errorMsg,
      });
      try {
        await sender(`Scheduled task dispatch failed: "${task.prompt.slice(0, 60)}..." -- check logs.`);
      } catch {
        // ignore send failure
      }
    }
  }
}

export function computeNextRun(cronExpression: string): number {
  const interval = CronExpressionParser.parse(cronExpression);
  return Math.floor(interval.next().getTime() / 1000);
}
