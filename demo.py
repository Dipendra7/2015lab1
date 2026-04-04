"""
AI HR & Recruitment Automation — Demo Script
Demonstrates the full hiring pipeline with realistic sample data.

Usage:
    ANTHROPIC_API_KEY=your_key python demo.py
    ANTHROPIC_API_KEY=your_key python demo.py --step jd
    ANTHROPIC_API_KEY=your_key python demo.py --step screen
    ANTHROPIC_API_KEY=your_key python demo.py --full
"""

from __future__ import annotations
import argparse
import os
import sys

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from hr_recruitment import (
    HiringPipeline,
    JobDescriptionGenerator,
    CVScreener,
    RoleRequirements,
    CandidateProfile,
)
from hr_recruitment.pipeline import PipelineConfig


# ── Sample Data ────────────────────────────────────────────────────────────────

ROLE = RoleRequirements(
    title="Senior Machine Learning Engineer",
    department="AI Platform",
    location="London, UK",
    employment_type="Full-time",
    remote_policy="Hybrid (3 days in-office)",
    salary_range="£95,000 – £130,000 + equity",
    company_name="NovaTech AI",
    company_description=(
        "NovaTech AI builds enterprise-grade AI infrastructure that powers "
        "over 500 companies globally. We're on a mission to make AI reliable, "
        "scalable, and accessible. Our team of 200 engineers ships fast, "
        "thinks deeply, and treats each other with respect."
    ),
    required_skills=[
        "Python", "PyTorch or TensorFlow", "MLOps",
        "Distributed training", "Model deployment", "SQL",
    ],
    nice_to_have_skills=[
        "Kubernetes", "Ray", "Triton Inference Server",
        "LLM fine-tuning", "Rust",
    ],
    years_experience=5,
    responsibilities=[
        "Design and implement scalable ML training pipelines",
        "Optimise model inference latency and throughput",
        "Collaborate with research team to productionise models",
        "Build and maintain ML monitoring and observability tooling",
        "Mentor junior engineers and contribute to technical roadmap",
        "Evaluate and adopt new ML frameworks and tooling",
    ],
)

