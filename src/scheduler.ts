import fs from 'fs';

import { CronExpressionParser } from 'cron-parser';

import { AGENT_ID, ALLOWED_CHAT_ID } from './config.js';
import {
  getDueTasks,
  getSession,
  logConversationTurn,
  markTaskRunning,
  updateTaskAfterRun,
  resetStuckTasks,
  claimNextMissionTask,
  claimNextWorkerMissionTask,
  completeMissionTask,
  resetStuckMissionTasks,
  resetStuckWorkerMissionTasks,
} from './db.js';
import { listAgentIds, loadAgentConfig, resolveAgentClaudeMd } from './agent-config.js';
import { logger } from './logger.js';
import { messageQueue } from './message-queue.js';
import { runAgent } from './agent.js';
import { formatForTelegram, splitMessage } from './bot.js';
import { emitChatEvent } from './state.js';

type Sender = (text: string) => Promise<void>;

/** Max time (ms) a scheduled task can run before being killed. */
const TASK_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

let sender: Sender;

/**
 * In-memory set of task IDs currently being executed.
 * Acts as a fast-path guard alongside the DB-level lock in markTaskRunning.
 */
const runningTaskIds = new Set<string>();

/**
 * Worker agent IDs that don't have their own PM2 process.
 * The main process picks up mission tasks for these agents.
 */
let workerAgentIds: string[] = [];

/**
 * Initialise the scheduler. Call once after the Telegram bot is ready.
 * @param send  Function that sends a message to the user's Telegram chat.
 */
let schedulerAgentId = 'main';

export function initScheduler(send: Sender, agentId = 'main'): void {
  if (!ALLOWED_CHAT_ID) {
    logger.warn('ALLOWED_CHAT_ID not set — scheduler will not send results');
  }
  sender = send;
  schedulerAgentId = agentId;

  // Only the main process picks up worker tasks (named agents have their own process)
  if (agentId === 'main') {
    try {
      workerAgentIds = listAgentIds().filter((id) => {
        try {
          const config = loadAgentConfig(id);
          return config.type === 'worker';
        } catch {
          return false;
        }
      });
      if (workerAgentIds.length > 0) {
        logger.info({ workers: workerAgentIds }, 'Main scheduler will pick up mission tasks for worker agents');
      }
    } catch (err) {
      logger.warn({ err }, 'Failed to enumerate worker agents');
    }
  }

  // Recover tasks stuck in 'running' from a previous crash
  const recovered = resetStuckTasks(agentId);
  if (recovered > 0) {
    logger.warn({ recovered, agentId }, 'Reset stuck tasks from previous crash');
  }
  const recoveredMission = resetStuckMissionTasks(agentId);
  if (recoveredMission > 0) {
    logger.warn({ recovered: recoveredMission, agentId }, 'Reset stuck mission tasks from previous crash');
  }
  if (agentId === 'main' && workerAgentIds.length > 0) {
    const recoveredWorker = resetStuckWorkerMissionTasks(workerAgentIds);
    if (recoveredWorker > 0) {
      logger.warn({ recovered: recoveredWorker }, 'Reset stuck worker mission tasks from previous crash');
    }
  }

  setInterval(() => void runDueTasks(), 60_000);
  logger.info({ agentId }, 'Scheduler started (checking every 60s)');
}

async function runDueTasks(): Promise<void> {
  const tasks = getDueTasks(schedulerAgentId);

  if (tasks.length > 0) {
    logger.info({ count: tasks.length }, 'Running due scheduled tasks');
  }

  for (const task of tasks) {
    // In-memory guard: skip if already running in this process
    if (runningTaskIds.has(task.id)) {
      logger.warn({ taskId: task.id }, 'Task already running, skipping duplicate fire');
      continue;
    }

    // Compute next occurrence BEFORE executing so we can lock the task
    // in the DB immediately, preventing re-fire on subsequent ticks.
    const nextRun = computeNextRun(task.schedule);
    runningTaskIds.add(task.id);
    markTaskRunning(task.id, nextRun);

    logger.info({ taskId: task.id, prompt: task.prompt.slice(0, 60) }, 'Firing task');

    // Route through the message queue so scheduled tasks wait for any
    // in-flight user message to finish before running. This prevents
    // two Claude processes from hitting the same session simultaneously.
    const chatId = ALLOWED_CHAT_ID || 'scheduler';
    messageQueue.enqueue(chatId, async () => {
      const abortController = new AbortController();
      const timeout = setTimeout(() => abortController.abort(), TASK_TIMEOUT_MS);

      try {
        await sender(`Scheduled task running: "${task.prompt.slice(0, 80)}${task.prompt.length > 80 ? '...' : ''}"`);

        // Run as a fresh agent call (no session — scheduled tasks are autonomous)
        const result = await runAgent(task.prompt, undefined, () => {}, undefined, undefined, abortController);
        clearTimeout(timeout);

        if (result.aborted) {
          updateTaskAfterRun(task.id, nextRun, 'Timed out after 10 minutes', 'timeout');
          await sender(`⏱ Task timed out after 10m: "${task.prompt.slice(0, 60)}..." — killed.`);
          logger.warn({ taskId: task.id }, 'Task timed out');
          return;
        }

        const text = result.text?.trim() || 'Task completed with no output.';
        for (const chunk of splitMessage(formatForTelegram(text))) {
          await sender(chunk);
        }

        // Inject task output into the active chat session so user replies have context
        if (ALLOWED_CHAT_ID) {
          const activeSession = getSession(ALLOWED_CHAT_ID, schedulerAgentId);
          logConversationTurn(ALLOWED_CHAT_ID, 'user', `[Scheduled task]: ${task.prompt}`, activeSession ?? undefined, schedulerAgentId);
          logConversationTurn(ALLOWED_CHAT_ID, 'assistant', text, activeSession ?? undefined, schedulerAgentId);
        }

        updateTaskAfterRun(task.id, nextRun, text, 'success');

        logger.info({ taskId: task.id, nextRun }, 'Task complete, next run scheduled');
      } catch (err) {
        clearTimeout(timeout);
        const errMsg = err instanceof Error ? err.message : String(err);
        updateTaskAfterRun(task.id, nextRun, errMsg.slice(0, 500), 'failed');

        logger.error({ err, taskId: task.id }, 'Scheduled task failed');
        try {
          await sender(`❌ Task failed: "${task.prompt.slice(0, 60)}..." — ${errMsg.slice(0, 200)}`);
        } catch {
          // ignore send failure
        }
      } finally {
        runningTaskIds.delete(task.id);
      }
    });
  }

  // Also check for queued mission tasks (one-shot async tasks from Mission Control)
  await runDueMissionTasks();
}

