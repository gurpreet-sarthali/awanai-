const TOKEN_KEY = 'askmydata.accessToken';

export const baseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export const apiUrl = (path: string) => `${baseUrl}${path}`;

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const authHeader: Record<string, string> = token ? { 'Authorization': `Bearer ${token}` } : {};
  const response = await fetch(apiUrl(path), {
    headers: { 'Content-Type': 'application/json', ...authHeader, ...(init?.headers || {}) },
    ...init,
  });
  if (response.status === 401) {
    // Token expired or invalid — clear it so the UI can redirect to login
    clearAccessToken();
  }
  if (!response.ok) {
    let detail = 'Unable to connect to the analytics server.';
    try { const body = await response.json(); detail = body.detail || body.error || detail; } catch { /* keep friendly fallback */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function assetUrl(path: string): string { return path.startsWith('http') ? path : `${baseUrl}${path}`; }
