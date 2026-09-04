export type JobStatus =
  | "UPLOADED"
  | "EXTRACTING"
  | "UNDERSTANDING_SCHEMA"
  | "PLANNING"
  | "VALIDATING_PLAN"
  | "RECONCILING"
  | "INVESTIGATING"
  | "GENERATING_REPORT"
  | "COMPLETED"
  | "FAILED";

export interface Job {
  job_id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  error_code: string | null;
  error_message: string | null;
}

export interface CheckDetail {
  field: string | null;
  expected: unknown;
  actual: unknown;
  result: string;
}

export interface Evidence {
  dataset_id: string;
  row_id: string;
  values: Record<string, unknown>;
}

export type RecordStatus = "MATCHED" | "MISMATCHED" | "EXCEPTION" | "UNRESOLVED";

export interface ReconciliationResult {
  record_id: string;
  job_id: string;
  step_id: string;
  status: RecordStatus;
  rule_applied: string;
  checks: CheckDetail[];
  evidence: Evidence[];
  reason: string | null;
}

export interface ExceptionExplanation {
  record_id: string;
  reason: string;
  evidence_used: string[];
  likely_cause: string | null;
  recommended_action: string | null;
  confidence: number;
  resolved: boolean;
}

export interface Metrics {
  total_records: number;
  matched: number;
  mismatched: number;
  exceptions: number;
  unresolved: number;
  match_rate: number;
  mismatch_rate: number;
  exception_rate: number;
  unresolved_rate: number;
  total_variance_amount: number;
}

export interface StepMetrics extends Metrics {
  step_id: string;
  rule_applied: string;
}

export interface Report {
  job_id: string;
  generated_at: string;
  metrics: Metrics;
  by_step: StepMetrics[];
  results: ReconciliationResult[];
  exception_explanations: ExceptionExplanation[];
  ai_calls_made: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}
