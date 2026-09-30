"""Dataset request and response schemas."""

from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class DatasetOut(BaseModel):
    """Dataset metadata representation."""

    id: uuid.UUID = Field(..., description="Unique dataset identifier")
    filename: str = Field(..., description="Original dataset filename")
    sha256: str = Field(..., description="SHA-256 hash of the immutable source file")
    row_count: int | None = Field(default=None, description="Total row count")
    col_count: int | None = Field(default=None, description="Total column count")
    status: str = Field(
        ...,
        description="Dataset status: uploaded, profiled, planned, executed, rolled_back",
    )
    created_at: datetime = Field(..., description="Upload creation timestamp")


class DatasetListOut(BaseModel):
    """Paginated dataset collection."""

    items: list[DatasetOut] = Field(..., description="List of dataset metadata records")
    total: int = Field(..., description="Total number of datasets available")


class UploadResponse(BaseModel):
    """Returned after ingest accepts the uploaded file."""

    dataset_id: uuid.UUID = Field(..., description="Assigned dataset identifier")
    filename: str = Field(..., description="Stored dataset filename")
    status: str = Field(default="uploaded", description="Initial status after upload acceptance")
