export interface ClawConfig {
  dbPath: string;
  ollamaBaseUrl: string;
  embeddingModel: string;
  embeddingDims: number;
  logLevel: string;
}

let config: ClawConfig | null = null;

export function getConfig(): ClawConfig {
  if (config) return config;

  config = {
    dbPath: process.env.CLAW_DB_PATH ?? '/home/apexaipc/projects/claudeclaw/store/claudeclaw.db',
    ollamaBaseUrl: process.env.OLLAMA_BASE_URL ?? 'http://127.0.0.1:11434',
    embeddingModel: process.env.EMBEDDING_MODEL ?? 'nomic-embed-text',
    embeddingDims: 768,
    logLevel: process.env.LOG_LEVEL ?? 'info',
  };

  return config;
}

export function resetConfig(): void {
  config = null;
}
