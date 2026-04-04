"""
AI HR & Recruitment Automation
Automates the full hiring pipeline using Claude claude-opus-4-6.
"""

from .jd_generator import JobDescriptionGenerator
from .cv_screener import CVScreener
from .scheduling_agent import SchedulingAgent
from .interview_prep import InterviewPrep
from .onboarding import OnboardingAutomation
from .pipeline import HiringPipeline
from .models import (
    RoleRequirements,
    JobDescription,
    CandidateProfile,
    ScoredCandidate,
    InterviewSchedule,
    InterviewKit,
    OnboardingPlan,
)

__all__ = [
    "JobDescriptionGenerator",
    "CVScreener",
    "SchedulingAgent",
    "InterviewPrep",
    "OnboardingAutomation",
    "HiringPipeline",
    "RoleRequirements",
    "JobDescription",
    "CandidateProfile",
    "ScoredCandidate",
    "InterviewSchedule",
    "InterviewKit",
    "OnboardingPlan",
]
