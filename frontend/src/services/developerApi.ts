import { apiFetch } from './api';

// ── Types ───────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: string;
  user_id: string;
  workspace_id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  rotated_from_id: string | null;
}

export interface ApiKeyCreateResult extends ApiKey {
  api_key: string;
  notice: string;
}

export interface WebhookEndpoint {
  id: string;
  user_id: string;
  workspace_id: string;
  url: string;
  description: string | null;
  events: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
  last_delivery_at: string | null;
  failure_count: number;
}

export interface WebhookCreateResult extends WebhookEndpoint {
  secret: string;
  notice: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  workspace_id: string;
  event_id: string;
  event_type: string;
  status: string;
  response_code: number | null;
  duration_ms: number | null;
  attempt_count: number;
  created_at: string;
  completed_at: string | null;
  last_error_code: string | null;
}

export interface UsageSummary {
  request_count: number;
  error_count: number;
  average_response_time_ms: number;
}

// ── Available scopes and events ─────────────────────────────────────────────

export const API_SCOPES = [
  { value: 'datasets:read', label: 'Datasets — Read', description: 'List and view dataset metadata' },
  { value: 'datasets:write', label: 'Datasets — Write', description: 'Upload and manage datasets' },
  { value: 'analytics:read', label: 'Analytics — Read', description: 'View saved analytics results' },
  { value: 'analytics:run', label: 'Analytics — Run', description: 'Execute structured analytics queries' },
  { value: 'analytics:question', label: 'Analytics — Question', description: 'Ask natural-language questions' },
  { value: 'reports:read', label: 'Reports — Read', description: 'View report metadata' },
  { value: 'workspace:read', label: 'Workspace — Read', description: 'View workspace information' },
  { value: 'webhooks:read', label: 'Webhooks — Read', description: 'View webhook configurations' },
  { value: 'webhooks:write', label: 'Webhooks — Write', description: 'Create and manage webhooks' },
];

export const WEBHOOK_EVENTS = [
  { value: 'dataset.created', label: 'Dataset Created' },
  { value: 'dataset.updated', label: 'Dataset Updated' },
  { value: 'dataset.deleted', label: 'Dataset Deleted' },
  { value: 'analytics.completed', label: 'Analytics Completed' },
  { value: 'analytics.failed', label: 'Analytics Failed' },
  { value: 'report.created', label: 'Report Created' },
  { value: 'workspace.member_added', label: 'Member Added' },
  { value: 'workspace.member_removed', label: 'Member Removed' },
  { value: 'subscription.updated', label: 'Subscription Updated' },
  { value: 'subscription.canceled', label: 'Subscription Canceled' },
  { value: 'usage.limit_reached', label: 'Usage Limit Reached' },
  { value: 'security.event', label: 'Security Event' },
  { value: 'webhook.test', label: 'Test Event' },
];

// ── API Key Management ──────────────────────────────────────────────────────

export async function listApiKeys(workspaceId: string): Promise<ApiKey[]> {
  const result = await apiFetch<{ keys: ApiKey[] }>(`/api/v1/developer/api-keys?workspace_id=${encodeURIComponent(workspaceId)}`);
  return result.keys;
}

export async function createApiKey(workspaceId: string, name: string, scopes: string[], expiresAt?: string): Promise<ApiKeyCreateResult> {
  return apiFetch<ApiKeyCreateResult>('/api/v1/developer/api-keys', {
    method: 'POST',
    body: JSON.stringify({ workspace_id: workspaceId, name, scopes, expires_at: expiresAt || null }),
  });
}

export async function revokeApiKey(workspaceId: string, keyId: string): Promise<void> {
  await apiFetch(`/api/v1/developer/api-keys/${encodeURIComponent(keyId)}/revoke?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'POST',
  });
}

export async function rotateApiKey(workspaceId: string, keyId: string, graceSeconds: number = 0): Promise<ApiKeyCreateResult> {
  return apiFetch<ApiKeyCreateResult>(`/api/v1/developer/api-keys/${encodeURIComponent(keyId)}/rotate`, {
    method: 'POST',
    body: JSON.stringify({ workspace_id: workspaceId, grace_seconds: graceSeconds }),
  });
}

// ── Webhook Management ──────────────────────────────────────────────────────

export async function listWebhooks(workspaceId: string): Promise<WebhookEndpoint[]> {
  const result = await apiFetch<{ webhooks: WebhookEndpoint[] }>(`/api/v1/developer/webhooks?workspace_id=${encodeURIComponent(workspaceId)}`);
  return result.webhooks;
}

export async function createWebhook(workspaceId: string, url: string, events: string[], description?: string): Promise<WebhookCreateResult> {
  return apiFetch<WebhookCreateResult>('/api/v1/developer/webhooks', {
    method: 'POST',
    body: JSON.stringify({ workspace_id: workspaceId, url, events, description: description || null }),
  });
}

export async function updateWebhook(workspaceId: string, webhookId: string, updates: { url?: string; description?: string; events?: string[]; active?: boolean }): Promise<WebhookEndpoint> {
  return apiFetch<WebhookEndpoint>(`/api/v1/developer/webhooks/${encodeURIComponent(webhookId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ workspace_id: workspaceId, ...updates }),
  });
}

export async function deleteWebhook(workspaceId: string, webhookId: string): Promise<void> {
  await apiFetch(`/api/v1/developer/webhooks/${encodeURIComponent(webhookId)}?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'DELETE',
  });
}

export async function rotateWebhookSecret(workspaceId: string, webhookId: string): Promise<{ secret: string }> {
  return apiFetch<{ secret: string }>(`/api/v1/developer/webhooks/${encodeURIComponent(webhookId)}/rotate-secret?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'POST',
  });
}

export async function testWebhook(workspaceId: string, webhookId: string): Promise<{ queued_deliveries: number }> {
  return apiFetch<{ queued_deliveries: number }>(`/api/v1/developer/webhooks/${encodeURIComponent(webhookId)}/test?workspace_id=${encodeURIComponent(workspaceId)}`, {
    method: 'POST',
  });
}

export async function listWebhookDeliveries(workspaceId: string, webhookId: string, limit: number = 50): Promise<WebhookDelivery[]> {
  const result = await apiFetch<{ deliveries: WebhookDelivery[] }>(`/api/v1/developer/webhooks/${encodeURIComponent(webhookId)}/deliveries?workspace_id=${encodeURIComponent(workspaceId)}&limit=${limit}`);
  return result.deliveries;
}

// ── Usage ────────────────────────────────────────────────────────────────────

export async function getDeveloperUsage(workspaceId: string, since?: string): Promise<UsageSummary> {
  const params = new URLSearchParams({ workspace_id: workspaceId });
  if (since) params.set('since', since);
  return apiFetch<UsageSummary>(`/api/v1/developer/usage?${params.toString()}`);
}
