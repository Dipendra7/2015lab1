"""
Candidate management routes: add candidates, view profiles, update status.
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db, Job, Candidate, InterviewSchedule, InterviewKit, OnboardingPlan, User
from ..auth import get_current_user
from ..schemas import AddCandidateRequest, UpdateCandidateStatusRequest

router = APIRouter()
templates = Jinja2Templates(directory="saas/templates")

VALID_STATUSES = {
    "applied", "screened", "shortlisted",
    "interviewing", "offer", "hired", "rejected",
}


# ── Page routes ───────────────────────────────────────────────────────────────

@router.get("/candidates/{candidate_id}", response_class=HTMLResponse)
async def candidate_detail_page(
    candidate_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = _get_candidate(candidate_id, current_user, db)
    job = db.query(Job).filter(Job.id == candidate.job_id).first()
    schedule = db.query(InterviewSchedule).filter(
        InterviewSchedule.candidate_id == candidate_id
    ).first()
    kit = db.query(InterviewKit).filter(
        InterviewKit.candidate_id == candidate_id
    ).first()
    onboarding = db.query(OnboardingPlan).filter(
        OnboardingPlan.candidate_id == candidate_id
    ).first()

    return templates.TemplateResponse("candidate_detail.html", {
        "request": request,
        "user": current_user,
        "candidate": candidate,
        "job": job,
        "score": candidate.score_data,
        "schedule": schedule.data if schedule else None,
        "kit": kit.data if kit else None,
        "onboarding": onboarding.data if onboarding else None,
        "VALID_STATUSES": sorted(VALID_STATUSES),
    })


# ── API routes ────────────────────────────────────────────────────────────────

@router.post("/api/jobs/{job_id}/candidates")
async def add_candidate(
    job_id: int,
    body: AddCandidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(
        Job.id == job_id, Job.company_id == current_user.company_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Prevent duplicate email per job
    existing = db.query(Candidate).filter(
        Candidate.job_id == job_id,
        Candidate.email == body.email,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Candidate already applied for this role")

    candidate = Candidate(
        job_id=job_id,
        company_id=current_user.company_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        source=body.source,
        cv_text=body.cv_text,
        status="applied",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return {"ok": True, "candidate_id": candidate.id}


@router.patch("/api/candidates/{candidate_id}/status")
async def update_status(
    candidate_id: int,
    body: UpdateCandidateStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    candidate = _get_candidate(candidate_id, current_user, db)
    candidate.status = body.status
    db.commit()
    return {"ok": True}


@router.delete("/api/candidates/{candidate_id}")
async def delete_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = _get_candidate(candidate_id, current_user, db)
    db.delete(candidate)
    db.commit()
    return {"ok": True}


@router.get("/api/candidates/{candidate_id}")
async def get_candidate_api(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = _get_candidate(candidate_id, current_user, db)
    return {
        "id": c.id, "name": c.name, "email": c.email,
        "phone": c.phone, "source": c.source, "status": c.status,
        "icp_score": c.icp_score, "rank": c.rank,
        "score_data": c.score_data,
        "applied_at": c.applied_at.isoformat(),
        "cv_text": c.cv_text,
    }


# ── Helper ─────────────────────────────────────────────────────────────────────

def _get_candidate(candidate_id: int, user: User, db: Session) -> Candidate:
    c = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.company_id == user.company_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c
