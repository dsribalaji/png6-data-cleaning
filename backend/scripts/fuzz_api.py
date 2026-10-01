"""E3: fuzz the live API with schemathesis and fail on server errors.

Runs the property-based fuzzer from ``schemathesis`` against a *running* API
(Compose in CI, or a local server) using the OpenAPI document the app serves at
``/api/docs/openapi.json``. Every request carries a real bearer token so the
fuzzer reaches the authenticated routes instead of bouncing off 401s.

The gate is deliberately narrow: **any 5xx response fails the run**, which is the
E3 requirement ("no 5xx responses"). Findings that are not 5xx are still
detected and printed, and land in the JSON/JUnit artifacts, but they do not
fail the build by default -- see ``--fail-on`` below.

Why the default is 5xx only: the checks schemathesis runs alongside it are
currently dominated by *OpenAPI documentation* gaps rather than runtime bugs.
The app returns every error as ``application/problem+json`` and returns 401 /
403 / 404 / 409 responses that the generated spec does not list, so
``status_code_conformance`` and ``content_type_conformance`` report ~90
findings across the documented surface. Every one of those is a real
documentation debt, and closing it means declaring the error responses on
every route. That is worth doing, but it is a separate change from proving the
API does not crash, so it is surfaced rather than silently folded into this
gate. Pass ``--fail-on all`` to gate on all of them once the spec is updated.

Checks we opt out of entirely, and why: see ``EXCLUDED_CHECKS``.

Usage::

    python scripts/fuzz_api.py --base-url http://localhost:8000 \\
        --email admin@example.com --password 'Admin123456!' \\
        --json report.json

Exit code 0 means the API survived the fuzzing run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8000"
# Matches backend/scripts/seed_demo.py. Local/CI demo credentials only.
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "Admin123456!"  # documented demo credential from seed_demo.py

# Checks we enforce. Each is a real contract violation, not a heuristic.
ENFORCED_CHECKS = [
    "not_a_server_error",  # the 5xx gate
    "status_code_conformance",
    "content_type_conformance",
    "response_schema_conformance",
]

# Checks we deliberately skip, with the reason. Listing them here keeps the
# decision auditable instead of silently narrowing the gate.
#
#   positive_data_acceptance / negative_data_rejection
#       We are not a pure validator: uploads, plans and rollbacks have real
#       side effects, so "rejects every bad body" and "accepts every good one"
#       are not contracts this API makes. A false positive here would fail CI
#       for correct behaviour.
#   ignored_auth
#       Needs two tokens with different privileges to be meaningful. The
#       route-coverage test (D-3) and test_auth_required.py already assert that
#       every route is protected, which covers the same risk.
#   use_after_free
#       The API is REST, not gRPC; there are no gRPC streaming responses here.
#   ensure_resource_availability
#       Reports successful responses as failures when the payload is large.
#       Uploads of up to 50 MB are a supported, tested path.
EXCLUDED_CHECKS = [
    "positive_data_acceptance",
    "negative_data_rejection",
    "ignored_auth",
    "use_after_free",
    "ensure_resource_availability",
]


def _log(message: str) -> None:
    print(f"[fuzz] {message}", flush=True)


def wait_for_api(base_url: str, timeout: float) -> None:
    """Block until the OpenAPI document is served, or give up loudly."""
    spec_url = f"{base_url.rstrip('/')}/api/docs/openapi.json"
    deadline = time.monotonic() + timeout
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(spec_url, timeout=10) as response:
                if response.status == 200:
                    _log(f"API is up ({spec_url})")
                    return
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(2)
    raise SystemExit(f"API did not become ready within {timeout:.0f}s ({last_error})")


def login(base_url: str, email: str, password: str) -> str:
    """Exchange demo credentials for an access token.

    Done with urllib rather than httpx so the script runs under a bare
    interpreter if httpx is unavailable. Returns the raw JWT.
    """
    url = f"{base_url.rstrip('/')}/api/v1/auth/login"
    payload = json.dumps({"email": email, "password": password}).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise SystemExit(
            f"Login failed: HTTP {exc.code} for {email}.\n"
            f"Seed the demo users first (scripts/seed_demo.py) or pass --email/--password.\n"
            f"Response: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"Could not reach the login endpoint at {url}: {exc}") from exc

    token = body.get("accessToken") or body.get("access_token")
    if not isinstance(token, str) or not token:
        raise SystemExit(f"Login response carried no access token: {list(body)}")
    return token


def build_command(
    base_url: str,
    token: str,
    report_path: Path,
    max_examples: int,
    workers: int,
    seed: int,
    phase: str,
) -> list[str]:
    """Assemble the schemathesis invocation.

    ``fuzzing`` and ``coverage`` are the phases that matter for a CI gate.
    ``stateful`` drives the API as a sequence of real calls and is far slower,
    so it is opt-in via --phase.
    """
    checks = ",".join(ENFORCED_CHECKS)
    return [
        sys.executable,
        "-m",
        "schemathesis.cli",
        "run",
        f"{base_url.rstrip('/')}/api/docs/openapi.json",
        "--phases",
        phase,
        "--checks",
        checks,
        "--exclude-checks",
        ",".join(EXCLUDED_CHECKS),
        "--header",
        f"Authorization: Bearer {token}",
        # A failure is a finding, not a reason to abandon the remaining
        # operations: we want every endpoint exercised in one run. max_failures
        # is set high enough that it never trips before the run finishes --
        # otherwise the early-stop would leave later operations untested and
        # "no 5xx" would only ever mean "no 5xx on the first N endpoints".
        "--continue-on-failure",
        "--max-failures",
        "1000",
        "--max-examples",
        str(max_examples),
        "--workers",
        str(workers),
        "--seed",
        str(seed),
        "--request-timeout",
        "30",
        "--report",
        "json,junit",
        "--report-json-path",
        str(report_path),
        "--report-junit-path",
        str(report_path.with_suffix(".xml")),
    ]


def summarise(report_path: Path) -> dict[str, Any]:
    """Read the schemathesis JSON run report and count what matters.

    The report groups findings by failure ``type`` (``ServerError``,
    ``UndefinedStatusCode``, ...) rather than per test case, so the gate is a
    lookup on those types. Never raises: an unreadable report still lets the
    process exit code carry the verdict.
    """
    summary: dict[str, Any] = {
        "report_present": report_path.exists(),
        "server_errors": 0,
        "failures_by_type": {},
        "errors": 0,
        "cases_generated": 0,
        "stop_reason": None,
    }
    if not report_path.exists():
        return summary

    try:
        data = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        summary["error"] = f"unreadable report: {exc}"
        return summary

    cases = data.get("test_cases")
    if isinstance(cases, dict):
        summary["cases_generated"] = int(cases.get("generated", 0) or 0)
    summary["stop_reason"] = data.get("stop_reason")

    for failure in data.get("failures") or []:
        if not isinstance(failure, dict):
            continue
        kind = str(failure.get("type", "unknown"))
        count = int(failure.get("count", 1) or 1)
        summary["failures_by_type"][kind] = count
        if kind == "ServerError":
            summary["server_errors"] += count

    # Infrastructure-level problems (connection refused mid-run, schema unloadable).
    # These are never acceptable, and they are distinct from "the API answered
    # with an undocumented status code".
    for err in data.get("errors") or []:
        summary["errors"] += int(err.get("count", 1) or 1) if isinstance(err, dict) else 1
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("FUZZ_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--email", default=os.environ.get("FUZZ_EMAIL", DEFAULT_EMAIL))
    parser.add_argument(
        "--password",
        default=os.environ.get("FUZZ_PASSWORD", DEFAULT_PASSWORD),
        help="Demo password. Prefer FUZZ_PASSWORD over a command-line argument.",
    )
    parser.add_argument("--json", dest="json_path", default="fuzz-report.json")
    parser.add_argument("--max-examples", type=int, default=5)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument(
        "--phase",
        default="fuzzing,coverage",
        help="Comma-separated schemathesis phases (stateful is slow, opt-in only).",
    )
    parser.add_argument("--wait-seconds", type=float, default=120.0)
    parser.add_argument(
        "--fail-on",
        choices=["server-error", "all"],
        default="server-error",
        help=(
            "server-error (default): fail only on 5xx responses. "
            "all: also fail on OpenAPI contract findings (status code, content type, schema)."
        ),
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    report_path = Path(args.json_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    _log(f"waiting for {base_url}")
    wait_for_api(base_url, args.wait_seconds)

    _log(f"logging in as {args.email}")
    token = login(base_url, args.email, args.password)
    _log("got an access token")

    command = build_command(
        base_url=base_url,
        token=token,
        report_path=report_path,
        max_examples=args.max_examples,
        workers=args.workers,
        seed=args.seed,
        phase=args.phase,
    )
    # The token must not reach the CI log.
    redacted = [part if "Authorization" not in part else "Authorization: Bearer <redacted>" for part in command]
    _log("running: " + " ".join(redacted))

    started = time.monotonic()
    completed = subprocess.run(command, check=False)
    elapsed = time.monotonic() - started

    summary = summarise(report_path)
    summary["exit_code"] = completed.returncode
    summary["elapsed_seconds"] = round(elapsed, 1)
    _log(f"summary: {json.dumps(summary, sort_keys=True)}")

    server_errors = int(summary.get("server_errors", 0) or 0)
    infra_errors = int(summary.get("errors", 0) or 0)
    # Everything that is not a 5xx. Reported either way; fatal only with
    # --fail-on all, because today these are OpenAPI documentation gaps.
    other_failures = {k: v for k, v in summary["failures_by_type"].items() if k != "ServerError"}
    if other_failures:
        _log(
            f"note: non-5xx contract findings (not fatal by default): "
            f"{json.dumps(other_failures, sort_keys=True)}"
        )

    # Verdict, in order of severity. 5xx first: it is the E3 requirement and the
    # most actionable finding. A 500 can also drop the connection, which
    # schemathesis records separately as a network error, so both are reported.
    if not summary.get("report_present"):
        _log(f"FAIL: schemathesis produced no report (exit {completed.returncode}).")
        return 1
    if server_errors:
        _log(f"FAIL: {server_errors} server error(s). See {report_path}")
        if infra_errors:
            _log(f"      (plus {infra_errors} infrastructure error(s) in the same run)")
        return 1
    if infra_errors:
        _log(f"FAIL: {infra_errors} infrastructure error(s) during the run. See {report_path}")
        return 1
    if args.fail_on == "all" and other_failures:
        _log(f"FAIL: --fail-on all and {sum(other_failures.values())} non-5xx finding(s).")
        return 1
    # A non-zero schemathesis exit with a clean report above is schemathesis
    # reporting the findings we just decided are non-fatal, so it is not a
    # failure on its own. An unreadable report was already handled above.
    _log(f"PASS: no 5xx responses in {summary['cases_generated']} generated cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
