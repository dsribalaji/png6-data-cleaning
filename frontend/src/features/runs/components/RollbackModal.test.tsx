import "@testing-library/jest-dom/vitest";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ROLLBACK_REASON_MAX_LENGTH,
  ROLLBACK_REASON_MIN_LENGTH,
  RollbackModal,
  rollbackReasonSchema,
} from "./RollbackModal";
import type { Version } from "../api";
import { MSG_ENTER_REASON_MIN_10, MESSAGES, rollbackConfirm } from "../../../shared/constants/messages";

const VERSION: Version = {
  n: 2,
  createdAt: "2026-02-02T11:05:30Z",
  rows: 1200,
  cols: 9,
  isCurrent: false,
};

function renderModal(overrides: Partial<Parameters<typeof RollbackModal>[0]> = {}) {
  const onClose = vi.fn();
  const onConfirm = vi.fn();
  const props = {
    isOpen: true,
    version: VERSION,
    fromStep: 3,
    toStep: 5,
    onClose,
    onConfirm,
    ...overrides,
  };
  const view = render(<RollbackModal {...props} />);
  return { ...view, onClose, onConfirm };
}

/**
 * The shared Modal focuses its Close button ~50ms after opening (one-shot
 * timer). Typing before that timer fires gets truncated when focus is yanked
 * away, so tests that type must wait for the focus to land first.
 */
async function settleModalFocus() {
  await waitFor(
    () => expect(screen.getByRole("button", { name: /close modal/i })).toHaveFocus(),
    { timeout: 2000 }
  );
}

describe("RollbackModal copy", () => {
  it("renders nothing while closed", () => {
    renderModal({ isOpen: false });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText(MESSAGES.ROLL_BACK)).not.toBeInTheDocument();
  });

  it("states what the rollback undoes, with the en dash range", () => {
    renderModal();

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: MESSAGES.ROLL_BACK })).toBeInTheDocument();
    expect(screen.getByText(rollbackConfirm(2, 3, 5))).toBeInTheDocument();
    expect(screen.getByText(rollbackConfirm(2, 3, 5))).toHaveTextContent("Steps 3–5");
  });

  it("shows the reason field with its length hint", () => {
    renderModal();

    expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();
    expect(screen.getByText(`10-500 characters`)).toBeInTheDocument();
    expect(screen.getByText(`0/${ROLLBACK_REASON_MAX_LENGTH}`)).toBeInTheDocument();
  });
});

describe("RollbackModal reason validation", () => {
  it("refuses an empty reason and never calls onConfirm", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderModal();

    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));

    expect(await screen.findByRole("alert")).toHaveTextContent(MSG_ENTER_REASON_MIN_10);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("refuses a reason of nine characters", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderModal();
    await settleModalFocus();

    await user.type(screen.getByLabelText(/reason/i), "too short");
    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));

    expect(await screen.findByRole("alert")).toHaveTextContent(MSG_ENTER_REASON_MIN_10);
    expect(onConfirm).not.toHaveBeenCalled();
    expect("too short".length).toBeLessThan(ROLLBACK_REASON_MIN_LENGTH);
  });

  it("accepts exactly ten characters and hands the reason over", async () => {
    const user = userEvent.setup();
    const { onConfirm } = renderModal();
    const reason = "vendor ids";
    await settleModalFocus();

    expect(reason).toHaveLength(ROLLBACK_REASON_MIN_LENGTH);
    await user.type(screen.getByLabelText(/reason/i), reason);
    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(reason);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("clears the inline error as soon as the reason changes", async () => {
    const user = userEvent.setup();
    renderModal();
    await settleModalFocus();

    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/reason/i), "a");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("prefers the local error over the server error", async () => {
    const user = userEvent.setup();
    renderModal({ error: "The rollback could not be started." });

    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));
    expect(await screen.findByRole("alert")).toHaveTextContent(MSG_ENTER_REASON_MIN_10);
  });

  it("shows the server error when there is no local one", () => {
    renderModal({ error: "A job of this type is already running for this item." });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "A job of this type is already running for this item."
    );
  });

  it("marks the textarea invalid while an error is shown", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("button", { name: MESSAGES.ROLL_BACK }));
    await screen.findByRole("alert");

    expect(screen.getByLabelText(/reason/i)).toHaveAttribute("aria-invalid", "true");
  });

  it("closes without confirming when Cancel is pressed", async () => {
    const user = userEvent.setup();
    const { onClose, onConfirm } = renderModal();

    await user.click(screen.getByRole("button", { name: MESSAGES.CANCEL }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("resets the reason when it is reopened", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    const { rerender } = render(
      <RollbackModal isOpen version={VERSION} fromStep={3} toStep={5} onClose={onClose} onConfirm={onConfirm} />
    );

    // fireEvent (not user.type): the Modal's 50ms focus-on-open timer can steal
    // focus mid-typing under load and truncate the value — this is setup, not
    // the interaction under test.
    fireEvent.change(screen.getByLabelText(/reason/i), { target: { value: "vendor ids" } });
    expect(screen.getByLabelText(/reason/i)).toHaveValue("vendor ids");

    rerender(
      <RollbackModal isOpen={false} version={null} fromStep={3} toStep={5} onClose={onClose} onConfirm={onConfirm} />
    );
    rerender(
      <RollbackModal isOpen version={VERSION} fromStep={3} toStep={5} onClose={onClose} onConfirm={onConfirm} />
    );

    expect(screen.getByLabelText(/reason/i)).toHaveValue("");
    expect(screen.getByText(`0/${ROLLBACK_REASON_MAX_LENGTH}`)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("rollbackReasonSchema", () => {
  it("accepts 10 to 500 characters", () => {
    expect(rollbackReasonSchema.safeParse("x".repeat(10)).success).toBe(true);
    expect(rollbackReasonSchema.safeParse("x".repeat(500)).success).toBe(true);
  });

  it("rejects fewer than 10 and more than 500 characters", () => {
    expect(rollbackReasonSchema.safeParse("x".repeat(9)).success).toBe(false);
    expect(rollbackReasonSchema.safeParse("").success).toBe(false);
    expect(rollbackReasonSchema.safeParse("x".repeat(501)).success).toBe(false);
  });

  it("reports the canonical message", () => {
    const result = rollbackReasonSchema.safeParse("short");

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe(MSG_ENTER_REASON_MIN_10);
    }
  });
});
