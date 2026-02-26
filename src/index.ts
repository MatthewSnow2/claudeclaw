import fs from 'fs';
import path from 'path';

import { Api, RawApi } from 'grammy';

import { createBot } from './bot.js';
import { ALLOWED_CHAT_ID, STORE_DIR, TELEGRAM_BOT_TOKEN } from './config.js';
import { initDatabase } from './db.js';
import { logger } from './logger.js';
import { cleanupOldUploads } from './media.js';
import { runDecaySweep } from './memory.js';
import { startResultPoller, stopResultPoller } from './result-poller.js';
import { initScheduler } from './scheduler.js';
import { initTelemetry } from './telemetry.js';

const PID_FILE = path.join(STORE_DIR, 'claudeclaw.pid');

/**
 * Acquire a process lock. If another instance is running, kill it first.
 * Prevents the "409 Conflict: terminated by other getUpdates request" error.
 */
function acquireLock(): void {
  try {
    if (fs.existsSync(PID_FILE)) {
      const oldPid = parseInt(fs.readFileSync(PID_FILE, 'utf-8').trim(), 10);
      if (oldPid && !isNaN(oldPid)) {
        try {
          process.kill(oldPid, 0); // Check if alive
          logger.info({ oldPid }, 'Killing previous instance');
          process.kill(oldPid, 'SIGTERM');
        } catch {
          // Process not running, stale PID file
        }
      }
    }
  } catch {
    // PID file doesn't exist or can't be read
  }
  fs.mkdirSync(path.dirname(PID_FILE), { recursive: true });
  fs.writeFileSync(PID_FILE, process.pid.toString());
}

function releaseLock(): void {
  try {
    fs.unlinkSync(PID_FILE);
  } catch {
    // Best effort
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main(): Promise<void> {
  if (!TELEGRAM_BOT_TOKEN) {
    logger.error('TELEGRAM_BOT_TOKEN is not set. Add it to .env and restart.');
    process.exit(1);
  }

  acquireLock();

  initTelemetry();
  initDatabase();
  logger.info('Database ready');

  runDecaySweep();
  // Schedule daily decay sweep
  setInterval(() => runDecaySweep(), 24 * 60 * 60 * 1000);

  cleanupOldUploads();

  // Retry loop: create a fresh Bot instance each attempt to avoid grammyjs
  // internal state leakage (reusing a Bot after a failed start can cause
  // overlapping getUpdates connections that self-perpetuate 409 conflicts).
  //
  // KEY FIX: Initial delay must be >= 35s to outlast Telegram's 30s long-poll.
  // The old 3s delay caused a permanent 409 loop where the new connection
  // always collided with the still-alive old connection.
  let attempt = 0;
  let delay = 35000; // Must exceed Telegram's 30s long-poll timeout
  const MAX_DELAY = 60000;
  const MAX_409_RETRIES = 5; // Crash after this many to let PM2 do a clean restart

  // Mutable ref so the scheduler sender always uses the latest bot API.
  // Previous approach used a closure over a local var that never updated.
  const botApiRef: { current: Api<RawApi> | null } = { current: null };

  while (true) {
    attempt++;
    const bot = createBot();
    botApiRef.current = bot.api;

    // Scheduler: initScheduler is idempotent (clears old interval).
    // The sender closure reads botApiRef.current, which always points
    // to the latest bot instance's API.
    if (ALLOWED_CHAT_ID) {
      initScheduler((text) => {
        if (!botApiRef.current) return Promise.resolve();
        return botApiRef.current.sendMessage(ALLOWED_CHAT_ID, text, { parse_mode: 'HTML' }).then(() => {});
      });
    }

    // Result poller: checks dispatch_queue for completed/failed tasks every 10s
    startResultPoller(bot.api);

    // Graceful shutdown
    const shutdown = async () => {
      logger.info('Shutting down...');
      stopResultPoller();
      releaseLock();
      await bot.stop();
      process.exit(0);
    };
    process.on('SIGINT', () => void shutdown());
    process.on('SIGTERM', () => void shutdown());

    try {
      // Drop pending updates on retry to prevent re-processing messages
      // that were already handled before the 409 cycle.
      const dropPending = attempt > 1;
      await bot.api.deleteWebhook({ drop_pending_updates: dropPending });
      if (dropPending) {
        logger.info('Dropped pending updates after 409 recovery');
      }

      logger.info({ attempt, dropPending }, 'Starting EA-Claude...');

      await bot.start({
        onStart: (botInfo) => {
          // DON'T reset backoff immediately -- the 409 can arrive 30s after
          // onStart fires. Schedule a delayed reset so backoff only clears
          // after the connection has been stable for 90s.
          setTimeout(() => {
            attempt = 0;
            delay = 35000;
            logger.info('Backoff reset after stable connection (90s)');
          }, 90_000);
          logger.info({ username: botInfo.username, attempt }, 'EA-Claude is running');
          console.log(`\n  EA-Claude online: @${botInfo.username}`);
          console.log(`  Send /chatid to get your chat ID for ALLOWED_CHAT_ID\n`);
        },
      });
      return; // Clean exit (bot.stop() was called)
    } catch (err: unknown) {
      // Remove signal handlers from this bot instance before retrying
      process.removeAllListeners('SIGINT');
      process.removeAllListeners('SIGTERM');

      const is409 =
        err instanceof Error &&
        err.message.includes('409') &&
        err.message.includes('Conflict');

      if (!is409) throw err; // Non-409 errors still crash immediately

      if (attempt >= MAX_409_RETRIES) {
        logger.error(
          { attempt, maxRetries: MAX_409_RETRIES },
          '409 conflict persists after max retries. Crashing for PM2 clean restart.',
        );
        throw err;
      }

      logger.warn(
        { attempt, delayMs: delay, maxRetries: MAX_409_RETRIES },
        'getUpdates conflict. Waiting for stale connection to expire...',
      );

      // Stop the bot to clean up any internal polling state
      try { await bot.stop(); } catch { /* ignore */ }

      await sleep(delay);
      delay = Math.min(delay * 1.5, MAX_DELAY);
    }
  }
}

main().catch((err: unknown) => {
  logger.error({ err }, 'Fatal error');
  releaseLock();
  process.exit(1);
});
