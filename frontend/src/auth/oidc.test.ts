import { describe, expect, it } from "vitest";
import { codeChallenge } from "./oidc";

describe("PKCE (Level 3 D-2)", () => {
  it("matches the RFC 7636 appendix B example", async () => {
    // Verifier and expected S256 challenge straight from RFC 7636, Appendix B.
    const verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
    expect(await codeChallenge(verifier)).toBe("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
  });
});
