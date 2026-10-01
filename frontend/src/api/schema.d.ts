// Hand-written from backend/CLAUDE.md endpoint table — regenerate with openapi-typescript from /api/docs/openapi.json when the backend is up.

/**
 * User roles defined in PRD Section 2 / Wireframe 1c.
 * One role per user (OQ-21).
 */
export type Role = "data_engineer" | "administrator" | "auditor" | "viewer";

/**
 * Standard RFC 7807 / 9457 Problem Details error response.
 */
export interface ProblemDetail {
  type?: string;
  title: string;
  status: number;
  detail?: string;
  code?: string;
  errors?: Record<string, string[]> | Array<{ field?: string; message: string }>;
}

/**
 * Universal paginated list response wrapper.
 */
export interface Page<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

// -----------------------------------------------------------------------------
// Auth & Users
// -----------------------------------------------------------------------------

export type UserStatus = "invited" | "active" | "deactivated";

export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  role: Role;
  status: UserStatus;
  lastLoginAt?: string | null;
  createdAt: string;
  updatedAt?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/** POST /auth/login. The user profile is fetched separately from GET /auth/me. */
export interface AuthResponse {
  accessToken: string;
  tokenType?: string;
  expiresIn?: number;
}

export interface RefreshResponse {
  accessToken: string;
  user?: User;
}

export interface LogoutResponse {
  message: string;
}

export interface AcceptInviteRequest {
  password: string;
}

export interface InviteUserRequest {
  email: string;
  role: Role;
}

export interface UserInvite {
  id: string;
  email: string;
  role: Role;
  expiresAt: string;
  acceptedAt?: string | null;
}

export interface UpdateUserRoleRequest {
  role: Role;
}

// -----------------------------------------------------------------------------
// Datasets & Quarantine
// -----------------------------------------------------------------------------

export type DatasetSource = "upload" | "n8n_folder";

export type DatasetStatus =
  | "profiling"
  | "profiled"
  | "plan_ready"
  | "approved"
  | "executed"
  | "tests_failed"
  | "rolled_back"
  | "failed";

export interface Dataset {
  id: string;
  name: string;
  source: DatasetSource;
  fileName: string;
  rowCount: number;
  columnCount: number;
  status: DatasetStatus;
  rawObjectKey?: string;
  ingestedAt: string;
  uploadedBy?: string;
  quarantineCount?: number;
  activePlanId?: string | null;
}

export interface DatasetDetail extends Dataset {
  fileSize?: number;
  mimeType?: string;
  errorMessage?: string;
}

export interface QuarantineRecord {
  id: string;
  datasetId: string;
  rowRef: string | number;
  reason: string;
  rowData?: Record<string, unknown>;
  createdAt: string;
}

// -----------------------------------------------------------------------------
// Real-time SSE & Jobs
// -----------------------------------------------------------------------------

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface Job {
  id: string;
  datasetId: string;
  planId?: string | null;
  type: string;
  status: JobStatus;
  progressPct: number;
  errorCode?: string | null;
  errorMessage?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
}

export interface DatasetEvent {
  jobId: string;
  type: string;
  status: JobStatus;
  progressPct: number;
  message: string;
  planId?: string;
}

// -----------------------------------------------------------------------------
// Profiling & Rules
// -----------------------------------------------------------------------------

export interface ColumnProfile {
  id: string;
  datasetId: string;
  columnName: string;
  ordinal: number;
  physicalType: string;
  semanticType: string;
  nullCount: number;
  nullPct: number;
  distinctCount: number;
  minValue?: string | number | null;
  maxValue?: string | number | null;
  meanValue?: number | null;
  flags: string[];
}

export interface ProfileSummary {
  rowCount: number;
  columnCount: number;
  columnsWithNullsCount: number;
  nestedColumnsCount: number;
  quarantinedRowsCount: number;
}

/** "used" = AI suggestions included; "off" = no model configured; "failed" = see aiMessage. */
export type AiStatus = "used" | "off" | "failed";

/** A cell that looks like an instruction to an AI model (FR-045); never sent to one. */
export interface FlaggedCell {
  column: string;
  row: number;
  preview: string;
  reason: string;
}

