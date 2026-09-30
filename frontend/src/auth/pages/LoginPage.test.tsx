import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { LoginPage } from "./LoginPage";
import { useSessionStore } from "../session.store";
import { MESSAGES } from "../../shared/constants/messages";
import { server } from "../../test/msw/server";
import { MSW_ACCESS_TOKEN, problem } from "../../test/msw/handlers";

const EMAIL = "engineer@example.com";
/** The form requires at least 12 characters, so the 401 sentinel cannot be typed. */
const VALID_PASSWORD = "correct-horse-battery";
const WRONG_PASSWORD = "not-my-password!";

function renderLogin(initialEntry = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/datasets" element={<p>Landing: datasets</p>} />
        <Route path="/settings/model" element={<p>Landing: model settings</p>} />
        <Route path="/audit" element={<p>Landing: audit trail</p>} />
      </Routes>
    </MemoryRouter>
  );
}

async function signIn(password = VALID_PASSWORD, email = EMAIL) {
  const user = userEvent.setup();
  if (email) {
    await user.type(screen.getByLabelText(/work email/i), email);
  }
  if (password) {
    await user.type(
      screen.getByLabelText(/password/i, { selector: "input" }),
      password
    );
  }
  await user.click(screen.getByRole("button", { name: MESSAGES.SIGN_IN }));
  return user;
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  useSessionStore.setState({ accessToken: null, user: null });
});
afterAll(() => server.close());

describe("LoginPage validation", () => {
  it("rejects an empty form with the canonical messages", async () => {
    renderLogin();
    await signIn("", "");

    expect(await screen.findByText(MESSAGES.ENTER_VALID_EMAIL)).toBeInTheDocument();
    expect(screen.getByText(MESSAGES.ENTER_PASSWORD)).toBeInTheDocument();
    expect(useSessionStore.getState().accessToken).toBeNull();
  });

  it("rejects an address that is not an email", async () => {
    renderLogin();
    await signIn(VALID_PASSWORD, "not-an-email");

    expect(await screen.findByText(MESSAGES.ENTER_VALID_EMAIL)).toBeInTheDocument();
  });

  it("rejects a password shorter than 12 characters", async () => {
    renderLogin();
    await signIn("short");

    expect(await screen.findByText(MESSAGES.ENTER_PASSWORD)).toBeInTheDocument();
  });
});

describe("LoginPage sign-in", () => {
  it("stores the session and lands a data engineer on the dataset list", async () => {
    renderLogin();
    await signIn();

    expect(await screen.findByText("Landing: datasets")).toBeInTheDocument();
    const state = useSessionStore.getState();
    expect(state.accessToken).toBe(MSW_ACCESS_TOKEN);
    expect(state.user).toMatchObject({ email: EMAIL, role: "data_engineer" });
  });

  it("lands an administrator on the model settings page", async () => {
    server.use(
      http.post("*/api/v1/auth/login", () =>
        HttpResponse.json({
          accessToken: MSW_ACCESS_TOKEN,
          user: {
            id: "user-2",
            email: "admin@example.com",
            firstName: "Ada",
            lastName: "Admin",
            role: "administrator",
            status: "active",
            createdAt: "2026-01-05T09:00:00Z",
          },
        })
      )
    );

    renderLogin();
    await signIn();

    expect(await screen.findByText("Landing: model settings")).toBeInTheDocument();
  });

  it("shows the canonical error for a problem+json 401", async () => {
    server.use(
      http.post("*/api/v1/auth/login", () =>
        problem(401, "INVALID_CREDENTIALS", "Unauthorized", "Email or password is incorrect.")
      )
    );

    renderLogin();
    await signIn(WRONG_PASSWORD);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(MESSAGES.EMAIL_PASSWORD_INCORRECT);
    expect(useSessionStore.getState().accessToken).toBeNull();
  });

  it("keeps the user on the form when the sign-in fails", async () => {
    server.use(
      http.post("*/api/v1/auth/login", () =>
        problem(401, "INVALID_CREDENTIALS", "Unauthorized", "Email or password is incorrect.")
      )
    );

    renderLogin();
    await signIn(WRONG_PASSWORD);
    await screen.findByRole("alert");

    expect(screen.getByRole("button", { name: MESSAGES.SIGN_IN })).toBeInTheDocument();
    expect(screen.queryByText("Landing: datasets")).not.toBeInTheDocument();
  });

  it("shows the session-expired banner for ?expired=1", () => {
    renderLogin("/login?expired=1");

    expect(screen.getByRole("alert")).toHaveTextContent(MESSAGES.SESSION_EXPIRED);
  });

  it("has no banner on a plain /login visit", () => {
    renderLogin();

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("toggles the password field type", async () => {
    renderLogin();
    const user = userEvent.setup();
    const field = screen.getByLabelText(/password/i, { selector: "input" });

    expect(field).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: MESSAGES.SHOW_PASSWORD }));
    expect(field).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: MESSAGES.HIDE_PASSWORD })).toBeInTheDocument();
  });
});
