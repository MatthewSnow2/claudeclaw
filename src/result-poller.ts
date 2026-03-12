import type { Api, RawApi } from 'grammy';

import { getPendingResults, markNotified, reDispatchTask } from './db.js';
import { logger } from './logger.js';
import { redactSecrets, formatForTelegram, splitMessage } from './bot.js';
import { scoreResult, RE_DISPATCH_THRESHOLD } from './compliance.js';

const POLL_INTERVAL_MS = 10_000; // 10 seconds

const WORKER_LABELS: Record<string, string> = {
  starscream: 'Starscream',
  ravage: 'Ravage',
  soundwave: 'Soundwave',
  astrotrain: 'AstroTrain',
  default: 'Worker',
};

let pollTimer: ReturnType<typeof setInterval> | null = null;

/**
 * Poll the dispatch_queue for completed/failed tasks and send results
 * back to the user via Telegram.
 */
async function pollResults(botApi: Api<RawApi>): Promise<void> {
  try {
    const pending = getPendingResults();

    for (const task of pending) {
      const label = WORKER_LABELS[task.worker_type] ?? 'Worker';
      const chatId = task.chat_id;

      try {
        if (task.status === 'completed' && task.result) {
          // Compliance gate: score result quality before posting
          const { score, issues } = scoreResult(task);
          if (score < RE_DISPATCH_THRESHOLD) {
            logger.warn(
              { taskId: task.id, score, issues, workerType: task.worker_type },
              'Compliance score below threshold -- re-dispatching task',
            );
            reDispatchTask(task.id);
            await botApi.sendMessage(
              chatId,
              `${label} output was too low-quality (score: ${score}). Re-dispatching.`,
              { parse_mode: 'HTML' },
            );
            continue;
          }

          const elapsed = task.completed_at && task.started_at
            ? task.completed_at - task.started_at
            : null;
          const timeStr = elapsed ? ` (${formatDuration(elapsed)})` : '';

          const header = `<b>${label} completed${timeStr}</b>\n\n`;
          const body = redactSecrets(task.result);
          const formatted = header + formatForTelegram(body);

          for (const part of splitMessage(formatted)) {
            await botApi.sendMessage(chatId, part, { parse_mode: 'HTML' });
          }
        } else if (task.status === 'failed') {
          const errorMsg = task.error
            ? redactSecrets(task.error)
            : 'Unknown error';
          await botApi.sendMessage(
            chatId,
            `<b>${label} failed:</b> ${errorMsg}`,
            { parse_mode: 'HTML' },
          );
        }

        markNotified(task.id);
      } catch (err) {
        logger.error(
          { err, taskId: task.id, chatId },
          'Failed to send dispatch result to Telegram',
        );
        // Don't mark as notified so we retry next poll
      }
    }
  } catch (err) {
    logger.error({ err }, 'Error polling dispatch results');
  }
}

/**
 * Format seconds into a human-readable duration string.
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (secs === 0) return `${mins}m`;
  return `${mins}m ${secs}s`;
}

/**
 * Start the result poller. Call once during bot startup.
 * The poller checks every 10s for completed/failed dispatch tasks
 * and sends results back to Telegram.
 */
export function startResultPoller(botApi: Api<RawApi>): void {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
  pollTimer = setInterval(() => void pollResults(botApi), POLL_INTERVAL_MS);
  logger.info({ intervalMs: POLL_INTERVAL_MS }, 'Dispatch result poller started');
}

/**
 * Stop the result poller. Call during shutdown.
 */
export function stopResultPoller(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
    logger.info('Dispatch result poller stopped');
  }
}
