import http from 'http';
import https from 'https';

import { readEnvFile } from './env.js';
import { logger } from './logger.js';

export interface LLMResponse {
  text: string;
  backend: string;
  model: string;
}

// ── Shared HTTP helper ──────────────────────────────────────────────────────

function jsonRequest(
  url: string,
  headers: Record<string, string>,
  body: object,
): Promise<string> {
  const payload = JSON.stringify(body);
  const isHttps = url.startsWith('https');
  const mod = isHttps ? https : http;

  return new Promise((resolve, reject) => {
    const req = mod.request(
      url,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload).toString(),
          ...headers,
        },
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (chunk: Buffer) => chunks.push(chunk));
        res.on('end', () => {
          const raw = Buffer.concat(chunks).toString('utf-8');
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${raw.slice(0, 500)}`));
            return;
          }
          resolve(raw);
        });
        res.on('error', reject);
      },
    );
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// ── Gemini ──────────────────────────────────────────────────────────────────

export async function callGemini(message: string): Promise<LLMResponse> {
  const env = readEnvFile(['GEMINI_API_KEY', 'GOOGLE_API_KEY']);
  const apiKey = env.GEMINI_API_KEY || env.GOOGLE_API_KEY;
  if (!apiKey) throw new Error('GEMINI_API_KEY not configured in .env or ~/.env.shared');

  const model = 'gemini-3-flash-preview';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const raw = await jsonRequest(url, {}, {
    contents: [{ parts: [{ text: message }] }],
  });

  const data = JSON.parse(raw) as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
  };

  const text = data.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
  if (!text) throw new Error('Gemini returned empty response');

  logger.info({ backend: 'gemini', model }, 'Gemini response received');
  return { text, backend: 'gemini', model };
}

// ── Perplexity ──────────────────────────────────────────────────────────────

export async function callPerplexity(message: string): Promise<LLMResponse> {
  const env = readEnvFile(['PERPLEXITY_API_KEY']);
  const apiKey = env.PERPLEXITY_API_KEY;
  if (!apiKey) throw new Error('PERPLEXITY_API_KEY not configured in .env or ~/.env.shared');

  const model = 'sonar';
  const raw = await jsonRequest(
    'https://api.perplexity.ai/chat/completions',
    { Authorization: `Bearer ${apiKey}` },
    {
      model,
      messages: [{ role: 'user', content: message }],
    },
  );

  const data = JSON.parse(raw) as {
    choices?: Array<{ message?: { content?: string } }>;
  };

  const text = data.choices?.[0]?.message?.content ?? '';
  if (!text) throw new Error('Perplexity returned empty response');

  logger.info({ backend: 'perplexity', model }, 'Perplexity response received');
  return { text, backend: 'perplexity', model };
}

// ── Ollama (local) ──────────────────────────────────────────────────────────

export async function callOllama(message: string): Promise<LLMResponse> {
  const model = 'qwen2.5:7b-instruct';
  const raw = await jsonRequest(
    'http://127.0.0.1:11434/api/chat',
    {},
    {
      model,
      messages: [{ role: 'user', content: message }],
      stream: false,
    },
  );

  const data = JSON.parse(raw) as {
    message?: { content?: string };
  };

  const text = data.message?.content ?? '';
  if (!text) throw new Error('Ollama returned empty response');

  logger.info({ backend: 'ollama', model }, 'Ollama response received');
  return { text, backend: 'ollama', model };
}

// ── OpenAI ──────────────────────────────────────────────────────────────────

export async function callOpenAI(message: string): Promise<LLMResponse> {
  const env = readEnvFile(['OPENAI_API_KEY']);
  const apiKey = env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY not configured in .env or ~/.env.shared');

  const model = 'gpt-4o';
  const raw = await jsonRequest(
    'https://api.openai.com/v1/chat/completions',
    { Authorization: `Bearer ${apiKey}` },
    {
      model,
      messages: [{ role: 'user', content: message }],
    },
  );

  const data = JSON.parse(raw) as {
    choices?: Array<{ message?: { content?: string } }>;
  };

  const text = data.choices?.[0]?.message?.content ?? '';
  if (!text) throw new Error('OpenAI returned empty response');

  logger.info({ backend: 'openai', model }, 'OpenAI response received');
  return { text, backend: 'openai', model };
}
