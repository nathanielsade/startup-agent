from startup_agent.domain.models import Job
from startup_agent.domain.preferences import Preferences

INSTRUCTIONS = (
    "You are a job-matching assistant. Given a candidate's CV and a single job's "
    "summary card, score how well the job fits the candidate's SKILLS and ROLE from "
    "0 to 100. Weigh: tech-stack overlap (high), role/domain alignment (high), "
    "must-have requirements met (medium-high), domain/industry match and skill "
    "recency (medium). For the SCORE, ignore experience level/seniority/years and "
    "location (handled separately). "
    "Then write a concise reason of 2-3 sentences (not a list) that names the "
    "CONCRETE overlap — which of the candidate's skills, tech-stack, and prior "
    "experience match this role and domain — and the main gap (including if the "
    "role needs more years/seniority than the candidate has). Be specific, not "
    "generic. Be strict on the score: 70+ a genuinely strong skills fit; 40-69 a "
    "stretch; below 40 poor."
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


def job_text(job: Job, card: dict | None = None, district: str | None = None) -> str:
    loc = (f"Location district: {district} (already validated - do not score location).\n"
           if district else "")
    if card:
        import json
        return f"Title: {job.title}\n{loc}\nJob card (use this):\n{json.dumps(card)}"
    return f"Title: {job.title}\n{loc}\n{(job.description or '')[:4000]}"