export interface DatasetProfile {
  datasetId: string;
  summary: ProfileSummary;
  columns: ColumnProfile[];
  aiStatus?: AiStatus | null;
  aiMessage?: string | null;
  flaggedCells?: FlaggedCell[];
}

export type InferredRuleType =
  | "entity_group"
  | "arithmetic"
  | "primary_key"
  | "one_to_many"
  | "semantic_type"
  | "cross_field_fill";

export interface InferredRule {
  id: string;
  datasetId: string;
  ruleType: InferredRuleType;
  columns: string[];
  expression: Record<string, unknown>;
  confidence: number;
  evidenceRows: Array<Record<string, unknown>>;
  promptVersion?: string;
  /** "llm" when the rule came from the AI model; anything else is deterministic. */
  source?: string;
}

// -----------------------------------------------------------------------------
// Planning & Steps
// -----------------------------------------------------------------------------

export type PlanStatus = "proposed" | "in_review" | "approved" | "rejected" | "superseded";

export type StepOperation =
  | "replace_value"
  | "fill_missing"
  | "drop_column"
  | "cast_type"
  | "derive_column"
  | "expand_nested"
  | "deduplicate"
  | "standardise_format";

export type StepDecision = "pending" | "accepted" | "edited" | "rejected";

export interface LossEstimate {
  rowsAffected: number;
  columnsAffected: number;
  cellsAffected: number;
  estimatedLoss: number; // percentage of cells
}

export interface PlanStep {
  id: string;
  planId: string;
  stepNo: number;
  operation: StepOperation;
  summary?: string;
  parameters: Record<string, unknown>;
  rationale: string;
  confidence: number;
  decision: StepDecision;
  decisionReason?: string | null;
  decidedBy?: string | null;
  decidedAt?: string | null;
  lossEstimate: LossEstimate;
  sampleBefore?: Array<Record<string, unknown>>;
  sampleAfter?: Array<Record<string, unknown>>;
  changedColumns?: string[];
  /** "llm" = AI-suggested step; "deterministic" otherwise. */
  source?: string;
}

export interface Plan {
  id: string;
  datasetId: string;
  status: PlanStatus;
  totalEstimatedLoss: number;
  lossThreshold: number;
  approvedBy?: string | null;
  approvedAt?: string | null;
  createdAt: string;
  steps?: PlanStep[];
  aiStatus?: AiStatus | null;
  aiMessage?: string | null;
  /** FR-046: the lowest step confidence (null when the plan has no steps). */
  confidence?: number | null;
}

export interface PlanDetail extends Plan {
  steps: PlanStep[];
}

export interface CreatePlanRequest {
  lossThreshold?: number;
}

export interface DecideStepRequest {
  decision: StepDecision;
  decisionReason?: string;
  parameters?: Record<string, unknown>;
}

export interface ApprovePlanResponse {
  planId: string;
  status: PlanStatus;
  job: Job;
}

// -----------------------------------------------------------------------------
// Execution, Versions & Rollback
// -----------------------------------------------------------------------------

export interface PipelineVersion {
  id: string;
  planId: string;
  versionNo: number;
  stepId?: string | null;
  stepNo?: number | null;
  operation?: StepOperation | null;
  snapshotObjectKey?: string;
  inverseOperation?: Record<string, unknown>;
  executedAt: string;
  executedBy?: string;
}

export interface RollbackRequest {
  toVersionNo: number;
  reason: string;
}

export interface RollbackResult {
  rollbackId: string;
  planId: string;
  fromVersionNo: number;
  toVersionNo: number;
  job: Job;
}

// -----------------------------------------------------------------------------
// Validation & Reconciliations
// -----------------------------------------------------------------------------

export type TestCaseType = "unit" | "integration";
export type TestResultPhase = "before" | "after";
export type TestRunResult = "passed" | "failed" | "error";

export interface TestCase {
  id: string;
  planId: string;
  type: TestCaseType;
  targetStepId?: string | null;
  targetStepNo?: number | null;
  name: string;
  definition: Record<string, unknown>;
}

