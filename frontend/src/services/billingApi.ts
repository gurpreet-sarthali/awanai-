import { apiFetch } from './api';

export type BillingPlan = {
  plan_id: string;
  name: string;
  description: string | null;
  price: number;
  currency: string;
  billing_interval: string;
  active: boolean;
  max_ai_requests: number | null;
  max_analytics_queries: number | null;
  max_reports: number | null;
  max_exports: number | null;
  max_conversations: number | null;
  feature_flags: Record<string, boolean>;
};

export async function getBillingPlans(): Promise<BillingPlan[]> {
  return apiFetch<BillingPlan[]>('/api/v1/billing/plans');
}
