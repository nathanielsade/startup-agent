from datetime import datetime, timezone

from startup_agent.domain.models import Job


def _age(job: Job, now: datetime) -> str:
    if not job.posted_at:
        return ""
    delta = now - job.posted_at.astimezone(timezone.utc)
    if delta.days >= 1:
        return f" · {delta.days}d ago"
    return f" · {int(delta.seconds // 3600)}h ago"


def render_markdown(title: str, entries: list[tuple[Job, int, str | None]],
                    company_names: dict[str, str], now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [f"# Job digest — {title} ({len(entries)} new)", ""]
    if not entries:
        lines.append("_No new matching jobs._")
    for job, score, reason in entries:
        company = company_names.get(job.company_id, "?")
        line = (f"- [{job.title} @ {company}]({job.url}) — "
                f"{job.location or 'n/a'}{_age(job, now)} · {score}")
        if reason:
            line += f" — {reason}"
        lines.append(line)
    return "\n".join(lines) + "\n"
