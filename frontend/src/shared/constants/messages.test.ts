import { describe, expect, it } from "vitest";
import {
  MSG_ENTER_REASON_MIN_10,
  MSG_EXPORT_BLOCKED_TESTS_FAILED,
  MSG_FORBIDDEN,
  MSG_GENERATING_PLAN,
  MESSAGES,
  approveConfirm,
  approvePlanLabel,
  datasetNameRules,
  fileTooLarge,
  formatDuration,
  planGenerationFailed,
  quarantinedBanner,
  rollbackConfirm,
  stepExceedsThreshold,
  totalEstLoss,
} from "./messages";

describe("canonical strings", () => {
  it("states the export gate copy exactly (FR-043)", () => {
    expect(MESSAGES.EXPORT_BLOCKED_TESTS_FAILED).toBe(
      "Export is blocked because 1 or more tests failed."
    );
    expect(MSG_EXPORT_BLOCKED_TESTS_FAILED).toBe(MESSAGES.EXPORT_BLOCKED_TESTS_FAILED);
  });

  it("states the rollback reason rule exactly", () => {
    expect(MESSAGES.ENTER_REASON_MIN_10).toBe("Enter a reason of at least 10 characters.");
    expect(MSG_ENTER_REASON_MIN_10).toBe(MESSAGES.ENTER_REASON_MIN_10);
  });

  it("states the forbidden copy exactly", () => {
    expect(MESSAGES.FORBIDDEN).toBe("You don't have access to this page.");
    expect(MSG_FORBIDDEN).toBe(MESSAGES.FORBIDDEN);
  });

  it("uses the single-character ellipsis for the generating state", () => {
    expect(MESSAGES.GENERATING_PLAN).toBe("Generating plan…");
    expect(MSG_GENERATING_PLAN).toBe(MESSAGES.GENERATING_PLAN);
    expect(MESSAGES.GENERATING_PLAN).not.toBe("Generating plan...");
  });
});

describe("plan copy", () => {
  it("counts decided steps on the approve button", () => {
    expect(approvePlanLabel(2, 5)).toBe("Approve plan (2 of 5 decided)");
    expect(MESSAGES.approvePlanLabel(2, 5)).toBe("Approve plan (2 of 5 decided)");
    expect(approvePlanLabel(0, 0)).toBe("Approve plan (0 of 0 decided)");
    expect(approvePlanLabel("2", "5")).toBe("Approve plan (2 of 5 decided)");
  });

  it("uses an en dash for the step range in the rollback copy", () => {
    expect(rollbackConfirm(2, 2, 3)).toBe(
      "Roll back to v2? Steps 2–3 will be undone. The rollback is itself logged and can be re-applied."
    );
    expect(MESSAGES.rollbackConfirm(2, 2, 3)).toBe(rollbackConfirm(2, 2, 3));
    expect(rollbackConfirm(2, 2, 3)).toContain("–");
    expect(rollbackConfirm(2, 2, 3)).not.toContain("2-3");
  });

  it("confirms how many steps get tests", () => {
    expect(approveConfirm(3)).toBe("Approve 3 steps? Unit and integration tests will be generated.");
    expect(MESSAGES.approveConfirm(3)).toBe(approveConfirm(3));
  });

  it("formats loss and threshold warnings", () => {
    expect(totalEstLoss(2.4)).toBe("Total est. loss: 2.4% of cells");
    expect(stepExceedsThreshold(3)).toBe(
      "Step 3 exceeds the loss threshold and needs a decision before approval."
    );
    expect(planGenerationFailed("no rules inferred")).toBe(
      "Plan generation failed: no rules inferred"
    );
  });
});

describe("shared page furniture", () => {
  it("pluralises counts by the parsed number, not the string", () => {
    expect(MESSAGES.PAGE_OF(2, 9)).toBe("Page 2 of 9");
    expect(MESSAGES.EVENTS_COUNT(1)).toBe("1 event");
    expect(MESSAGES.EVENTS_COUNT(4)).toBe("4 events");
    expect(MESSAGES.EVENTS_COUNT("1")).toBe("1 event");
    expect(MESSAGES.USERS_COUNT(1)).toBe("1 user");
    expect(MESSAGES.USERS_COUNT(12)).toBe("12 users");
    expect(MESSAGES.LOADING("Datasets")).toBe("Loading Datasets…");
  });

  it("formats durations under and over a minute", () => {
    expect(formatDuration(42)).toBe("42s");
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(60)).toBe("1m");
    expect(formatDuration(95)).toBe("1m 35s");
    expect(formatDuration(null)).toBe(MESSAGES.NOT_AVAILABLE);
    expect(formatDuration(undefined)).toBe(MESSAGES.NOT_AVAILABLE);
    expect(formatDuration(-1)).toBe(MESSAGES.NOT_AVAILABLE);
  });

  it("formats dataset and file copy", () => {
    expect(fileTooLarge(50)).toBe("The file is larger than 50 MB.");
    expect(MESSAGES.fileTooLarge(50)).toBe(fileTooLarge(50));
    expect(quarantinedBanner(3)).toBe("3 rows were quarantined during ingest. View rows");
    expect(datasetNameRules(2, 80)).toBe(
      "Use 2–80 characters: letters, numbers, spaces, dot, dash or underscore."
    );
  });
});
