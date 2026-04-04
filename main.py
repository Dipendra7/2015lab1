"""
AI HR & Recruitment Automation — CLI Entry Point

Usage:
    python main.py --help
    python main.py jd --title "Software Engineer" --company "Acme Corp" \
                      --skills "Python,Django,PostgreSQL" --experience 3
    python main.py screen --role-file role.json --cvs-dir ./cvs/
    python main.py pipeline --role-file role.json --cvs-dir ./cvs/
"""

from __future__ import annotations
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from hr_recruitment import (
    JobDescriptionGenerator,
    CVScreener,
    HiringPipeline,
    RoleRequirements,
    CandidateProfile,
)
from hr_recruitment.pipeline import PipelineConfig


def cmd_jd(args: argparse.Namespace) -> None:
    """Generate a job description from CLI args or a JSON role file."""
    if args.role_file:
        with open(args.role_file) as f:
            data = json.load(f)
        role = RoleRequirements(**data)
    else:
        role = RoleRequirements(
            title=args.title,
            department=args.department or "Engineering",
            location=args.location or "Remote",
            employment_type=args.employment_type or "Full-time",
            required_skills=[s.strip() for s in (args.skills or "").split(",") if s.strip()],
            nice_to_have_skills=[s.strip() for s in (args.nice_to_have or "").split(",") if s.strip()],
            years_experience=args.experience or 3,
            responsibilities=[r.strip() for r in (args.responsibilities or "").split(";") if r.strip()],
            salary_range=args.salary,
            remote_policy=args.remote_policy or "Hybrid",
            company_name=args.company or "Company",
            company_description=args.company_desc or "",
        )

    gen = JobDescriptionGenerator()
    jd = gen.generate(role, verbose=True)
    formatted = gen.format_for_display(jd)
    print("\n" + formatted)

    if args.output:
        with open(args.output, "w") as f:
            f.write(formatted)
        print(f"\nSaved to: {args.output}")

    if args.sync_boards:
        print("\nSyncing to job boards...")
        gen.sync_to_job_boards(jd)


def cmd_screen(args: argparse.Namespace) -> None:
    """Screen a set of candidate CVs against a role."""
    if not args.role_file:
        print("Error: --role-file is required for the screen command.")
        sys.exit(1)

    with open(args.role_file) as f:
        role = RoleRequirements(**json.load(f))

    candidates = _load_candidates(args)
    if not candidates:
        print("Error: No candidates found. Provide --cvs-dir or --candidates-file.")
        sys.exit(1)

    screener = CVScreener()
    scored = screener.screen_all(candidates, role, verbose=True)
    screener.print_leaderboard(scored)
    shortlist = screener.get_shortlist(scored, threshold=args.threshold or 60)

    if args.output:
        output_data = [
            {
                "rank": c.rank,
                "name": c.name,
                "email": c.email,
                "score": c.score.total_score,
                "recommendation": c.score.recommendation,
                "summary": c.score.one_line_summary,
            }
            for c in scored
        ]
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")


def cmd_pipeline(args: argparse.Namespace) -> None:
    """Run the full end-to-end hiring pipeline."""
    if not args.role_file:
        print("Error: --role-file is required for the pipeline command.")
        sys.exit(1)

    with open(args.role_file) as f:
        role = RoleRequirements(**json.load(f))

    candidates = _load_candidates(args)
    if not candidates:
        print("Error: No candidates found.")
        sys.exit(1)

    config = PipelineConfig(
        shortlist_threshold=args.threshold or 65,
        shortlist_max=args.max_shortlist or 5,
        generate_jd=not args.skip_jd,
        screen_cvs=True,
        schedule_interviews=not args.skip_scheduling,
        generate_interview_kits=not args.skip_interview_prep,
        generate_onboarding=not args.skip_onboarding,
        interviewer_name=args.interviewer_name or "Hiring Manager",
        interviewer_email=args.interviewer_email or "hiring@company.com",
        verbose=True,
    )

    pipeline = HiringPipeline(config=config)
    result = pipeline.run(role, candidates)

    if args.output:
        summary = {
            "role": result.role,
            "total_reviewed": result.total_candidates_reviewed,
            "shortlisted": len(result.shortlisted_candidates),
            "time_saved_hours": result.time_saved_hours_estimate,
            "shortlist": [
                {
                    "name": c.name,
                    "email": c.email,
                    "score": c.score.total_score,
                    "recommendation": c.score.recommendation,
                }
                for c in result.shortlisted_candidates
            ],
        }
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nPipeline summary saved to: {args.output}")


