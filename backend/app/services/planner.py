"""Cleaning plan generation service.

STATUS: scaffold stub — not implemented.

Generates deterministic sequence of transformation steps from profiling results (FR-021, FR-022).
Allowed op_types: replace_value, fill_missing, drop_column, cast_type, derive_column,
expand_nested, deduplicate, standardise_format.
"""

from typing import Any


def generate_plan(profile: dict[str, Any]) -> dict[str, Any]:
    """Generate a cleaning plan from column profile metrics (FR-021, FR-022).

    TODO: Implement Level-2 deterministic rules:
    - Map `all-null-columns` to drop_column
    - Map `padding-rows` to drop empty records
    - Map `json-buried-line-items` to expand_nested
    - Map `dollar-text-in-json` to standardise_format / replace_value
    - Map `supplier-variants-7-to-5` to replace_value / standardise_format
    - Map `invalid-9char-gstin` to standardise_format
    - Map `float-artifacts` to cast_type
    """
    raise NotImplementedError("planner not started")


def infer_rules_with_llm(profile_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Infer semantic cleaning rules using an LLM.

    # NOT STARTED — Level 3. LiteLLM seam: provider-agnostic call (Ollama/vLLM, provider not locked).
    # MUST NOT be called by the Level-2 deterministic path.
    """
    raise NotImplementedError(
        "NOT STARTED — Level 3 AI rule inference via LiteLLM is not implemented in Level 2."
    )
