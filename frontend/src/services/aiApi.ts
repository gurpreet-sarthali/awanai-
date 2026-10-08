// gurpreet singh 8-oct-26
import { apiFetch } from './api';
import type { AIAnalysis, AIPlan } from '../types/api';
import { DEFAULT_DATASET_ID } from '../hooks/useSelectedDataset';

export const createPlan = (question: string, datasetId = DEFAULT_DATASET_ID) =>
  apiFetch<{ question: string; plan: AIPlan }>('/api/v1/ai/plan', { method: 'POST', body: JSON.stringify({ question, dataset_id: datasetId }) });

export const analyzeQuestion = (question: string, datasetId = DEFAULT_DATASET_ID) =>
  apiFetch<AIAnalysis>('/api/v1/ai/analyze', { method: 'POST', body: JSON.stringify({ question, dataset_id: datasetId }) });