"""
Configuration for the HR Recruitment Automation system.
"""

import os

# ── Claude API ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-6"

# Adaptive thinking + high effort for complex reasoning tasks
THINKING_CONFIG = {"type": "adaptive"}
EFFORT_HIGH = {"effort": "high"}
EFFORT_MEDIUM = {"effort": "medium"}

# Token budgets
MAX_TOKENS_JD = 4096
MAX_TOKENS_SCREENING = 2048
MAX_TOKENS_SCHEDULING = 2048
MAX_TOKENS_INTERVIEW = 4096
MAX_TOKENS_ONBOARDING = 8192

# ── Pipeline defaults ─────────────────────────────────────────────────────────
SHORTLIST_THRESHOLD = 60          # Minimum ICP score to shortlist
SHORTLIST_MAX_CANDIDATES = 10     # Maximum candidates to shortlist
DEFAULT_INTERVIEW_DURATION = 60   # minutes
DEFAULT_INTERVIEW_FORMAT = "Video call"

# ── Simulated integrations (stubs — replace with real API calls) ──────────────
CALENDLY_BASE_URL = "https://calendly.com/company-hiring"
ATS_WEBHOOK_URL = os.environ.get("ATS_WEBHOOK_URL", "https://ats.example.com/webhook")
GREENHOUSE_API_KEY = os.environ.get("GREENHOUSE_API_KEY", "")
WORKABLE_API_KEY = os.environ.get("WORKABLE_API_KEY", "")

# Job board targets for JD sync
JOB_BOARDS = ["LinkedIn", "Indeed", "Glassdoor"]

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_JD = """\
You are an expert HR copywriter and talent acquisition specialist.
You write inclusive, SEO-optimised job descriptions that attract top talent.
Your JDs are clear, compelling, free of gendered language, and structured for
easy scanning. Always output valid JSON matching the requested schema."""

SYSTEM_SCREENER = """\
You are a senior talent acquisition specialist with deep expertise in CV evaluation.
You apply a structured Ideal Candidate Profile (ICP) rubric to objectively score
and rank candidates. You identify both strengths and red flags clearly.
Always output valid JSON matching the requested schema."""

SYSTEM_SCHEDULER = """\
You are an AI recruiting coordinator. You draft personalised, warm outreach messages
and handle interview scheduling logistics professionally.
Always output valid JSON matching the requested schema."""

SYSTEM_INTERVIEW = """\
You are an expert interviewer and hiring coach. You design structured, behavioural,
and competency-based interview kits tailored to each candidate's background.
Always output valid JSON matching the requested schema."""

SYSTEM_ONBOARDING = """\
You are an HR specialist and onboarding expert. You create comprehensive, welcoming
onboarding plans that set new hires up for success from day 1.
Always output valid JSON matching the requested schema."""
