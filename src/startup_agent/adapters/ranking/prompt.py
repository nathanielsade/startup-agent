from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

INSTRUCTIONS = (
    "You are a job-matching assistant. Given a candidate's CV and a single job "
    "posting, score how well the job fits the candidate from 0 to 100 and give a "
    "one-line reason (max ~20 words). Weigh role, seniority, skills, and domain. "
    "Be strict: 70+ means a genuinely strong fit worth applying to; 40-69 a "
    "stretch; below 40 a poor fit."
)


def preferences_clause(preferences: Preferences | None) -> str:
    if preferences is None:
        return ""
    parts: list[str] = []
    if preferences.roles:
        parts.append("prefers roles in " + ", ".join(preferences.roles))
    if preferences.seniority:
        parts.append("seniority " + "/".join(preferences.seniority))
    if preferences.max_years is not None:
        parts.append(f"up to {preferences.max_years} years of experience")
    if preferences.districts:
        parts.append("districts " + ", ".join(preferences.districts))
    if not parts:
        return ""
    return "Candidate preferences: " + "; ".join(parts) + "."


def job_text(job: Job) -> str:
    return (
        f"Title: {job.title}\n"
        f"Location: {job.location or 'n/a'}\n\n"
        f"{(job.description or '')[:4000]}"
    )
