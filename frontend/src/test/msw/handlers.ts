import { http, HttpResponse } from "msw";
import type {
  ApprovePlanResponse,
  AuditEvent,
  AuthResponse,
  ColumnProfile,
  Dataset,
  DatasetDetail,
  DatasetProfile,
  EvaluationRun,
  EvaluationRunDetail,
  ExportResponse,
  InferredRule,
  Job,
  LossEstimate,
  ModelConfig,
  Page,
  PipelineVersion,
  PlanDetail,
  PlanStep,
  ProviderOption,
  QuarantineRecord,
  RefreshResponse,
  RollbackResult,
  TestRun,
  UserInvite,
  UploadConfig,
  User,
  ValidationReport,
} from "../../api/schema";

/**
 * MSW v2 handlers for the whole `/api/v1` surface the SPA talks to.
 *
 * Two rules the tests rely on:
 *  1. Every path is written with a leading wildcard (e.g. "STAR/api/v1/...")
 *     so the wildcard origin matches whatever `location.origin` jsdom
 *     happens to use for the current run. (The literal pattern is
 *     star + "/api/v1/..." — written out here because a block comment
 *     cannot contain the two characters star-slash.)
 *  2. Errors are `application/problem+json` with a `code`, which is what
 *     `ApiError` (src/api/client.ts) and the `map*Error` helpers read.
 */

// -----------------------------------------------------------------------------
// Fixtures / sentinels
// -----------------------------------------------------------------------------

export const MSW_ACCESS_TOKEN = "msw-access-token";
export const MSW_REFRESHED_ACCESS_TOKEN = "msw-refreshed-access-token";

/** The one password the login handler rejects (see `POST auth/login`). */
export const MSW_WRONG_PASSWORD = "wrong";

/** The one address the invite handler rejects with 409 USER_EXISTS. */
export const MSW_EXISTING_USER_EMAIL = "existing@example.com";

export const MSW_DATASET_ID = "dataset-1";
export const MSW_PLAN_ID = "plan-1";
export const MSW_JOB_ID = "job-1";

export const mswUser: User = {
  id: "user-1",
  email: "engineer@example.com",
  firstName: "Tita",
  lastName: "Engineer",
  role: "data_engineer",
  status: "active",
  createdAt: "2026-01-05T09:00:00Z",
};

export const mswDataset: Dataset = {
  id: MSW_DATASET_ID,
  name: "Vendor invoices",
  source: "upload",
  fileName: "VendorInvoices_uncleaned.xlsx",
  rowCount: 1200,
  columnCount: 9,
  status: "profiled",
  ingestedAt: "2026-02-02T10:00:00Z",
  uploadedBy: mswUser.id,
  quarantineCount: 3,
  activePlanId: null,
};

export const mswDatasetDetail: DatasetDetail = {
  ...mswDataset,
  fileSize: 248_320,
  mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
};

function msColumn(overrides: Partial<ColumnProfile> & Pick<ColumnProfile, "id" | "columnName">): ColumnProfile {
  return {
    datasetId: MSW_DATASET_ID,
    ordinal: 0,
    physicalType: "string",
    semanticType: "unknown",
    nullCount: 0,
    nullPct: 0,
    distinctCount: 0,
    flags: [],
    ...overrides,
  };
}

export const mswProfile: DatasetProfile = {
  datasetId: MSW_DATASET_ID,
  summary: {
    rowCount: 1200,
    columnCount: 9,
    columnsWithNullsCount: 3,
    nestedColumnsCount: 1,
    quarantinedRowsCount: 3,
  },
  columns: [
    msColumn({
      id: "col-1",
      columnName: "invoice_id",
      ordinal: 1,
      physicalType: "string",
      semanticType: "identifier",
      distinctCount: 1200,
    }),
    msColumn({
      id: "col-2",
      columnName: "vendor_name",
      ordinal: 2,
      nullCount: 120,
      nullPct: 10,
      distinctCount: 214,
      flags: ["nulls"],
    }),
    msColumn({
      id: "col-3",
      columnName: "total",
      ordinal: 3,
      physicalType: "double",
      semanticType: "currency",
      nullCount: 40,
      nullPct: 3.33,
      flags: ["nulls", "outliers"],
      minValue: 0,
      maxValue: 91_450,
      meanValue: 812.4,
    }),
  ],
};

