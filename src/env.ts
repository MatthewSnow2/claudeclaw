import fs from 'fs';
import os from 'os';
import path from 'path';

/**
 * Parse an env file and extract values for the requested keys.
 * Does NOT load anything into process.env.
 */
function parseEnv(filePath: string, keys: Set<string>): Record<string, string> {
  let content: string;
  try {
    content = fs.readFileSync(filePath, 'utf-8');
  } catch {
    return {};
  }

  const result: Record<string, string> = {};

  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    if (!keys.has(key)) continue;
    let value = trimmed.slice(eqIdx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) result[key] = value;
  }

  return result;
}

/**
 * Read values for the requested keys from the local .env file,
 * falling back to ~/.env.telegram then ~/.env.shared for any keys not found.
 *
 * Does NOT load anything into process.env — callers decide what to
 * do with the values. This keeps secrets out of the process environment
 * so they don't leak to child processes.
 *
 * Load order (first found wins):
 *   1. Local .env (project-specific overrides)
 *   2. ~/.env.telegram (isolated Telegram credentials — not in project dir)
 *   3. ~/.env.shared (shared secrets fallback)
 */
export function readEnvFile(keys: string[]): Record<string, string> {
  const wanted = new Set(keys);

  // 1. Local .env (project-specific overrides)
  const localFile = path.join(process.cwd(), '.env');
  const local = parseEnv(localFile, wanted);

  // 2. ~/.env.telegram (Telegram creds isolated from project directory)
  const missingAfterLocal = new Set(keys.filter((k) => !local[k]));
  let telegram: Record<string, string> = {};
  if (missingAfterLocal.size > 0) {
    const telegramFile = path.join(os.homedir(), '.env.telegram');
    telegram = parseEnv(telegramFile, missingAfterLocal);
  }

  // 3. ~/.env.shared (shared secrets fallback)
  const missingAfterTelegram = new Set(
    keys.filter((k) => !local[k] && !telegram[k]),
  );
  let shared: Record<string, string> = {};
  if (missingAfterTelegram.size > 0) {
    const sharedFile = path.join(os.homedir(), '.env.shared');
    shared = parseEnv(sharedFile, missingAfterTelegram);
  }

  return { ...shared, ...telegram, ...local };
}

/**
 * Read values from the LOCAL .env file only (no ~/.env.shared fallback).
 * Use this for auth overrides that should not be picked up from shared secrets
 * (e.g. ANTHROPIC_API_KEY which would override Max plan OAuth with API billing).
 */
export function readLocalEnvFile(keys: string[]): Record<string, string> {
  const localFile = path.join(process.cwd(), '.env');
  return parseEnv(localFile, new Set(keys));
}
