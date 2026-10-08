import { apiFetch } from './api';
import type { AnalyticsOperation, ChartMetadata, ChartType } from '../types/api';
import { DEFAULT_DATASET_ID } from '../hooks/useSelectedDataset';

export const generateChart = (
  chart_type: ChartType,
  analysis_operation: AnalyticsOperation,
  datasetId = DEFAULT_DATASET_ID,
  column?: string,
  groupBy?: string,
) =>
  apiFetch<ChartMetadata>('/api/v1/visualizations/generate', {
    method: 'POST',
    body: JSON.stringify({ chart_type, analysis_operation, dataset_id: datasetId, column, group_by: groupBy }),
  });