export const mswRules: InferredRule[] = [
  {
    id: "rule-1",
    datasetId: MSW_DATASET_ID,
    ruleType: "primary_key",
    columns: ["invoice_id"],
    expression: { source: "invoice_id" },
    confidence: 0.98,
    evidenceRows: [{ invoice_id: "INV-0001" }],
    promptVersion: "planner-2026-02",
  },
  {
    id: "rule-2",
    datasetId: MSW_DATASET_ID,
    ruleType: "semantic_type",
    columns: ["vendor_name"],
    expression: { strategy: "title_case" },
    confidence: 0.81,
    evidenceRows: [{ vendor_name: "acme  corp " }],
  },
];

export const mswQuarantine: Page<QuarantineRecord> = {
  items: [
    {
      id: "q-1",
      datasetId: MSW_DATASET_ID,
      rowRef: 41,
      reason: "Unparseable date in invoice_date",
      rowData: { invoice_id: "INV-0041" },
      createdAt: "2026-02-02T10:00:05Z",
    },
    {
      id: "q-2",
      datasetId: MSW_DATASET_ID,
      rowRef: 42,
      reason: "Unparseable date in invoice_date",
      rowData: { invoice_id: "INV-0042" },
      createdAt: "2026-02-02T10:00:05Z",
    },
    {
      id: "q-3",
      datasetId: MSW_DATASET_ID,
      rowRef: 43,
      reason: "Duplicate primary key",
      rowData: { invoice_id: "INV-0043" },
      createdAt: "2026-02-02T10:00:05Z",
    },
  ],
  page: 1,
  pageSize: 50,
  total: 3,
};

function msLoss(overrides: Partial<LossEstimate> = {}): LossEstimate {
  return {
    rowsAffected: 0,
    columnsAffected: 0,
    cellsAffected: 0,
    estimatedLoss: 0,
    ...overrides,
  };
}

/** Every step is already decided, so the plan review screen can be approved. */
export const mswSteps: PlanStep[] = [
  {
    id: "step-1",
    planId: MSW_PLAN_ID,
    stepNo: 1,
    operation: "standardise_format",
    summary: "Standardise the format of vendor_name",
    parameters: { column: "vendor_name", strategy: "title_case" },
    rationale: "18 spelling variants of the same vendor.",
    confidence: 0.94,
    decision: "accepted",
    decidedBy: mswUser.id,
    decidedAt: "2026-02-02T11:00:00Z",
    lossEstimate: msLoss({ rowsAffected: 214, columnsAffected: 1, cellsAffected: 214, estimatedLoss: 0.02 }),
  },
  {
    id: "step-2",
    planId: MSW_PLAN_ID,
    stepNo: 2,
    operation: "fill_missing",
    summary: "Fill missing values in total using the median",
    parameters: { column: "total", strategy: "median" },
    rationale: "40 invoices have no total; the median keeps the column comparable.",
    confidence: 0.77,
    decision: "accepted",
    decidedBy: mswUser.id,
    decidedAt: "2026-02-02T11:01:00Z",
    lossEstimate: msLoss({ rowsAffected: 40, columnsAffected: 1, cellsAffected: 40, estimatedLoss: 0.004 }),
  },
];

export const mswPlan: PlanDetail = {
  id: MSW_PLAN_ID,
  datasetId: MSW_DATASET_ID,
  status: "in_review",
  totalEstimatedLoss: 0.024,
  lossThreshold: 0.05,
  createdAt: "2026-02-02T10:30:00Z",
  steps: mswSteps,
};

export const mswJob: Job = {
  id: MSW_JOB_ID,
  datasetId: MSW_DATASET_ID,
  planId: MSW_PLAN_ID,
  type: "execute",
  status: "queued",
  progressPct: 0,
  startedAt: "2026-02-02T11:05:00Z",
  finishedAt: null,
};

function msTestRun(overrides: Partial<TestRun> & Pick<TestRun, "id" | "testCaseId">): TestRun {
  return {
    testCaseName: "vendor_name is title-cased",
    type: "unit",
    targetStepNo: 1,
    versionNo: 2,
    phase: "after",
    result: "passed",
    runAt: "2026-02-02T11:06:00Z",
    durationMs: 42,
    ...overrides,
  };
}

/** `allPassed: true` opens the export gate (FR-043). */
export const mswValidation: ValidationReport = {
  planId: MSW_PLAN_ID,
  versionNo: 2,
  allPassed: true,
  unitSummary: { passed: 2, total: 2 },
  integrationSummary: { passed: 1, total: 1 },
  testRuns: [
    msTestRun({ id: "run-1", testCaseId: "case-1" }),
    msTestRun({ id: "run-2", testCaseId: "case-2", type: "integration", targetStepNo: 2 }),
  ] satisfies TestRun[],
  reconciliations: [
    {
      id: "recon-1",
      planId: MSW_PLAN_ID,
      versionNo: 2,
      checkName: "Row count is preserved",
      sourceValue: 1200,
      outputValue: 1200,
      ok: true,
    },
  ],
};

