import fs from 'fs';
import path from 'path';

import { STORE_DIR } from './config.js';

const TELEMETRY_FILE = path.join(STORE_DIR, 'telemetry.jsonl');

/**
 * Telemetry event types emitted by Data (ClaudeClaw).
 * Each event is a single JSONL line appended to store/telemetry.jsonl.
 *
 * Consumers: Sky-Lynx (weekly analysis), ST Factory (optional import).
 */
export type TelemetryEvent =
  | MessageReceivedEvent
  | MessageRoutedEvent
  | AgentCompletedEvent
  | ToolUsedEvent
  | ScheduledTaskExecutedEvent
  | ScheduledTaskDispatchedEvent
  | TaskDispatchedEvent
  | DispatchTaskCompletedEvent
  | ErrorEvent;

interface BaseEvent {
  timestamp: string; // ISO 8601
  event_type: string;
  chat_id?: string;
}

export interface MessageReceivedEvent extends BaseEvent {
  event_type: 'message_received';
  message_type: 'text' | 'voice' | 'photo' | 'document' | 'video' | 'video_note';
  message_length: number;
}

export interface MessageRoutedEvent extends BaseEvent {
  event_type: 'message_routed';
  backend: string;
  message_length: number;
}

export interface AgentCompletedEvent extends BaseEvent {
  event_type: 'agent_completed';
  backend: string;
  latency_ms: number;
  success: boolean;
  response_length: number;
  session_id?: string;
}

export interface ToolUsedEvent extends BaseEvent {
  event_type: 'tool_used';
  tool_name: string;
  tool_summary?: string;
}

export interface ScheduledTaskExecutedEvent extends BaseEvent {
  event_type: 'scheduled_task_executed';
  task_id: string;
  prompt_preview: string;
  success: boolean;
  latency_ms: number;
}

export interface ScheduledTaskDispatchedEvent extends BaseEvent {
  event_type: 'scheduled_task_dispatched';
  task_id: string;
  dispatch_id: string;
  worker_type: string;
  prompt_preview: string;
}

export interface TaskDispatchedEvent extends BaseEvent {
  event_type: 'task_dispatched';
  task_id: string;
  worker_type: string;
}

export interface DispatchTaskCompletedEvent extends BaseEvent {
  event_type: 'dispatch_task_completed';
  task_id: string;
  worker_type: string;
  success: boolean;
  latency_ms: number;
}

export interface ErrorEvent extends BaseEvent {
  event_type: 'error';
  error_source: string;
  error_message: string;
}

/**
 * Append a telemetry event as a single JSONL line.
 * Fire-and-forget: never throws, never blocks the main flow.
 */
export function emit(event: TelemetryEvent): void {
  try {
    const line = JSON.stringify(event) + '\n';
    fs.appendFileSync(TELEMETRY_FILE, line, 'utf-8');
  } catch {
    // Telemetry is best-effort. Never crash the bot for logging.
  }
}

/** Ensure the store directory exists (called once at startup). */
export function initTelemetry(): void {
  try {
    fs.mkdirSync(path.dirname(TELEMETRY_FILE), { recursive: true });
  } catch {
    // Best-effort
  }
}
