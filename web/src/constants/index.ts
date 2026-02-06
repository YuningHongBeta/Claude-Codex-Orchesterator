import type { JobStage } from '../types';

export const STAGE_LABELS: Record<JobStage | 'pending', string> = {
  pending: '待機中',
  initialized: '初期化中',
  rewriter: '指揮者が言い直し中',
  rewriter_done: '言い直し完了',
  advisor: 'アドバイザーレビュー中',
  advisor_done: 'レビュー完了',
  conductor: '指揮者が分担中',
  conductor_done: '分担完了',
  pre_review: '実行前レビュー中',
  post_review: '実行後レビュー中',
  performer: '演奏中',
  performer_done: '演奏完了',
  mix: '統合中',
  mix_done: '統合完了',
  done: '完了',
  error: 'エラー',
  killed: '強制終了',
  token_warning: 'トークン警告',
  stalled: '停滞（途中停止）',
};

export const STAGE_ICONS: Record<JobStage | 'pending', string> = {
  pending: '⏳',
  initialized: '🔄',
  rewriter: '✍️',
  rewriter_done: '✅',
  advisor: '🔍',
  advisor_done: '✅',
  conductor: '🎭',
  conductor_done: '✅',
  pre_review: '🛡️',
  post_review: '📋',
  performer: '🎵',
  performer_done: '✅',
  mix: '🎛️',
  mix_done: '✅',
  done: '🎉',
  error: '❌',
  killed: '🛑',
  token_warning: '⚠️',
  stalled: '⏸️',
};

export const API_CONFIG = {
  baseUrl: (window as unknown as { ORCHESTRATOR_API_BASE?: string }).ORCHESTRATOR_API_BASE || '',
  token: (window as unknown as { ORCHESTRATOR_API_TOKEN?: string }).ORCHESTRATOR_API_TOKEN || '',
};

export const AUTH_CONFIG = {
  enabled: Boolean((window as unknown as { ORCHESTRATOR_LOGIN_ENABLED?: boolean }).ORCHESTRATOR_LOGIN_ENABLED),
  user: (window as unknown as { ORCHESTRATOR_LOGIN_USER?: string }).ORCHESTRATOR_LOGIN_USER || '',
  pass: (window as unknown as { ORCHESTRATOR_LOGIN_PASS?: string }).ORCHESTRATOR_LOGIN_PASS || '',
  passHash: (window as unknown as { ORCHESTRATOR_LOGIN_PASS_SHA256?: string }).ORCHESTRATOR_LOGIN_PASS_SHA256 || '',
};

export const AUTH_STORAGE_KEY = 'orchestrator:auth';

export const REFRESH_INTERVAL = 10000;
