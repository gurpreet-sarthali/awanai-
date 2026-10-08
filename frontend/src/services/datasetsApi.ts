import { apiFetch, apiUrl, getAccessToken } from './api';

export interface ManagedDatasetSummary {
  dataset_id: string;
  dataset_name: string;
  filename: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  status: string;
  is_builtin: boolean;
  created_at: string;
}

export interface ManagedDatasetDetail {
  dataset_id: string;
  dataset_name: string;
  filename: string;
  rows: number;
  columns: number;
  status: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
  validation: Record<string, unknown>;
}

export interface ManagedDatasetColumn {
  column_name: string;
  original_column_name: string;
  data_type: string;
  nullable: boolean;
  description: string | null;
  position: number;
}

export interface DatasetUploadResult {
  dataset_id: string;
  filename: string;
  dataset_name: string;
  rows: number;
  columns: number;
  missing_values: Record<string, number>;
  duplicate_rows: number;
  cleaning: Record<string, unknown>;
  warnings: string[];
  status: string;
}

export const listDatasets = () => apiFetch<{ datasets: ManagedDatasetSummary[] }>('/api/v1/datasets').then(body => body.datasets);
export const getManagedDataset = (datasetId: string) => apiFetch<ManagedDatasetDetail>(`/api/v1/datasets/${datasetId}`);
export const getManagedSchema = (datasetId: string) =>
  apiFetch<{ dataset_id: string; dataset_name: string; columns: ManagedDatasetColumn[] }>(`/api/v1/datasets/${datasetId}/schema`);
export const getManagedPreview = (datasetId: string, limit = 10) =>
  apiFetch<{ rows: Record<string, unknown>[]; limit: number }>(`/api/v1/datasets/${datasetId}/preview?limit=${limit}`);
export const deleteDataset = (datasetId: string) => apiFetch<{ dataset_id: string; status: string }>(`/api/v1/datasets/${datasetId}`, { method: 'DELETE' });

export async function uploadDataset(file: File, datasetName?: string): Promise<DatasetUploadResult> {
  const form = new FormData();
  form.append('file', file);
  if (datasetName?.trim()) {
    form.append('dataset_name', datasetName.trim());
  }
  const token = getAccessToken();
  const headers: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {};
  const response = await fetch(apiUrl('/api/v1/datasets/upload'), { method: 'POST', body: form, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.message === 'string' ? body.message : (body.detail || 'Dataset upload failed.'));
  }
  return body as DatasetUploadResult;
}
