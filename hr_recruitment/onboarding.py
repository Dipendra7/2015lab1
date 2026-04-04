"""
Step 6: Onboarding Workflow Automation
On offer acceptance: auto-send contract, IT setup form, welcome email sequence,
and a 30/60/90 day onboarding checklist.
"""

from __future__ import annotations
import json
from datetime import datetime
import anthropic
from pydantic import ValidationError

from .models import ScoredCandidate, RoleRequirements, OnboardingPlan, OnboardingTask
from .config import (
    MODEL, THINKING_CONFIG, EFFORT_HIGH,
    MAX_TOKENS_ONBOARDING, SYSTEM_ONBOARDING,
)


class OnboardingAutomation:
    """
    Generate comprehensive onboarding plans and trigger automated workflows
    when a candidate accepts an offer.
    """

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def generate_plan(
        self,
        candidate: ScoredCandidate,
        role: RoleRequirements,
        start_date: str | None = None,
        verbose: bool = True,
    ) -> OnboardingPlan:
        """
        Generate a complete onboarding plan for a new hire.
        Uses streaming — onboarding plans are long-form content.
        """
        if start_date is None:
            # Default: 2 weeks from now
            start_date = (
                datetime.now()
                .replace(hour=9, minute=0)
            ).strftime("%Y-%m-%d")

        prompt = self._build_onboarding_prompt(candidate, role, start_date)

        if verbose:
            print(f"\n  Generating onboarding plan for: {candidate.name}...", end="")

        full_text = ""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS_ONBOARDING,
            thinking=THINKING_CONFIG,
            output_config=EFFORT_HIGH,
            system=SYSTEM_ONBOARDING,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        full_text += event.delta.text
            stream.get_final_message()

        plan_data = self._extract_json(full_text)
        try:
            plan = OnboardingPlan(**plan_data)
        except (ValidationError, TypeError) as exc:
            raise ValueError(
                f"Invalid onboarding plan for {candidate.name}: {exc}"
            ) from exc

        if verbose:
            task_count = len(plan.tasks)
            print(f" Done ({task_count} tasks across 90 days)")

        return plan

    def trigger_day_zero_actions(
        self,
        plan: OnboardingPlan,
        verbose: bool = True,
    ) -> dict:
        """
        Trigger all Day 0 actions when the offer is accepted.
        Simulates integrations with DocuSign, IT ticketing, and email.
        Replace stubs with real API calls.
        """
        results = {
            "contract_sent": self._send_contract(plan),
            "it_ticket_created": self._create_it_ticket(plan),
            "welcome_email_sent": self._send_welcome_email(plan),
            "ats_updated": self._update_ats_status(plan, "Offer Accepted"),
        }

        if verbose:
            print(f"\n  Day-0 actions triggered for {plan.candidate_name}:")
            for action, result in results.items():
                status = "✓" if result.get("success") else "✗"
                print(f"    {status} {action.replace('_', ' ').title()}")

        return results

    def print_checklist(self, plan: OnboardingPlan) -> None:
        """Print the onboarding checklist grouped by timeline."""
        print(f"\n{'='*60}")
        print(f"  Onboarding Plan: {plan.candidate_name}")
        print(f"  Role: {plan.role}  |  Start Date: {plan.start_date}")
        print(f"{'='*60}")

        # Group tasks by day
        from collections import defaultdict
        groups: dict[str, list[OnboardingTask]] = defaultdict(list)
        order = ["Day 1", "Week 1", "30 days", "60 days", "90 days"]
        for task in plan.tasks:
            groups[task.day].append(task)

        for period in order:
            tasks = groups.get(period, [])
            if tasks:
                print(f"\n  {period.upper()}")
                for task in tasks:
                    print(f"    [{task.owner:12}] {task.task}")

        print(f"\n{'─'*60}")
        print("  30/60/90 Day Goals:")
        for line in plan.thirty_sixty_ninety_goals.split("\n"):
            print(f"  {line}")

    def format_welcome_email(self, plan: OnboardingPlan) -> str:
        """Return the formatted welcome email as a string."""
        return (
            f"Subject: {plan.welcome_email_subject}\n\n"
            + plan.welcome_email_body
        )

    # ── Private stubs (replace with real integrations) ────────────────────────

    def _send_contract(self, plan: OnboardingPlan) -> dict:
        """Send offer letter + contract via DocuSign / HelloSign stub."""
        items = plan.contract_checklist
        return {
            "success": True,
            "method": "DocuSign",
            "documents": items,
            "recipient": plan.candidate_name,
        }

    def _create_it_ticket(self, plan: OnboardingPlan) -> dict:
        """Create IT setup ticket in Jira / ServiceNow stub."""
        return {
            "success": True,
            "ticket_id": f"IT-{abs(hash(plan.candidate_name)) % 10000:04d}",
            "items": plan.it_setup_items,
            "due_date": plan.start_date,
        }

    def _send_welcome_email(self, plan: OnboardingPlan) -> dict:
        """Send welcome email sequence via email provider stub."""
        return {
            "success": True,
            "subject": plan.welcome_email_subject,
            "recipient": plan.candidate_name,
            "sequence_length": 3,
        }

    def _update_ats_status(self, plan: OnboardingPlan, status: str) -> dict:
        """Update candidate status in ATS (Greenhouse / Workable) stub."""
        return {
            "success": True,
            "candidate": plan.candidate_name,
            "new_status": status,
        }

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def _build_onboarding_prompt(
        self, candidate: ScoredCandidate, role: RoleRequirements, start_date: str
    ) -> str:
        return f"""
Create a comprehensive onboarding plan for a new hire.

NEW HIRE DETAILS
================
Name: {candidate.name}
Role: {role.title}
Department: {role.department}
Company: {role.company_name}
Start Date: {start_date}
ICP Score: {candidate.score.total_score}/100
Strengths: {", ".join(candidate.score.strengths[:4])}

ROLE CONTEXT
============
Key Responsibilities: {"; ".join(role.responsibilities[:5])}
Required Skills: {", ".join(role.required_skills)}

REQUIREMENTS
============
1. Write a warm, personalised welcome email (subject + body).
2. List all contract documents to send on offer acceptance.
3. List all IT setup items (laptop, accounts, access, tools).
4. Create a 90-day onboarding task list with:
   - Day 1: orientation, introductions, first tasks
   - Week 1: team meetings, system setup, training start
   - 30 days: initial goals, first check-in
   - 60 days: ramp-up milestones, feedback cycle
   - 90 days: independent contributions, performance review prep
5. Provide a Day 1 detailed schedule (hour by hour).
6. Write SMART 30/60/90 day goals for this specific role.

Return ONLY valid JSON matching this exact schema:
{{
  "candidate_name": "{candidate.name}",
  "role": "{role.title}",
  "start_date": "{start_date}",
  "welcome_email_subject": "string",
  "welcome_email_body": "string (warm, personalised, multi-paragraph)",
  "contract_checklist": ["string", ...],
  "it_setup_items": ["string", ...],
  "tasks": [
    {{
      "day": "Day 1" | "Week 1" | "30 days" | "60 days" | "90 days",
      "category": "IT Setup" | "HR Admin" | "Training" | "Team Integration" | "Role Tasks",
      "task": "string",
      "owner": "IT" | "HR" | "Hiring Manager" | "New Hire" | "Team",
      "due_date_offset_days": integer
    }},
    ...
  ],
  "day_1_schedule": "string (hour-by-hour schedule for day 1)",
  "thirty_sixty_ninety_goals": "string (SMART goals for 30/60/90 days)"
}}
"""

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in onboarding response.")
        return json.loads(text[start:end])
