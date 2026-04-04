"""
Pipeline routes: AI-powered CV screening, scheduling, interview prep, onboarding.
All heavy AI work runs as background tasks so the API returns immediately.
"""

from __future__ import annotations
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import (
    get_db, Job, Candidate, InterviewSchedule, InterviewKit,
    OnboardingPlan, User, SessionLocal,
)
from ..auth import get_current_user
from ..schemas import (
    RunScreeningRequest, ScheduleInterviewRequest,
    GenerateOnboardingRequest, DebriefRequest,
)

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from hr_recruitment import (
    CVScreener, SchedulingAgent, InterviewPrep, OnboardingAutomation,
    CandidateProfile, RoleRequirements,
)
from hr_recruitment.models import ScoredCandidate, ICPScore

router = APIRouter()


# ── Screening ─────────────────────────────────────────────────────────────────

@router.post("/api/jobs/{job_id}/screen")
async def screen_candidates(
    job_id: int,
    body: RunScreeningRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start AI CV screening for all (or selected) candidates in a job."""
    job = _get_job(job_id, current_user, db)

    query = db.query(Candidate).filter(Candidate.job_id == job_id)
    if body.candidate_ids:
        query = query.filter(Candidate.id.in_(body.candidate_ids))
    else:
        query = query.filter(Candidate.screened_at.is_(None))

    candidates = query.all()
    if not candidates:
        return {"ok": True, "message": "No candidates to screen", "count": 0}

    candidate_ids = [c.id for c in candidates]
    background_tasks.add_task(_screen_bg, job_id, candidate_ids)
    return {"ok": True, "message": f"Screening {len(candidates)} candidates", "count": len(candidates)}


@router.get("/api/jobs/{job_id}/screening-status")
async def screening_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_job(job_id, current_user, db)
    total = db.query(Candidate).filter(Candidate.job_id == job_id).count()
    screened = db.query(Candidate).filter(
        Candidate.job_id == job_id, Candidate.screened_at.isnot(None)
    ).count()
    return {"total": total, "screened": screened, "pending": total - screened}


# ── Scheduling ────────────────────────────────────────────────────────────────

@router.post("/api/pipeline/schedule")
async def schedule_interview(
    body: ScheduleInterviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    candidate = _get_candidate(body.candidate_id, current_user, db)
    background_tasks.add_task(
        _schedule_bg,
        body.candidate_id,
        body.interviewer_name,
        body.interviewer_email,
    )
    candidate.status = "interviewing"
    db.commit()
    return {"ok": True, "message": "Interview scheduling started"}


# ── Interview Kit ─────────────────────────────────────────────────────────────

@router.post("/api/pipeline/interview-kit/{candidate_id}")
async def generate_interview_kit(
    candidate_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_candidate(candidate_id, current_user, db)
    background_tasks.add_task(_interview_kit_bg, candidate_id)
    return {"ok": True, "message": "Interview kit generation started"}


# ── Onboarding ────────────────────────────────────────────────────────────────

@router.post("/api/pipeline/onboarding")
async def generate_onboarding(
    body: GenerateOnboardingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_candidate(body.candidate_id, current_user, db)
    background_tasks.add_task(_onboarding_bg, body.candidate_id, body.start_date)
    return {"ok": True, "message": "Onboarding plan generation started"}


# ── Debrief ───────────────────────────────────────────────────────────────────

@router.post("/api/pipeline/debrief")
async def capture_debrief(
    body: DebriefRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_candidate(body.candidate_id, current_user, db)
    background_tasks.add_task(_debrief_bg, body.candidate_id, body.notes)
    return {"ok": True, "message": "Debrief processing started"}


# ── Dashboard stats API ───────────────────────────────────────────────────────

@router.get("/api/dashboard/stats")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cid = current_user.company_id
    total_jobs = db.query(Job).filter(Job.company_id == cid, Job.status == "active").count()
    total_candidates = db.query(Candidate).filter(Candidate.company_id == cid).count()
    screened = db.query(Candidate).filter(
        Candidate.company_id == cid, Candidate.screened_at.isnot(None)
    ).count()
    shortlisted = db.query(Candidate).filter(
        Candidate.company_id == cid, Candidate.icp_score >= 65
    ).count()
    interviews = db.query(InterviewSchedule).join(Candidate).filter(
        Candidate.company_id == cid
    ).count()
    hired = db.query(Candidate).filter(
        Candidate.company_id == cid, Candidate.status == "hired"
    ).count()
    return {
        "active_jobs": total_jobs,
        "total_candidates": total_candidates,
        "screened": screened,
        "shortlisted": shortlisted,
        "interviews_scheduled": interviews,
        "hired": hired,
    }


# ── Background tasks ───────────────────────────────────────────────────────────

def _screen_bg(job_id: int, candidate_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        role = _job_to_role(job)
        screener = CVScreener()
        candidates_db = db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).all()

        profiles = [
            CandidateProfile(
                candidate_id=str(c.id),
                name=c.name, email=c.email, phone=c.phone,
                cv_text=c.cv_text, source=c.source,
                application_date=c.applied_at.strftime("%Y-%m-%d"),
            )
            for c in candidates_db
        ]

        scored = screener.screen_all(profiles, role, verbose=False)
        score_map = {s.candidate_id: s for s in scored}

        for c in candidates_db:
            sc = score_map.get(str(c.id))
            if sc:
                c.icp_score = float(sc.score.total_score)
                c.icp_score_json = sc.score.model_dump_json()
                c.rank = sc.rank
                c.screened_at = datetime.utcnow()
                c.status = (
                    "shortlisted" if sc.score.total_score >= 65
                    else "screened"
                )
        db.commit()
    except Exception as e:
        print(f"[Screening error] job_id={job_id}: {e}")
    finally:
        db.close()


def _schedule_bg(candidate_id: int, interviewer_name: str, interviewer_email: str) -> None:
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return
        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        role = _job_to_role(job)

        scored = _candidate_to_scored(candidate)
        agent = SchedulingAgent(
            interviewer_name=interviewer_name,
            interviewer_email=interviewer_email,
        )
        schedule = agent.schedule_candidate(scored, role, verbose=False)

        existing = db.query(InterviewSchedule).filter(
            InterviewSchedule.candidate_id == candidate_id
        ).first()
        if existing:
            existing.schedule_json = schedule.model_dump_json()
        else:
            db.add(InterviewSchedule(
                candidate_id=candidate_id,
                job_id=candidate.job_id,
                schedule_json=schedule.model_dump_json(),
            ))
        db.commit()
    except Exception as e:
        print(f"[Scheduling error] candidate_id={candidate_id}: {e}")
    finally:
        db.close()


def _interview_kit_bg(candidate_id: int) -> None:
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return
        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        role = _job_to_role(job)
        scored = _candidate_to_scored(candidate)

        prep = InterviewPrep()
        kit = prep.generate_kit(scored, role, verbose=False)

        existing = db.query(InterviewKit).filter(
            InterviewKit.candidate_id == candidate_id
        ).first()
        if existing:
            existing.kit_json = kit.model_dump_json()
        else:
            db.add(InterviewKit(
                candidate_id=candidate_id,
                job_id=candidate.job_id,
                kit_json=kit.model_dump_json(),
            ))
        db.commit()
    except Exception as e:
        print(f"[Interview kit error] candidate_id={candidate_id}: {e}")
    finally:
        db.close()


def _onboarding_bg(candidate_id: int, start_date: str | None) -> None:
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return
        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        role = _job_to_role(job)
        scored = _candidate_to_scored(candidate)

        onboarding = OnboardingAutomation()
        plan = onboarding.generate_plan(scored, role, start_date=start_date, verbose=False)

        existing = db.query(OnboardingPlan).filter(
            OnboardingPlan.candidate_id == candidate_id
        ).first()
        if existing:
            existing.plan_json = plan.model_dump_json()
        else:
            db.add(OnboardingPlan(
                candidate_id=candidate_id,
                job_id=candidate.job_id,
                plan_json=plan.model_dump_json(),
            ))

        candidate.status = "offer"
        db.commit()
    except Exception as e:
        print(f"[Onboarding error] candidate_id={candidate_id}: {e}")
    finally:
        db.close()


def _debrief_bg(candidate_id: int, notes: str) -> None:
    db = SessionLocal()
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return
        kit_row = db.query(InterviewKit).filter(
            InterviewKit.candidate_id == candidate_id
        ).first()
        if not kit_row:
            return

        from hr_recruitment import InterviewPrep
        from hr_recruitment.models import InterviewKit as IKModel
        kit_data = kit_row.data
        kit = IKModel(**kit_data)

        prep = InterviewPrep()
        debrief = prep.capture_debrief(kit, notes, verbose=False)
        candidate.notes = json.dumps(debrief)
        db.commit()
    except Exception as e:
        print(f"[Debrief error] candidate_id={candidate_id}: {e}")
    finally:
        db.close()


# ── Conversion helpers ─────────────────────────────────────────────────────────

def _job_to_role(job: Job) -> RoleRequirements:
    return RoleRequirements(
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
        company_name=job.company.name,
        company_description=job.company.description,
    )


def _candidate_to_scored(candidate: Candidate) -> ScoredCandidate:
    if candidate.icp_score_json:
        icp = ICPScore(**json.loads(candidate.icp_score_json))
    else:
        icp = ICPScore(
            skills_match_score=20, experience_score=15, culture_fit_score=10,
            red_flags_deduction=0, total_score=45,
            skills_matched=[], skills_missing=[], red_flags=[],
            strengths=[candidate.name], recommendation="Maybe",
            one_line_summary="Unscreened candidate",
        )
    return ScoredCandidate(
        candidate_id=str(candidate.id),
        name=candidate.name,
        email=candidate.email,
        score=icp,
        rank=candidate.rank or 0,
    )


def _get_company_stats(company_id: int, db: Session) -> object:
    """Return a simple stats object for the dashboard."""
    from types import SimpleNamespace
    return SimpleNamespace(
        active_jobs=db.query(Job).filter(Job.company_id == company_id, Job.status == "active").count(),
        total_candidates=db.query(Candidate).filter(Candidate.company_id == company_id).count(),
        screened=db.query(Candidate).filter(Candidate.company_id == company_id, Candidate.screened_at.isnot(None)).count(),
        shortlisted=db.query(Candidate).filter(Candidate.company_id == company_id, Candidate.icp_score >= 65).count(),
        interviews_scheduled=db.query(InterviewSchedule).join(Candidate).filter(Candidate.company_id == company_id).count(),
        hired=db.query(Candidate).filter(Candidate.company_id == company_id, Candidate.status == "hired").count(),
    )


def _get_job(job_id: int, user: User, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.company_id == user.company_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_candidate(candidate_id: int, user: User, db: Session) -> Candidate:
    c = db.query(Candidate).filter(
        Candidate.id == candidate_id, Candidate.company_id == user.company_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return c
