import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  DATASET_STATUS_LABEL,
  DATASET_STATUS_OPTIONS,
  DATASET_STATUS_VARIANT,
  StatusBadge,
} from "./StatusBadge";
import type { DatasetStatus } from "../../../api/schema";

const ALL_STATUSES: DatasetStatus[] = [
  "profiling",
  "profiled",
  "plan_ready",
  "approved",
  "executed",
  "tests_failed",
  "failed",
  "rolled_back",
];

/** The badge wraps its label, so the variant classes live one span up. */
function pill(label: string): HTMLElement {
  const element = screen.getByText(label).parentElement;
  if (!element) throw new Error(`No badge found for "${label}"`);
  return element;
}

describe("StatusBadge", () => {
  it.each(ALL_STATUSES)("labels %s in plain language", (status) => {
    render(<StatusBadge status={status} />);

    expect(screen.getByText(DATASET_STATUS_LABEL[status])).toBeInTheDocument();
  });

  it("shows Unknown rather than an empty pill when the status is missing", () => {
    render(<StatusBadge status={undefined} />);

    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("keeps colour and label paired for the failure states", () => {
    const { rerender } = render(<StatusBadge status="tests_failed" />);
    expect(pill("Tests failed")).toHaveClass("text-rose-700");

    rerender(<StatusBadge status="executed" />);
    expect(pill("Executed")).toHaveClass("text-emerald-700");

    rerender(<StatusBadge status="plan_ready" />);
    expect(pill("Plan ready")).toHaveClass("text-amber-700");

    rerender(<StatusBadge status="rolled_back" />);
    expect(pill("Rolled back")).toHaveClass("text-gray-700");
  });

  it("uses the neutral pill for an unknown status", () => {
    render(<StatusBadge status={undefined} />);

    expect(pill("Unknown")).toHaveClass("text-gray-700");
  });

  it("passes the caller's className through", () => {
    render(<StatusBadge status="profiled" className="mr-2" />);

    expect(pill("Profiled")).toHaveClass("mr-2");
  });
});

describe("status maps", () => {
  it("covers every dataset status exactly once", () => {
    expect(Object.keys(DATASET_STATUS_LABEL).sort()).toEqual([...ALL_STATUSES].sort());
    expect(Object.keys(DATASET_STATUS_VARIANT).sort()).toEqual([...ALL_STATUSES].sort());
    expect([...DATASET_STATUS_OPTIONS].sort()).toEqual([...ALL_STATUSES].sort());
  });

  it("uses the PRD colours", () => {
    expect(DATASET_STATUS_VARIANT).toEqual({
      profiling: "info",
      profiled: "info",
      plan_ready: "warning",
      approved: "success",
      executed: "success",
      tests_failed: "danger",
      failed: "danger",
      rolled_back: "secondary",
    });
  });

  it("never leaves a status without a visible label", () => {
    for (const status of ALL_STATUSES) {
      expect(DATASET_STATUS_LABEL[status].length).toBeGreaterThan(0);
    }
  });
});
