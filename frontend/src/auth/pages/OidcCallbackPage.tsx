import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import type { User } from "../../api/schema";
import { completeOidcLogin } from "../oidc";
import { useSessionStore } from "../session.store";

/** /auth/callback: Keycloak returns here after password + MFA (Level 3 D-2). */
export function OidcCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await completeOidcLogin(window.location.search);
        const me = await fetch("/api/v1/auth/me", { headers: { Authorization: `Bearer ${token}` } });
        if (!me.ok) throw new Error("Your account has no access to this app. Ask an Administrator.");
        useSessionStore.getState().setSession(token, (await me.json()) as User);
        if (!cancelled) navigate("/datasets", { replace: true });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <main className="flex min-h-screen items-center justify-center p-6 text-sm">
      {error ? (
        <p role="alert">
          {error} <Link to="/login" className="font-medium text-primary underline">Back to sign-in</Link>
        </p>
      ) : (
        <p role="status">Signing you in…</p>
      )}
    </main>
  );
}
