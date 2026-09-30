import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { api, ApiError, type ProblemDetail } from "./client";
import { useSessionStore } from "../auth/session.store";
import { server } from "../test/msw/server";
import {
  MSW_ACCESS_TOKEN,
  MSW_REFRESHED_ACCESS_TOKEN,
  MSW_WRONG_PASSWORD,
  problem,
} from "../test/msw/handlers";

const DATA_ENGINEER = { id: "user-1", email: "engineer@example.com", role: "data_engineer" } as const;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSessionStore.setState({ accessToken: null, user: null });
});
afterAll(() => server.close());

describe("api auth header", () => {
  it("sends the Bearer token once a session exists", async () => {
    let authorization: string | null = null;
    server.use(
      http.get("*/api/v1/datasets", ({ request }) => {
        authorization = request.headers.get("Authorization");
        return HttpResponse.json({ items: [], page: 1, pageSize: 20, total: 0 });
      })
    );

    useSessionStore.getState().setSession(MSW_ACCESS_TOKEN, DATA_ENGINEER);
    await api.get("datasets").json();

    expect(authorization).toBe(`Bearer ${MSW_ACCESS_TOKEN}`);
  });

  it("sends no Authorization header when nobody is signed in", async () => {
    let seen: string | null = "unset";
    server.use(
      http.get("*/api/v1/datasets", ({ request }) => {
        seen = request.headers.get("Authorization");
        return HttpResponse.json({ items: [], page: 1, pageSize: 20, total: 0 });
      })
    );

    await api.get("datasets").json();

    expect(seen).toBeNull();
  });
});

describe("api 401 handling", () => {
  it("refreshes once and replays the request with the new token", async () => {
    let datasetCalls = 0;
    let refreshCalls = 0;
    server.use(
      http.post("*/api/v1/auth/refresh", () => {
        refreshCalls += 1;
        return HttpResponse.json({ accessToken: MSW_REFRESHED_ACCESS_TOKEN });
      }),
      http.get("*/api/v1/datasets", ({ request }) => {
        datasetCalls += 1;
        if (request.headers.get("Authorization") === `Bearer ${MSW_REFRESHED_ACCESS_TOKEN}`) {
          return HttpResponse.json({ items: [], page: 1, pageSize: 20, total: 7 });
        }
        return problem(401, "TOKEN_EXPIRED", "Unauthorized", "The access token has expired.");
      })
    );

    useSessionStore.getState().setSession(MSW_ACCESS_TOKEN, DATA_ENGINEER);
    const body = await api.get("datasets").json<{ total: number }>();

    expect(body.total).toBe(7);
    expect(datasetCalls).toBe(2);
    expect(refreshCalls).toBe(1);
    expect(useSessionStore.getState().accessToken).toBe(MSW_REFRESHED_ACCESS_TOKEN);
    expect(useSessionStore.getState().user).toEqual(DATA_ENGINEER);
  });

  it("clears the session when the refresh itself fails", async () => {
    server.use(
      http.post("*/api/v1/auth/refresh", () => problem(401, "INVALID_REFRESH", "Unauthorized")),
      http.get("*/api/v1/datasets", () =>
        problem(401, "TOKEN_EXPIRED", "Unauthorized", "The access token has expired.")
      )
    );

    useSessionStore.getState().setSession(MSW_ACCESS_TOKEN, DATA_ENGINEER);

    await expect(api.get("datasets").json()).rejects.toBeInstanceOf(Error);
    expect(useSessionStore.getState().accessToken).toBeNull();
    expect(useSessionStore.getState().user).toBeNull();
  });

  it("never tries to refresh a failed sign-in", async () => {
    let refreshCalls = 0;
    server.use(
      http.post("*/api/v1/auth/refresh", () => {
        refreshCalls += 1;
        return HttpResponse.json({ accessToken: MSW_REFRESHED_ACCESS_TOKEN });
      })
    );

    await expect(
      api.post("auth/login", { json: { email: "engineer@example.com", password: MSW_WRONG_PASSWORD } }).json()
    ).rejects.toBeInstanceOf(ApiError);

    expect(refreshCalls).toBe(0);
  });
});

describe("ApiError", () => {
  it("carries the problem fields through from problem+json", async () => {
    server.use(
      http.get("*/api/v1/datasets/dataset-9", () =>
        problem(409, "DATASET_NAME_TAKEN", "Conflict", "A dataset with this name already exists.")
      )
    );

    const error = await api.get("datasets/dataset-9").json().catch((err: unknown) => err);

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.code).toBe("DATASET_NAME_TAKEN");
    expect(apiError.title).toBe("Conflict");
    expect(apiError.detail).toBe("A dataset with this name already exists.");
    expect(apiError.message).toBe("A dataset with this name already exists.");
    expect(apiError.problem.status).toBe(409);
  });

  it("falls back to the status line when the body is not JSON", async () => {
    server.use(
      http.get("*/api/v1/model-config", () =>
        HttpResponse.text("upstream is down", { status: 502, statusText: "Bad Gateway" })
      )
    );

    const error = (await api.get("model-config").json().catch((err: unknown) => err)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.detail).toBe("HTTP error 502");
    expect(error.code).toBeUndefined();
  });

  it("reads a plain application/json error body too", async () => {
    server.use(
      http.get("*/api/v1/audit-events", () =>
        HttpResponse.json(
          { title: "Bad Request", status: 400, code: "INVALID_DATE_RANGE", detail: "from > to" },
          { status: 400, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    const error = (await api.get("audit-events").json().catch((err: unknown) => err)) as ApiError;

    expect(error.status).toBe(400);
    expect(error.code).toBe("INVALID_DATE_RANGE");
    expect(error.detail).toBe("from > to");
  });

  it("keeps field errors when the backend sends them", () => {
    const problemDetail: ProblemDetail = {
      title: "Unprocessable Entity",
      status: 422,
      code: "VALIDATION_FAILED",
      errors: { name: ["Enter a dataset name."] },
    };
    const error = new ApiError(problemDetail);

    expect(error.status).toBe(422);
    expect(error.message).toBe("Unprocessable Entity");
    expect(error.errors).toEqual({ name: ["Enter a dataset name."] });
  });
});

describe("api happy path", () => {
  it("reaches the stubbed dataset list", async () => {
    const body = await api.get("datasets").json<{ total: number; items: Array<{ id: string }> }>();

    expect(body.total).toBe(1);
    expect(body.items[0]?.id).toBe("dataset-1");
  });
});
