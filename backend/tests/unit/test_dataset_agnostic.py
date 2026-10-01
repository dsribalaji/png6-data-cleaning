"""FR-050: no dataset-specific hard-coded rules in the pipeline code."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "planner"
# Names from the reference invoice dataset that must never steer the logic.
FORBIDDEN = re.compile(r"invoice|supplier|line_?items|vendorinvoices", re.IGNORECASE)
# Fixture generators may legitimately use invoice-like sample data: the whole
# point of the benchmark corpus is to exercise the pipeline on datasets that look
# like the reference one, plus non-invoice domains that prove FR-050 holds.
# The guard exists to catch dataset names steering *logic*, not appearing as data.
ALLOWED = {
    "modules/evaluation/adversarial.py",
    "engine/evaluation/corpus.py",
}


def test_pipeline_code__no_reference_dataset_names() -> None:
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel in ALLOWED or path.name.startswith("test_"):
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if FORBIDDEN.search(code) and not code.strip().startswith(("e.g.", '"""', "``")):
                hits.append(f"{rel}:{n}: {line.strip()}")
    assert not hits, "dataset-specific names in pipeline code:\n" + "\n".join(hits)
