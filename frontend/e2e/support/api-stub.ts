import { Buffer } from "node:buffer";
import type { Page, Route } from "@playwright/test";

/**
 * Playwright stubs for the whole `/api/v1` surface.
 *
 * The SPA keeps its access token in memory (src/auth/session.store.ts) and the
 * backend is not part of the E2E loop, so every spec routes the API to fixed
 * fixtures here. `stubApi` records every call so a spec can assert on the
 * requests the UI made without a server log.
 */

export const E2E_PASSWORD = "correct-horse-battery";
export const E2E_WRONG_PASSWORD = "definitely-wrong-pass";
export const DATASET_ID = "dataset-1";
export const PLAN_ID = "plan-1";
export const NEW_DATASET_NAME = "Q3 vendor invoices";
export const ROLLBACK_REASON = "vendor ids were mapped to the wrong column";
export const UPLOAD_FILE = {
  name: "VendorInvoices_uncleaned.xlsx",
  mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  buffer: Buffer.from("stubbed workbook"),
};

export type StubRole = "data_engineer" | "administrator" | "auditor" | "viewer";

export interface StubOptions {
  role: StubRole;
  datasetId?: string;
  planId?: string;
  /** When set, every sign-in is answered with 401 problem+json. */
  rejectSignIn?: boolean;
}

export interface StubApi {
  /** `"GET /datasets"`, `"POST /plans/plan-1/rollback"`, … in call order. */
  calls: string[];
  /** Requests the SPA made that no stub matched. */
  unhandled: string[];
}

interface Reply {
  status?: number;
  json?: unknown;
  text?: string;
  contentType?: string;
}

function problem(status: number, code: string, title: string, detail?: string): Reply {
  return {
    status,
    json: {
      type: `https://png6.local/problems/${code.toLowerCase()}`,
      title,
      status,
      code,
      ...(detail ? { detail } : {}),
    },
    contentType: "application/problem+json",
  };
}

function user(role: StubRole, email: string) {
  return {
    id: "user-1",
    email,
    firstName: "Tita",
    lastName: "Engineer",
    role,
    status: "active",
    createdAt: "2026-01-05T09:00:00Z",
  };
}

function dataset(overrides: Record<string, unknown> = {}) {
  return {
    id: DATASET_ID,
    name: "Vendor invoices",
    source: "upload",
    fileName: "VendorInvoices_uncleaned.xlsx",
    rowCount: 1200,
    columnCount: 9,
    status: "profiled",
    ingestedAt: "2026-02-02T10:00:00Z",
    uploadedBy: "user-1",
    quarantineCount: 3,
    activePlanId: PLAN_ID,
    fileSize: 248320,
    mimeType: UPLOAD_FILE.mimeType,
    ...overrides,
  };
}

function planSteps(planId: string) {
  return [
    {
      id: "step-1",
      planId,
      stepNo: 1,
      operation: "standardise_format",
      summary: "Standardise the format of vendor_name",
      parameters: { column: "vendor_name", strategy: "title_case" },
      rationale: "18 spelling variants of the same vendor.",
      confidence: 0.94,
      decision: "accepted",
      decidedBy: "user-1",
      decidedAt: "2026-02-02T11:00:00Z",
      lossEstimate: {
        rowsAffected: 214,
        columnsAffected: 1,
        cellsAffected: 214,
        estimatedLoss: 0.02,
      },
    },
    {
      id: "step-2",
      planId,
      stepNo: 2,
      operation: "fill_missing",
      summary: "Fill missing values in total using the median",
      parameters: { column: "total", strategy: "median" },
      rationale: "40 invoices have no total; the median keeps the column comparable.",
      confidence: 0.77,
      decision: "accepted",
      decidedBy: "user-1",
      decidedAt: "2026-02-02T11:01:00Z",
      lossEstimate: {
        rowsAffected: 40,
        columnsAffected: 1,
        cellsAffected: 40,
        estimatedLoss: 0.004,
      },
    },
  ];
}

function plan(planId: string) {
  return {
    id: planId,
    datasetId: DATASET_ID,
    status: "in_review",
    totalEstimatedLoss: 0.024,
    lossThreshold: 0.05,
    createdAt: "2026-02-02T10:30:00Z",
    steps: planSteps(planId),
  };
}