export const mswVersions: PipelineVersion[] = [
  {
    id: "version-2",
    planId: MSW_PLAN_ID,
    versionNo: 2,
    stepId: "step-2",
    stepNo: 2,
    operation: "fill_missing",
    executedAt: "2026-02-02T11:05:30Z",
    executedBy: mswUser.id,
  },
  {
    id: "version-1",
    planId: MSW_PLAN_ID,
    versionNo: 1,
    stepId: "step-1",
    stepNo: 1,
    operation: "standardise_format",
    executedAt: "2026-02-02T11:05:10Z",
    executedBy: mswUser.id,
  },
];

export const mswModelConfig: ModelConfig = {
  id: "model-config-1",
  provider: "ollama",
  model: "llama3.1",
  endpointUrl: "http://localhost:11434",
  credentialLast4: "cdef",
  allowDataSharing: false,
  isActive: true,
  updatedBy: mswUser.id,
  updatedAt: "2026-01-20T12:00:00Z",
};

export const mswProviders: ProviderOption[] = [
  {
    id: "ollama",
    name: "Ollama (self-hosted)",
    models: [
      { id: "llama3.1", name: "Llama 3.1" },
      { id: "qwen2.5", name: "Qwen 2.5" },
    ],
    requiresEndpoint: true,
  },
  {
    id: "openai-compatible",
    name: "OpenAI-compatible",
    models: [{ id: "gpt-4o-mini", name: "GPT-4o mini" }],
  },
];

export const mswUsers: User[] = [
  mswUser,
  {
    id: "user-2",
    email: MSW_EXISTING_USER_EMAIL,
    firstName: "Existing",
    lastName: "Person",
    role: "auditor",
    status: "active",
    createdAt: "2026-01-07T09:00:00Z",
  },
];

export const mswAuditEvents: AuditEvent[] = [
  {
    id: "audit-1",
    occurredAt: "2026-02-02T11:05:30Z",
    userId: mswUser.id,
    userEmail: mswUser.email,
    userRole: mswUser.role,
    eventType: "plan.execute",
    objectType: "plan",
    objectId: MSW_PLAN_ID,
    details: { versionNo: 2 },
    correlationId: "corr-1",
  },
  {
    id: "audit-2",
    occurredAt: "2026-02-02T10:30:00Z",
    userId: mswUser.id,
    userEmail: mswUser.email,
    userRole: mswUser.role,
    eventType: "plan.approve",
    objectType: "plan",
    objectId: MSW_PLAN_ID,
    details: {},
  },
];

export const mswEvaluationRun: EvaluationRun = {
  id: "evaluation-1",
  benchmarkSetId: "vendor-invoices-golden",
  benchmarkSetName: "vendor-invoices-golden",
  modelName: "llama3.1",
  passRate: 0.94,
  startedAt: "2026-02-01T08:00:00Z",
  durationSeconds: 74,
  finishedAt: "2026-02-01T08:01:14Z",
  scores: { recovered: 0.94, untouched: 0.06 },
};

export const mswUploadConfig: UploadConfig = {
  maxFileSizeMb: 50,
  allowedExtensions: [".xlsx", ".csv"],
  n8nFolder: "/srv/n8n/out",
};

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/**
 * RFC 9457 problem body. `Content-Type` must be `application/problem+json`,
 * because `ApiError` only parses the body when it sees that header.
 */
export function problem(status: number, code: string, title: string, detail?: string): Response {
  return HttpResponse.json(
    {
      type: `https://png6.local/problems/${code.toLowerCase()}`,
      title,
      status,
      code,
      ...(detail ? { detail } : {}),
    },
    { status, headers: { "Content-Type": "application/problem+json" } }
  );
}

function page<T>(items: T[], pageSize = 50): Page<T> {
  return { items, page: 1, pageSize, total: items.length };
}

