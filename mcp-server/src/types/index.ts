export type MemoryCategory =
  | 'decision'
  | 'preference'
  | 'project_state'
  | 'action_item'
  | 'technical_detail'
  | 'person_info'
  | 'insight';

export interface MemoryRow {
  id: number;
  chat_id: string;
  topic_key: string | null;
  content: string;
  sector: string;
  salience: number;
  created_at: number;
  accessed_at: number;
}

export interface MemoryVectorRow {
  id: number;
  chat_id: string;
  content: string;
  source_type: string;
  embedding: Buffer;
  salience: number;
  created_at: number;
  accessed_at: number;
  source_log_ids: string | null;
  category: MemoryCategory | null;
  tags: string | null;
  people: string | null;
  is_action_item: number;
  confidence: number;
}

export interface ToolResult {
  [key: string]: unknown;
  content: Array<{ type: 'text'; text: string }>;
  isError?: boolean;
}
