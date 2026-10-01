import type { User } from "../api/schema";
import { useSessionStore } from "./session.store";
import { isOidc } from "./oidc";

/**
 * On page load the in-memory access token is gone; trade the httpOnly refresh
 * cookie for a new one so a reload doesn't sign the user out. Silent on failure:
 * the route guards then send the user to /login as usual.
 */
export async function restoreSession(): Promise<void> {
  // SSO: tokens live in memory only, so a reload goes back through Keycloak, which
  // signs the user straight in while its own session is still open.
  if (isOidc) return;
  try {
    const refresh = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!refresh.ok) return;
    const { accessToken } = (await refresh.json()) as { accessToken: string };
    const me = await fetch("/api/v1/auth/me", { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!me.ok) return;
    useSessionStore.getState().setSession(accessToken, (await me.json()) as User);
  } catch {
    // offline or API down: fall through to the login page
  }
}
