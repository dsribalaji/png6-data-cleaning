import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Can } from "./Can";
import { useSessionStore } from "./session.store";
import type { Role } from "./session.store";

function signInAs(role: Role | null) {
  useSessionStore.setState({
    accessToken: role ? "test-token" : null,
    user: role ? { id: "user-1", email: "user@example.com", role } : null,
  });
}

afterEach(() => {
  useSessionStore.setState({ accessToken: null, user: null });
});

describe("Can", () => {
  it("renders the children when the role holds the permission", () => {
    signInAs("data_engineer");
    render(
      <Can perm="dataset.upload">
        <button type="button">Upload dataset</button>
      </Can>
    );

    expect(screen.getByRole("button", { name: "Upload dataset" })).toBeInTheDocument();
  });

  it("renders nothing at all when the role lacks the permission (PRD S2: hidden, not disabled)", () => {
    signInAs("viewer");
    const { container } = render(
      <Can perm="dataset.upload">
        <button type="button">Upload dataset</button>
      </Can>
    );

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("button", { name: "Upload dataset" })).not.toBeInTheDocument();
  });

  it("renders the fallback instead when one is given", () => {
    signInAs("auditor");
    render(
      <Can perm="plan.approve" fallback={<p>Approve is hidden for you</p>}>
        <button type="button">Approve plan</button>
      </Can>
    );

    expect(screen.getByText("Approve is hidden for you")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve plan" })).not.toBeInTheDocument();
  });

  it("renders nothing when nobody is signed in", () => {
    signInAs(null);
    const { container } = render(
      <Can perm="dataset.view">
        <p>Datasets</p>
      </Can>
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("reacts to the role held by the current session", () => {
    signInAs("administrator");
    const { rerender } = render(
      <Can perm="users.view">
        <p>Users</p>
      </Can>
    );
    expect(screen.getByText("Users")).toBeInTheDocument();

    signInAs("auditor");
    rerender(
      <Can perm="users.view">
        <p>Users</p>
      </Can>
    );

    expect(screen.queryByText("Users")).not.toBeInTheDocument();
  });

  it("gives a data engineer the pipeline actions but not the admin ones", () => {
    signInAs("data_engineer");
    render(
      <>
        <Can perm="plan.rollback">
          <p>Roll back here</p>
        </Can>
        <Can perm="users.invite">
          <p>Invite user</p>
        </Can>
      </>
    );

    expect(screen.getByText("Roll back here")).toBeInTheDocument();
    expect(screen.queryByText("Invite user")).not.toBeInTheDocument();
  });
});
