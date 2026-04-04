"""
Step 4: Candidate Outreach & Scheduling Agent
Sends personalised outreach, answers questions, and books interview slots —
no human coordination needed. Uses Claude tool use to simulate integrations.
"""

from __future__ import annotations
import json
from datetime import datetime, timedelta
import anthropic
from pydantic import ValidationError

from .models import (
    ScoredCandidate, RoleRequirements,
    OutreachMessage, InterviewSchedule,
)
from .config import (
    MODEL, THINKING_CONFIG, EFFORT_MEDIUM,
    MAX_TOKENS_SCHEDULING, SYSTEM_SCHEDULER,
    DEFAULT_INTERVIEW_DURATION, DEFAULT_INTERVIEW_FORMAT,
    CALENDLY_BASE_URL,
)


# ── Tool definitions (Claude will call these to schedule interviews) ───────────

SCHEDULING_TOOLS = [
    {
        "name": "check_calendar_availability",
        "description": (
            "Check the hiring manager's calendar for available interview slots "
            "in the next 14 days. Returns a list of available ISO-8601 datetime strings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "interviewer_name": {
                    "type": "string",
                    "description": "Name of the interviewer/hiring manager",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Required meeting duration in minutes",
                },
                "num_slots": {
                    "type": "integer",
                    "description": "Number of slot options to return",
                },
            },
            "required": ["interviewer_name", "duration_minutes"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Create a calendar event for the interview and generate a meeting link. "
            "Returns the calendar event ID and video call URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "datetime_iso": {"type": "string", "description": "ISO-8601 datetime"},
                "duration_minutes": {"type": "integer"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses",
                },
                "description": {"type": "string"},
            },
            "required": ["title", "datetime_iso", "duration_minutes", "attendees"],
        },
    },
    {
        "name": "send_outreach_email",
        "description": "Send a personalised outreach email to a shortlisted candidate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string"},
                "to_name": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to_email", "to_name", "subject", "body"],
        },
    },
]


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Stub implementations of the scheduling tools.
    Replace each block with real API calls to Google Calendar / Calendly / SMTP.
    """
    if tool_name == "check_calendar_availability":
        # Generate realistic-looking available slots starting tomorrow
        base = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        slots = []
        day_offset = 1
        while len(slots) < tool_input.get("num_slots", 3):
            slot = base + timedelta(days=day_offset)
            if slot.weekday() < 5:  # Mon-Fri only
                slots.append(slot.strftime("%Y-%m-%dT%H:%M:00"))
                slot2 = slot.replace(hour=14)
                slots.append(slot2.strftime("%Y-%m-%dT%H:%M:00"))
            day_offset += 1
        return json.dumps({
            "available_slots": slots[:tool_input.get("num_slots", 3)],
            "timezone": "UTC",
        })

    elif tool_name == "create_calendar_event":
        event_id = f"evt_{hash(tool_input['datetime_iso']) % 100000:05d}"
        return json.dumps({
            "event_id": event_id,
            "calendar_link": f"https://calendar.google.com/event?eid={event_id}",
            "video_call_url": f"https://meet.google.com/{event_id[:3]}-{event_id[3:6]}-{event_id[6:]}",
            "status": "confirmed",
        })

    elif tool_name == "send_outreach_email":
        return json.dumps({
            "status": "sent",
            "message_id": f"msg_{abs(hash(tool_input['to_email'])) % 100000:05d}",
            "timestamp": datetime.now().isoformat(),
        })

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class SchedulingAgent:
    """
    Agentic scheduler that autonomously handles candidate outreach
    and interview slot booking using Claude tool use.
    """

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        interviewer_name: str = "Hiring Manager",
        interviewer_email: str = "hiring@company.com",
    ):
        self.client = client or anthropic.Anthropic()
        self.interviewer_name = interviewer_name
        self.interviewer_email = interviewer_email

    def schedule_candidate(
        self,
        candidate: ScoredCandidate,
        role: RoleRequirements,
        verbose: bool = True,
    ) -> InterviewSchedule:
        """
        Run the full outreach + scheduling loop for one candidate.
        Claude autonomously calls tools to check calendars and book slots.
        """
        prompt = self._build_scheduling_prompt(candidate, role)
        messages = [{"role": "user", "content": prompt}]

        if verbose:
            print(f"\n  Scheduling: {candidate.name}...", end="")

        # Agentic tool-use loop
        schedule_data: dict | None = None
        max_iterations = 6
        for _ in range(max_iterations):
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS_SCHEDULING,
                thinking=THINKING_CONFIG,
                output_config=EFFORT_MEDIUM,
                system=SYSTEM_SCHEDULER,
                tools=SCHEDULING_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                # Claude is done — extract final JSON schedule
                text = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                schedule_data = self._extract_json(text)
                break

            if response.stop_reason == "tool_use":
                # Execute all tool calls Claude requested
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = _execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        if not schedule_data:
            raise RuntimeError(
                f"Scheduling agent failed to produce a schedule for {candidate.name}"
            )

        try:
            schedule = InterviewSchedule(**schedule_data)
        except (ValidationError, TypeError) as exc:
            raise ValueError(f"Invalid schedule data: {exc}") from exc

        if verbose:
            print(f" Booked ✓  ({schedule.proposed_slots[0] if schedule.proposed_slots else 'TBD'})")

        return schedule

    def schedule_shortlist(
        self,
        shortlist: list[ScoredCandidate],
        role: RoleRequirements,
        verbose: bool = True,
    ) -> list[InterviewSchedule]:
        """Schedule interviews for all shortlisted candidates."""
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Scheduling {len(shortlist)} interviews for: {role.title}")
            print(f"{'='*60}")

        schedules = []
        for candidate in shortlist:
            schedule = self.schedule_candidate(candidate, role, verbose=verbose)
            schedules.append(schedule)
        return schedules

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_scheduling_prompt(
        self, candidate: ScoredCandidate, role: RoleRequirements
    ) -> str:
        return f"""
You are scheduling an interview for a shortlisted candidate.

ROLE: {role.title} at {role.company_name}
CANDIDATE: {candidate.name} (score: {candidate.score.total_score}/100)
CANDIDATE EMAIL: {candidate.email}
INTERVIEWER: {self.interviewer_name} <{self.interviewer_email}>

CANDIDATE STRENGTHS: {", ".join(candidate.score.strengths[:3])}
RECOMMENDATION: {candidate.score.recommendation}

TASKS (use tools in order):
1. Call check_calendar_availability to get 3 available slots for {self.interviewer_name}
   (duration: {DEFAULT_INTERVIEW_DURATION} minutes)
2. Call create_calendar_event to book the first available slot
3. Call send_outreach_email to send a warm, personalised invitation to {candidate.name}
   — mention their specific strengths, explain the role, provide the meeting link
4. Once all tools are called, return a JSON schedule summary

Return ONLY valid JSON matching this exact schema:
{{
  "candidate_id": "{candidate.candidate_id}",
  "candidate_name": "{candidate.name}",
  "candidate_email": "{candidate.email}",
  "proposed_slots": ["ISO-8601 datetime string", ...],
  "interview_format": "{DEFAULT_INTERVIEW_FORMAT}",
  "duration_minutes": {DEFAULT_INTERVIEW_DURATION},
  "interviewer_names": ["{self.interviewer_name}"],
  "calendar_link": "string",
  "confirmation_message": "string (brief confirmation sent to candidate)"
}}
"""

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in scheduling response.")
        return json.loads(text[start:end])
