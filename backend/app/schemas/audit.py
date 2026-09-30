"""Audit trail schemas."""

from datetime import datetime
import uuid
from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    """Audit event record representation."""

    id: uuid.UUID = Field(..., description="Unique audit event identifier")
    actor: str = Field(..., description="User or service initiating action")
    action: str = Field(..., description="Action name performed")
    entity: str = Field(..., description="Entity category modified")
    entity_id: str | None = Field(default=None, description="Identifier of the modified entity")
    timestamp: datetime = Field(..., description="Timestamp of the event")


class AuditExportOut(BaseModel):
    """Audit trail export download info.

    STATUS: Export download URL is a stub for scaffold.
    """

    format: str = Field(..., description="Export format (json, csv)")
    download_url: str = Field(..., description="Download URL for the exported audit package")
