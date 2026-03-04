const LOG_LEVEL = process.env.LOG_LEVEL ?? 'info';

const LEVELS: Record<string, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const threshold = LEVELS[LOG_LEVEL] ?? 1;

function timestamp(): string {
  return new Date().toISOString();
}

/** All output goes to stderr -- stdout is reserved for MCP protocol messages. */
export const logger = {
  debug(msg: string, data?: unknown): void {
    if (threshold <= 0) {
      console.error(`[${timestamp()}] [CLAW-MCP] [DEBUG] ${msg}`, data !== undefined ? JSON.stringify(data) : '');
    }
  },
  info(msg: string, data?: unknown): void {
    if (threshold <= 1) {
      console.error(`[${timestamp()}] [CLAW-MCP] [INFO] ${msg}`, data !== undefined ? JSON.stringify(data) : '');
    }
  },
  warn(msg: string, data?: unknown): void {
    if (threshold <= 2) {
      console.error(`[${timestamp()}] [CLAW-MCP] [WARN] ${msg}`, data !== undefined ? JSON.stringify(data) : '');
    }
  },
  error(msg: string, data?: unknown): void {
    console.error(`[${timestamp()}] [CLAW-MCP] [ERROR] ${msg}`, data !== undefined ? JSON.stringify(data) : '');
  },
};
