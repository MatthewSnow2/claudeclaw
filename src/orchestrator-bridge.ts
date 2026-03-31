/**
 * Orchestrator Bridge — Connects agentic-orchestrator to ClaudeClaw's Mission Control.
 *
 * Converts ClaudeClaw's MissionResult into the orchestrator's SubtaskResult format,
 * creates the adapter with real ClaudeClaw functions, and runs the reasoning loop.
 *
 * Gated behind ORCHESTRATOR_ENABLED=true environment variable.
 */

import path from 'path';

import {
  orchestrate,
  ClaudeClawAdapter,
  getDb as getOrchestratorDb,
  closeDb as closeOrchestratorDb,
  type OrchestratorResult,
  type SubtaskResult,
  type MissionContext,
  type OrchestratorConfig,
} from 'agentic-orchestrator';

import { delegateToAgent, getAgentCards, reviseMission } from './mission-control.js';
import { getMissionSubtasks, logToHiveMind } from './db.js';
import { logger } from './logger.js';

import type { MissionResult, MissionProgress } from './mission-control.js';

// ── Feature flag ────────────────────────────────────────────────────

export const ORCHESTRATOR_ENABLED =
  (process.env.ORCHESTRATOR_ENABLED || '').toLowerCase() === 'true';

import { STORE_DIR } from './config.js';

// ── DB lifecycle ────────────────────────────────────────────────────

let orchestratorDbReady = false;

function ensureOrchestratorDb(): void {
  if (!orchestratorDbReady) {
    // Use ClaudeClaw's store directory for the orchestrator DB
    const dbPath = path.join(STORE_DIR, 'orchestrator.db');
    getOrchestratorDb(dbPath);
    orchestratorDbReady = true;
  }
}

export function shutdownOrchestratorDb(): void {
  if (orchestratorDbReady) {
    closeOrchestratorDb();
    orchestratorDbReady = false;
  }
}

// ── Task type inference ─────────────────────────────────────────────

const TASK_TYPE_PATTERNS: Array<[RegExp, string]> = [
  [/\b(code|build|implement|fix|refactor|test|debug|write.*function|create.*api)\b/i, 'coding'],
  [/\b(research|analyze|investigate|find|compare|evaluate|review)\b/i, 'research'],
  [/\b(write|draft|blog|post|tweet|content|copy|article|email)\b/i, 'content'],
  [/\b(deploy|configure|setup|install|migrate|backup|monitor)\b/i, 'ops'],
];

function inferTaskType(prompt: string): string {
  for (const [pattern, taskType] of TASK_TYPE_PATTERNS) {
    if (pattern.test(prompt)) return taskType;
  }
  return 'general';
}

// ── Main bridge ─────────────────────────────────────────────────────

