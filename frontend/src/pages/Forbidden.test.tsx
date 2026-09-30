import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { Forbidden } from "./Forbidden";
import { useSessionStore } from "../auth/session.store";
import { MESSAGES } from "../shared/constants/messages";

function renderForbidden() {
  return render(
    <MemoryRouter initialEntries={["/403"]}>
      <Routes>
        <Route path="/403" element={<Forbidden />} />
        <Route path="/login" element={<p>Sign in page</p>} />
        <Route path="/datasets" element={<p>Datasets page</p>} />
        <Route path="/settings/model" element={<p>Model settings page</p>} />
        <Route path="/audit" element={<p>Audit page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  useSessionStore.setState({ accessToken: null, user: null });
});

describe("Forbidden", () => {
  it("explains the refusal in plain language", () => {
    renderForbidden();

    expect(screen.getByRole("heading", { name: "403 Forbidden" })).toBeInTheDocument();
    expect(screen.getByText(MESSAGES.FORBIDDEN)).toBeInTheDocument();
  });

  it("sends a signed-out visitor to the sign-in page", async () => {
    renderForbidden();
    const user = userEvent.setup();

    expect(screen.getByRole("button", { name: MESSAGES.SIGN_IN })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: MESSAGES.SIGN_IN }));

    expect(await screen.findByText("Sign in page")).toBeInTheDocument();
  });

  it("sends a signed-in engineer back to their own landing page", async () => {
    useSessionStore.getState().setSession("token", {
      id: "user-1",
      email: "engineer@example.com",
      role: "data_engineer",
    });
    renderForbidden();
    const user = userEvent.setup();

    const button = screen.getByRole("button", { name: "Back to Dashboard" });
    expect(button).toBeInTheDocument();
    await user.click(button);

    expect(await screen.findByText("Datasets page")).toBeInTheDocument();
  });

  it("sends an administrator back to the model settings page", async () => {
    useSessionStore.getState().setSession("token", {
      id: "user-2",
      email: "admin@example.com",
      role: "administrator",
    });
    renderForbidden();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Back to Dashboard" }));

    expect(await screen.findByText("Model settings page")).toBeInTheDocument();
  });

  it("sends an auditor back to the audit trail", async () => {
    useSessionStore.getState().setSession("token", {
      id: "user-3",
      email: "auditor@example.com",
      role: "auditor",
    });
    renderForbidden();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Back to Dashboard" }));

    expect(await screen.findByText("Audit page")).toBeInTheDocument();
  });
});