function validationReport() {
  return {
    planId: PLAN_ID,
    versionNo: 2,
    allPassed: true,
    unitSummary: { passed: 2, total: 2 },
    integrationSummary: { passed: 1, total: 1 },
    testRuns: [
      {
        id: "run-1",
        testCaseId: "case-1",
        testCaseName: "vendor_name is title-cased",
        type: "unit",
        targetStepNo: 1,
        versionNo: 2,
        phase: "after",
        result: "passed",
        runAt: "2026-02-02T11:06:00Z",
        durationMs: 42,
      },
      {
        id: "run-2",
        testCaseId: "case-2",
        testCaseName: "row count is preserved",
        type: "integration",
        targetStepNo: 2,
        versionNo: 2,
        phase: "after",
        result: "passed",
        runAt: "2026-02-02T11:06:01Z",
        durationMs: 88,
      },
    ],
    reconciliations: [
      {
        id: "recon-1",
        planId: PLAN_ID,
        versionNo: 2,
        checkName: "Row count is preserved",
        sourceValue: 1200,
        outputValue: 1200,
        ok: true,
      },
    ],
  };
}

function versions() {
  return [
    {
      id: "version-2",
      planId: PLAN_ID,
      versionNo: 2,
      stepId: "step-2",
      stepNo: 2,
      operation: "fill_missing",
      executedAt: "2026-02-02T11:05:30Z",
      executedBy: "user-1",
    },
    {
      id: "version-1",
      planId: PLAN_ID,
      versionNo: 1,
      stepId: "step-1",
      stepNo: 1,
      operation: "standardise_format",
      executedAt: "2026-02-02T11:05:10Z",
      executedBy: "user-1",
    },
  ];
}

/** One working dataset is enough for the E2E flows, so it is reused. */
interface StubState {
  /** Name of the file the spec uploaded, once it has been through POST /datasets. */
  uploadedName: string | null;
  /** Set by POST /datasets/{id}/plans; releases the held SSE stream. */
  planRequested: boolean;
}

const SSE_WAIT_MS = 12_000;

/**
 * GET /datasets/{id}/events (SSE).
 *
 * The page subscribes on mount and only routes to the plan once a
 * `PlanGenerated` event arrives, so the stream is held open until the spec has
 * actually asked for a plan. That keeps the profile page stable for the RBAC
 * specs while the happy path still gets its event. Capped below the client's
 * 15s heartbeat watchdog so the connection is never aborted mid-test.
 */
async function fulfilEventStream(
  route: Route,
  state: StubState,
  planId: string
): Promise<void> {
  const deadline = Date.now() + SSE_WAIT_MS;
  while (!state.planRequested && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  const event = state.planRequested
    ? {
        jobId: "job-1",
        type: "PlanGenerated",
        status: "succeeded",
        progressPct: 100,
        message: "The plan is ready for review.",
        planId,
      }
    : null;

  try {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-cache", Connection: "keep-alive" },
      body: event ? `id: 1\ndata: ${JSON.stringify(event)}\n\n` : ": ping\n\n",
    });
  } catch {
    // The page navigated away or the stream was aborted; nothing to send.
  }
}

