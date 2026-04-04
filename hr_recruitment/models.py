"""
Data models for the HR Recruitment Automation pipeline.
Uses Pydantic for structured outputs from Claude.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel


# ── Input models ──────────────────────────────────────────────────────────────

@dataclass
class RoleRequirements:
    """Input spec for generating a job description."""
    title: str
    department: str
    location: str
    employment_type: str                   # e.g. "Full-time", "Contract"
    required_skills: List[str]
    nice_to_have_skills: List[str]
    years_experience: int
    responsibilities: List[str]
    salary_range: Optional[str] = None
    remote_policy: str = "Hybrid"
    company_name: str = "Company"
    company_description: str = ""


@dataclass
class CandidateProfile:
    """Raw candidate data (from ATS or manual entry)."""
    candidate_id: str
    name: str
    email: str
    phone: str
    cv_text: str                           # Full CV as plain text
    application_date: str = ""
    source: str = "Direct"                 # LinkedIn / Indeed / Referral


# ── Structured output schemas (Pydantic — returned by Claude) ─────────────────

class JobDescription(BaseModel):
    title: str
    department: str
    location: str
    employment_type: str
    summary: str
    responsibilities: List[str]
    required_qualifications: List[str]
    preferred_qualifications: List[str]
    what_we_offer: List[str]
    about_company: str
    equal_opportunity_statement: str
    seo_keywords: List[str]
    estimated_read_time_seconds: int


class ICPScore(BaseModel):
    """Ideal Candidate Profile score breakdown."""
    skills_match_score: int        # 0-40
    experience_score: int          # 0-30
    culture_fit_score: int         # 0-20
    red_flags_deduction: int       # 0-30 (subtracted)
    total_score: int               # 0-100
    skills_matched: List[str]
    skills_missing: List[str]
    red_flags: List[str]
    strengths: List[str]
    recommendation: str            # "Strong Yes" / "Yes" / "Maybe" / "No"
    one_line_summary: str


class ScoredCandidate(BaseModel):
    candidate_id: str
    name: str
    email: str
    score: ICPScore
    rank: int = 0


class OutreachMessage(BaseModel):
    subject: str
    body: str
    call_to_action: str


class InterviewSchedule(BaseModel):
    candidate_id: str
    candidate_name: str
    candidate_email: str
    proposed_slots: List[str]      # ISO-8601 datetime strings
    interview_format: str          # "Video call" / "Phone" / "On-site"
    duration_minutes: int
    interviewer_names: List[str]
    calendar_link: str
    confirmation_message: str


class InterviewQuestion(BaseModel):
    category: str                  # "Technical" / "Behavioural" / "Culture Fit" / "Role-Specific"
    question: str
    follow_up_probes: List[str]
    what_good_looks_like: str


class InterviewKit(BaseModel):
    candidate_id: str
    candidate_name: str
    role: str
    opening_script: str
    questions: List[InterviewQuestion]
    scoring_rubric: str
    closing_script: str
    debrief_template: str


class OnboardingTask(BaseModel):
    day: str                       # "Day 1" / "Week 1" / "30 days" / "60 days" / "90 days"
    category: str                  # "IT Setup" / "HR Admin" / "Training" / "Team Integration"
    task: str
    owner: str                     # "IT" / "HR" / "Hiring Manager" / "New Hire"
    due_date_offset_days: int


class OnboardingPlan(BaseModel):
    candidate_name: str
    role: str
    start_date: str
    welcome_email_subject: str
    welcome_email_body: str
    contract_checklist: List[str]
    it_setup_items: List[str]
    tasks: List[OnboardingTask]
    day_1_schedule: str
    thirty_sixty_ninety_goals: str


# ── Pipeline summary ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """End-to-end result for a single hiring run."""
    role: str
    job_description: Optional[JobDescription] = None
    shortlisted_candidates: List[ScoredCandidate] = field(default_factory=list)
    interview_schedules: List[InterviewSchedule] = field(default_factory=list)
    interview_kits: List[InterviewKit] = field(default_factory=list)
    onboarding_plans: List[OnboardingPlan] = field(default_factory=list)
    total_candidates_reviewed: int = 0
    time_saved_hours_estimate: float = 0.0