CANDIDATES = [
    CandidateProfile(
        candidate_id="C001",
        name="Aisha Patel",
        email="aisha.patel@email.com",
        phone="+44 7700 900001",
        application_date="2026-04-01",
        source="LinkedIn",
        cv_text="""
AISHA PATEL | Senior ML Engineer | London, UK
aisha.patel@email.com | github.com/aishapatel | linkedin.com/in/aishapatel

SUMMARY
ML engineer with 7 years of experience building and deploying large-scale ML systems
at Google DeepMind and two fast-growing startups. Deep expertise in distributed training,
model serving, and MLOps. Speaker at NeurIPS 2024 and PyData London.

EXPERIENCE
Senior ML Engineer | Qubit AI (Series B, London) | 2022–Present
- Led migration of training infrastructure to Ray + Kubernetes, reducing training time by 60%
- Built real-time model serving platform handling 50K req/s with p99 <20ms
- Implemented LLM fine-tuning pipelines for GPT-4 class models
- Managed team of 4 junior engineers; introduced ML observability standards

ML Engineer | Google DeepMind (London) | 2019–2022
- Contributed to AlphaFold protein structure prediction pipeline
- Built distributed training framework for 1000-GPU clusters using PyTorch
- Implemented model quantisation reducing inference cost by 45%

Data Scientist | Monzo Bank (London) | 2017–2019
- Built fraud detection models (XGBoost, neural networks) saving £2M annually
- Deployed models using Flask + Docker on AWS

EDUCATION
MSc Machine Learning | University College London | 2017 | Distinction
BSc Computer Science | University of Edinburgh | 2016 | First Class Honours

SKILLS
Languages: Python (expert), Rust (intermediate), SQL, Bash
ML Frameworks: PyTorch, TensorFlow, JAX, Hugging Face
MLOps: Kubernetes, Ray, MLflow, Weights & Biases, Triton Inference Server
Cloud: AWS (SageMaker, EC2, S3), GCP (Vertex AI), Azure

PUBLICATIONS & TALKS
- "Efficient LLM Serving at Scale" — NeurIPS 2024 Workshop
- "Ray for ML Pipelines" — PyData London 2023
""",
    ),
    CandidateProfile(
        candidate_id="C002",
        name="Marcus Johnson",
        email="m.johnson.dev@email.com",
        phone="+44 7700 900002",
        application_date="2026-04-02",
        source="Indeed",
        cv_text="""
MARCUS JOHNSON
m.johnson.dev@email.com | London, UK

WORK HISTORY
2023-Present: ML Engineer, DataStream Ltd
- Work on recommendation system using collaborative filtering
- Use Python and scikit-learn for data processing
- Help deploy models to production with Docker

2021-2023: Junior Data Scientist, RetailCo
- Built reports and dashboards in Tableau
- Wrote SQL queries for data analysis
- Attended Python training course

2019-2021: Business Analyst, KPMG
- Excel modelling and PowerPoint presentations
- Client-facing project management

EDUCATION
BA Economics, University of Exeter, 2019

SKILLS
Python, SQL, Excel, Tableau, scikit-learn, some PyTorch
""",
    ),
    CandidateProfile(
        candidate_id="C003",
        name="Sophie Chen",
        email="sophie.chen.ml@email.com",
        phone="+44 7700 900003",
        application_date="2026-04-01",
        source="Referral",
        cv_text="""
SOPHIE CHEN | ML Platform Engineer
sophie.chen.ml@email.com | github.com/sophiechen | London, UK

ABOUT
ML platform engineer specialising in MLOps and model serving infrastructure.
6 years building production ML systems at scale. Strong background in distributed
systems and cloud-native engineering.

EXPERIENCE
Staff ML Platform Engineer | Revolut (London) | 2021–Present
- Architected ML feature store serving 300+ features to 50 production models
- Led adoption of Kubernetes-based training infrastructure (cut infra cost 40%)
- Built model registry and CI/CD pipeline for ML models (PyTorch + TensorFlow)
- Reduced model deployment time from 2 weeks to 4 hours through automation
- Mentored 6 junior engineers across platform team

Senior ML Engineer | Babylon Health (London) | 2019–2021
- Built clinical NLP pipelines using BERT fine-tuning on medical text
- Implemented distributed training on GCP with Vertex AI and TPUs
- Deployed models via Triton Inference Server with ONNX optimisation

ML Engineer | Expedia Group (London) | 2018–2019
- Recommendation models using TensorFlow and A/B testing framework
- REST API deployment with FastAPI and Docker

EDUCATION
MEng Computer Science | Imperial College London | 2018 | First Class Honours

SKILLS
Python, PyTorch, TensorFlow, Kubernetes, Triton, MLflow, Ray
GCP (Vertex AI, TPUs), AWS (SageMaker), Docker, Terraform
SQL, Apache Spark, Redis, Kafka
""",
    ),
    CandidateProfile(
        candidate_id="C004",
        name="David Okafor",
        email="david.okafor@email.com",
        phone="+44 7700 900004",
        application_date="2026-04-03",
        source="LinkedIn",
        cv_text="""
DAVID OKAFOR | Machine Learning Engineer
david.okafor@email.com | London, UK

EXPERIENCE
ML Engineer | Palantir Technologies (London) | 2020–Present
- Build ML pipelines for defence and government clients
- Python, PyTorch, distributed training on internal HPC cluster
- Model deployment and monitoring in Kubernetes environments
- 5 years total ML experience

ML Research Engineer | University of Cambridge | 2018–2020
- PhD-level research in reinforcement learning
- Published 2 papers at ICML and ICLR
- Implemented RL algorithms in PyTorch from scratch

EDUCATION
MPhil Machine Learning | University of Cambridge | 2018
BSc Mathematics | Imperial College London | 2016 | First Class

SKILLS
Python, PyTorch, TensorFlow, SQL, Kubernetes, AWS
RL, NLP, computer vision, distributed training

NOTES
- Currently on 3-month notice period
- Not eligible for US work authorisation
- Open to hybrid working (min 2 days from home)
""",
    ),
    CandidateProfile(
        candidate_id="C005",
        name="Priya Sharma",
        email="priya.sharma.data@email.com",
        phone="+44 7700 900005",
        application_date="2026-04-04",
        source="Direct",
        cv_text="""
Priya Sharma | Data Scientist
priya.sharma.data@email.com

Experience:
2024-Present: Data Scientist at small startup (3 months)
  - Python, pandas, some machine learning

2022-2024: Data Analyst at insurance company
  - SQL reporting, Excel, Tableau

2020-2022: Graduate scheme at Barclays
  - Rotations across technology and data teams

Education: BSc Statistics, University of Leeds, 2020

I am very enthusiastic about AI and machine learning. I have been doing
Coursera courses in deep learning and am excited to learn more. I know
Python and SQL and am familiar with scikit-learn. I am a quick learner.
""",
    ),
]


# ── Demo Functions ─────────────────────────────────────────────────────────────

def demo_jd_only():
    """Demo: Generate a job description only."""
    print("\n=== Demo: Job Description Generator ===")
    gen = JobDescriptionGenerator()
    jd = gen.generate(ROLE, verbose=True)
    print("\n" + gen.format_for_display(jd))

    print("\n--- Syncing to Job Boards ---")
    gen.sync_to_job_boards(jd)
    return jd


def demo_screening_only():
    """Demo: Screen and rank candidates only."""
    print("\n=== Demo: CV Screening & Scoring ===")
    screener = CVScreener()
    scored = screener.screen_all(CANDIDATES, ROLE, verbose=True)
    screener.print_leaderboard(scored)
    shortlist = screener.get_shortlist(scored)
    print(f"\nShortlisted {len(shortlist)} candidates:")
    for c in shortlist:
        print(f"  #{c.rank} {c.name}: {c.score.total_score}/100 — {c.score.one_line_summary}")
    return shortlist


def demo_full_pipeline():
    """Demo: Run the complete hiring pipeline."""
    config = PipelineConfig(
        shortlist_threshold=65,
        shortlist_max=3,
        generate_jd=True,
        screen_cvs=True,
        schedule_interviews=True,
        generate_interview_kits=True,
        generate_onboarding=True,
        interviewer_name="Sarah Williams",
        interviewer_email="sarah.williams@novatech.ai",
        verbose=True,
    )

    pipeline = HiringPipeline(config=config)
    result = pipeline.run(ROLE, CANDIDATES)
    return result


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it with: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="AI HR & Recruitment Automation Demo"
    )
    parser.add_argument(
        "--step",
        choices=["jd", "screen", "full"],
        default="full",
        help="Which pipeline step to demo (default: full)",
    )
    args = parser.parse_args()

    if args.step == "jd":
        demo_jd_only()
    elif args.step == "screen":
        demo_screening_only()
    else:
        demo_full_pipeline()


if __name__ == "__main__":
    main()