/** Dispatch table: first match wins, so the specific paths come first. */
function replyFor(
  method: string,
  path: string,
  rawBody: string | null,
  options: Required<StubOptions>,
  state: StubState
): Reply {
  const { role, datasetId, planId } = options;

  if (method === "POST" && path === "/auth/login") {
    let password = "";
    try {
      const parsed = JSON.parse(rawBody ?? "{}") as { password?: string };
      password = parsed.password ?? "";
    } catch {
      password = "";
    }
    if (options.rejectSignIn || password !== E2E_PASSWORD) {
      return problem(401, "INVALID_CREDENTIALS", "Unauthorized", "Email or password is incorrect.");
    }
    return { json: { accessToken: "e2e-access-token", user: user(role, "engineer@example.com") } };
  }

  if (method === "POST" && path === "/auth/refresh") {
    return { json: { accessToken: "e2e-refreshed-token", user: user(role, "engineer@example.com") } };
  }
  if (method === "POST" && path === "/auth/logout") return { json: { message: "Signed out." } };
  if (method === "GET" && path === "/auth/me") return { json: user(role, "engineer@example.com") };

  const workingName = state.uploadedName ?? "Vendor invoices";

  if (method === "GET" && path === "/datasets") {
    return { json: { items: [dataset({ name: workingName })], page: 1, pageSize: 20, total: 1 } };
  }
  if (method === "POST" && path === "/datasets") {
    const name = /name="([^"]*)"/.exec(rawBody ?? "")?.[1] ?? NEW_DATASET_NAME;
    state.uploadedName = name;
    return { json: dataset({ name, status: "profiling", activePlanId: null }) };
  }

  if (method === "GET" && path === `/datasets/${datasetId}/profile`) {
    return {
      json: {
        datasetId,
        summary: {
          rowCount: 1200,
          columnCount: 9,
          columnsWithNullsCount: 3,
          nestedColumnsCount: 1,
          quarantinedRowsCount: 3,
        },
        columns: [
          {
            id: "col-1",
            datasetId,
            columnName: "invoice_id",
            ordinal: 1,
            physicalType: "string",
            semanticType: "identifier",
            nullCount: 0,
            nullPct: 0,
            distinctCount: 1200,
            flags: [],
          },
          {
            id: "col-2",
            datasetId,
            columnName: "vendor_name",
            ordinal: 2,
            physicalType: "string",
            semanticType: "text",
            nullCount: 120,
            nullPct: 10,
            distinctCount: 214,
            flags: ["nulls"],
          },
        ],
      },
    };
  }
  if (method === "GET" && path === `/datasets/${datasetId}/rules`) {
    return {
      json: [
        {
          id: "rule-1",
          datasetId,
          ruleType: "primary_key",
          columns: ["invoice_id"],
          expression: { source: "invoice_id" },
          confidence: 0.98,
          evidenceRows: [{ invoice_id: "INV-0001" }],
        },
      ],
    };
  }
  if (method === "GET" && path === `/datasets/${datasetId}/quarantine`) {
    return {
      json: {
        items: [
          {
            id: "q-1",
            datasetId,
            rowRef: 41,
            reason: "Unparseable date in invoice_date",
            rowData: { invoice_id: "INV-0041" },
            createdAt: "2026-02-02T10:00:05Z",
          },
        ],
        page: 1,
        pageSize: 50,
        total: 1,
      },
    };
  }
  if (method === "POST" && path === `/datasets/${datasetId}/plans`) {
    state.planRequested = true;
    return { json: { ...plan(planId), planId, job: null } };
  }
  if (method === "GET" && path === `/datasets/${datasetId}`) return { json: dataset({ name: workingName }) };

  if (method === "GET" && path === `/plans/${planId}`) return { json: plan(planId) };
  if (method === "PATCH" && new RegExp(`^/plans/${planId}/steps/`).test(path)) {
    return { json: planSteps(planId)[0] };
  }
  if (method === "POST" && path === `/plans/${planId}/approve`) {
    return {
      json: {
        planId,
        status: "approved",
        job: {
          id: "job-1",
          datasetId,
          planId,
          type: "execute",
          status: "queued",
          progressPct: 0,
          startedAt: "2026-02-02T11:05:00Z",
          finishedAt: null,
        },
      },
    };
  }
  if (method === "GET" && path === `/plans/${planId}/validation`) return { json: validationReport() };
  if (method === "GET" && path === `/plans/${planId}/versions`) return { json: versions() };
  if (method === "POST" && path === `/plans/${planId}/rollback`) {
    let reason = "";
    try {
      const parsed = JSON.parse(rawBody ?? "{}") as { reason?: string };
      reason = parsed.reason ?? "";
    } catch {
      reason = "";
    }
    if (reason.trim().length < 10) {
      return problem(
        400,
        "REASON_REQUIRED",
        "Bad Request",
        "A rollback reason of at least 10 characters is required."
      );
    }
    return {
      json: {
        rollbackId: "rollback-1",
        planId,
        fromVersionNo: 2,
        toVersionNo: 1,
        job: {
          id: "job-rollback",
          datasetId,
          planId,
          type: "rollback",
          status: "queued",
          progressPct: 0,
          startedAt: "2026-02-02T11:20:00Z",
          finishedAt: null,
        },
      },
    };
  }
  if (method === "POST" && path === `/plans/${planId}/exports`) {
    let format = "xlsx";
    try {
      const parsed = JSON.parse(rawBody ?? "{}") as { format?: string };
      format = parsed.format ?? format;
    } catch {
      format = "xlsx";
    }
    return {
      json: {
        downloadUrl: `/api/v1/plans/${planId}/exports/download.${format}`,
        expiresAt: "2026-02-02T11:45:00Z",
        format,
        versionNo: 2,
      },
    };
  }
  if (method === "GET" && path.startsWith(`/plans/${planId}/exports/download`)) {
    return {
      contentType: "application/octet-stream",
      text: "stubbed export body",
    };
  }

  if (method === "GET" && path === "/model-config") {
    return {
      json: {
        id: "model-config-1",
        provider: "ollama",
        model: "llama3.1",
        endpointUrl: "http://localhost:11434",
        credentialLast4: "cdef",
        allowDataSharing: false,
        isActive: true,
        updatedBy: "user-1",
        updatedAt: "2026-01-20T12:00:00Z",
      },
    };
  }
  if (method === "GET" && path === "/model-config/providers") {
    return {
      json: [
        {
          id: "ollama",
          name: "Ollama (self-hosted)",
          models: [{ id: "llama3.1", name: "Llama 3.1" }],
          requiresEndpoint: true,
        },
      ],
    };
  }

  if (method === "GET" && path === "/users") {
    return {
      json: {
        items: [user(role, "engineer@example.com"), user("auditor", "auditor@example.com")],
        page: 1,
        pageSize: 50,
        total: 2,
      },
    };
  }

  if (method === "GET" && path === "/audit-events") {
    return {
      json: {
        items: [
          {
            id: "audit-1",
            occurredAt: "2026-02-02T11:05:30Z",
            userId: "user-1",
            userEmail: "engineer@example.com",
            userRole: role,
            eventType: "plan.execute",
            objectType: "plan",
            objectId: PLAN_ID,
            details: {},
          },
        ],
        page: 1,
        pageSize: 50,
        total: 1,
      },
    };
  }

  if (method === "GET" && path === "/evaluations") {
    return {
      json: [
        {
          id: "evaluation-1",
          benchmarkSetId: "vendor-invoices-golden",
          benchmarkSetName: "vendor-invoices-golden",
          modelName: "llama3.1",
          passRate: 0.94,
          startedAt: "2026-02-01T08:00:00Z",
          durationSeconds: 74,
          finishedAt: "2026-02-01T08:01:14Z",
          scores: { recovered: 0.94 },
        },
      ],
    };
  }
  if (method === "GET" && path.startsWith("/evaluations/")) {
    return { json: { id: "evaluation-1", benchmarkSetId: "vendor-invoices-golden", startedAt: "2026-02-01T08:00:00Z", detailedResults: [] } };
  }

  if (method === "GET" && path === "/config/upload") {
    return {
      json: { maxFileSizeMb: 50, allowedExtensions: [".xlsx", ".csv"], n8nFolder: "/srv/n8n/out" },
    };
  }

  return problem(404, "NOT_STUBBED", "Not Found", `No E2E stub for ${method} ${path}`);
}