export interface TestRun {
  id: string;
  testCaseId: string;
  testCaseName?: string;
  type?: TestCaseType;
  targetStepNo?: number | null;
  versionNo: number;
  phase: TestResultPhase;
  result: TestRunResult;
  detail?: string | null;
  runAt: string;
  durationMs?: number;
}

export interface ReconciliationCheck {
  id: string;
  planId: string;
  versionNo: number;
  checkName: string;
  sourceValue: string | number;
  outputValue: string | number;
  ok: boolean;
}

export interface ValidationReport {
  planId: string;
  versionNo: number;
  allPassed: boolean;
  unitSummary: {
    passed: number;
    total: number;
  };
  integrationSummary: {
    passed: number;
    total: number;
  };
  testRuns: TestRun[];
  reconciliations: ReconciliationCheck[];
}

// -----------------------------------------------------------------------------
// Exports
// -----------------------------------------------------------------------------

export type ExportFormat = "xlsx" | "csv" | "pipeline";

export interface CreateExportRequest {
  format: ExportFormat;
  versionNo?: number;
}

export interface ExportResponse {
  downloadUrl: string;
  expiresAt: string;
  format: ExportFormat;
  versionNo: number;
}

// -----------------------------------------------------------------------------
// Model Configuration
// -----------------------------------------------------------------------------

export interface ModelConfig {
  id: string;
  provider: string;
  model: string;
  endpointUrl?: string | null;
  credentialLast4?: string;
  allowDataSharing: boolean;
  isActive: boolean;
  updatedBy?: string;
  updatedAt?: string;
}

export interface UpdateModelConfigRequest {
  provider: string;
  model: string;
  apiKey?: string;
  endpointUrl?: string | null;
  allowDataSharing: boolean;
}

export interface TestModelConfigRequest {
  provider: string;
  model: string;
  apiKey?: string;
  endpointUrl?: string | null;
}

export interface TestConnectionResult {
  ok: boolean;
  latencyMs: number;
  message?: string;
}

export interface ProviderModelOption {
  id: string;
  name: string;
}

export interface ProviderOption {
  id: string;
  name: string;
  models: ProviderModelOption[];
  requiresEndpoint?: boolean;
}

// -----------------------------------------------------------------------------
// Audit Trail
// -----------------------------------------------------------------------------

export interface AuditEvent {
  id: string;
  occurredAt: string; // UTC ISO-8601
  userId?: string | null;
  userEmail?: string;
  userRole: Role;
  eventType: string;
  objectType: string;
  objectId: string;
  details: Record<string, unknown>;
  correlationId?: string;
}

export interface AuditEventFilter {
  fromDate?: string;
  toDate?: string;
  eventType?: string[];
  userId?: string;
  page?: number;
  pageSize?: number;
}

// -----------------------------------------------------------------------------
// Evaluation
// -----------------------------------------------------------------------------

export interface BenchmarkSet {
  id: string;
  name: string;
  description?: string;
  objectKeys: string[];
}

export interface EvaluationRun {
  id: string;
  benchmarkSetId: string;
  benchmarkSetName?: string;
  modelConfigId?: string;
  modelName?: string;
  passRate?: number;
  startedAt: string;
  durationSeconds?: number;
  finishedAt?: string | null;
  scores?: Record<string, unknown>;
  /** "pending" | "running" | "succeeded" | "failed" (backend run status). */
  status?: string;
  errorMessage?: string | null;
  /** The benchmark's own verdict: every check met its pass bar. */
  passed?: boolean;
}

export interface EvaluationRunDetail extends EvaluationRun {
  detailedResults?: Array<Record<string, unknown>>;
}

export interface StartEvaluationRequest {
  benchmarkSetId: string;
  modelConfigId?: string;
}

// -----------------------------------------------------------------------------
// System Configuration & Health
// -----------------------------------------------------------------------------

export interface UploadConfig {
  maxFileSizeMb: number;
  allowedExtensions: string[];
  n8nFolder?: string;
}

export interface HealthLiveResponse {
  status: "ok" | "degraded" | "down";
}

export interface HealthReadyResponse {
  status: "ok" | "degraded" | "down";
  checks: Record<string, boolean>;
}
