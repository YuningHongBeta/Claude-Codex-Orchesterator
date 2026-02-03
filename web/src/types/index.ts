export type JobStage =
  | 'initialized'
  | 'rewriter'
  | 'rewriter_done'
  | 'conductor'
  | 'conductor_done'
  | 'performer'
  | 'performer_done'
  | 'mix'
  | 'mix_done'
  | 'done'
  | 'error'
  | 'killed'
  | 'token_warning'
  | 'stalled';

export interface Job {
  id: string;
  task: string;
  stage: JobStage;
  progress: number;
  running: boolean;
  started_at?: string;
  updated_at: string;
  run_dir?: string;
  error?: string;
  final_text?: string;
  // Performer tracking
  performer_index?: number;
  performer_total?: number;
  performer_name?: string;
  // Log tracking / stall detection
  last_log_update?: string;
  seconds_since_log_update?: number;
  stalled?: boolean;
}

export interface Performer {
  name: string;
  task: string;
  notes?: string;
}

export interface ExchangeHistoryItem {
  role: string;
  type?: string;
  content: string;
  timestamp?: string;
}

export interface ExchangePending {
  type?: 'ok_ng' | 'choice' | 'free_text';
  question?: string;
  options?: string[];
  ok_reply?: string;
  ng_reply?: string;
  choice_reply_template?: string;
  reason?: string;
  suggested_reply?: string;
  user_reply?: string;
  user_approved?: boolean;
  user_choice?: string;
}

export interface ExchangeSummary {
  id: string;
  filename: string;
  status?: string;
  updated_at?: string;
  performer?: Performer;
  pending?: ExchangePending;
}

export interface ExchangeDetail {
  performer?: Performer;
  status?: string;
  turn?: number;
  history?: ExchangeHistoryItem[];
  pending?: ExchangePending;
  updated_at?: string;
}

export interface Score {
  title?: string;
  performers: Performer[];
  refined_task?: string;
  global_notes?: string;
}

export interface LogFile {
  filename: string;
  stage: string;
  type: 'stdout' | 'stderr';
  size: number;
}

export interface ApiConfig {
  baseUrl: string;
  token?: string;
}

export interface CommandConfig {
  cmd: string[];
  timeout_sec?: number;
}

export interface TokenManagement {
  max_tokens: number;
  warning_threshold: number;
  compact_threshold: number;
  max_compact_attempts: number;
}

export interface CliTokenStatus {
  available: boolean;
  raw_output: string;
  error: string | null;
  used_percentage?: number | null;
  short_term_percentage?: number | null;
  weekly_percentage?: number | null;
  rate_limit_5h?: string | null;
  weekly_token_limit?: string | null;
  // Claude Code specific stats from stats-cache.json
  daily_tokens?: number | null;
  weekly_tokens?: number | null;
  total_tokens?: number | null;
}

export interface TokenStatusResponse {
  claude: CliTokenStatus;
  codex: CliTokenStatus;
}

export interface ClaudePermissions {
  mode?: 'default' | 'bypassPermissions' | 'acceptEdits' | 'dontAsk';
  add_dirs?: string[];
}

export interface CodexPermissions {
  sandbox?: 'read-only' | 'workspace-write' | 'danger-full-access';
  approval?: 'untrusted' | 'on-failure' | 'on-request' | 'never';
  add_dirs?: string[];
}

export interface Permissions {
  claude?: ClaudePermissions;
  codex?: CodexPermissions;
}

export interface OrchestratorConfig {
  language?: string;
  instrument_pool?: string[];
  permissions?: Permissions;
  rewriter?: CommandConfig;
  concertmaster?: CommandConfig;
  performer?: CommandConfig;
  max_turns_performer?: number;
  mix_with_conductor?: boolean;
  token_management?: TokenManagement;
  stall_timeout_sec?: number;
  stall_error_timeout_sec?: number;
}
