export interface DatasetSummary { table: string; rows: number; columns: number; missing_values: Record<string, number>; available_columns: string[]; warnings: string[]; }
export interface DatasetColumn { name: string; data_type: string; nullable: boolean; primary_key: boolean; }
export interface DatasetSchema { table: string; columns: DatasetColumn[]; }
export interface DatasetSample { table: string; rows: Record<string, unknown>[]; }
export interface AnalyticsResponse { operation: string; dataset_id?: string; result: unknown; }
export type GenericAnalyticsOperation = 'overview' | 'count' | 'average' | 'minimum' | 'maximum' | 'sum' | 'value_counts' | 'group_average';
export interface ChartMetadata { status: string; chart_type: string; title: string; file_url: string; metadata: Record<string, unknown>; }
export type AnalyticsOperation =
  | 'overall_placement_rate'
  | 'placement_by_internship'
  | 'placement_by_cgpa_group'
  | 'placement_by_project_group'
  | 'placement_by_communication'
  | 'average_metrics_by_placement'
  | GenericAnalyticsOperation;
export type ChartType = 'bar' | 'line' | 'pie' | 'histogram' | 'scatter' | 'box';
export interface AIPlan { intent: string; operation: string; filters: { field: string; value: string }[]; chart_type: ChartType | null; needs_chart: boolean; }
export interface AIAnalysis { question: string; answer: string; metrics: unknown; chart: { file_url: string; title: string; chart_type: string } | null; insights: string[]; recommendations: string[]; warnings: string[]; analysis: { operation: string; filters: { field: string; value: string }[]; chart_type: string | null; needs_chart: boolean }; }
