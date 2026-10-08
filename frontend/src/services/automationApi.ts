import { apiFetch, apiUrl, getAccessToken } from './api';

const root = '/api/v1/automations';

export type SavedAnalyticsQuery = {
  id: string;
  title: string;
  question: string;
  dataset_id: string;
  config: { operation: string; column?: string; group_by?: string; limit?: number };
};

export type AnalyticsAutomation = {
  id: string;
  workspace_id: string;
  dataset_id: string;
  saved_query_id: string;
  name: string;
  frequency: 'daily' | 'weekly' | 'monthly';
  run_time: string;
  weekday: number;
  day_of_month: number;
  timezone: string;
  active: boolean;
  next_run_at: string;
  last_run_at?: string | null;
  last_status?: string | null;
  ai_summary: boolean;
};

export type AutomationRun = {
  id: string;
  status: string;
  error_code?: string | null;
  created_at: string;
  result?: {
    metrics?: unknown;
    profile?: { rows: number; columns: number };
    changes?: { schema_changed?: boolean; row_delta?: number | null };
    alerts_triggered?: Array<{ name: string; metric: string; value: number }>;
    ai_summary?: string;
  };
};

export type AnalyticsAlert = {
  id: string;
  name: string;
  dataset_id: string;
  metric: string;
  operator: string;
  threshold: number;
  active: boolean;
  cooldown_seconds: number;
};

export type AutomationAdminOverview = {
  total_automations: number;
  active_automations: number;
  successful_runs: number;
  failed_runs: number;
  average_execution_time_ms: number;
};

export type AutomationAdminRun = {
  id: string;
  automation_id: string;
  automation_name: string;
  workspace_id: string;
  dataset_id: string;
  status: string;
  attempt: number;
  error_code?: string | null;
  execution_time_ms?: number | null;
  created_at: string;
};

export const listSavedQueries = (workspaceId: string) =>
  apiFetch<SavedAnalyticsQuery[]>(`${root}/queries?workspace_id=${encodeURIComponent(workspaceId)}`);

export const createSavedQuery = (payload: {
  workspace_id: string; dataset_id: string; title: string; question: string;
  config: SavedAnalyticsQuery['config'];
}) => apiFetch<SavedAnalyticsQuery>(`${root}/queries`, { method: 'POST', body: JSON.stringify(payload) });

export const listAutomations = (workspaceId: string) =>
  apiFetch<AnalyticsAutomation[]>(`${root}?workspace_id=${encodeURIComponent(workspaceId)}`);

export const createAutomation = (payload: {
  workspace_id: string; saved_query_id: string; name: string;
  frequency: AnalyticsAutomation['frequency']; run_time: string; timezone: string;
  weekday: number; day_of_month: number; ai_summary: boolean;
}) => apiFetch<AnalyticsAutomation>(root, { method: 'POST', body: JSON.stringify(payload) });

export const updateAutomation = (id: string, workspaceId: string, update: {
  active?: boolean; saved_query_id?: string; name?: string;
  frequency?: AnalyticsAutomation['frequency']; run_time?: string; timezone?: string;
  weekday?: number; day_of_month?: number; ai_summary?: boolean;
}) =>
  apiFetch<AnalyticsAutomation>(`${root}/${encodeURIComponent(id)}?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH', body: JSON.stringify({ workspace_id: workspaceId, ...update }),
  });

export const deleteAutomation = (id: string, workspaceId: string) =>
  apiFetch<{ deleted: boolean }>(`${root}/${encodeURIComponent(id)}?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'DELETE' });

export const runAutomation = (id: string, workspaceId: string) =>
  apiFetch<AutomationRun>(`${root}/${encodeURIComponent(id)}/run?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST' });

export const listAutomationRuns = (id: string, workspaceId: string) =>
  apiFetch<AutomationRun[]>(`${root}/${encodeURIComponent(id)}/runs?workspace_id=${encodeURIComponent(workspaceId)}`);

export async function downloadRunReport(id: string, workspaceId: string, runId: string): Promise<void> {
  const token = getAccessToken();
  const response = await fetch(apiUrl(`${root}/${encodeURIComponent(id)}/runs/${encodeURIComponent(runId)}/report.csv?workspace_id=${encodeURIComponent(workspaceId)}`), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error('The CSV report is not available for this run.');
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `automation-${id}-run-${runId}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export const listAlerts = (workspaceId: string, datasetId?: string) => {
  const query = new URLSearchParams({ workspace_id: workspaceId });
  if (datasetId) query.set('dataset_id', datasetId);
  return apiFetch<AnalyticsAlert[]>(`${root}/alerts?${query.toString()}`);
};

export const createAlert = (payload: {
  workspace_id: string; dataset_id: string; name: string; alert_type: 'threshold' | 'anomaly';
  metric: string; operator: '>' | '<' | '>=' | '<=' | '=' | '!='; threshold: number; cooldown_seconds: number;
}) => apiFetch<AnalyticsAlert>(`${root}/alerts`, { method: 'POST', body: JSON.stringify(payload) });

export const updateAlert = (id: string, workspaceId: string, active: boolean) =>
  apiFetch<AnalyticsAlert>(`${root}/alerts/${encodeURIComponent(id)}?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH', body: JSON.stringify({ active }),
  });

export const deleteAlert = (id: string, workspaceId: string) =>
  apiFetch<{ deleted: boolean }>(`${root}/alerts/${encodeURIComponent(id)}?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'DELETE' });

export const getAutomationAdminOverview = () =>
  apiFetch<AutomationAdminOverview>(`${root}/admin/overview`);

export const getAutomationAdminRuns = (filters: { since?: string; status?: string; workspace_id?: string; limit?: number } = {}) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== '') query.set(key, String(value));
  return apiFetch<AutomationAdminRun[]>(`${root}/admin/runs?${query.toString()}`);
};