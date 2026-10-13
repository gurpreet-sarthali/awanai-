/**
 * visitorApi.ts - Frontend service for visitor registration.
 *
 * Calls the backend /api/v1/visitors/register endpoint.
 * The backend holds the Supabase service-role key — it is NEVER exposed here.
 */
import { apiUrl } from './api';

export interface VisitorRegistrationRequest {
  name: string;
  email: string;
}

export interface VisitorRegistrationResponse {
  visitor_id: string;
  name: string;
  email: string;
  registered_at: string;
  is_returning: boolean;
  access_token?: string;
}

export async function registerVisitor(
  payload: VisitorRegistrationRequest,
): Promise<VisitorRegistrationResponse> {
  const response = await fetch(apiUrl('/api/v1/visitors/register'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = 'Registration failed. Please try again.';
    try {
      const body = await response.json();
      // Avoid exposing internal detail - use a friendly message
      if (response.status === 429) {
        detail = 'Too many requests. Please wait a moment and try again.';
      } else if (response.status >= 500) {
        detail = 'A server error occurred. Please try again later.';
      } else {
        detail = body.detail || body.error || detail;
      }
    } catch { /* keep fallback */ }
    throw new Error(detail);
  }

  return response.json() as Promise<VisitorRegistrationResponse>;
}
