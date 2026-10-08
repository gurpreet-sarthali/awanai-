import { apiFetch } from './api';
import type { DatasetSample, DatasetSchema, DatasetSummary } from '../types/api';
export const getDatasetSummary = () => apiFetch<DatasetSummary>('/api/v1/dataset/summary');
export const getDatasetSchema = () => apiFetch<DatasetSchema>('/api/v1/dataset/schema');
export const getDatasetSample = (limit = 6) => apiFetch<DatasetSample>(`/api/v1/dataset/sample?limit=${limit}`);