async function readJsonBody(request: Request): Promise<Record<string, unknown>> {
  try {
    const body = await request.json();
    return typeof body === "object" && body !== null
      ? (body as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

// -----------------------------------------------------------------------------
// Handlers
// -----------------------------------------------------------------------------

export const handlers = [
  // ----- Auth ---------------------------------------------------------------

  http.post("*/api/v1/auth/login", async ({ request }) => {
    const body = await readJsonBody(request);
    const password = typeof body.password === "string" ? body.password : "";

    if (password === MSW_WRONG_PASSWORD) {
      return problem(401, "INVALID_CREDENTIALS", "Unauthorized", "Email or password is incorrect.");
    }

    const email = typeof body.email === "string" && body.email ? body.email : mswUser.email;
    const response: AuthResponse = {
      accessToken: MSW_ACCESS_TOKEN,
      user: { ...mswUser, email },
    };
    return HttpResponse.json(response);
  }),

  http.post("*/api/v1/auth/refresh", () => {
    const response: RefreshResponse = { accessToken: MSW_REFRESHED_ACCESS_TOKEN, user: mswUser };
    return HttpResponse.json(response);
  }),

  http.post("*/api/v1/auth/logout", () => HttpResponse.json({ message: "Signed out." })),

  http.get("*/api/v1/auth/me", () => HttpResponse.json(mswUser)),

  // ----- Datasets -----------------------------------------------------------

  http.get("*/api/v1/datasets", () => HttpResponse.json(page([mswDataset], 20))),

  http.post("*/api/v1/datasets", async ({ request }) => {
    const form = await request.formData();
    const name = form.get("name");
    if (name === mswDataset.name) {
      return problem(409, "DATASET_NAME_TAKEN", "Conflict", "A dataset with this name already exists.");
    }
    // The created row always comes back "Profiling" (PRD S3).
    return HttpResponse.json({ ...mswDatasetDetail, name: typeof name === "string" ? name : mswDataset.name, status: "profiling" });
  }),

  http.get("*/api/v1/datasets/:id", () => HttpResponse.json(mswDatasetDetail)),

  http.get("*/api/v1/datasets/:id/profile", () => HttpResponse.json(mswProfile)),

  http.get("*/api/v1/datasets/:id/rules", () => HttpResponse.json(mswRules)),

  http.get("*/api/v1/datasets/:id/quarantine", () => HttpResponse.json(mswQuarantine)),

  http.post("*/api/v1/datasets/:id/plans", () => {
    // `useGeneratePlan` reads `planId`; `useRegeneratePlan` reads the whole
    // plan, so the response is a superset of both.
    return HttpResponse.json({ ...mswPlan, planId: MSW_PLAN_ID, job: mswJob });
  }),

  // ----- Plans --------------------------------------------------------------

  http.get("*/api/v1/plans/:id", () => HttpResponse.json(mswPlan)),

  http.patch("*/api/v1/plans/:id/steps/:stepId", async ({ params, request }) => {
    const body = await readJsonBody(request);
    const step = mswSteps.find((candidate) => candidate.id === params.stepId);
    if (!step) {
      return problem(404, "STEP_NOT_FOUND", "Not Found", "That plan step no longer exists.");
    }
    return HttpResponse.json({
      ...step,
      decision: typeof body.decision === "string" ? body.decision : step.decision,
      decisionReason: typeof body.reason === "string" ? body.reason : step.decisionReason ?? null,
      parameters:
        typeof body.parameters === "object" && body.parameters !== null
          ? (body.parameters as Record<string, unknown>)
          : step.parameters,
    });
  }),

  http.post("*/api/v1/plans/:id/approve", () => {
    const response: ApprovePlanResponse = {
      planId: MSW_PLAN_ID,
      status: "approved",
      job: mswJob,
    };
    return HttpResponse.json(response);
  }),

  http.get("*/api/v1/plans/:id/validation", () => HttpResponse.json(mswValidation)),

  http.get("*/api/v1/plans/:id/versions", () => HttpResponse.json(mswVersions)),

  http.post("*/api/v1/plans/:id/rollback", async ({ request }) => {
    const body = await readJsonBody(request);
    const reason = typeof body.reason === "string" ? body.reason : "";
    if (reason.trim().length < 10) {
      return problem(400, "REASON_REQUIRED", "Bad Request", "A rollback reason of at least 10 characters is required.");
    }
    const toVersionNo = typeof body.version === "number" ? body.version : 1;
    const response: RollbackResult = {
      rollbackId: "rollback-1",
      planId: MSW_PLAN_ID,
      fromVersionNo: 2,
      toVersionNo,
      job: { ...mswJob, id: "job-rollback", type: "rollback" },
    };
    return HttpResponse.json(response);
  }),

  http.post("*/api/v1/plans/:id/exports", async ({ request }) => {
    const body = await readJsonBody(request);
    const format = (typeof body.format === "string" ? body.format : "xlsx") as
      | "xlsx"
      | "csv"
      | "pipeline";
    const response: ExportResponse = {
      downloadUrl: `/api/v1/plans/${MSW_PLAN_ID}/exports/download.${format}`,
      expiresAt: "2026-02-02T11:45:00Z",
      format,
      versionNo: 2,
    };
    return HttpResponse.json(response);
  }),

  // ----- Model configuration ----------------------------------------------

  http.get("*/api/v1/model-config", () => HttpResponse.json(mswModelConfig)),

  http.get("*/api/v1/model-config/providers", () => HttpResponse.json(mswProviders)),

  http.post("*/api/v1/model-config/test", () =>
    HttpResponse.json({ ok: true, latencyMs: 128, message: "Connection OK" })
  ),

  http.put("*/api/v1/model-config", async ({ request }) => {
    const body = await readJsonBody(request);
    return HttpResponse.json({
      ...mswModelConfig,
      provider: typeof body.provider === "string" ? body.provider : mswModelConfig.provider,
      model: typeof body.model === "string" ? body.model : mswModelConfig.model,
      allowDataSharing:
        typeof body.allowDataSharing === "boolean"
          ? body.allowDataSharing
          : mswModelConfig.allowDataSharing,
      updatedAt: "2026-02-02T12:00:00Z",
    });
  }),

  // ----- Users --------------------------------------------------------------

  http.get("*/api/v1/users", () => HttpResponse.json(page(mswUsers))),

  http.post("*/api/v1/users/invites", async ({ request }) => {
    const body = await readJsonBody(request);
    const email = typeof body.email === "string" ? body.email : "";
    if (email === MSW_EXISTING_USER_EMAIL || mswUsers.some((user) => user.email === email)) {
      return problem(409, "USER_EXISTS", "Conflict", "This user already exists.");
    }
    const invite: UserInvite = {
      id: "invite-1",
      email,
      role: (typeof body.role === "string" ? body.role : "viewer") as UserInvite["role"],
      expiresAt: "2026-02-09T12:00:00Z",
      acceptedAt: null,
    };
    return HttpResponse.json(invite, { status: 201 });
  }),

  http.patch("*/api/v1/users/:id/role", async ({ params, request }) => {
    const body = await readJsonBody(request);
    const user = mswUsers.find((candidate) => candidate.id === params.id);
    if (!user) {
      return problem(404, "USER_NOT_FOUND", "Not Found", "That user no longer exists.");
    }
    return HttpResponse.json({
      ...user,
      role: (typeof body.role === "string" ? body.role : user.role) as User["role"],
    });
  }),

  http.post("*/api/v1/users/:id/deactivate", ({ params }) => {
    const user = mswUsers.find((candidate) => candidate.id === params.id);
    if (!user) {
      return problem(404, "USER_NOT_FOUND", "Not Found", "That user no longer exists.");
    }
    return HttpResponse.json({ ...user, status: "deactivated" });
  }),

  // ----- Audit trail -------------------------------------------------------

  http.get("*/api/v1/audit-events", () => HttpResponse.json(page(mswAuditEvents))),

  http.get("*/api/v1/audit-events/export", () =>
    HttpResponse.json({
      downloadUrl: "/api/v1/audit-events/export/download.csv",
      expiresAt: "2026-02-02T11:45:00Z",
    })
  ),

  // ----- Evaluation --------------------------------------------------------

  http.post("*/api/v1/evaluations", async ({ request }) => {
    const body = await readJsonBody(request);
    const benchmarkSet = typeof body.benchmarkSet === "string" ? body.benchmarkSet : "vendor-invoices-golden";
    return HttpResponse.json(
      {
        ...mswEvaluationRun,
        id: "evaluation-2",
        benchmarkSetId: benchmarkSet,
        benchmarkSetName: benchmarkSet,
        passRate: undefined,
        durationSeconds: undefined,
        finishedAt: null,
        startedAt: "2026-02-02T12:00:00Z",
      },
      { status: 202 }
    );
  }),

  http.get("*/api/v1/evaluations", () => HttpResponse.json([mswEvaluationRun])),

  http.get("*/api/v1/evaluations/:id", () => {
    const detail: EvaluationRunDetail = {
      ...mswEvaluationRun,
      detailedResults: [{ stepNo: 1, result: "passed" }],
    };
    return HttpResponse.json(detail);
  }),

  // ----- System configuration ---------------------------------------------

  http.get("*/api/v1/config/upload", () => HttpResponse.json(mswUploadConfig)),
];
