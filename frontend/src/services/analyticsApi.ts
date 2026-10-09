// gurpreet good
import { apiFetch } from './api';
import type { AnalyticsOperation, AnalyticsResponse } from '../types/api';
import { DEFAULT_DATASET_ID } from '../hooks/useSelectedDataset';

export const getAnalytics = (operation: AnalyticsOperation, datasetId = DEFAULT_DATASET_ID, column?: string, groupBy?: string) =>
  apiFetch<AnalyticsResponse>('/api/v1/analytics/run', {
    method: 'POST',
    body: JSON.stringify({ operation, dataset_id: datasetId, column, group_by: groupBy }),
  });

export const getAnalyticsSummary = (datasetId = DEFAULT_DATASET_ID) =>
  apiFetch<AnalyticsResponse>(`/api/v1/analytics/summary?dataset_id=${encodeURIComponent(datasetId)}`);

export const getPlacementAnalytics = (datasetId = DEFAULT_DATASET_ID) =>
  apiFetch<AnalyticsResponse>(`/api/v1/analytics/placement?dataset_id=${encodeURIComponent(datasetId)}`);
