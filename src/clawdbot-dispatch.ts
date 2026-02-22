import http from 'http';

import { readEnvFile } from './env.js';
import { logger } from './logger.js';

export interface DispatchResult {
  ok: boolean;
  runId?: string;
  error?: string;
}

const CLAWDBOT_GATEWAY_URL = 'http://127.0.0.1:18789/hooks/agent';

/**
 * Dispatch a message to the Clawdbot HTTP gateway.
 *
 * Fire-and-forget for now: the result is delivered to the Chad bot chat,
 * not returned here. This function confirms the gateway accepted the request.
 */
export async function dispatchToClawdbot(
  message: string,
  agentId?: string,
): Promise<DispatchResult> {
  const env = readEnvFile(['CLAWDBOT_GATEWAY_TOKEN']);
  const token = env.CLAWDBOT_GATEWAY_TOKEN;

  const payload = JSON.stringify({
    message,
    ...(agentId ? { agent_id: agentId } : {}),
  });

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload).toString(),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return new Promise((resolve) => {
    const req = http.request(
      CLAWDBOT_GATEWAY_URL,
      { method: 'POST', headers },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const raw = Buffer.concat(chunks).toString('utf-8');
          if (res.statusCode && res.statusCode >= 400) {
            logger.error({ status: res.statusCode, body: raw.slice(0, 300) }, 'Clawdbot gateway error');
            resolve({ ok: false, error: `HTTP ${res.statusCode}` });
            return;
          }
          try {
            const data = JSON.parse(raw) as { run_id?: string };
            logger.info({ runId: data.run_id }, 'Dispatched to Clawdbot');
            resolve({ ok: true, runId: data.run_id });
          } catch {
            logger.info('Dispatched to Clawdbot (non-JSON response)');
            resolve({ ok: true });
          }
        });
        res.on('error', (err) => {
          logger.error({ err }, 'Clawdbot gateway response error');
          resolve({ ok: false, error: err.message });
        });
      },
    );

    req.on('error', (err) => {
      logger.error({ err }, 'Clawdbot gateway connection error');
      resolve({ ok: false, error: err.message });
    });

    req.write(payload);
    req.end();
  });
}