export async function runOrchestrator(
  missionResult: MissionResult,
  chatId: string,
  onProgress?: (progress: MissionProgress) => void,
  config?: Partial<OrchestratorConfig>,
): Promise<{ orchestratorResult: OrchestratorResult; updatedMissionResult: MissionResult }> {
  ensureOrchestratorDb();

  const mission: MissionContext = {
    missionId: missionResult.missionId,
    goal: missionResult.goal,
    chatId,
  };

  // Get full subtask records from DB (includes prompts, timestamps)
  const dbSubtasks = getMissionSubtasks(missionResult.missionId);

  // Convert ClaudeClaw subtask results to orchestrator format
  const subtaskResults: SubtaskResult[] = missionResult.subtaskResults.map((sr) => {
    const dbRecord = dbSubtasks.find((s) => s.id === sr.id);
    const prompt = dbRecord?.prompt ?? '';
    const startedAt = dbRecord?.started_at ?? 0;
    const completedAt = dbRecord?.completed_at ?? Date.now();

    return {
      subtaskId: sr.id,
      missionId: missionResult.missionId,
      agentId: sr.agentId ?? 'worker',
      prompt,
      taskType: inferTaskType(prompt),
      status: sr.status === 'completed' ? 'completed' : 'failed',
      result: sr.result ?? '',
      durationMs: startedAt ? completedAt - startedAt : 0,
      costUsd: sr.costUsd,
      retryCount: 0,
    };
  });

  // Create adapter with real ClaudeClaw functions
  const adapter = new ClaudeClawAdapter(
    {
      delegateToAgent: async (agentId, prompt, cId, fromAgent) => {
        const result = await delegateToAgent(agentId, prompt, cId, fromAgent, (msg) => {
          onProgress?.({
            missionId: missionResult.missionId,
            subtaskId: '',
            agentId,
            status: 'started',
            description: msg,
          });
        });
        return {
          text: result.text,
          durationMs: result.durationMs,
          usage: result.usage ? { totalCostUsd: result.usage.totalCostUsd } : undefined,
        };
      },

      getAgentCards: () => {
        return getAgentCards().map((c) => ({
          id: c.id,
          name: c.name,
          description: c.description,
          skills: c.skills.map((s) => s.name),
          type: c.type as 'named' | 'worker' | 'stock',
          execution: c.execution ? { mode: c.execution.mode } : undefined,
        }));
      },

      reviseMission: async (missionId, feedback) => {
        const plan = await reviseMission(missionId, feedback);
        return {
          subtasks: plan.subtasks.map((st) => ({
            id: st.id,
            prompt: st.prompt,
            agentId: st.agentId ?? 'worker',
            agentType: st.agentType,
            verification: st.verification,
            dependsOn: st.dependsOn,
          })),
        };
      },

      notifyUser: async (_chatId, message) => {
        onProgress?.({
          missionId: missionResult.missionId,
          subtaskId: '',
          agentId: 'orchestrator',
          status: 'started',
          description: message,
        });
      },

      logToHiveMind: (agentId, cId, action, detail) => {
        logToHiveMind(agentId, cId, action, detail);
      },
    },
    chatId,
  );

  logger.info(
    { missionId: missionResult.missionId, subtasks: subtaskResults.length },
    'Orchestrator loop starting',
  );

  // Default config tuned for ClaudeClaw missions:
  // - maxIterations: 3 (not 5 — avoid excessive replan loops)
  // - acceptThreshold: 0.45 (research + code missions rarely score 0.6+ on completeness)
  // - maxCostUsd: 3.0 (reasonable budget cap for orchestrator overhead)
  const clawDefaults: Partial<OrchestratorConfig> = {
    maxIterations: 3,
    acceptThreshold: 0.45,
    maxCostUsd: 3.0,
  };
  const orchestratorResult = await orchestrate(mission, subtaskResults, adapter, {
    ...clawDefaults,
    ...config,
  });

  logger.info(
    {
      missionId: missionResult.missionId,
      status: orchestratorResult.status,
      iterations: orchestratorResult.iterations,
      decisions: orchestratorResult.decisions.map((d) => d.type),
    },
    'Orchestrator loop complete',
  );

  // Build updated mission result incorporating orchestrator outcomes
  const updatedMissionResult: MissionResult = {
    ...missionResult,
    // Update subtask results with any retried/reassigned data
    subtaskResults: subtaskResults.map((sr) => ({
      id: sr.subtaskId,
      agentId: sr.agentId,
      status: sr.status,
      result: sr.result,
      costUsd: sr.costUsd,
    })),
    totalCostUsd: missionResult.totalCostUsd + orchestratorResult.totalCostUsd,
    // Update status based on orchestrator outcome
    status: orchestratorResult.status === 'accepted' ? 'completed' : missionResult.status,
    // Enrich summary with orchestrator context
    summary: buildOrchestratorSummary(missionResult, orchestratorResult, subtaskResults),
  };

  return { orchestratorResult, updatedMissionResult };
}

// ── Summary builder ─────────────────────────────────────────────────

/** Strip HTML tags from agent output to prevent Telegram parse errors. */
function stripHtml(text: string): string {
  return text.replace(/<[^>]*>/g, '');
}

function buildOrchestratorSummary(
  original: MissionResult,
  result: OrchestratorResult,
  subtaskResults: SubtaskResult[],
): string {
  const parts: string[] = [];

  // Use the original mission summary as the base — it's already been assembled
  // by executeMission() from the first-pass subtask results. Agent output may
  // contain HTML/markdown that breaks Telegram's parse_mode=HTML, so strip tags.
  if (original.summary) {
    parts.push(stripHtml(original.summary));
  }

  // Orchestrator metadata (plain text — no HTML)
  const verdictSummary = Array.from(result.verdicts.entries())
    .map(([id, v]) => `${id.slice(0, 8)}: ${v.composite_score.toFixed(2)}`)
    .join(', ');

  parts.push(`\n[Orchestrator: ${result.status} after ${result.iterations} iteration(s) | Scores: ${verdictSummary}]`);

  if (result.escalationReason) {
    parts.push(`[Escalation: ${result.escalationReason}]`);
  }

  if (result.decisions.length > 1) {
    const actions = result.decisions
      .filter((d) => d.type !== 'accept')
      .map((d) => `${d.type}: ${d.reasoning.slice(0, 80)}`)
      .join('; ');
    if (actions) {
      parts.push(`[Actions taken: ${actions}]`);
    }
  }

  return parts.join('\n');
}
