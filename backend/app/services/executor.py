"""Plan execution engine service.

STATUS: scaffold stub — not implemented.

FR-035 to FR-038: Executes approved cleaning plans deterministically ON A COPY of the dataset.
Source files remain completely immutable (FR-004).
Each executed step is recorded with its inverse operation (FR-032) in pipeline_versions.
Produces cleaned master tables plus child tables (e.g. extracted line items).

Golden target for the reference invoice file (Level-2 exit gate):
- 22 invoice rows
- 313 line items
- Gross total 154,292 matched
"""

from typing import Any


def execute_plan(plan_id: str) -> dict[str, Any]:
    """Execute all approved steps of a cleaning plan deterministically on a copy (FR-035).

    TODO:
    - Load source data copy from MinIO
    - Sequentially apply approved steps (replace_value, fill_missing, drop_column, cast_type,
      derive_column, expand_nested, deduplicate, standardise_format)
    - Record inverse operations per step for rollback (FR-032)
    - Extract nested JSON line items to child table (`json-buried-line-items`)
    - Standardise supplier names from 7 variants to 5 canonical names (`supplier-variants-7-to-5`)
    - Verify output matches golden target: 22 invoices, 313 line items, gross total 154,292
    """
    raise NotImplementedError("executor not started")
