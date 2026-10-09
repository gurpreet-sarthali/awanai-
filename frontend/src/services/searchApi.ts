import { apiFetch } from './api';

export type SearchResultItem = {
  id: string;
  type: string;
  title: string;
  description: string;
  workspace_id?: string;
  workspace_name?: string;
  dataset_id?: string;
  dataset_name?: string;
  updated_at: string;
  score: number;
  matched_fields: string[];
  favorite: boolean;
  metadata: Record<string, unknown>;
};

export type GlobalSearchResponse = {
  query: string;
  results: {
    datasets: SearchResultItem[];
    columns: SearchResultItem[];
    conversations: SearchResultItem[];
    saved_queries: SearchResultItem[];
    reports: SearchResultItem[];
    workspaces: SearchResultItem[];
    analytics_results: SearchResultItem[];
  };
  total: number;
  page: number;
  limit: number;
};

export async function globalSearch(query: string, type?: string, workspace_id?: string, page = 1): Promise<GlobalSearchResponse> {
  const params = new URLSearchParams({ page: page.toString() });
  if (query) params.append('q', query);
  if (type) params.append('type', type);
  if (workspace_id) params.append('workspace_id', workspace_id);
  
  return apiFetch(`/api/v1/search?${params.toString()}`);
}

export async function getSearchSuggestions(query: string, workspace_id?: string) {
  const params = new URLSearchParams();
  if (query) params.append('q', query);
  if (workspace_id) params.append('workspace_id', workspace_id);
  return apiFetch(`/api/v1/search/suggestions?${params.toString()}`);
}

export async function getRecentItems(limit = 20) {
  return apiFetch(`/api/v1/search/recent?limit=${limit}`);
}

export async function getDatasetCatalog(query: string = '', workspace_id?: string, page = 1) {
  const params = new URLSearchParams({ page: page.toString() });
  if (query) params.append('q', query);
  if (workspace_id) params.append('workspace_id', workspace_id);
  return apiFetch(`/api/v1/catalog/datasets?${params.toString()}`);
}

export async function toggleFavorite(resourceType: string, resourceId: string, workspaceId?: string, isFavorite = false) {
  if (isFavorite) {
    return apiFetch(`/api/v1/catalog/favorites/${resourceType}/${resourceId}`, { method: 'DELETE' });
  } else {
    return apiFetch(`/api/v1/catalog/favorites`, {
      method: 'POST',
      body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId, workspace_id: workspaceId })
    });
  }
}
