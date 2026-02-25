import fs from 'fs';
import path from 'path';

import { createBot } from './bot.js';
import { ALLOWED_CHAT_ID, STORE_DIR, TELEGRAM_BOT_TOKEN } from './config.js';
import { initDatabase } from './db.js';
import { logger } from './logger.js';
import { cleanupOldUploads } from './media.js';
import { runDecaySweep } from './memory.js';
import { initScheduler } from './scheduler.js';

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

async function main(): Promise<void> {
  if (!TELEGRAM_BOT_TOKEN) {
    logger.error('TELEGRAM_BOT_TOKEN is not set. Add it to .env and restart.');
    process.exit(1);
  }

  acquireLock();

  initDatabase();
  logger.info('Database ready');

  runDecaySweep();
  // Schedule daily decay sweep
  setInterval(() => runDecaySweep(), 24 * 60 * 60 * 1000);

  cleanupOldUploads();

  const bot = createBot();

  // Scheduler: sends results to Mark's chat
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

  logger.info('Starting EA-Claude...');

  await bot.start({
    onStart: (botInfo) => {
      logger.info({ username: botInfo.username }, 'EA-Claude is running');
      console.log(`\n  EA-Claude online: @${botInfo.username}`);
      console.log(`  Send /chatid to get your chat ID for ALLOWED_CHAT_ID\n`);
    },
  });
}

main().catch((err: unknown) => {
  logger.error({ err }, 'Fatal error');
  releaseLock();
  process.exit(1);
});
