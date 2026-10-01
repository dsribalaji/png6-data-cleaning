import { describe, expect, it } from "vitest";
import { isEvaluationRunning, toEvaluationRun } from "./api";

describe("toEvaluationRun (S10 shows the backend's benchmark run)", () => {
  const raw = {
    id: "r1",
    benchmarkSetId: "b1",
    status: "succeeded",
    startedAt: "2026-10-01T04:46:38.000Z",
    finishedAt: "2026-10-01T04:46:40.500Z",
    scores: {
      passed: true,
      llm_on: false,
      cases: [
        { caseId: "hr_employees", failures: [], rowCount: 6 },
        { caseId: "malformed", failures: ["quarantine missed row 2"], rowCount: 3 },
      ],
    },
  };

  it("derives pass rate, duration, model and per-case rows", () => {
    const run = toEvaluationRun(raw);
    expect(run.passRate).toBe(0.5);
    expect(run.durationSeconds).toBe(2.5);
    expect(run.modelName).toBe("Deterministic (AI off)");
    expect(run.passed).toBe(true);
    expect(run.detailedResults).toEqual([
      { case: "hr_employees", result: "passed", rows: 6, details: "" },
      { case: "malformed", result: "failed", rows: 3, details: "quarantine missed row 2" },
    ]);
  });

  it("stops polling a failed run even without finishedAt", () => {
    expect(isEvaluationRunning({ status: "failed", finishedAt: null })).toBe(false);
    expect(isEvaluationRunning({ status: "running", finishedAt: null })).toBe(true);
  });
});
