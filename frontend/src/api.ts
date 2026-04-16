export type CheckType =
  | 'model_llm_chat'
  | 'model_llm_completion'
  | 'model_vision_chat'
  | 'model_embedding'
  | 'model_rerank'
  | 'model_audio_transcription'
  | 'model_audio_translation'
  | 'model_audio_speech'
  | 'model_image_generation'
  | 'model_image_edit'
  | 'model_moderation'
  | 'model_custom_http'
  | 'http_health'
  | 'http_content_ai';

export interface CheckState {
  status: string;
  consecutive_failures: number;
  last_success_at?: string;
  last_failure_at?: string;
  last_run_id?: number;
  alert_open: boolean;
  last_alert_at?: string;
}

export interface Check {
  id: number;
  name: string;
  type: CheckType;
  enabled: boolean;
  interval_seconds: number;
  timeout_seconds: number;
  failure_threshold: number;
  new_api_instance_id?: number | null;
  model_name?: string | null;
  request_config: Record<string, unknown>;
  validation_config: Record<string, unknown>;
  ai_config: Record<string, unknown>;
  state?: CheckState;
}

export interface CheckRun {
  id: number;
  check_id: number;
  status: string;
  duration_ms: number;
  response_status_code?: number;
  response_summary?: string;
  error?: string;
  ai_result: Record<string, unknown>;
  created_at: string;
}

export interface ModelRule {
  id: number;
  name: string;
  pattern: string;
  match_type: 'glob' | 'regex' | 'exact';
  check_type: CheckType;
  enabled: boolean;
  priority: number;
  request_config: Record<string, unknown>;
  validation_config: Record<string, unknown>;
}

export interface NewApiModel {
  id: number;
  instance_id?: number | null;
  instance_name?: string | null;
  model_id: string;
  category: string;
  check_type?: string;
  matched_rule_id?: number;
  check_id?: number;
  last_seen_at: string;
}

export interface NewApiInstance {
  id: number;
  name: string;
  base_url: string;
  enabled: boolean;
  is_default: boolean;
  description?: string | null;
  api_key_configured: boolean;
  created_at: string;
  updated_at: string;
}

export interface AlertChannel {
  id: number;
  name: string;
  enabled: boolean;
  webhook_url: string;
  secret?: string | null;
  headers: Record<string, unknown>;
  cooldown_minutes: number;
}

export interface DashboardSummary {
  total_checks: number;
  enabled_checks: number;
  healthy_checks: number;
  failing_checks: number;
  unknown_checks: number;
  availability: number;
  model_total: number;
  model_unmatched: number;
  recent_runs: CheckRun[];
  recent_alerts: Array<Record<string, unknown>>;
}

