/**
 * Parses and validates the `execution:` block from agent.yaml.
 *
 * When absent, returns undefined (agent uses legacy prompt-inject path).
 * When present, validates all fields and applies sensible defaults.
 */

import type { ExecutionConfig, ExecutionMode, McpServerEntry } from './types.js';

const VALID_MODES: ExecutionMode[] = ['agent-sdk', 'prompt-inject'];

const DEFAULT_TOOLS = ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash'];
const DEFAULT_MAX_TURNS = 25;
const DEFAULT_TIMEOUT = 900_000; // 15 minutes
const MIN_TIMEOUT = 60_000;      // 1 minute floor

/**
 * Parse the `execution` block from a raw agent.yaml object.
 * Returns undefined if no execution block is present.
 * Throws on invalid configuration.
 */
export function parseExecutionConfig(
  raw: Record<string, unknown>,
  agentId: string,
): ExecutionConfig | undefined {
  const execRaw = raw['execution'] as Record<string, unknown> | undefined;
  if (!execRaw) return undefined;

  // Mode (required when execution block is present)
  const mode = execRaw['mode'] as string;
  if (!mode || !VALID_MODES.includes(mode as ExecutionMode)) {
    throw new Error(
      `[${agentId}] execution.mode must be one of: ${VALID_MODES.join(', ')}. Got: ${mode}`,
    );
  }

  // Tools
  const rawTools = execRaw['tools'] as string[] | undefined;
  if (rawTools && !Array.isArray(rawTools)) {
    throw new Error(`[${agentId}] execution.tools must be a string array`);
  }
  const tools = rawTools ?? DEFAULT_TOOLS;

  // MCP servers
  const mcpServers = parseMcpServers(execRaw['mcpServers'], agentId);

  // canSpawnSubAgents
  const canSpawnSubAgents = execRaw['canSpawnSubAgents'] === true;

  // maxTurns
  let maxTurns = DEFAULT_MAX_TURNS;
  if (execRaw['maxTurns'] !== undefined) {
    maxTurns = Math.max(1, Math.floor(Number(execRaw['maxTurns'])));
    if (isNaN(maxTurns)) maxTurns = DEFAULT_MAX_TURNS;
  }

  // timeout
  let timeout = DEFAULT_TIMEOUT;
  if (execRaw['timeout'] !== undefined) {
    timeout = Math.max(MIN_TIMEOUT, Math.floor(Number(execRaw['timeout'])));
    if (isNaN(timeout)) timeout = DEFAULT_TIMEOUT;
  }

  return {
    mode: mode as ExecutionMode,
    tools,
    mcpServers,
    canSpawnSubAgents,
    maxTurns,
    timeout,
  };
}

function parseMcpServers(
  raw: unknown,
  agentId: string,
): Record<string, McpServerEntry> {
  if (!raw) return {};

  if (typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error(
      `[${agentId}] execution.mcpServers must be an object mapping server names to configs`,
    );
  }

  const result: Record<string, McpServerEntry> = {};
  for (const [name, value] of Object.entries(raw as Record<string, unknown>)) {
    const entry = value as Record<string, unknown>;
    if (!entry['command'] || typeof entry['command'] !== 'string') {
      throw new Error(`[${agentId}] execution.mcpServers.${name} must have a 'command' string`);
    }

    // Resolve ${VAR} references in env values
    const rawEnv = (entry['env'] as Record<string, string>) ?? {};
    const resolvedEnv: Record<string, string> = {};
    for (const [k, v] of Object.entries(rawEnv)) {
      resolvedEnv[k] = resolveEnvVar(v);
    }

    result[name] = {
      command: entry['command'] as string,
      args: (entry['args'] as string[]) ?? [],
      ...(Object.keys(resolvedEnv).length > 0 ? { env: resolvedEnv } : {}),
    };
  }

  return result;
}

/** Resolve ${VAR_NAME} references against process.env. */
function resolveEnvVar(value: string): string {
  return value.replace(/\$\{(\w+)\}/g, (_match, varName: string) => {
    return process.env[varName] ?? '';
  });
}