def _load_candidates(args: argparse.Namespace) -> list[CandidateProfile]:
    """Load candidates from a JSON file or directory of text CVs."""
    candidates: list[CandidateProfile] = []

    if hasattr(args, "candidates_file") and args.candidates_file:
        with open(args.candidates_file) as f:
            data = json.load(f)
        for item in data:
            candidates.append(CandidateProfile(**item))

    elif hasattr(args, "cvs_dir") and args.cvs_dir:
        import glob
        for i, filepath in enumerate(glob.glob(os.path.join(args.cvs_dir, "*.txt"))):
            name = os.path.splitext(os.path.basename(filepath))[0].replace("_", " ").title()
            with open(filepath) as f:
                cv_text = f.read()
            candidates.append(CandidateProfile(
                candidate_id=f"C{i+1:03d}",
                name=name,
                email=f"{name.lower().replace(' ', '.')}@candidate.com",
                phone="",
                cv_text=cv_text,
                source="File Import",
            ))

    return candidates


def _check_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="AI HR & Recruitment Automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a job description
  python main.py jd --title "ML Engineer" --company "Acme" --skills "Python,PyTorch" --experience 5

  # Screen CVs from a JSON file
  python main.py screen --role-file role.json --candidates-file candidates.json

  # Run the full pipeline
  python main.py pipeline --role-file role.json --candidates-file candidates.json

  # Quick demo (built-in sample data)
  python demo.py --step full
        """,
    )
    parser.add_argument(
        "--api-key", help="Anthropic API key (overrides ANTHROPIC_API_KEY env var)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── jd subcommand ──────────────────────────────────────────────────────────
    jd_parser = subparsers.add_parser("jd", help="Generate a job description")
    jd_parser.add_argument("--role-file", help="JSON file with role requirements")
    jd_parser.add_argument("--title", help="Job title")
    jd_parser.add_argument("--department", help="Department")
    jd_parser.add_argument("--location", help="Location", default="Remote")
    jd_parser.add_argument("--employment-type", dest="employment_type", default="Full-time")
    jd_parser.add_argument("--skills", help="Comma-separated required skills")
    jd_parser.add_argument("--nice-to-have", dest="nice_to_have", help="Comma-separated nice-to-have skills")
    jd_parser.add_argument("--experience", type=int, help="Years of experience required")
    jd_parser.add_argument("--responsibilities", help="Semicolon-separated responsibilities")
    jd_parser.add_argument("--salary", help="Salary range string")
    jd_parser.add_argument("--remote-policy", dest="remote_policy", default="Hybrid")
    jd_parser.add_argument("--company", help="Company name")
    jd_parser.add_argument("--company-desc", dest="company_desc", help="Company description")
    jd_parser.add_argument("--output", "-o", help="Output file path (Markdown)")
    jd_parser.add_argument("--sync-boards", dest="sync_boards", action="store_true",
                           help="Sync to job boards after generation")

    # ── screen subcommand ──────────────────────────────────────────────────────
    screen_parser = subparsers.add_parser("screen", help="Screen and score CVs")
    screen_parser.add_argument("--role-file", required=True, help="JSON file with role requirements")
    screen_parser.add_argument("--candidates-file", dest="candidates_file", help="JSON file with candidates")
    screen_parser.add_argument("--cvs-dir", dest="cvs_dir", help="Directory of .txt CV files")
    screen_parser.add_argument("--threshold", type=int, default=60, help="Shortlist score threshold (default: 60)")
    screen_parser.add_argument("--output", "-o", help="Output JSON file for results")

    # ── pipeline subcommand ────────────────────────────────────────────────────
    pipe_parser = subparsers.add_parser("pipeline", help="Run the full hiring pipeline")
    pipe_parser.add_argument("--role-file", required=True, help="JSON file with role requirements")
    pipe_parser.add_argument("--candidates-file", dest="candidates_file", help="JSON file with candidates")
    pipe_parser.add_argument("--cvs-dir", dest="cvs_dir", help="Directory of .txt CV files")
    pipe_parser.add_argument("--threshold", type=int, default=65)
    pipe_parser.add_argument("--max-shortlist", dest="max_shortlist", type=int, default=5)
    pipe_parser.add_argument("--interviewer-name", dest="interviewer_name", default="Hiring Manager")
    pipe_parser.add_argument("--interviewer-email", dest="interviewer_email", default="hiring@company.com")
    pipe_parser.add_argument("--skip-jd", dest="skip_jd", action="store_true")
    pipe_parser.add_argument("--skip-scheduling", dest="skip_scheduling", action="store_true")
    pipe_parser.add_argument("--skip-interview-prep", dest="skip_interview_prep", action="store_true")
    pipe_parser.add_argument("--skip-onboarding", dest="skip_onboarding", action="store_true")
    pipe_parser.add_argument("--output", "-o", help="Output JSON file for pipeline summary")

    args = parser.parse_args()

    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key

    _check_api_key()

    if args.command == "jd":
        cmd_jd(args)
    elif args.command == "screen":
        cmd_screen(args)
    elif args.command == "pipeline":
        cmd_pipeline(args)


if __name__ == "__main__":
    main()
