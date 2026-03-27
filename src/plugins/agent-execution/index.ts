/**
 * Agent Execution Plugin — entry point.
 *
 * Re-exports all public types and functions for use by mission-control.ts
 * and agent-config.ts.
 */

export { parseExecutionConfig } from './config-parser.js';
export { executeWithEngine } from './executor.js';
export type {
  ExecutionConfig,
  ExecutionMode,
  ExecutorRequest,
  ExecutorResult,
  McpServerEntry,
} from './types.js';
