import { apiFetch } from './api';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface ResultMetadata {
  metrics?: Record<string, unknown> | null;
  chart?: { file_url?: string; title?: string; [key: string]: unknown } | null;
  insights?: string[] | null;
  recommendations?: string[] | null;
  warnings?: string[] | null;
  analysis?: string | null;
}

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  message_type: 'question' | 'answer' | 'error';
  content: string;
  dataset_id: string | null;
  created_at: string;
  result_metadata: ResultMetadata | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  dataset_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[];
}

// ─── API Calls ──────────────────────────────────────────────────────────────

export const listConversations = (limit = 50, offset = 0) =>
  apiFetch<ConversationSummary[]>(`/api/v1/conversations?limit=${limit}&offset=${offset}`);

export const createConversation = (datasetId?: string) =>
  apiFetch<ConversationSummary>('/api/v1/conversations', {
    method: 'POST',
    body: JSON.stringify({ dataset_id: datasetId ?? null }),
  });

export const getConversation = (conversationId: string) =>
  apiFetch<ConversationDetail>(`/api/v1/conversations/${conversationId}`);

export const renameConversation = (conversationId: string, title: string) =>
  apiFetch<ConversationSummary>(`/api/v1/conversations/${conversationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });

export const deleteConversation = (conversationId: string) =>
  apiFetch<{ status: string }>(`/api/v1/conversations/${conversationId}`, { method: 'DELETE' });

export const sendMessage = (conversationId: string, question: string, datasetId?: string) =>
  apiFetch<ChatMessage>(`/api/v1/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ question, dataset_id: datasetId ?? null }),
  });
