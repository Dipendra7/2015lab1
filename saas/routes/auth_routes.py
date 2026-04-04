"""
Auth routes: register, login, logout, invite team member.
"""

from __future__ import annotations
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db, Company, User
from ..auth import (
    hash_password, verify_password,
    create_access_token, get_current_user, get_optional_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ..schemas import RegisterRequest, LoginRequest, InviteUserRequest

router = APIRouter()
templates = Jinja2Templates(directory="saas/templates")


# ── Page routes ───────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── API routes ────────────────────────────────────────────────────────────────

@router.post("/api/auth/register")
async def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    company = Company(name=body.company_name, plan="starter")
    db.add(company)
    db.flush()

    user = User(
        company_id=company.id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        {"sub": str(user.id), "company_id": company.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        "access_token", token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"ok": True, "user_id": user.id, "company_id": company.id}


@router.post("/api/auth/login")
async def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(
        {"sub": str(user.id), "company_id": user.company_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        "access_token", token,
        httponly=True, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"ok": True, "redirect": "/dashboard"}


@router.get("/api/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "company_id": current_user.company_id,
    }


@router.post("/api/auth/invite")
async def invite_user(
    body: InviteUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a team member to your company workspace."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can invite users")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        company_id=current_user.company_id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    db.commit()
    return {"ok": True, "user_id": user.id}
