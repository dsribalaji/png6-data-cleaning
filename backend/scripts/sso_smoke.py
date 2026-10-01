"""SSO smoke test (Level 3 D-2): run in CI against the Compose stack with AUTH_MODE=oidc.

Proves, over HTTP:
1. a token issued by the Keycloak realm is accepted by the API (and /auth/me
   provisions the user with the realm role);
2. roles are enforced: a viewer cannot generate a plan, an engineer can list datasets;
3. password sign-in on the API is refused (SSO only), and a forged token is rejected;
4. MFA is required: a demo user whose authenticator is not yet set up cannot get
   a token (Keycloak answers "Account is not fully set up").

Usage: python scripts/sso_smoke.py --keycloak http://localhost:8080 --api http://localhost:8000
(the CI job first creates the png6-ci client and the ci-engineer / ci-viewer users).
"""

from __future__ import annotations

import argparse
import sys

import httpx


def token(kc: str, user: str, password: str) -> httpx.Response:
    return httpx.post(
        f"{kc}/realms/png6/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": "png6-ci", "username": user, "password": password},
        timeout=30,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--keycloak", default="http://localhost:8080")
    p.add_argument("--api", default="http://localhost:8000")
    a = p.parse_args()
    api = f"{a.api}/api/v1"
    failures: list[str] = []

    def check(name: str, ok: bool, detail: object = "") -> None:
        print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if not ok else ""))
        if not ok:
            failures.append(name)

    eng = token(a.keycloak, "ci-engineer", "CiEngineer123!")
    check("keycloak issues a token to ci-engineer", eng.status_code == 200, eng.text[:200])
    view = token(a.keycloak, "ci-viewer", "CiViewer1234!")
    check("keycloak issues a token to ci-viewer", view.status_code == 200, view.text[:200])
    if failures:
        return 1
    h_eng = {"Authorization": f"Bearer {eng.json()['access_token']}"}
    h_view = {"Authorization": f"Bearer {view.json()['access_token']}"}

    me = httpx.get(f"{api}/auth/me", headers=h_eng, timeout=30)
    check("API accepts the Keycloak token (/auth/me)", me.status_code == 200, me.text[:200])
    check("realm role mapped", me.status_code == 200 and me.json().get("role") == "data_engineer", me.text[:200])

    r = httpx.get(f"{api}/datasets", headers=h_eng, timeout=30)
    check("engineer can list datasets", r.status_code == 200, r.status_code)
    dummy = "00000000-0000-0000-0000-000000000000"
    r = httpx.post(f"{api}/datasets/{dummy}/plans", headers=h_view, json={}, timeout=30)
    check("viewer cannot generate a plan (403)", r.status_code == 403, f"{r.status_code} {r.text[:120]}")

    r = httpx.post(f"{api}/auth/login", json={"email": "engineer@example.com", "password": "Engineer123!"}, timeout=30)
    check("password sign-in refused under SSO (403 SSO_REQUIRED)", r.status_code == 403, r.text[:120])
    forged = h_eng["Authorization"][:-8] + "AAAAAAAA"
    r = httpx.get(f"{api}/auth/me", headers={"Authorization": forged}, timeout=30)
    check("tampered token rejected (401)", r.status_code == 401, r.status_code)

    demo = token(a.keycloak, "engineer", "Engineer123!")
    check(
        "MFA required: demo user without an authenticator gets no token",
        demo.status_code == 400 and "not fully set up" in demo.text,
        f"{demo.status_code} {demo.text[:160]}",
    )

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