export async function stubApi(page: Page, options: StubOptions): Promise<StubApi> {
  const resolved: Required<StubOptions> = {
    role: options.role,
    datasetId: options.datasetId ?? DATASET_ID,
    planId: options.planId ?? PLAN_ID,
    rejectSignIn: options.rejectSignIn ?? false,
  };
  const api: StubApi = { calls: [], unhandled: [] };
  const state: StubState = { uploadedName: null, planRequested: false };

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname.replace(/^\/api\/v1/, "");
    api.calls.push(`${method} ${path}`);

    if (method === "GET" && path === `/datasets/${resolved.datasetId}/events`) {
      await fulfilEventStream(route, state, resolved.planId);
      return;
    }

    const reply = replyFor(method, path, request.postData(), resolved, state);
    if (reply.status === 404 && reply.json && (reply.json as { code?: string }).code === "NOT_STUBBED") {
      api.unhandled.push(`${method} ${path}`);
    }

    try {
      if (reply.text !== undefined) {
        await route.fulfill({
          status: reply.status ?? 200,
          contentType: reply.contentType ?? "text/plain; charset=utf-8",
          body: reply.text,
        });
        return;
      }

      await route.fulfill({
        status: reply.status ?? 200,
        contentType: reply.contentType ?? "application/json",
        body: JSON.stringify(reply.json ?? {}),
      });
    } catch {
      // React Query cancels requests on unmount; an aborted route is expected.
    }
  });

  return api;
}

/** Fills in the sign-in form and waits for the SPA to route away from /login. */
export async function signIn(page: Page, password: string = E2E_PASSWORD): Promise<void> {
  await page.getByLabel(/work email/i).fill("engineer@example.com");
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 15_000 });
}

/**
 * In-SPA navigation.
 *
 * `page.goto` would rebuild the app and wipe the in-memory session, so the
 * specs move between routes with the History API and let react-router pick the
 * change up through its own popstate listener.
 */
export async function gotoInApp(page: Page, path: string): Promise<void> {
  await page.evaluate((target) => {
    window.history.pushState({}, "", target);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
}
