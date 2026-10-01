"""Run the evaluation benchmark and report the D5 pass bar (Level 3, workstream C).

Usage (from `backend/`):

    python scripts/evaluate_benchmark.py                  # report only
    python scripts/evaluate_benchmark.py --fail-under-bar  # exit 1 if below the bar
    python scripts/evaluate_benchmark.py --json out.json   # write the full report

The model is off by default, so a run is deterministic and free -- this is what
CI uses. Pass `--llm-on` to record that a run used a configured model; the
deterministic scores are identical either way, and the D5 requirement "LLM-on
scores at least LLM-off" is checked by comparing two report files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/evaluate_benchmark.py` from the backend directory without
# installing the package first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from planner.engine.evaluation import bar_report, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fail-under-bar",
        action="store_true",
        help="exit non-zero when any D5 metric is below its bar",
    )
    parser.add_argument("--llm-on", action="store_true", help="record that a model was configured")
    parser.add_argument("--json", dest="json_path", default=None, help="write the full report here")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args()

    report = run_benchmark(llm_on=args.llm_on)
    metrics = report["metrics"]

    print(f"evaluation benchmark: {metrics['cases']} cases, model {'on' if args.llm_on else 'off'}")
    for row in bar_report(metrics):
        if args.quiet and row["passed"]:
            continue
        verdict = "PASS" if row["passed"] else "FAIL"
        print(
            f"  {row['check']:<22} {row['actual']:>8} "
            f"{row['direction']} {row['bar']:<6} {verdict}"
        )

    if not report["passed"]:
        for case in report["cases_detail"]:
            if case["crashed"]:
                print(f"  crash {case['case_id']}: {case['error']}")
            for failure in case["failures"]:
                print(f"  fail  {case['case_id']}: {failure}")

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(f"report written to {args.json_path}")

    if args.fail_under_bar and not report["passed"]:
        print("RESULT: below the D5 pass bar")
        return 1
    print(f"RESULT: {'passes' if report['passed'] else 'below'} the D5 pass bar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
