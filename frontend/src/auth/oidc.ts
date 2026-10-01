/// <reference types="vite/client" />
/**
 * Keycloak sign-in (Level 3 D-2) when built with VITE_AUTH_MODE=oidc: the
 * authorization-code flow with PKCE (proof key for code exchange), so no client
 * secret lives in the browser. MFA is enforced by Keycloak during its own sign-in
 * page. Tokens stay in memory only (contract §10.3); the one-time PKCE verifier and
 * state sit in sessionStorage for the redirect round trip, then are deleted.
 */
const env = import.meta.env;

export const isOidc = env.VITE_AUTH_MODE === "oidc";
const ISSUER = String(env.VITE_OIDC_ISSUER ?? "").replace(/\/$/, "");
const CLIENT_ID = String(env.VITE_OIDC_CLIENT_ID ?? "png6-web");
const PKCE_KEY = "png6.oidc.pkce";

let refreshToken: string | null = null;

export function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function randomString(length: number): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(length)));
}

/** S256 code challenge for a PKCE verifier (RFC 7636). */
export async function codeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}

const redirectUri = () => `${window.location.origin}/auth/callback`;
const endpoint = (path: string) => `${ISSUER}/protocol/openid-connect/${path}`;

/** Send the browser to Keycloak's sign-in page (password, then the authenticator code). */
export async function startOidcLogin(): Promise<void> {
  const verifier = randomString(48);
  const state = randomString(16);
  sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state }));
  const params = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    redirect_uri: redirectUri(),
    scope: "openid email profile",
    code_challenge: await codeChallenge(verifier),
    code_challenge_method: "S256",
    state,
  });
  window.location.assign(`${endpoint("auth")}?${params}`);
}

async function tokenRequest(body: Record<string, string>): Promise<string> {
  const response = await fetch(endpoint("token"), {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: CLIENT_ID, ...body }),
  });
  if (!response.ok) throw new Error(`Keycloak token request failed (${response.status})`);
  const data = (await response.json()) as { access_token: string; refresh_token?: string };
  refreshToken = data.refresh_token ?? null;
  return data.access_token;
}

/** Back from Keycloak with ?code&state: exchange the code for an access token. */
export async function completeOidcLogin(search: string): Promise<string> {
  const params = new URLSearchParams(search);
  const saved = JSON.parse(sessionStorage.getItem(PKCE_KEY) ?? "null") as {
    verifier: string;
    state: string;
  } | null;
  sessionStorage.removeItem(PKCE_KEY);
  const code = params.get("code");
  if (!saved || !code || params.get("state") !== saved.state) {
    throw new Error(params.get("error_description") ?? "Sign-in was interrupted. Try again.");
  }
  return tokenRequest({
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri(),
    code_verifier: saved.verifier,
  });
}

/** New access token from the in-memory refresh token; null when the session is over. */
export async function refreshOidcToken(): Promise<string | null> {
  if (!refreshToken) return null;
  try {
    return await tokenRequest({ grant_type: "refresh_token", refresh_token: refreshToken });
  } catch {
    refreshToken = null;
    return null;
  }
}
