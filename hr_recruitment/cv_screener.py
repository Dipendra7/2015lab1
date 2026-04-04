"""
Step 3: Automated CV Screening & Scoring
Reads each CV, scores it against the ICP rubric, and ranks candidates.
Reduces manual CV review time by 70-80%.
"""

from __future__ import annotations
import json
import anthropic
from pydantic import ValidationError

from .models import (
    RoleRequirements, CandidateProfile,
    ICPScore, ScoredCandidate,
)
from .config import (
    MODEL, THINKING_CONFIG, EFFORT_MEDIUM,
    MAX_TOKENS_SCREENING, SYSTEM_SCREENER,
    SHORTLIST_THRESHOLD, SHORTLIST_MAX_CANDIDATES,
)


class CVScreener:
    """
    Screen and score CVs against an Ideal Candidate Profile (ICP) rubric.

    Scoring breakdown (0-100):
      Skills match    : 0-40 pts
      Experience      : 0-30 pts
      Culture fit     : 0-20 pts
      Red flags       : 0-30 pts deduction
    """

    def __init__(self, client: anthropic.Anthropic | None = None):
        self.client = client or anthropic.Anthropic()

    def score_candidate(
        self,
        candidate: CandidateProfile,
        role: RoleRequirements,
    ) -> ScoredCandidate:
        """Score a single candidate CV against the ICP rubric."""
        prompt = self._build_scoring_prompt(candidate, role)

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_SCREENING,
            thinking=THINKING_CONFIG,
            output_config=EFFORT_MEDIUM,
            system=SYSTEM_SCREENER,
            messages=[{"role": "user", "content": prompt}],
        )

        text = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        score_data = self._extract_json(text)

        try:
            icp_score = ICPScore(**score_data)
        except (ValidationError, TypeError) as exc:
            raise ValueError(
                f"Invalid score structure for {candidate.name}: {exc}"
            ) from exc

        return ScoredCandidate(
            candidate_id=candidate.candidate_id,
            name=candidate.name,
            email=candidate.email,
            score=icp_score,
        )

    def screen_all(
        self,
        candidates: list[CandidateProfile],
        role: RoleRequirements,
        verbose: bool = True,
    ) -> list[ScoredCandidate]:
        """
        Screen all candidates, rank them by score, and return shortlist.
        Processes candidates one at a time to stay within rate limits.
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Screening {len(candidates)} candidates for: {role.title}")
            print(f"{'='*60}")

        scored: list[ScoredCandidate] = []
        for i, candidate in enumerate(candidates, 1):
            if verbose:
                print(f"\n  [{i}/{len(candidates)}] Screening: {candidate.name}...", end="")
            result = self.score_candidate(candidate, role)
            scored.append(result)
            if verbose:
                rec = result.score.recommendation
                total = result.score.total_score
                print(f" Score: {total}/100 — {rec}")

        # Sort by total score descending, assign ranks
        scored.sort(key=lambda c: c.score.total_score, reverse=True)
        for rank, candidate in enumerate(scored, 1):
            candidate.rank = rank

        return scored

    def get_shortlist(
        self,
        scored_candidates: list[ScoredCandidate],
        threshold: int = SHORTLIST_THRESHOLD,
        max_candidates: int = SHORTLIST_MAX_CANDIDATES,
    ) -> list[ScoredCandidate]:
        """Return top candidates above the ICP score threshold."""
        shortlist = [
            c for c in scored_candidates
            if c.score.total_score >= threshold
        ]
        return shortlist[:max_candidates]

    def print_leaderboard(self, scored: list[ScoredCandidate]) -> None:
        """Print a ranked leaderboard of all screened candidates."""
        print(f"\n{'─'*70}")
        print(f"  {'RANK':<6} {'NAME':<25} {'SCORE':>6}  {'RECOMMENDATION'}")
        print(f"{'─'*70}")
        for c in scored:
            shortlisted = "✓" if c.score.total_score >= SHORTLIST_THRESHOLD else " "
            print(
                f"  {c.rank:<6} {c.name:<25} "
                f"{c.score.total_score:>5}/100  "
                f"{shortlisted} {c.score.recommendation}"
            )
        print(f"{'─'*70}")
        shortlist_count = sum(
            1 for c in scored if c.score.total_score >= SHORTLIST_THRESHOLD
        )
        print(f"  Shortlisted (≥{SHORTLIST_THRESHOLD}): {shortlist_count} candidates")

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_scoring_prompt(
        self, candidate: CandidateProfile, role: RoleRequirements
    ) -> str:
        return f"""
Score this candidate's CV against the Ideal Candidate Profile (ICP) for the role below.

ROLE: {role.title} at {role.company_name}
Required Skills: {", ".join(role.required_skills)}
Nice-to-Have Skills: {", ".join(role.nice_to_have_skills)}
Years of Experience Required: {role.years_experience}+
Key Responsibilities: {"; ".join(role.responsibilities)}

CANDIDATE CV
============
Name: {candidate.name}
Applied: {candidate.application_date}
Source: {candidate.source}

{candidate.cv_text}

SCORING RUBRIC
==============
1. Skills Match (0-40 pts)
   - Award points for each required skill present
   - Bonus for nice-to-have skills
   - Penalise for critical skill gaps

2. Experience (0-30 pts)
   - Years of relevant experience vs requirement
   - Seniority level and career progression
   - Domain/industry relevance

3. Culture Fit (0-20 pts)
   - Communication clarity in the CV
   - Demonstrated initiative and ownership
   - Alignment with company values signals

4. Red Flags Deduction (0-30 pts subtracted)
   - Unexplained employment gaps >6 months
   - Frequent short tenures (<1 year)
   - Misrepresentation signals
   - Missing critical required skills

Calculate total_score = skills_match_score + experience_score + culture_fit_score - red_flags_deduction
Clamp total_score to range [0, 100].

Recommendation rules:
  total_score >= 80 → "Strong Yes"
  total_score >= 65 → "Yes"
  total_score >= 50 → "Maybe"
  total_score < 50  → "No"

Return ONLY valid JSON matching this exact schema:
{{
  "skills_match_score": integer (0-40),
  "experience_score": integer (0-30),
  "culture_fit_score": integer (0-20),
  "red_flags_deduction": integer (0-30),
  "total_score": integer (0-100),
  "skills_matched": ["string", ...],
  "skills_missing": ["string", ...],
  "red_flags": ["string", ...],
  "strengths": ["string", ...],
  "recommendation": "Strong Yes" | "Yes" | "Maybe" | "No",
  "one_line_summary": "string (max 20 words)"
}}
"""

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in scoring response.")
        return json.loads(text[start:end])
