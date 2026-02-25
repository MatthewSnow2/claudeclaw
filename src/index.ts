import fs from 'fs';
import path from 'path';

import { createBot } from './bot.js';
import { ALLOWED_CHAT_ID, STORE_DIR, TELEGRAM_BOT_TOKEN } from './config.js';
import { initDatabase } from './db.js';
import { logger } from './logger.js';
import { cleanupOldUploads } from './media.js';
import { runDecaySweep } from './memory.js';
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
  let attempt = 0;
  let delay = 3000;
  const MAX_DELAY = 35000; // > Telegram's 30s long-poll timeout

  while (true) {
    attempt++;
    const bot = createBot();

    // Scheduler: sends results to Matthew's chat (re-bind on each new bot instance)
    if (ALLOWED_CHAT_ID) {
      initScheduler((text) => bot.api.sendMessage(ALLOWED_CHAT_ID, text, { parse_mode: 'HTML' }).then(() => {}));
    }

    // Graceful shutdown
    const shutdown = async () => {
      logger.info('Shutting down...');
      releaseLock();
      await bot.stop();
      process.exit(0);
    };
    process.on('SIGINT', () => void shutdown());
    process.on('SIGTERM', () => void shutdown());

    try {
      // Clear any stale webhook config
      await bot.api.deleteWebhook({ drop_pending_updates: false });

      logger.info({ attempt }, 'Starting EA-Claude...');

      await bot.start({
        onStart: (botInfo) => {
          // Reset backoff on successful stable start
          attempt = 0;
          delay = 3000;
          logger.info({ username: botInfo.username }, 'EA-Claude is running');
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

      logger.warn(
        { attempt, delayMs: delay },
        'getUpdates conflict. Waiting for stale connection to expire...',
      );

      // Stop the bot to clean up any internal polling state
      try { await bot.stop(); } catch { /* ignore */ }

      await sleep(delay);
      delay = Math.min(delay * 2, MAX_DELAY);
    }
  }
}

main().catch((err: unknown) => {
  logger.error({ err }, 'Fatal error');
  releaseLock();
  process.exit(1);
});
