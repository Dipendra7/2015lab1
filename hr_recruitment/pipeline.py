"""
Full Hiring Pipeline Orchestrator
Ties all steps together: audit → JD → screening → scheduling → interviews → onboarding.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Callable

import anthropic

from .models import (
    RoleRequirements, CandidateProfile, PipelineResult,
)
from .jd_generator import JobDescriptionGenerator
from .cv_screener import CVScreener
from .scheduling_agent import SchedulingAgent
from .interview_prep import InterviewPrep
from .onboarding import OnboardingAutomation
from .config import SHORTLIST_THRESHOLD, SHORTLIST_MAX_CANDIDATES


@dataclass
class PipelineConfig:
    """Runtime configuration for the hiring pipeline."""
    shortlist_threshold: int = SHORTLIST_THRESHOLD
    shortlist_max: int = SHORTLIST_MAX_CANDIDATES
    generate_jd: bool = True
    screen_cvs: bool = True
    schedule_interviews: bool = True
    generate_interview_kits: bool = True
    generate_onboarding: bool = True
    interviewer_name: str = "Hiring Manager"
    interviewer_email: str = "hiring@company.com"
    start_date: str | None = None
    verbose: bool = True


class HiringPipeline:
    """
    End-to-end AI hiring pipeline.

    Usage:
        pipeline = HiringPipeline()
        result = pipeline.run(role, candidates)
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        config: PipelineConfig | None = None,
    ):
        self.client = client or anthropic.Anthropic()
        self.config = config or PipelineConfig()

        # Instantiate all modules with the shared client
        self.jd_gen = JobDescriptionGenerator(self.client)
        self.screener = CVScreener(self.client)
        self.scheduler = SchedulingAgent(
            self.client,
            interviewer_name=self.config.interviewer_name,
            interviewer_email=self.config.interviewer_email,
        )
        self.interview_prep = InterviewPrep(self.client)
        self.onboarding = OnboardingAutomation(self.client)

    def run(
        self,
        role: RoleRequirements,
        candidates: list[CandidateProfile],
        on_step_complete: Callable[[str, object], None] | None = None,
    ) -> PipelineResult:
        """
        Execute the full hiring pipeline.

        Args:
            role: Role requirements spec.
            candidates: List of candidate profiles to evaluate.
            on_step_complete: Optional callback(step_name, result) after each step.

        Returns:
            PipelineResult with all outputs.
        """
        cfg = self.config
        result = PipelineResult(
            role=role.title,
            total_candidates_reviewed=len(candidates),
        )
        t0 = time.time()

        self._banner(f"AI HR PIPELINE — {role.title.upper()}")
        print(f"  Company : {role.company_name}")
        print(f"  Mode    : {'Verbose' if cfg.verbose else 'Silent'}")
        print(f"  Steps   : {self._enabled_steps()}")

        # ── Step 1: Hiring Process Audit (prompt-driven) ──────────────────────
        self._step_header("1", "Hiring Process Audit")
        audit = self._run_audit(role)
        self._emit(on_step_complete, "audit", audit)

        # ── Step 2: AI Job Description Generator ─────────────────────────────
        if cfg.generate_jd:
            self._step_header("2", "AI Job Description Generator")
            result.job_description = self.jd_gen.generate(role, verbose=cfg.verbose)
            jd_display = self.jd_gen.format_for_display(result.job_description)
            print("\n" + jd_display[:1500] + ("..." if len(jd_display) > 1500 else ""))
            self._emit(on_step_complete, "jd_generated", result.job_description)

        # ── Step 3: Automated CV Screening & Scoring ──────────────────────────
        if cfg.screen_cvs and candidates:
            self._step_header("3", "Automated CV Screening & Scoring")
            scored = self.screener.screen_all(candidates, role, verbose=cfg.verbose)
            self.screener.print_leaderboard(scored)
            shortlist = self.screener.get_shortlist(
                scored,
                threshold=cfg.shortlist_threshold,
                max_candidates=cfg.shortlist_max,
            )
            result.shortlisted_candidates = shortlist
            print(
                f"\n  Shortlisted {len(shortlist)}/{len(scored)} candidates "
                f"(threshold ≥{cfg.shortlist_threshold})"
            )
            self._emit(on_step_complete, "screening_complete", scored)
        else:
            shortlist = []

        # ── Step 4: Candidate Outreach & Scheduling ───────────────────────────
        if cfg.schedule_interviews and shortlist:
            self._step_header("4", "Candidate Outreach & Scheduling")
            result.interview_schedules = self.scheduler.schedule_shortlist(
                shortlist, role, verbose=cfg.verbose
            )
            self._emit(
                on_step_complete, "scheduling_complete", result.interview_schedules
            )

        # ── Step 5: Interview Prep & Debrief Automation ───────────────────────
        if cfg.generate_interview_kits and shortlist:
            self._step_header("5", "Interview Prep & Debrief Automation")
            result.interview_kits = self.interview_prep.generate_all_kits(
                shortlist, role, verbose=cfg.verbose
            )
            if cfg.verbose and result.interview_kits:
                sample = self.interview_prep.format_kit_for_display(result.interview_kits[0])
                print("\n" + sample[:2000] + ("..." if len(sample) > 2000 else ""))
            self._emit(
                on_step_complete, "interview_kits_ready", result.interview_kits
            )

        # ── Step 6: Onboarding Workflow Automation ────────────────────────────
        if cfg.generate_onboarding and shortlist:
            self._step_header("6", "Onboarding Workflow Automation")
            for candidate in shortlist[:3]:  # Generate for top 3 candidates
                plan = self.onboarding.generate_plan(
                    candidate, role,
                    start_date=cfg.start_date,
                    verbose=cfg.verbose,
                )
                result.onboarding_plans.append(plan)
                if cfg.verbose:
                    self.onboarding.print_checklist(plan)
                    self.onboarding.trigger_day_zero_actions(plan, verbose=cfg.verbose)
            self._emit(
                on_step_complete, "onboarding_ready", result.onboarding_plans
            )

        # ── Pipeline Summary ──────────────────────────────────────────────────
        elapsed = time.time() - t0
        result.time_saved_hours_estimate = self._estimate_time_saved(result)
        self._print_summary(result, elapsed)

        return result

    # ── Private helpers ────────────────────────────────────────────────────────

    def _run_audit(self, role: RoleRequirements) -> dict:
        """Quick AI audit of current hiring process pain points."""
        prompt = f"""
Perform a quick hiring process audit for this role.

Role: {role.title} at {role.company_name}
Department: {role.department}
Required Skills: {", ".join(role.required_skills)}

Identify:
1. Top 3 likely time drains in the hiring process
2. Key bottlenecks specific to this role/skill set
3. Recommended priority order for automation

Return a brief JSON summary:
{{
  "time_drains": ["string", ...],
  "bottlenecks": ["string", ...],
  "automation_priorities": ["string", ...]
}}
"""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(
            (b.text for b in response.content if b.type == "text"), "{}"
        )
        import json
        start = text.find("{")
        end = text.rfind("}") + 1
        try:
            audit = json.loads(text[start:end]) if start != -1 else {}
        except Exception:
            audit = {}

        if self.config.verbose and audit:
            print("\n  Time Drains Identified:")
            for d in audit.get("time_drains", []):
                print(f"    • {d}")
            print("  Automation Priorities:")
            for p in audit.get("automation_priorities", []):
                print(f"    ✓ {p}")
        return audit

    def _estimate_time_saved(self, result: PipelineResult) -> float:
        """Estimate hours saved vs. manual process."""
        n = result.total_candidates_reviewed
        shortlisted = len(result.shortlisted_candidates)
        manual_hours = (
            n * 0.5           # 30 min per CV manually
            + 1.5             # JD writing
            + shortlisted * 0.75  # scheduling per candidate
            + shortlisted * 1.0   # interview prep per candidate
            + min(shortlisted, 3) * 2.0  # onboarding plan per hire
        )
        ai_hours = (
            n * 0.02          # AI screening ~1-2 min per CV
            + 0.1             # JD generation
            + shortlisted * 0.05  # scheduling
            + shortlisted * 0.1   # interview prep
            + min(shortlisted, 3) * 0.1  # onboarding
        )
        return round(manual_hours - ai_hours, 1)

    def _enabled_steps(self) -> str:
        cfg = self.config
        steps = ["Audit"]
        if cfg.generate_jd:
            steps.append("JD Gen")
        if cfg.screen_cvs:
            steps.append("CV Screen")
        if cfg.schedule_interviews:
            steps.append("Scheduling")
        if cfg.generate_interview_kits:
            steps.append("Interview Prep")
        if cfg.generate_onboarding:
            steps.append("Onboarding")
        return " → ".join(steps)

    def _print_summary(self, result: PipelineResult, elapsed: float) -> None:
        self._banner("PIPELINE COMPLETE")
        print(f"  Role                  : {result.role}")
        print(f"  Candidates reviewed   : {result.total_candidates_reviewed}")
        print(f"  Shortlisted           : {len(result.shortlisted_candidates)}")
        print(f"  Interviews scheduled  : {len(result.interview_schedules)}")
        print(f"  Interview kits        : {len(result.interview_kits)}")
        print(f"  Onboarding plans      : {len(result.onboarding_plans)}")
        print(f"  Estimated time saved  : ~{result.time_saved_hours_estimate}h vs manual")
        print(f"  Pipeline duration     : {elapsed:.0f}s")
        pct = min(75, round((result.time_saved_hours_estimate / max(1, result.time_saved_hours_estimate + elapsed / 3600)) * 100))
        print(f"  Time-to-hire reduction: ~{pct}%")

    def _banner(self, text: str) -> None:
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}")

    def _step_header(self, number: str, title: str) -> None:
        print(f"\n{'─'*60}")
        print(f"  Step {number}: {title}")
        print(f"{'─'*60}")

    def _emit(
        self,
        callback: Callable | None,
        step: str,
        data: object,
    ) -> None:
        if callback:
            try:
                callback(step, data)
            except Exception:
                pass
