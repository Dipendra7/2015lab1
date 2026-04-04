"""
Step 5: Interview Prep & Debrief Automation
Auto-generates tailored interview questions per candidate CV.
After the interview, captures structured debrief and stores in ATS.
"""

from __future__ import annotations
import json
import anthropic
from pydantic import ValidationError

from .models import (
    ScoredCandidate, RoleRequirements,
    InterviewKit, InterviewQuestion,
)
from .config import (
    MODEL, THINKING_CONFIG, EFFORT_HIGH,
    MAX_TOKENS_INTERVIEW, SYSTEM_INTERVIEW,
)


class InterviewPrep:
    """Generate tailored interview kits and capture structured debriefs."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def generate_kit(
        self,
        candidate: ScoredCandidate,
        role: RoleRequirements,
        verbose: bool = True,
    ) -> InterviewKit:
        """
        Generate a complete, tailored interview kit for a candidate.
        Uses adaptive thinking to reason about candidate-specific probes.
        Streams for real-time output on long responses.
        """
        prompt = self._build_kit_prompt(candidate, role)

        if verbose:
            print(f"\n  Generating interview kit for: {candidate.name}...", end="")

        full_text = ""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS_INTERVIEW,
            thinking=THINKING_CONFIG,
            output_config=EFFORT_HIGH,
            system=SYSTEM_INTERVIEW,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        full_text += event.delta.text
            stream.get_final_message()

        kit_data = self._extract_json(full_text)
        try:
            kit = InterviewKit(**kit_data)
        except (ValidationError, TypeError) as exc:
            raise ValueError(
                f"Invalid interview kit for {candidate.name}: {exc}"
            ) from exc

        if verbose:
            print(f" Done ({len(kit.questions)} questions)")

        return kit

    def generate_all_kits(
        self,
        shortlist: list[ScoredCandidate],
        role: RoleRequirements,
        verbose: bool = True,
    ) -> list[InterviewKit]:
        """Generate interview kits for all shortlisted candidates."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Generating {len(shortlist)} interview kits for: {role.title}")
            print(f"{'='*60}")

        kits = []
        for candidate in shortlist:
            kit = self.generate_kit(candidate, role, verbose=verbose)
            kits.append(kit)
        return kits

    def capture_debrief(
        self,
        kit: InterviewKit,
        interviewer_notes: str,
        verbose: bool = True,
    ) -> dict:
        """
        Process raw interviewer notes into a structured debrief.
        Returns a debrief dict suitable for storing in the ATS.
        """
        prompt = f"""
Process these raw interview notes into a structured debrief.

CANDIDATE: {kit.candidate_name}
ROLE: {kit.role}
QUESTIONS ASKED: {len(kit.questions)}
DEBRIEF TEMPLATE: {kit.debrief_template}

RAW INTERVIEWER NOTES:
{interviewer_notes}

Return ONLY valid JSON:
{{
  "candidate_name": "string",
  "role": "string",
  "overall_rating": integer (1-5),
  "hire_recommendation": "Strong Hire" | "Hire" | "Maybe" | "No Hire",
  "technical_rating": integer (1-5),
  "communication_rating": integer (1-5),
  "culture_fit_rating": integer (1-5),
  "key_strengths": ["string", ...],
  "key_concerns": ["string", ...],
  "standout_moments": "string",
  "summary": "string (3-5 sentences)",
  "next_steps": "string"
}}
"""
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_INTERVIEW,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        debrief = self._extract_json(text)

        if verbose:
            rec = debrief.get("hire_recommendation", "Unknown")
            rating = debrief.get("overall_rating", "?")
            print(f"\n  Debrief captured: {kit.candidate_name} — {rating}/5 — {rec}")

        return debrief

    def format_kit_for_display(self, kit: InterviewKit) -> str:
        """Format an InterviewKit as a human-readable document."""
        lines = [
            f"# Interview Kit: {kit.candidate_name}",
            f"**Role:** {kit.role}",
            "",
            "## Opening Script",
            kit.opening_script,
            "",
            "## Interview Questions",
        ]
        for i, q in enumerate(kit.questions, 1):
            lines += [
                f"\n### Q{i}. [{q.category}] {q.question}",
                "**Follow-up probes:**",
                *[f"- {p}" for p in q.follow_up_probes],
                f"**What good looks like:** {q.what_good_looks_like}",
            ]
        lines += [
            "",
            "## Scoring Rubric",
            kit.scoring_rubric,
            "",
            "## Closing Script",
            kit.closing_script,
            "",
            "## Debrief Template",
            kit.debrief_template,
        ]
        return "\n".join(lines)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_kit_prompt(
        self, candidate: ScoredCandidate, role: RoleRequirements
    ) -> str:
        strengths = ", ".join(candidate.score.strengths[:4])
        missing = ", ".join(candidate.score.skills_missing[:3]) or "None identified"
        red_flags = ", ".join(candidate.score.red_flags) or "None"

        return f"""
Create a complete, tailored interview kit for this candidate applying for the role below.

ROLE: {role.title} at {role.company_name}
Required Skills: {", ".join(role.required_skills)}
Key Responsibilities: {"; ".join(role.responsibilities[:5])}

CANDIDATE PROFILE
=================
Name: {candidate.name}
ICP Score: {candidate.score.total_score}/100
Recommendation: {candidate.score.recommendation}
Strengths: {strengths}
Skills to Probe: {missing}
Red Flags to Explore: {red_flags}
Summary: {candidate.score.one_line_summary}

INSTRUCTIONS
============
1. Write an opening script that makes the candidate comfortable and sets context.
2. Create 8-10 questions across 4 categories:
   - Technical (3 questions): Probe required skills, especially any gaps
   - Behavioural (3 questions): STAR-format, past behaviour predicts future performance
   - Role-Specific (2 questions): Scenarios relevant to key responsibilities
   - Culture Fit (2 questions): Values alignment, work style
3. Each question must have follow-up probes and a "what good looks like" guide.
4. Address any red flags with specific but tactful questions.
5. Write a closing script.
6. Provide a 1-page debrief template with scoring dimensions.

Return ONLY valid JSON matching this exact schema:
{{
  "candidate_id": "{candidate.candidate_id}",
  "candidate_name": "{candidate.name}",
  "role": "{role.title}",
  "opening_script": "string",
  "questions": [
    {{
      "category": "Technical" | "Behavioural" | "Role-Specific" | "Culture Fit",
      "question": "string",
      "follow_up_probes": ["string", ...],
      "what_good_looks_like": "string"
    }},
    ...
  ],
  "scoring_rubric": "string",
  "closing_script": "string",
  "debrief_template": "string"
}}
"""

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in interview kit response.")
        return json.loads(text[start:end])
