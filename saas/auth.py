"""
JWT Authentication for the HR SaaS platform.
Handles login, token creation, and current-user resolution.
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import User, get_db

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-use-a-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8   # 8 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── FastAPI dependencies ───────────────────────────────────────────────────────

def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the current user from the access_token cookie.
    Raises 401 if missing or invalid, 403 if inactive.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(access_token)
        user_id: int = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_optional_user(
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None instead of raising (for page routes)."""
    if not access_token:
        return None
    try:
        payload = decode_token(access_token)
        user_id: int = int(payload.get("sub", 0))
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except Exception:
        return None
