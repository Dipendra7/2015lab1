"""
HireAI — SaaS HR Recruitment Platform
FastAPI application entry point.

Run with:
    ANTHROPIC_API_KEY=sk-ant-... uvicorn saas.app:app --reload
"""

from __future__ import annotations
import os
import sys
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .database import init_db, get_db, Job, Candidate, InterviewSchedule
from .auth import get_current_user, get_optional_user
from .routes.auth_routes import router as auth_router
from .routes.job_routes import router as job_router
from .routes.candidate_routes import router as candidate_router
from .routes.pipeline_routes import router as pipeline_router
from sqlalchemy.orm import Session

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HireAI",
    description="AI-powered HR Recruitment SaaS Platform",
    version="1.0.0",
    docs_url="/api/docs",
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# ── Register routers ──────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(job_router)
app.include_router(candidate_router)
app.include_router(pipeline_router)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    init_db()
    print("\n✓ HireAI started")
    print(f"  API Key present: {'Yes' if os.environ.get('ANTHROPIC_API_KEY') else 'NO — set ANTHROPIC_API_KEY'}")
    print("  Docs: http://localhost:8000/api/docs\n")


# ── Root & dashboard routes ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cid = current_user.company_id
    hour = datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    # Stats
    from .routes.pipeline_routes import _get_company_stats
    stats = _get_company_stats(cid, db)

    # Recent active jobs
    jobs = (
        db.query(Job)
        .filter(Job.company_id == cid, Job.status == "active")
        .order_by(Job.created_at.desc())
        .limit(5)
        .all()
    )
    recent_jobs = []
    for job in jobs:
        count = db.query(Candidate).filter(Candidate.job_id == job.id).count()
        recent_jobs.append({
            "id": job.id, "title": job.title,
            "department": job.department, "location": job.location,
            "status": job.status, "candidate_count": count,
        })

    # Activity feed: recent AI actions
    activity = _build_activity_feed(cid, db)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "greeting": greeting,
        "stats": stats,
        "recent_jobs": recent_jobs,
        "activity": activity,
    })


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "HireAI",
        "ai_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_activity_feed(company_id: int, db: Session) -> list[dict]:
    """Build a simple activity feed from recent DB actions."""
    items = []

    # Recent screenings
    recent_screened = (
        db.query(Candidate)
        .filter(
            Candidate.company_id == company_id,
            Candidate.screened_at.isnot(None),
        )
        .order_by(Candidate.screened_at.desc())
        .limit(3)
        .all()
    )
    for c in recent_screened:
        items.append({
            "text": f"AI screened {c.name} — score {int(c.icp_score or 0)}/100",
            "time": c.screened_at.strftime("%d %b, %H:%M"),
            "icon": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
        })

    # Recent job creations
    recent_jobs = (
        db.query(Job)
        .filter(Job.company_id == company_id)
        .order_by(Job.created_at.desc())
        .limit(2)
        .all()
    )
    for job in recent_jobs:
        items.append({
            "text": f"Job posted: {job.title}",
            "time": job.created_at.strftime("%d %b, %H:%M"),
            "icon": "M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
        })

    # Recent interviews
    recent_interviews = (
        db.query(InterviewSchedule)
        .join(Candidate)
        .filter(Candidate.company_id == company_id)
        .order_by(InterviewSchedule.created_at.desc())
        .limit(2)
        .all()
    )
    for sched in recent_interviews:
        items.append({
            "text": f"Interview scheduled: {sched.candidate.name}",
            "time": sched.created_at.strftime("%d %b, %H:%M"),
            "icon": "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
        })

    # Sort by time, take top 8
    items.sort(key=lambda x: x["time"], reverse=True)
    return items[:8]
