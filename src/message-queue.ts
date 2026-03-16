import { logger } from './logger.js';

/**
 * Per-chat FIFO message queue. Ensures only one message is processed
 * at a time per chat_id (or chat_id:topic_id), preventing race conditions
 * on sessions, abort controllers, and conversation logs.
 */
class MessageQueue {
  private chains = new Map<string, Promise<void>>();
  private pending = new Map<string, number>();

  /**
   * Enqueue a message handler for a given chat. Handlers for the same
   * chatId (or chatId:topicId composite key) run sequentially in FIFO order.
   * Different keys run in parallel.
   */
  enqueue(chatId: string, handler: () => Promise<void>, topicId?: string | null): void {
    const key = topicId ? `${chatId}:${topicId}` : chatId;
    const queued = (this.pending.get(key) ?? 0) + 1;
    this.pending.set(key, queued);

    if (queued > 1) {
      logger.info({ chatId, topicId, queued }, 'Message queued (another is processing)');
    }

    const prev = this.chains.get(key) ?? Promise.resolve();
    const next = prev.then(async () => {
      try {
        await handler();
      } catch (err) {
        logger.error({ err, chatId, topicId }, 'Unhandled message error');
      } finally {
        const remaining = (this.pending.get(key) ?? 1) - 1;
        if (remaining <= 0) {
          this.pending.delete(key);
          this.chains.delete(key);
        } else {
          this.pending.set(key, remaining);
        }
      }
    });

    this.chains.set(key, next);
  }

  /** Number of chats with pending messages. */
  get activeChats(): number {
    return this.chains.size;
  }

  /** Number of pending messages for a given chat. */
  queuedFor(chatId: string): number {
    return this.pending.get(chatId) ?? 0;
  }
}

export const messageQueue = new MessageQueue();
