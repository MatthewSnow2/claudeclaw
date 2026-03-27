/**
 * Types for the agent execution plugin.
 *
 * Defines the execution config schema (parsed from agent.yaml `execution:` block)
 * and the executor request/result interfaces used by mission-control.ts.
 */

import type { UsageInfo } from '../../agent.js';

/** Execution mode for an agent. */
export type ExecutionMode = 'agent-sdk' | 'prompt-inject';

/** Parsed execution config from agent.yaml `execution:` block. */
export interface ExecutionConfig {
  mode: ExecutionMode;
  tools: string[];
  mcpServers: Record<string, McpServerEntry>;
  canSpawnSubAgents: boolean;
  maxTurns: number;
  timeout: number;
}

/** MCP server entry matching Agent SDK's expected format. */
export interface McpServerEntry {
  command: string;
  args: string[];
  env?: Record<string, string>;
}

/** Input to the execution engine. */
export interface ExecutorRequest {
  agentId: string;
  prompt: string;
  /** Agent's working directory. */
  cwd: string;
  /** CLAUDE.md content for the agent. */
  systemPrompt?: string;
  /** Model override from agent.yaml. */
  model?: string;
  /** Parsed execution config. */
  execution: ExecutionConfig;
  /** Abort controller for timeout/cancellation. */
  abortController?: AbortController;
  /** Progress callback for status updates. */
  onProgress?: (msg: string) => void;
}

/** Output from the execution engine. */
export interface ExecutorResult {
  text: string | null;
  usage: UsageInfo | null;
  aborted?: boolean;
  durationMs: number;
}
