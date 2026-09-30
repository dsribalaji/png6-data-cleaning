"""Pipeline execution and rollback schemas."""

import uuid
from pydantic import BaseModel, Field


class ExecutionResultOut(BaseModel):
    """Result summary of plan execution."""

    plan_id: uuid.UUID = Field(..., description="Executed plan identifier")
    version_no: int = Field(..., description="Generated pipeline version number")
    rows_out: int = Field(..., description="Count of cleaned invoice rows")
    line_items_out: int = Field(..., description="Count of extracted line items")
    gross_total: float = Field(..., description="Gross total matched across line items")
    tests_passed: bool = Field(..., description="Whether all post-execution tests passed")


class RollbackRequest(BaseModel):
    """Rollback request payload."""

    version_no: int = Field(..., description="Target pipeline version to restore")


class RollbackResultOut(BaseModel):
    """Result of rollback operation."""

    restored_version_no: int = Field(..., description="Version number restored")
    byte_match: bool = Field(
        ...,
        description="Whether restored state matches original source byte-for-byte (sha256 match)",
    )
