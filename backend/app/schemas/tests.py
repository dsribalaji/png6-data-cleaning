"""Generated test case and test run schemas."""

from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, Field


class TestCaseOut(BaseModel):
    """Generated test case representation."""

    id: uuid.UUID = Field(..., description="Unique test case identifier")
    name: str = Field(..., description="Test name")
    kind: str = Field(..., description="Test kind: unit or integration")
    code: str = Field(..., description="Test executable code")


class TestRunOut(BaseModel):
    """Test execution result representation."""

    id: uuid.UUID = Field(..., description="Test run identifier")
    phase: str = Field(..., description="Execution phase: pre or post")
    passed: bool = Field(..., description="Pass/fail status")
    details: dict[str, Any] = Field(default_factory=dict, description="Test output details and assertions")
    ran_at: datetime = Field(..., description="Timestamp when test ran")
