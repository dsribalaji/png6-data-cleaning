// NOT GENERATED YET — API types will be generated from the FastAPI OpenAPI spec (openapi-typescript). The interfaces below are PROVISIONAL hand-written placeholders.

export type PlanStepOpType =
  | "replace_value"
  | "fill_missing"
  | "drop_column"
  | "cast_type"
  | "derive_column"
  | "expand_nested"
  | "deduplicate"
  | "standardise_format";

export interface Dataset {
  id: string;
  name: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  storage_path: string;
  status: "uploaded" | "profiling" | "profiled" | "planning" | "planned" | "executing" | "completed" | "failed";
  created_at: string;
  updated_at: string;
}

export interface ColumnProfile {
  column_name: string;
  detected_type: string;
  null_count: number;
  null_percentage: number;
  distinct_count: number;
  unique_count: number;
  min_value?: string | number | null;
  max_value?: string | number | null;
  mean_value?: number | null;
  is_all_null: boolean;
  has_nested_json: boolean;
  has_text_numerics: boolean;
  inferred_semantic_type?: string | null;
}

export interface ProfileReport {
  id: string;
  dataset_id: string;
  total_rows: number;
  total_columns: number;
  columns: ColumnProfile[];
  quarantined_rows_count: number;
  flags: string[];
  created_at: string;
}

export interface LossEstimate {
  step_id?: string;
  rows_affected: number;
  columns_affected: number;
  cells_affected: number;
  estimated_loss_percentage: number;
  exceeds_threshold: boolean;
  details?: Record<string, unknown>;
}

export interface PlanStep {
  id: string;
  plan_id: string;
  step_number: number;
  op_type: PlanStepOpType;
  target_column?: string | null;
  parameters: Record<string, unknown>;
  loss_estimate?: LossEstimate | null;
  status: "pending" | "approved" | "rejected" | "edited";
  requires_approval: boolean;
}

export interface Plan {
  id: string;
  dataset_id: string;
  steps: PlanStep[];
  cumulative_loss_percentage: number;
  status: "draft" | "under_review" | "approved" | "rejected" | "executed";
  created_at: string;
  updated_at: string;
}

export interface TestCase {
  id: string;
  plan_id: string;
  step_id?: string | null;
  test_type: "unit" | "integration" | "schema_compliance" | "reconciliation";
  description: string;
  expected_outcome: string;
}

export interface TestRun {
  id: string;
  plan_id: string;
  phase: "pre_execution" | "post_execution";
  passed: boolean;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  results: Array<{
    test_id: string;
    passed: boolean;
    error_message?: string | null;
  }>;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  user_id: string;
  action: "profile" | "plan" | "approve" | "reject" | "execute" | "rollback";
  dataset_id: string;
  plan_id?: string | null;
  details: Record<string, unknown>;
}

export interface QuarantineRecord {
  id: string;
  dataset_id: string;
  row_index: number;
  raw_content: string;
  reason: string;
  poison_flag: boolean;
  created_at: string;
}

export interface ExecutionResult {
  id: string;
  plan_id: string;
  dataset_id: string;
  version_number: number;
  status: "success" | "failed" | "rolled_back";
  output_tables: Array<{
    table_name: string;
    row_count: number;
    column_count: number;
    download_url: string;
  }>;
  completed_at: string;
}
