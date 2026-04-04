"""
Job management routes: CRUD for job postings + AI JD generation.
"""

from __future__ import annotations
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db, Job, Candidate, User
from ..auth import get_current_user
from ..schemas import CreateJobRequest, UpdateJobRequest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from hr_recruitment import JobDescriptionGenerator, RoleRequirements

router = APIRouter()
templates = Jinja2Templates(directory="saas/templates")


# ── Page routes ───────────────────────────────────────────────────────────────

@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(Job)
        .filter(Job.company_id == current_user.company_id)
        .order_by(Job.created_at.desc())
        .all()
    )
    job_data = []
    for job in jobs:
        count = db.query(Candidate).filter(Candidate.job_id == job.id).count()
        shortlisted = (
            db.query(Candidate)
            .filter(Candidate.job_id == job.id, Candidate.icp_score >= 65)
            .count()
        )
        job_data.append({
            "id": job.id, "title": job.title, "department": job.department,
            "location": job.location, "status": job.status,
            "candidate_count": count, "shortlisted_count": shortlisted,
            "created_at": job.created_at.strftime("%d %b %Y"),
        })
    return templates.TemplateResponse("jobs.html", {
        "request": request, "user": current_user, "jobs": job_data,
    })


@router.get("/jobs/new", response_class=HTMLResponse)
async def new_job_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse("job_new.html", {
        "request": request, "user": current_user,
    })


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, current_user, db)
    candidates = (
        db.query(Candidate)
        .filter(Candidate.job_id == job_id)
        .order_by(Candidate.rank, Candidate.applied_at.desc())
        .all()
    )
    pipeline_stages = {
        "applied": [], "screened": [], "shortlisted": [],
        "interviewing": [], "offer": [], "hired": [], "rejected": [],
    }
    for c in candidates:
        stage = c.status if c.status in pipeline_stages else "applied"
        pipeline_stages[stage].append({
            "id": c.id, "name": c.name, "email": c.email,
            "source": c.source, "icp_score": c.icp_score,
            "rank": c.rank, "status": c.status,
            "applied_at": c.applied_at.strftime("%d %b %Y"),
            "score_data": c.score_data,
        })
    return templates.TemplateResponse("job_detail.html", {
        "request": request, "user": current_user,
        "job": job, "pipeline": pipeline_stages,
        "total_candidates": len(candidates),
        "jd": job.jd,
    })


# ── API routes ────────────────────────────────────────────────────────────────

@router.get("/api/jobs")
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.query(Job).filter(Job.company_id == current_user.company_id).all()
    return [
        {
            "id": j.id, "title": j.title, "department": j.department,
            "status": j.status, "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.post("/api/jobs")
async def create_job(
    body: CreateJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = Job(
        company_id=current_user.company_id,
        created_by=current_user.id,
        title=body.title,
        department=body.department,
        location=body.location,
        employment_type=body.employment_type,
        remote_policy=body.remote_policy,
        salary_range=body.salary_range,
        years_experience=body.years_experience,
        required_skills=json.dumps(body.required_skills),
        nice_to_have_skills=json.dumps(body.nice_to_have_skills),
        responsibilities=json.dumps(body.responsibilities),
        status="active",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if body.generate_jd:
        background_tasks.add_task(_generate_jd_bg, job.id, current_user.company_id, db)

    return {"ok": True, "job_id": job.id}


@router.patch("/api/jobs/{job_id}")
async def update_job(
    job_id: int,
    body: UpdateJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, current_user, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(job, field, value)
    job.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.delete("/api/jobs/{job_id}")
async def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, current_user, db)
    job.status = "closed"
    db.commit()
    return {"ok": True}


@router.post("/api/jobs/{job_id}/generate-jd")
async def regenerate_jd(
    job_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_job(job_id, current_user, db)
    background_tasks.add_task(_generate_jd_bg, job.id, current_user.company_id, db)
    return {"ok": True, "message": "JD generation started"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_job(job_id: int, user: User, db: Session) -> Job:
    job = db.query(Job).filter(
        Job.id == job_id, Job.company_id == user.company_id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _generate_jd_bg(job_id: int, company_id: int, db: Session) -> None:
    """Background task: generate JD with Claude and persist it."""
    from ..database import SessionLocal
    db2 = SessionLocal()
    try:
        job = db2.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        company = job.company
        role = RoleRequirements(
            title=job.title,
            department=job.department,
            location=job.location,
            employment_type=job.employment_type,
            remote_policy=job.remote_policy,
            salary_range=job.salary_range,
            years_experience=job.years_experience,
            required_skills=job.required_skills_list,
            nice_to_have_skills=job.nice_to_have_list,
            responsibilities=job.responsibilities_list,
            company_name=company.name,
            company_description=company.description,
        )
        gen = JobDescriptionGenerator()
        jd = gen.generate(role, verbose=False)
        job.job_description_json = jd.model_dump_json()
        db2.commit()
    except Exception as e:
        print(f"[JD generation error] job_id={job_id}: {e}")
    finally:
        db2.close()
