import { describe, expect, it } from "vitest";
import {
  PERMISSIONS,
  getRoleLandingRoute,
  hasPermission,
  type Permission,
  type Role,
} from "./permissions";

const ALL_PERMISSIONS: Permission[] = [
  "dataset.upload",
  "dataset.view",
  "profile.view",
  "plan.generate",
  "plan.decide",
  "plan.approve",
  "plan.rollback",
  "export",
  "evaluation.run",
  "model.view",
  "model.edit",
  "users.view",
  "users.invite",
  "users.edit",
  "audit.view",
  "audit.export",
];

const ROLES: Role[] = ["data_engineer", "administrator", "auditor", "viewer"];

describe("PERMISSIONS matrix", () => {
  it("gives the data engineer the whole cleaning pipeline", () => {
    expect(PERMISSIONS.data_engineer).toEqual([
      "dataset.upload",
      "dataset.view",
      "profile.view",
      "plan.generate",
      "plan.decide",
      "plan.approve",
      "plan.rollback",
      "export",
      "evaluation.run",
    ]);
  });

  it("gives the administrator configuration, users and audit but no cleaning work", () => {
    expect(PERMISSIONS.administrator).toEqual([
      "model.view",
      "model.edit",
      "users.view",
      "users.invite",
      "users.edit",
      "audit.view",
      "evaluation.run",
    ]);
    expect(hasPermission("administrator", "dataset.upload")).toBe(false);
    expect(hasPermission("administrator", "dataset.view")).toBe(false);
    expect(hasPermission("administrator", "plan.approve")).toBe(false);
    expect(hasPermission("administrator", "export")).toBe(false);
    expect(hasPermission("administrator", "audit.export")).toBe(false);
  });

  it("lets the auditor read datasets, profiles and the audit trail, and export it", () => {
    expect(PERMISSIONS.auditor).toEqual([
      "dataset.view",
      "profile.view",
      "audit.view",
      "audit.export",
    ]);
    expect(hasPermission("auditor", "plan.generate")).toBe(false);
    expect(hasPermission("auditor", "plan.approve")).toBe(false);
    expect(hasPermission("auditor", "plan.rollback")).toBe(false);
    expect(hasPermission("auditor", "evaluation.run")).toBe(false);
    expect(hasPermission("auditor", "export")).toBe(false);
  });

  it("keeps the viewer read-only apart from exporting", () => {
    expect(PERMISSIONS.viewer).toEqual(["dataset.view", "profile.view", "export"]);
    expect(hasPermission("viewer", "dataset.upload")).toBe(false);
    expect(hasPermission("viewer", "plan.generate")).toBe(false);
    expect(hasPermission("viewer", "plan.decide")).toBe(false);
    expect(hasPermission("viewer", "audit.view")).toBe(false);
  });

  it("only ever lists permissions from the Permission union", () => {
    const known = new Set<string>(ALL_PERMISSIONS);
    for (const role of ROLES) {
      for (const permission of PERMISSIONS[role]) {
        expect(known.has(permission)).toBe(true);
      }
    }
  });

  it("never lists the same permission twice for one role", () => {
    for (const role of ROLES) {
      expect(new Set(PERMISSIONS[role]).size).toBe(PERMISSIONS[role].length);
    }
  });
});

describe("hasPermission", () => {
  it("returns false when nobody is signed in", () => {
    expect(hasPermission(null, "dataset.view")).toBe(false);
    expect(hasPermission(undefined, "dataset.view")).toBe(false);
  });

  it("answers for each declared role", () => {
    for (const role of ROLES) {
      for (const permission of ALL_PERMISSIONS) {
        expect(hasPermission(role, permission)).toBe(PERMISSIONS[role].includes(permission));
      }
    }
  });
});

describe("getRoleLandingRoute", () => {
  it("sends each role to its own landing page", () => {
    expect(getRoleLandingRoute("data_engineer")).toBe("/datasets");
    expect(getRoleLandingRoute("administrator")).toBe("/settings/model");
    expect(getRoleLandingRoute("auditor")).toBe("/audit");
    expect(getRoleLandingRoute("viewer")).toBe("/datasets");
  });
});
