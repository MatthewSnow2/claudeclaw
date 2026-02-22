import { createBot } from './bot.js';
import { ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN } from './config.js';
import { initDatabase } from './db.js';
import { logger } from './logger.js';
import { cleanupOldUploads } from './media.js';
import { runDecaySweep } from './memory.js';
import { initScheduler } from './scheduler.js';

async function main(): Promise<void> {
  if (!TELEGRAM_BOT_TOKEN) {
    logger.error('TELEGRAM_BOT_TOKEN is not set. Add it to .env and restart.');
    process.exit(1);
  }

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
    await bot.stop();
    process.exit(0);
  };
  process.on('SIGINT', () => void shutdown());
  process.on('SIGTERM', () => void shutdown());

  logger.info('Starting ClaudeClaw...');

  await bot.start({
    onStart: (botInfo) => {
      logger.info({ username: botInfo.username }, 'ClaudeClaw is running');
      console.log(`\n  ClaudeClaw online: @${botInfo.username}`);
      console.log(`  Send /chatid to get your chat ID for ALLOWED_CHAT_ID\n`);
    },
  });
}

main().catch((err: unknown) => {
  logger.error({ err }, 'Fatal error');
  process.exit(1);
});
