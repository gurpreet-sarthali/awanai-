import { apiFetch } from './api';

export interface NLValidateResult {
  question: string;
  plan: Record<string, unknown>;
  sql: string;
  parameters: unknown[];
  read_only: boolean;
  row_query: boolean;
}

export interface NLExecuteResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  metadata: Record<string, unknown>;
}

export const validateQuestion = (question: string, datasetId: string) =>
  apiFetch<NLValidateResult>('/api/v1/nlsql/validate', { method: 'POST', body: JSON.stringify({ question, dataset_id: datasetId }) });

export const executePlan = (plan: Record<string, unknown>, datasetId: string) =>
  apiFetch<NLExecuteResult>('/api/v1/nlsql/execute', { method: 'POST', body: JSON.stringify({ plan, dataset_id: datasetId }) });
