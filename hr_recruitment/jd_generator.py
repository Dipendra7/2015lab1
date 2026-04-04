"""
Step 2: AI Job Description Generator
Takes role requirements → outputs inclusive, SEO-optimised JD in ~60 seconds.
Streams output for real-time display; syncs to job boards.
"""

from __future__ import annotations
import json
import anthropic
from pydantic import ValidationError

from .models import RoleRequirements, JobDescription
from .config import (
    MODEL, THINKING_CONFIG, EFFORT_HIGH,
    MAX_TOKENS_JD, SYSTEM_JD, JOB_BOARDS,
)


class JobDescriptionGenerator:
    """Generate inclusive, SEO-optimised job descriptions using Claude."""

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def generate(
        self,
        requirements: RoleRequirements,
        verbose: bool = True,
    ) -> JobDescription:
        """
        Generate a structured job description from role requirements.

        Uses streaming + adaptive thinking so long-form content never times out.
        Returns a validated JobDescription Pydantic model.
        """
        prompt = self._build_prompt(requirements)

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Generating JD: {requirements.title}")
            print(f"{'='*60}")

        # Stream the response — JDs can be long, streaming prevents timeouts
        full_text = ""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS_JD,
            thinking=THINKING_CONFIG,
            output_config=EFFORT_HIGH,
            system=SYSTEM_JD,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        full_text += event.delta.text
                        if verbose:
                            print(event.delta.text, end="", flush=True)

            final_msg = stream.get_final_message()

        if verbose:
            print(f"\n\n[Tokens: in={final_msg.usage.input_tokens}, "
                  f"out={final_msg.usage.output_tokens}]")

        # Parse JSON from the response
        jd_data = self._extract_json(full_text)
        try:
            jd = JobDescription(**jd_data)
        except (ValidationError, TypeError) as exc:
            raise ValueError(f"Claude returned invalid JD structure: {exc}") from exc

        return jd

    def sync_to_job_boards(self, jd: JobDescription, boards: list[str] | None = None) -> dict:
        """
        Simulate syncing JD to job boards (LinkedIn, Indeed, etc.).
        Replace the body of each branch with real API calls.
        """
        boards = boards or JOB_BOARDS
        results = {}
        for board in boards:
            # In production: call board's API with jd.dict()
            results[board] = {
                "status": "posted",
                "url": f"https://{board.lower()}.com/jobs/{jd.title.lower().replace(' ', '-')}",
            }
            print(f"  [Job Board] Synced to {board}: {results[board]['url']}")
        return results

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_prompt(self, r: RoleRequirements) -> str:
        return f"""
Create a complete, inclusive, SEO-optimised job description for the role below.

ROLE DETAILS
============
Title: {r.title}
Department: {r.department}
Location: {r.location}
Employment Type: {r.employment_type}
Remote Policy: {r.remote_policy}
{"Salary Range: " + r.salary_range if r.salary_range else ""}
Company: {r.company_name}
Company Description: {r.company_description}

Required Skills: {", ".join(r.required_skills)}
Nice-to-Have Skills: {", ".join(r.nice_to_have_skills)}
Years of Experience Required: {r.years_experience}+

Key Responsibilities:
{chr(10).join(f"- {resp}" for resp in r.responsibilities)}

INSTRUCTIONS
============
1. Write an engaging, inclusive JD (avoid gendered or exclusionary language).
2. Optimise for SEO — include relevant keywords naturally.
3. Structure for easy scanning (bullet points, clear sections).
4. Highlight growth opportunities and company culture.
5. Include a strong equal opportunity statement.

Return ONLY valid JSON matching this exact schema:
{{
  "title": "string",
  "department": "string",
  "location": "string",
  "employment_type": "string",
  "summary": "string (2-3 sentence role overview)",
  "responsibilities": ["string", ...],
  "required_qualifications": ["string", ...],
  "preferred_qualifications": ["string", ...],
  "what_we_offer": ["string", ...],
  "about_company": "string",
  "equal_opportunity_statement": "string",
  "seo_keywords": ["string", ...],
  "estimated_read_time_seconds": integer
}}
"""

    def _extract_json(self, text: str) -> dict:
        """Extract JSON object from Claude's response text."""
        text = text.strip()
        # Find the outermost JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in response.")
        return json.loads(text[start:end])

    def format_for_display(self, jd: JobDescription) -> str:
        """Format a JobDescription for human-readable display."""
        lines = [
            f"# {jd.title}",
            f"**{jd.department} · {jd.location} · {jd.employment_type}**",
            "",
            "## About the Role",
            jd.summary,
            "",
            "## What You'll Do",
            *[f"- {r}" for r in jd.responsibilities],
            "",
            "## What You'll Bring",
            *[f"- {q}" for q in jd.required_qualifications],
            "",
            "## Nice to Have",
            *[f"- {q}" for q in jd.preferred_qualifications],
            "",
            "## What We Offer",
            *[f"- {o}" for o in jd.what_we_offer],
            "",
            "## About Us",
            jd.about_company,
            "",
            jd.equal_opportunity_statement,
            "",
            f"*Keywords: {', '.join(jd.seo_keywords)}*",
        ]
        return "\n".join(lines)