async function runDueMissionTasks(): Promise<void> {
  // 1. Check for tasks assigned to this agent
  const mission = claimNextMissionTask(schedulerAgentId);
  if (mission) {
    await executeMissionTask(mission);
    return;
  }

  // 2. Main process also picks up tasks for worker agents
  if (schedulerAgentId === 'main' && workerAgentIds.length > 0) {
    const workerMission = claimNextWorkerMissionTask(workerAgentIds);
    if (workerMission) {
      await executeMissionTask(workerMission);
    }
  }
}

async function executeMissionTask(mission: { id: string; title: string; prompt: string; assigned_agent: string | null }): Promise<void> {
  const missionKey = 'mission-' + mission.id;
  if (runningTaskIds.has(missionKey)) return;
  runningTaskIds.add(missionKey);

  const isWorkerTask = mission.assigned_agent && mission.assigned_agent !== schedulerAgentId;
  logger.info(
    { missionId: mission.id, title: mission.title, agent: mission.assigned_agent, isWorkerTask },
    'Running mission task',
  );

  // Load worker agent's CLAUDE.md as system prompt prefix
  let workerSystemPrompt = '';
  if (isWorkerTask && mission.assigned_agent) {
    const claudeMdPath = resolveAgentClaudeMd(mission.assigned_agent);
    if (claudeMdPath) {
      try { workerSystemPrompt = fs.readFileSync(claudeMdPath, 'utf-8'); } catch { /* no CLAUDE.md */ }
    }
  }

  const chatId = ALLOWED_CHAT_ID || 'mission';
  messageQueue.enqueue(chatId, async () => {
    const abortController = new AbortController();
    const timeout = setTimeout(() => abortController.abort(), TASK_TIMEOUT_MS);

    try {
      // Prefix the prompt with the worker's system prompt so the agent runs in-character
      const fullPrompt = workerSystemPrompt
        ? `[Agent role -- follow these instructions]\n${workerSystemPrompt}\n[End agent role]\n\n${mission.prompt}`
        : mission.prompt;

      // Use the worker's configured model if available
      let model: string | undefined;
      if (isWorkerTask && mission.assigned_agent) {
        try {
          const config = loadAgentConfig(mission.assigned_agent);
          model = config.model;
        } catch { /* use default */ }
      }

      const result = await runAgent(fullPrompt, undefined, () => {}, undefined, model, abortController);
      clearTimeout(timeout);

      if (result.aborted) {
        completeMissionTask(mission.id, null, 'failed', 'Timed out after 10 minutes');
        logger.warn({ missionId: mission.id }, 'Mission task timed out');
        try { await sender('Mission task timed out: "' + mission.title + '"'); } catch {}
      } else {
        const text = result.text?.trim() || 'Task completed with no output.';
        completeMissionTask(mission.id, text, 'completed');
        logger.info({ missionId: mission.id, agent: mission.assigned_agent }, 'Mission task completed');

        // Send result to Telegram
        const agentLabel = isWorkerTask ? ` [${mission.assigned_agent}]` : '';
        for (const chunk of splitMessage(formatForTelegram(text))) {
          await sender(chunk);
        }

        // Inject into conversation context so agent can reference it
        if (ALLOWED_CHAT_ID) {
          const activeSession = getSession(ALLOWED_CHAT_ID, schedulerAgentId);
          logConversationTurn(ALLOWED_CHAT_ID, 'user', '[Mission task' + agentLabel + ': ' + mission.title + ']: ' + mission.prompt, activeSession ?? undefined, schedulerAgentId);
          logConversationTurn(ALLOWED_CHAT_ID, 'assistant', text, activeSession ?? undefined, schedulerAgentId);
        }
      }

      emitChatEvent({
        type: 'mission_update' as 'progress',
        chatId,
        content: JSON.stringify({
          id: mission.id,
          status: result.aborted ? 'failed' : 'completed',
          title: mission.title,
        }),
      });
    } catch (err) {
      clearTimeout(timeout);
      const errMsg = err instanceof Error ? err.message : String(err);
      completeMissionTask(mission.id, null, 'failed', errMsg.slice(0, 500));
      logger.error({ err, missionId: mission.id }, 'Mission task failed');
    } finally {
      runningTaskIds.delete(missionKey);
    }
  });
}

export function computeNextRun(cronExpression: string): number {
  const interval = CronExpressionParser.parse(cronExpression);
  return Math.floor(interval.next().getTime() / 1000);
}
