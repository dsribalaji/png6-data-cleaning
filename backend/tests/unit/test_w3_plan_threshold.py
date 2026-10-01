"""Regression tests for the plan loss-threshold bound (found by API fuzzing, E3).

A huge ``lossThreshold`` reached Postgres as a numeric overflow and the request
failed with a 500. It is a client input error, so Pydantic now rejects it with
a 422 before it reaches the database.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from planner.modules.planning.schemas import CreatePlanRequest


def test_create_plan_request__default_threshold__is_five_percent() -> None:
    """The documented default (Backend.md, contract §6 P3) is 0.05 = 5%."""
    assert CreatePlanRequest().loss_threshold == 0.05


@pytest.mark.parametrize("value", [0.0, 0.05, 0.5, 1.0])
def test_create_plan_request__threshold_in_range__accepted(value: float) -> None:
    """Every ratio from 0 to 1 inclusive is a legitimate threshold."""
    assert CreatePlanRequest(loss_threshold=value).loss_threshold == value


@pytest.mark.parametrize("value", [-0.1, 1.1, 3.473775499819916e16, 1e30])
def test_create_plan_request__threshold_out_of_range__rejected(value: float) -> None:
    """Out-of-range thresholds are a 422, not a database overflow and a 500."""
    with pytest.raises(ValidationError):
        CreatePlanRequest(loss_threshold=value)


def test_create_plan_request__accepts_camel_case_alias() -> None:
    """The wire format is camelCase; the alias must still reach the validator."""
    with pytest.raises(ValidationError):
        CreatePlanRequest.model_validate({"lossThreshold": 2.0})
    assert CreatePlanRequest.model_validate({"lossThreshold": 0.2}).loss_threshold == 0.2
