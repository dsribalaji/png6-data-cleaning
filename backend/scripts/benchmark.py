"""Level-2 pipeline benchmark over HTTP against a running API (local dev or Docker).

Times each stage of the exit-gate loop for one or more files:
upload -> profiled -> plan -> approve (tests + execute + validate) -> XLSX/CSV export.

Usage (API running, demo users seeded):
    python scripts/benchmark.py FILE [FILE ...] [--base http://localhost:8000] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

API = "/api/v1"
POLL_S = 1.0
STAGE_TIMEOUT_S = 1800


def _ok(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        raise RuntimeError(f"{r.request.method} {r.request.url}: {r.status_code} {r.text[:300]}")
    return r.json()


def _wait(check, what: str):
    deadline = time.monotonic() + STAGE_TIMEOUT_S
    while time.monotonic() < deadline:
        result = check()
        if result is not None:
            return result
        time.sleep(POLL_S)
    raise TimeoutError(f"{what} did not finish in {STAGE_TIMEOUT_S}s")


def run_one(c: httpx.Client, path: Path) -> dict:
    out: dict = {"file": path.name, "bytes": path.stat().st_size}
    t = {}

    t0 = time.monotonic()
    ds = _ok(c.post(f"{API}/datasets", files={"file": (path.name, path.read_bytes())},
                    data={"name": f"bench {path.stem[:50]} {int(time.time())}"}))
    t["upload"] = time.monotonic() - t0

    def profiled():
        d = _ok(c.get(f"{API}/datasets/{ds['id']}"))
        if d["status"] == "profiling":
            return None
        if d["status"] != "profiled":
            raise RuntimeError(f"dataset status {d['status']}")
        return d

    ds = _wait(profiled, "profiling")
    t["profile"] = time.monotonic() - t0 - t["upload"]
    out.update(rows=ds["rowCount"], columns=ds["columnCount"])

    t1 = time.monotonic()
    plan = _ok(c.post(f"{API}/datasets/{ds['id']}/plans"))
    t["plan"] = time.monotonic() - t1
    out.update(steps=len(plan["steps"]), est_loss=plan["totalEstimatedLoss"], loss_limit=plan["lossThreshold"])

    for s in plan["steps"]:
        _ok(c.patch(f"{API}/plans/{plan['id']}/steps/{s['id']}", json={"decision": "accepted"}))
    t2 = time.monotonic()
    _ok(c.post(f"{API}/plans/{plan['id']}/approve"))

    def validated():
        v = _ok(c.get(f"{API}/plans/{plan['id']}/validation"))
        cases = v["testCases"]
        if not cases or not v["reconciliation"] or any(tc.get("latestRun") is None for tc in cases):
            return None
        return v

    v = _wait(validated, "execute + validate")
    t["execute_validate"] = time.monotonic() - t2
    rec = v["reconciliation"]
    out.update(
        validation_passed=v["passed"],
        tests=f"{sum(tc['latestRun']['result'] == 'passed' for tc in v['testCases'])}/{len(v['testCases'])}",
        reconciliation=f"{sum(r['ok'] for r in rec)}/{len(rec)}",
    )

    for fmt in ("xlsx", "csv"):
        t3 = time.monotonic()
        url = _ok(c.post(f"{API}/plans/{plan['id']}/exports", json={"format": fmt}))["downloadUrl"]
        r = c.get(url)
        r.raise_for_status()
        t[f"export_{fmt}"] = time.monotonic() - t3
        out[f"{fmt}_bytes"] = len(r.content)

    t["total"] = time.monotonic() - t0
    out["seconds"] = {k: round(v, 2) for k, v in t.items()}
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--email", default="engineer@example.com")
    p.add_argument("--password", default="Engineer123!")
    p.add_argument("--json", type=Path)
    a = p.parse_args()

    with httpx.Client(base_url=a.base, timeout=900) as c:
        results = []
        for f in a.files:
            # fresh token per file: access tokens live 15 minutes
            tok = _ok(c.post(f"{API}/auth/login", json={"email": a.email, "password": a.password}))["accessToken"]
            c.headers["Authorization"] = f"Bearer {tok}"
            print(f"== {f.name}", flush=True)
            res = run_one(c, f)
            print(json.dumps(res, indent=2), flush=True)
            results.append(res)

    if a.json:
        a.json.write_text(json.dumps(results, indent=2))
    return 0 if all(r["validation_passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
