"""Authentication API router.

STATUS: scaffold stub — not implemented.
"""

from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import LoginIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def register(credentials: LoginIn) -> UserOut:
    """Register a new user account.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.post("/login", response_model=TokenOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def login(credentials: LoginIn) -> TokenOut:
    """Sign in and obtain a JWT bearer token.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")


@router.get("/me", response_model=UserOut, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_current_user() -> UserOut:
    """Get current authenticated user profile.

    STATUS: not started.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not started")
