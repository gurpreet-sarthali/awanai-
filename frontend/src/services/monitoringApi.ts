import { apiFetch } from './api';
import {
  AdminDashboardData,
  AIMessageFeedbackPayload,
  ErrorLogItem,
  FeedbackItem,
  UserFeedbackPayload,
} from '../types/monitoring';

export async function submitGeneralFeedback(_token: string, payload: UserFeedbackPayload): Promise<FeedbackItem> {
  return apiFetch<FeedbackItem>('/api/v1/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function submitAIMessageFeedback(
  _token: string,
  messageId: string,
  payload: AIMessageFeedbackPayload
): Promise<any> {
  return apiFetch(`/api/v1/messages/${messageId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getAdminAnalytics(_token: string, days: number = 30): Promise<AdminDashboardData> {
  return apiFetch<AdminDashboardData>(`/api/v1/admin/analytics?days=${days}`, {
    method: 'GET',
  });
}

export async function getAdminErrors(_token: string, limit: number = 50): Promise<ErrorLogItem[]> {
  return apiFetch<ErrorLogItem[]>(`/api/v1/admin/errors?limit=${limit}`, {
    method: 'GET',
  });
}

export async function triggerLogCleanup(_token: string, usageDays: number = 90, errorDays: number = 30): Promise<any> {
  return apiFetch('/api/v1/admin/retention/cleanup', {
    method: 'POST',
    body: JSON.stringify({ usage_retention_days: usageDays, error_retention_days: errorDays }),
  });
}
