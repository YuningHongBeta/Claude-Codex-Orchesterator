import { API_CONFIG } from '../constants';
import type { Job, Score, LogFile, ExchangeSummary, ExchangeDetail, OrchestratorConfig, TokenStatusResponse } from '../types';

function getApiUrl(path: string): string {
  const base = API_CONFIG.baseUrl.replace(/\/$/, '');
  return path.startsWith('/') ? `${base}${path}` : `${base}/${path}`;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string>),
  };

  if (API_CONFIG.token) {
    headers['X-Orchestrator-Token'] = API_CONFIG.token;
  }

  const response = await fetch(getApiUrl(path), {
    cache: 'no-store',
    ...options,
    headers,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
}

async function apiFetchText(path: string): Promise<string> {
  const headers: Record<string, string> = {};
  if (API_CONFIG.token) {
    headers['X-Orchestrator-Token'] = API_CONFIG.token;
  }

  const response = await fetch(getApiUrl(path), { headers, cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  return response.text();
}

export async function fetchJobs(): Promise<Job[]> {
  return apiFetch<Job[]>('/api/jobs');
}

export async function fetchJob(id: string, includeOutput = false): Promise<Job> {
  const query = includeOutput ? '?include_output=1' : '';
  return apiFetch<Job>(`/api/jobs/${id}${query}`);
}

export async function createJob(task: string, expertReview?: boolean): Promise<Job> {
  const payload: Record<string, unknown> = { task };
  if (expertReview !== undefined) {
    payload.expert_review = expertReview;
  }
  return apiFetch<Job>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function fetchScore(id: string): Promise<Score | null> {
  try {
    return await apiFetch<Score>(`/api/jobs/${id}/score`);
  } catch {
    return null;
  }
}

export async function fetchLogs(id: string): Promise<LogFile[]> {
  try {
    return await apiFetch<LogFile[]>(`/api/jobs/${id}/logs`);
  } catch {
    return [];
  }
}

export async function fetchLogContent(id: string, filename: string): Promise<string> {
  return apiFetchText(`/api/jobs/${id}/logs/${filename}`);
}

export async function fetchExchanges(id: string): Promise<ExchangeSummary[]> {
  try {
    return await apiFetch<ExchangeSummary[]>(`/api/jobs/${id}/exchanges`);
  } catch {
    return [];
  }
}

export async function fetchExchange(id: string, exchangeId: string): Promise<ExchangeDetail | null> {
  try {
    return await apiFetch<ExchangeDetail>(`/api/jobs/${id}/exchanges/${exchangeId}`);
  } catch {
    return null;
  }
}

export async function postExchangeReply(
  id: string,
  exchangeId: string,
  payload: { reply?: string; approved?: boolean; decision?: 'ok' | 'ng'; choice?: string }
): Promise<boolean> {
  try {
    await apiFetch(`/api/jobs/${id}/exchanges/${exchangeId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return true;
  } catch {
    return false;
  }
}

export async function fetchConfig(): Promise<OrchestratorConfig> {
  return apiFetch<OrchestratorConfig>('/api/config');
}

export async function updateConfig(config: OrchestratorConfig): Promise<{ ok: boolean; config: OrchestratorConfig }> {
  return apiFetch<{ ok: boolean; config: OrchestratorConfig }>('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
}

export async function killJob(id: string): Promise<{ ok: boolean; message?: string; error?: string }> {
  return apiFetch<{ ok: boolean; message?: string; error?: string }>(`/api/jobs/${id}/kill`, {
    method: 'POST',
  });
}

export async function fetchTokenStatus(): Promise<TokenStatusResponse> {
  return apiFetch<TokenStatusResponse>('/api/token-status');
}
