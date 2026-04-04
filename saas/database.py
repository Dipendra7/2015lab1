"""
Database models for the HR Recruitment SaaS platform.
Uses SQLAlchemy with SQLite (swap DATABASE_URL to PostgreSQL for production).
"""

from __future__ import annotations
import json
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, ForeignKey, Boolean, Float,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hr_saas.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM Models ────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    plan = Column(String(50), default="starter")     # starter / pro / enterprise
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    jobs = relationship("Job", back_populates="company")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(String(50), default="recruiter")   # admin / recruiter / interviewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    department = Column(String(100), default="")
    location = Column(String(100), default="")
    employment_type = Column(String(50), default="Full-time")
    remote_policy = Column(String(100), default="Hybrid")
    salary_range = Column(String(100), default="")
    years_experience = Column(Integer, default=3)
    required_skills = Column(Text, default="[]")     # JSON list
    nice_to_have_skills = Column(Text, default="[]") # JSON list
    responsibilities = Column(Text, default="[]")    # JSON list
    status = Column(String(50), default="draft")     # draft / active / closed / paused
    job_description_json = Column(Text, default="")  # Generated JD (JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")
    candidates = relationship("Candidate", back_populates="job")

    @property
    def required_skills_list(self) -> list:
        return json.loads(self.required_skills or "[]")

    @property
    def nice_to_have_list(self) -> list:
        return json.loads(self.nice_to_have_skills or "[]")

    @property
    def responsibilities_list(self) -> list:
        return json.loads(self.responsibilities or "[]")

    @property
    def jd(self) -> dict:
        return json.loads(self.job_description_json) if self.job_description_json else {}


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False)
    phone = Column(String(50), default="")
    source = Column(String(100), default="Direct")
    cv_text = Column(Text, nullable=False)
    status = Column(String(50), default="applied")
    # applied → screened → shortlisted → interviewing → offer → hired / rejected
    icp_score = Column(Float, default=None)
    icp_score_json = Column(Text, default="")        # Full ICPScore JSON
    rank = Column(Integer, default=0)
    applied_at = Column(DateTime, default=datetime.utcnow)
    screened_at = Column(DateTime, default=None)
    notes = Column(Text, default="")

    job = relationship("Job", back_populates="candidates")
    interview_schedule = relationship("InterviewSchedule", back_populates="candidate", uselist=False)
    interview_kit = relationship("InterviewKit", back_populates="candidate", uselist=False)
    onboarding_plan = relationship("OnboardingPlan", back_populates="candidate", uselist=False)

    @property
    def score_data(self) -> dict:
        return json.loads(self.icp_score_json) if self.icp_score_json else {}


class InterviewSchedule(Base):
    __tablename__ = "interview_schedules"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), unique=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    schedule_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="interview_schedule")

    @property
    def data(self) -> dict:
        return json.loads(self.schedule_json) if self.schedule_json else {}


class InterviewKit(Base):
    __tablename__ = "interview_kits"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), unique=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    kit_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="interview_kit")

    @property
    def data(self) -> dict:
        return json.loads(self.kit_json) if self.kit_json else {}


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), unique=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    plan_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="onboarding_plan")

    @property
    def data(self) -> dict:
        return json.loads(self.plan_json) if self.plan_json else {}


# ── DB helpers ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
