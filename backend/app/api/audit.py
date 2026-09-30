"""Audit trail API router.

STATUS: scaffold stub — not implemented.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.audit import AuditEventOut, AuditExportOut

# FR-051 / FR-052: Complete audit logging of all system actions and plan decisions
router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut], status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_audit_trail() -> list[AuditEventOut]:
    """Retrieve audit log events (FR-051).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.get("/export", response_model=AuditExportOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def export_audit_trail() -> AuditExportOut:
    """Export complete audit trail log (FR-052).

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
