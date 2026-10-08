import { apiFetch } from './api';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  profile_picture_url: string | null;
  is_active: boolean;
  is_admin?: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export const registerUser = (email: string, name: string, password: string) =>
  apiFetch<AuthTokenResponse>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, name, password }) });

export const loginUser = (email: string, password: string) =>
  apiFetch<AuthTokenResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });

export const logoutUser = () => apiFetch<{ message: string }>('/api/v1/auth/logout', { method: 'POST', body: JSON.stringify({}) });

export const getCurrentUser = () => apiFetch<AuthUser>('/api/v1/auth/me');

export const getGoogleAuthStatus = () => apiFetch<{ configured: boolean; authorization_url: string | null }>('/api/v1/auth/google/status');
