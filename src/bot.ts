import { Api, Bot, Context, InputFile, RawApi } from 'grammy';

import {
  ALLOWED_CHAT_ID,
  ALLOWED_CHAT_IDS,
  MAX_MESSAGE_LENGTH,
  TELEGRAM_BOT_TOKEN,
  TYPING_REFRESH_MS,
} from './config.js';
import { clearSession, getRecentMemories, getSession, setSession } from './db.js';
import { logger } from './logger.js';
import { downloadMedia, buildPhotoMessage, buildDocumentMessage } from './media.js';
import { buildMemoryContext, saveConversationTurn } from './memory.js';
import { routeMessage } from './router.js';
import {
  downloadTelegramFile,
  transcribeAudio,
  synthesizeSpeech,
  voiceCapabilities,
  UPLOADS_DIR,
} from './voice.js';

// Per-chat voice mode toggle (in-memory, resets on restart)
const voiceEnabledChats = new Set<string>();

/**
 * Scan outgoing text for patterns that look like API keys or secrets
 * and replace them with [REDACTED]. Defence-in-depth measure.
 */
export function redactSecrets(text: string): string {
  return text
    // OpenAI keys: sk-...
    .replace(/sk-[A-Za-z0-9_-]{20,}/g, '[REDACTED]')
    // GitHub tokens: ghp_, gho_, ghs_, ghu_, ghr_
    .replace(/gh[pousr]_[A-Za-z0-9_]{20,}/g, '[REDACTED]')
    // Generic Bearer/API tokens (long hex or base64 strings after common prefixes)
    .replace(/(?:key|token|secret|password|apikey|api_key)[\s=:]+['"]?[A-Za-z0-9_\-/.]{20,}/gi, '[REDACTED]')
    // PEM private key blocks
    .replace(/-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----/g, '[REDACTED]')
    // AWS keys: AKIA...
    .replace(/AKIA[A-Z0-9]{16}/g, '[REDACTED]')
    // Long hex strings (40+ chars, likely tokens)
    .replace(/\b[0-9a-f]{40,}\b/gi, '[REDACTED]');
}

/**
 * Convert Markdown to Telegram HTML.
 *
 * Telegram supports a limited HTML subset: <b>, <i>, <s>, <u>, <code>, <pre>, <a>.
 * It does NOT support: # headings, ---, - [ ] checkboxes, or most Markdown syntax.
 * This function bridges the gap so Claude's responses render cleanly.
 */
export function formatForTelegram(text: string): string {
  // 1. Extract and protect code blocks before any other processing
  const codeBlocks: string[] = [];
  let result = text.replace(/```(?:\w*\n)?([\s\S]*?)```/g, (_, code) => {
    const escaped = code.trim()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    codeBlocks.push(`<pre>${escaped}</pre>`);
    return `\x00CODE${codeBlocks.length - 1}\x00`;
  });

  // 2. Escape HTML entities in the remaining text
  result = result
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 3. Inline code (after block extraction)
  const inlineCodes: string[] = [];
  result = result.replace(/`([^`]+)`/g, (_, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    inlineCodes.push(`<code>${escaped}</code>`);
    return `\x00INLINE${inlineCodes.length - 1}\x00`;
  });

  // 4. Headings → bold (strip the # prefix, keep the text)
  result = result.replace(/^#{1,6}\s+(.+)$/gm, '<b>$1</b>');

  // 5. Horizontal rules → remove entirely (including surrounding blank lines)
  result = result.replace(/\n*^[-*_]{3,}$\n*/gm, '\n');

  // 6. Checkboxes — handle both `- [ ]` and `- [ ] ` with any whitespace variant
  result = result.replace(/^(\s*)-\s+\[x\]\s*/gim, '$1✓ ');
  result = result.replace(/^(\s*)-\s+\[\s\]\s*/gm, '$1☐ ');

  // 7. Bold **text** and __text__
  result = result.replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>');
  result = result.replace(/__([^_\n]+)__/g, '<b>$1</b>');

  // 8. Italic *text* and _text_ (single, not inside words)
  result = result.replace(/\*([^*\n]+)\*/g, '<i>$1</i>');
  result = result.replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, '<i>$1</i>');

  // 9. Strikethrough ~~text~~
  result = result.replace(/~~([^~\n]+)~~/g, '<s>$1</s>');

  // 10. Links [text](url)
  result = result.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2">$1</a>');

  // 11. Restore code blocks and inline code
  result = result.replace(/\x00CODE(\d+)\x00/g, (_, i) => codeBlocks[parseInt(i)]);
  result = result.replace(/\x00INLINE(\d+)\x00/g, (_, i) => inlineCodes[parseInt(i)]);

  // 12. Collapse 3+ consecutive blank lines down to 2 (one blank line between sections)
  result = result.replace(/\n{3,}/g, '\n\n');

  return result.trim();
}

/**
 * Split a long response into Telegram-safe chunks (4096 chars).
 * Splits on newlines where possible to avoid breaking mid-sentence.
 */
export function splitMessage(text: string): string[] {
  if (text.length <= MAX_MESSAGE_LENGTH) return [text];

  const parts: string[] = [];
  let remaining = text;

  while (remaining.length > MAX_MESSAGE_LENGTH) {
    // Try to split on a newline within the limit
    const chunk = remaining.slice(0, MAX_MESSAGE_LENGTH);
    const lastNewline = chunk.lastIndexOf('\n');
    const splitAt = lastNewline > MAX_MESSAGE_LENGTH / 2 ? lastNewline : MAX_MESSAGE_LENGTH;
    parts.push(remaining.slice(0, splitAt));
    remaining = remaining.slice(splitAt).trimStart();
  }

  if (remaining) parts.push(remaining);
  return parts;
}

/**
 * Send a Telegram typing action. Silently ignores errors (e.g. bot was blocked).
 */
async function sendTyping(api: Api<RawApi>, chatId: number): Promise<void> {
  try {
    await api.sendChatAction(chatId, 'typing');
  } catch {
    // Ignore — typing is best-effort
  }
}

/**
 * Authorise an incoming message by checking both the sender (from) and
 * the chat against ALLOWED_CHAT_IDS. This supports:
 * - DMs: chatId matches your user ID
 * - Groups: senderId matches your user ID (you sent it in the group)
 * - Explicit group allow: group chat ID is in the allowed list
 */
function isAuthorised(chatId: number, senderId?: number): boolean {
  if (ALLOWED_CHAT_IDS.size === 0) {
    // Not yet configured — let every request through but warn in the reply handler
    return true;
  }
  // Check if the chat itself is allowed (DMs, or explicitly listed groups)
  if (ALLOWED_CHAT_IDS.has(chatId.toString())) return true;
  // Check if the sender is allowed (you messaging in any group)
  if (senderId && ALLOWED_CHAT_IDS.has(senderId.toString())) return true;
  return false;
}

/**
 * Core message handler. Called for every inbound text/voice/photo/document.
 */
async function handleMessage(ctx: Context, message: string): Promise<void> {
  const chatId = ctx.chat!.id;
  const chatIdStr = chatId.toString();

  // Security gate
  if (!isAuthorised(chatId, ctx.from?.id)) {
    logger.warn({ chatId }, 'Rejected message from unauthorised chat');
    return;
  }

  // First-run setup guidance: ALLOWED_CHAT_ID not set yet
  if (!ALLOWED_CHAT_ID) {
    await ctx.reply(
      `Your chat ID is ${chatId}.\n\nAdd this to your .env:\n\nALLOWED_CHAT_ID=${chatId}\n\nThen restart ClaudeClaw.`,
    );
    return;
  }

  logger.info(
    { chatId, messageLen: message.length },
    'Processing message',
  );

  // Route based on the ORIGINAL message (before memory context),
  // so @prefix detection works regardless of memory state.
  // Memory context is only useful for Claude, not external backends.
  const sessionId = getSession(chatIdStr);

  // Start typing immediately, then refresh on interval
  await sendTyping(ctx.api, chatId);
  const typingInterval = setInterval(
    () => void sendTyping(ctx.api, chatId),
    TYPING_REFRESH_MS,
  );

  try {
    // Build memory context (only used by Claude backend)
    const memCtx = await buildMemoryContext(chatIdStr, message);
    const fullMessage = memCtx ? `${memCtx}\n\n${message}` : message;

    // Route using original message for @prefix detection,
    // pass full memory-enriched message for Claude backend
    const result = await routeMessage(message, fullMessage, sessionId, () =>
      void sendTyping(ctx.api, chatId),
    );

    clearInterval(typingInterval);

    // null = message directed at another bot, ignore silently
    if (!result) return;

    if (result.newSessionId) {
      setSession(chatIdStr, result.newSessionId);
      logger.info({ newSessionId: result.newSessionId }, 'Session saved');
    }

    let responseText = result.text?.trim() || 'Done.';

    // Prepend [backend] tag for non-Claude responses
    if (result.backend !== 'claude') {
      responseText = `[${result.backend}]\n\n${responseText}`;
    }

    // Redact any secrets that may have leaked into the response
    responseText = redactSecrets(responseText);

    // Save conversation turn to memory
    saveConversationTurn(chatIdStr, message, responseText);

    // Check if voice response is enabled for this chat
    const caps = voiceCapabilities();
    if (voiceEnabledChats.has(chatIdStr) && caps.tts) {
      try {
        const audioBuffer = await synthesizeSpeech(responseText);
        await ctx.replyWithVoice(new InputFile(audioBuffer, 'response.mp3'));
      } catch (ttsErr) {
        logger.error({ err: ttsErr }, 'TTS synthesis failed, falling back to text');
        for (const part of splitMessage(formatForTelegram(responseText))) {
          await ctx.reply(part, { parse_mode: 'HTML' });
        }
      }
    } else {
      for (const part of splitMessage(formatForTelegram(responseText))) {
        await ctx.reply(part, { parse_mode: 'HTML' });
      }
    }
  } catch (err) {
    clearInterval(typingInterval);
    logger.error({ err }, 'Agent error');
    const errorMsg = err instanceof Error ? err.message : 'Unknown error';
    await ctx.reply(`Something went wrong: ${redactSecrets(errorMsg)}`);
  }
}

export function createBot(): Bot {
  if (!TELEGRAM_BOT_TOKEN) {
    throw new Error('TELEGRAM_BOT_TOKEN is not set in .env');
  }

  const bot = new Bot(TELEGRAM_BOT_TOKEN);

  // /chatid — get the chat ID (used during first-time setup)
  bot.command('chatid', (ctx) =>
    ctx.reply(`Your chat ID: ${ctx.chat!.id}`),
  );

  // /start — simple greeting
  bot.command('start', (ctx) =>
    ctx.reply('ClaudeClaw online. What do you need?'),
  );

  // /newchat — clear Claude session, start fresh
  bot.command('newchat', async (ctx) => {
    clearSession(ctx.chat!.id.toString());
    await ctx.reply('Session cleared. Starting fresh.');
    logger.info({ chatId: ctx.chat!.id }, 'Session cleared by user');
  });

  // /voice — toggle voice mode for this chat
  bot.command('voice', async (ctx) => {
    const caps = voiceCapabilities();
    if (!caps.tts) {
      await ctx.reply('ElevenLabs not configured. Add ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID to .env');
      return;
    }
    const chatIdStr = ctx.chat!.id.toString();
    if (voiceEnabledChats.has(chatIdStr)) {
      voiceEnabledChats.delete(chatIdStr);
      await ctx.reply('Voice mode OFF');
    } else {
      voiceEnabledChats.add(chatIdStr);
      await ctx.reply('Voice mode ON');
    }
  });

  // /memory — show recent memories for this chat
  bot.command('memory', async (ctx) => {
    const chatId = ctx.chat!.id.toString();
    const recent = getRecentMemories(chatId, 10);
    if (recent.length === 0) {
      await ctx.reply('No memories yet.');
      return;
    }
    const lines = recent.map(m => `<b>[${m.sector}]</b> ${m.content}`).join('\n');
    await ctx.reply(`<b>Recent memories</b>\n\n${lines}`, { parse_mode: 'HTML' });
  });

  // /forget — clear session (memory decay handles the rest)
  bot.command('forget', async (ctx) => {
    clearSession(ctx.chat!.id.toString());
    await ctx.reply('Session cleared. Memories will fade naturally over time.');
  });

  // Text messages — and any slash commands not owned by this bot (skills, e.g. /todo /gmail)
  const OWN_COMMANDS = new Set(['/start', '/newchat', '/voice', '/memory', '/forget', '/chatid']);
  bot.on('message:text', async (ctx) => {
    const text = ctx.message.text;
    if (text.startsWith('/')) {
      const cmd = text.split(/[\s@]/)[0].toLowerCase();
      if (OWN_COMMANDS.has(cmd)) return; // already handled by bot.command() above
    }
    await handleMessage(ctx, text);
  });

  // Voice messages — real transcription via Groq Whisper
  bot.on('message:voice', async (ctx) => {
    const caps = voiceCapabilities();
    if (!caps.stt) {
      await ctx.reply('Voice transcription not configured. Add GROQ_API_KEY to .env');
      return;
    }
    const chatId = ctx.chat!.id;
    if (!isAuthorised(chatId, ctx.from?.id)) return;
    if (!ALLOWED_CHAT_ID) {
      await ctx.reply(
        `Your chat ID is ${chatId}.\n\nAdd this to your .env:\n\nALLOWED_CHAT_ID=${chatId}\n\nThen restart ClaudeClaw.`,
      );
      return;
    }

    await sendTyping(ctx.api, chatId);
    const typingInterval = setInterval(() => void sendTyping(ctx.api, chatId), TYPING_REFRESH_MS);
    try {
      const fileId = ctx.message.voice.file_id;
      const localPath = await downloadTelegramFile(TELEGRAM_BOT_TOKEN, fileId, UPLOADS_DIR);
      const transcribed = await transcribeAudio(localPath);
      clearInterval(typingInterval);
      await handleMessage(ctx, `[Voice transcribed]: ${transcribed}`);
    } catch (err) {
      clearInterval(typingInterval);
      logger.error({ err }, 'Voice transcription failed');
      await ctx.reply('Could not transcribe voice message. Try again.');
    }
  });

  // Photos — download and pass to Claude
  bot.on('message:photo', async (ctx) => {
    const chatId = ctx.chat!.id;
    if (!isAuthorised(chatId, ctx.from?.id)) return;
    if (!ALLOWED_CHAT_ID) {
      await ctx.reply(
        `Your chat ID is ${chatId}.\n\nAdd this to your .env:\n\nALLOWED_CHAT_ID=${chatId}\n\nThen restart ClaudeClaw.`,
      );
      return;
    }

    await sendTyping(ctx.api, chatId);
    const typingInterval = setInterval(() => void sendTyping(ctx.api, chatId), TYPING_REFRESH_MS);
    try {
      const photo = ctx.message.photo[ctx.message.photo.length - 1];
      const localPath = await downloadMedia(TELEGRAM_BOT_TOKEN, photo.file_id, 'photo.jpg');
      clearInterval(typingInterval);
      const msg = buildPhotoMessage(localPath, ctx.message.caption ?? undefined);
      await handleMessage(ctx, msg);
    } catch (err) {
      clearInterval(typingInterval);
      logger.error({ err }, 'Photo download failed');
      await ctx.reply('Could not download photo. Try again.');
    }
  });

  // Documents — download and pass to Claude
  bot.on('message:document', async (ctx) => {
    const chatId = ctx.chat!.id;
    if (!isAuthorised(chatId, ctx.from?.id)) return;
    if (!ALLOWED_CHAT_ID) {
      await ctx.reply(
        `Your chat ID is ${chatId}.\n\nAdd this to your .env:\n\nALLOWED_CHAT_ID=${chatId}\n\nThen restart ClaudeClaw.`,
      );
      return;
    }

    await sendTyping(ctx.api, chatId);
    const typingInterval = setInterval(() => void sendTyping(ctx.api, chatId), TYPING_REFRESH_MS);
    try {
      const doc = ctx.message.document;
      const filename = doc.file_name ?? 'file';
      const localPath = await downloadMedia(TELEGRAM_BOT_TOKEN, doc.file_id, filename);
      clearInterval(typingInterval);
      const msg = buildDocumentMessage(localPath, filename, ctx.message.caption ?? undefined);
      await handleMessage(ctx, msg);
    } catch (err) {
      clearInterval(typingInterval);
      logger.error({ err }, 'Document download failed');
      await ctx.reply('Could not download document. Try again.');
    }
  });

  // Graceful error handling — log but don't crash
  bot.catch((err) => {
    logger.error({ err: err.message }, 'Telegram bot error');
  });

  return bot;
}
