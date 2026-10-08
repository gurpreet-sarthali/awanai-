export interface UserFeedbackPayload {
  feedback_type: 'bug' | 'incorrect_answer' | 'feature_request' | 'usability' | 'general';
  rating: number;
  comment?: string;
}

export interface AIMessageFeedbackPayload {
  rating: 'helpful' | 'not_helpful';
  reason?: 'incorrect_result' | 'poor_explanation' | 'wrong_chart' | 'question_misunderstood' | 'other';
  comment?: string;
}

export interface FeedbackItem {
  id: string;
  user_id: string;
  user_email: string;
  feedback_type: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface AIMessageFeedbackItem {
  id: string;
  message_id: string;
  user_id: string;
  user_email: string;
  rating: string;
  reason: string | null;
  comment: string | null;
  created_at: string;
}

export interface AdminOverviewStats {
  total_users: number;
  dau: number;
  wau: number;
  mau: number;
  total_datasets: number;
  uploaded_datasets_in_period: number;
  total_analyses: number;
  failed_analyses: number;
  total_ai_requests: number;
  successful_ai_requests: number;
  avg_ai_response_time_ms: number;
  total_errors: number;
  avg_user_rating: number;
  ai_helpfulness_rate: number;
}

export interface AdminTimeSeriesPoint {
  date: string;
  active_users: number;
  analyses: number;
  dataset_uploads: number;
}

export interface ErrorLogItem {
  id: string;
  request_id: string | null;
  user_id: string | null;
  error_category: string;
  endpoint: string;
  http_status: number;
  error_message: string;
  created_at: string;
}

export interface AdminDashboardData {
  overview: AdminOverviewStats;
  time_series: AdminTimeSeriesPoint[];
  errors: ErrorLogItem[];
  feedback: FeedbackItem[];
  ai_feedback: AIMessageFeedbackItem[];
}