export interface SampleAsset {
  id: number;
  logical_name: string;
  version: number;
  filename: string;
  content_type?: string;
  file_path: string;
  size_bytes: number;
  description?: string;
  sample_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EvaluatorPrompt {
  id: number;
  name: string;
  version: number;
  active: boolean;
  prompt_template: string;
  output_schema: Record<string, unknown>;
}

export interface GoldenSet {
  id: number;
  name: string;
  description?: string;
  new_api_instance_id?: number | null;
  model_name: string;
  check_type: CheckType;
  enabled: boolean;
  evaluator_prompt_id?: number | null;
  evaluator_config: Record<string, unknown>;
  cases?: GoldenCase[];
}

export interface GoldenCase {
  id: number;
  golden_set_id: number;
  name: string;
  enabled: boolean;
  sample_asset_id?: number | null;
  input_config: Record<string, unknown>;
  expected_config: Record<string, unknown>;
}

export interface GoldenRun {
  id: number;
  golden_set_id: number;
  case_id: number;
  status: string;
  duration_ms: number;
  response_summary?: string;
  error?: string;
  score?: number;
  confidence?: number;
  rule_result: Record<string, unknown>;
  ai_result: Record<string, unknown>;
  created_at: string;
}

export interface TrendSummary {
  windows: Record<string, {
    label: string;
    total: number;
    success: number;
    failure: number;
    availability: number;
    error_rate: number;
    p50_ms?: number;
    p90_ms?: number;
    p95_ms?: number;
    p99_ms?: number;
  }>;
  current_failures: Array<Record<string, unknown>>;
  golden: {
    total: number;
    success: number;
    failure: number;
    pass_rate: number;
  };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('ai-eye-token');
  const headers = new Headers(options.headers);
  headers.set('Content-Type', headers.get('Content-Type') || 'application/json');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    localStorage.removeItem('ai-eye-token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function uploadRequest<T>(path: string, formData: FormData): Promise<T> {
  const token = localStorage.getItem('ai-eye-token');
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(path, { method: 'POST', headers, body: formData });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    }),
  summary: () => request<DashboardSummary>('/api/dashboard/summary'),
  checks: () => request<Check[]>('/api/checks'),
  createCheck: (payload: Partial<Check>) => request<Check>('/api/checks', { method: 'POST', body: JSON.stringify(payload) }),
  updateCheck: (id: number, payload: Partial<Check>) =>
    request<Check>(`/api/checks/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteCheck: (id: number) => request<void>(`/api/checks/${id}`, { method: 'DELETE' }),
  runCheck: (id: number) => request<CheckRun>(`/api/checks/${id}/run`, { method: 'POST' }),
  runs: (id: number) => request<CheckRun[]>(`/api/checks/${id}/runs`),
  allRuns: (params: { check_id?: number | null; status?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params.check_id) query.set('check_id', String(params.check_id));
    if (params.status) query.set('status', params.status);
    if (params.limit) query.set('limit', String(params.limit));
    return request<CheckRun[]>(`/api/runs?${query.toString()}`);
  },
  instances: () => request<NewApiInstance[]>('/api/new-api/instances'),
  createInstance: (payload: Partial<NewApiInstance> & { api_key?: string | null }) =>
    request<NewApiInstance>('/api/new-api/instances', { method: 'POST', body: JSON.stringify(payload) }),
  updateInstance: (id: number, payload: Partial<NewApiInstance> & { api_key?: string | null }) =>
    request<NewApiInstance>(`/api/new-api/instances/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteInstance: (id: number) => request<void>(`/api/new-api/instances/${id}`, { method: 'DELETE' }),
  setDefaultInstance: (id: number) => request<NewApiInstance>(`/api/new-api/instances/${id}/default`, { method: 'POST' }),
  testInstance: (id: number) => request(`/api/new-api/instances/${id}/test`, { method: 'POST' }),
  models: (params: { instance_id?: number | null } = {}) => {
    const query = new URLSearchParams();
    if (params.instance_id) query.set('instance_id', String(params.instance_id));
    return request<NewApiModel[]>(`/api/new-api/models${query.toString() ? `?${query.toString()}` : ''}`);
  },
  syncModels: (instanceId?: number | null) =>
    request<NewApiModel[]>(`/api/new-api/models/sync${instanceId ? `?instance_id=${instanceId}` : ''}`, { method: 'POST' }),
  syncAllModels: () => request<NewApiModel[]>('/api/new-api/models/sync-all', { method: 'POST' }),
  rules: () => request<ModelRule[]>('/api/model-rules'),
  createRule: (payload: Partial<ModelRule>) =>
    request<ModelRule>('/api/model-rules', { method: 'POST', body: JSON.stringify(payload) }),
  updateRule: (id: number, payload: Partial<ModelRule>) =>
    request<ModelRule>(`/api/model-rules/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteRule: (id: number) => request<void>(`/api/model-rules/${id}`, { method: 'DELETE' }),
  channels: () => request<AlertChannel[]>('/api/alert-channels'),
  createChannel: (payload: Partial<AlertChannel>) =>
    request<AlertChannel>('/api/alert-channels', { method: 'POST', body: JSON.stringify(payload) }),
  updateChannel: (id: number, payload: Partial<AlertChannel>) =>
    request<AlertChannel>(`/api/alert-channels/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteChannel: (id: number) => request<void>(`/api/alert-channels/${id}`, { method: 'DELETE' }),
  testChannel: (id: number) => request(`/api/alert-channels/${id}/test`, { method: 'POST' }),
  testDailyReport: () => request('/api/alert-channels/daily-report/test', { method: 'POST' }),
  settings: () => request<Record<string, unknown>>('/api/settings'),
  updateSettings: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>('/api/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  trends: () => request<TrendSummary>('/api/analytics/trends'),
  samples: () => request<SampleAsset[]>('/api/samples'),
  uploadSample: (payload: { file: File; logical_name: string; description?: string }) => {
    const formData = new FormData();
    formData.append('file', payload.file);
    formData.append('logical_name', payload.logical_name);
    if (payload.description) formData.append('description', payload.description);
    return uploadRequest<SampleAsset>('/api/samples', formData);
  },
  evaluatorPrompts: () => request<EvaluatorPrompt[]>('/api/evaluator-prompts'),
  createEvaluatorPrompt: (payload: Partial<EvaluatorPrompt>) =>
    request<EvaluatorPrompt>('/api/evaluator-prompts', { method: 'POST', body: JSON.stringify(payload) }),
  updateEvaluatorPrompt: (id: number, payload: Partial<EvaluatorPrompt>) =>
    request<EvaluatorPrompt>(`/api/evaluator-prompts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  goldenSets: () => request<GoldenSet[]>('/api/golden-sets'),
  goldenSet: (id: number) => request<GoldenSet>(`/api/golden-sets/${id}`),
  createGoldenSet: (payload: Partial<GoldenSet>) =>
    request<GoldenSet>('/api/golden-sets', { method: 'POST', body: JSON.stringify(payload) }),
  updateGoldenSet: (id: number, payload: Partial<GoldenSet>) =>
    request<GoldenSet>(`/api/golden-sets/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteGoldenSet: (id: number) => request<void>(`/api/golden-sets/${id}`, { method: 'DELETE' }),
  createGoldenCase: (setId: number, payload: Partial<GoldenCase>) =>
    request<GoldenCase>(`/api/golden-sets/${setId}/cases`, { method: 'POST', body: JSON.stringify(payload) }),
  updateGoldenCase: (setId: number, caseId: number, payload: Partial<GoldenCase>) =>
    request<GoldenCase>(`/api/golden-sets/${setId}/cases/${caseId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteGoldenCase: (setId: number, caseId: number) =>
    request<void>(`/api/golden-sets/${setId}/cases/${caseId}`, { method: 'DELETE' }),
  runGoldenSet: (setId: number) => request<GoldenRun[]>(`/api/golden-sets/${setId}/run`, { method: 'POST' }),
  goldenRuns: (setId: number) => request<GoldenRun[]>(`/api/golden-sets/${setId}/runs`)
};

export function parseJsonObject(text: string): Record<string, unknown> {
  if (!text.trim()) {
    return {};
  }
  const parsed = JSON.parse(text);
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('JSON 必须是对象');
  }
  return parsed as Record<string, unknown>;
}

export function statusType(status?: string): 'success' | 'danger' | 'warning' | 'info' {
  if (status === 'success') return 'success';
  if (status === 'failure') return 'danger';
  if (status === 'unknown' || !status) return 'info';
  return 'warning';
}
