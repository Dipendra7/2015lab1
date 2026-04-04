"""
Pydantic request/response schemas for the SaaS API.
"""

from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    company_name: str
    full_name: str
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class InviteUserRequest(BaseModel):
    email: str
    full_name: str
    role: str = "recruiter"
    password: str


# ── Jobs ──────────────────────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    title: str
    department: str = ""
    location: str = "Remote"
    employment_type: str = "Full-time"
    remote_policy: str = "Hybrid"
    salary_range: str = ""
    years_experience: int = 3
    required_skills: List[str] = []
    nice_to_have_skills: List[str] = []
    responsibilities: List[str] = []
    generate_jd: bool = True


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    salary_range: Optional[str] = None


class JobResponse(BaseModel):
    id: int
    title: str
    department: str
    location: str
    employment_type: str
    status: str
    candidate_count: int = 0
    shortlisted_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Candidates ────────────────────────────────────────────────────────────────

class AddCandidateRequest(BaseModel):
    name: str
    email: str
    phone: str = ""
    source: str = "Direct"
    cv_text: str


class UpdateCandidateStatusRequest(BaseModel):
    status: str


class CandidateResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    source: str
    status: str
    icp_score: Optional[float]
    rank: int
    applied_at: datetime

    model_config = {"from_attributes": True}


# ── Pipeline ──────────────────────────────────────────────────────────────────

class RunScreeningRequest(BaseModel):
    candidate_ids: Optional[List[int]] = None   # None = screen all unscreened


class ScheduleInterviewRequest(BaseModel):
    candidate_id: int
    interviewer_name: str = "Hiring Manager"
    interviewer_email: str = "hiring@company.com"


class GenerateOnboardingRequest(BaseModel):
    candidate_id: int
    start_date: Optional[str] = None


class DebriefRequest(BaseModel):
    candidate_id: int
    notes: str
