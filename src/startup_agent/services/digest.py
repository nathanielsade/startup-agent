import structlog

from startup_agent.domain.models import Job
from startup_agent.ports.delivery import DeliveryChannel
from startup_agent.ports.repository import JobRepository

logger = structlog.get_logger()

Entry = tuple[Job, int, "str | None"]


class DigestService:
    """Filters matches to never-delivered jobs, renders, delivers, marks delivered."""

    def __init__(self, repo: JobRepository, channel: DeliveryChannel, renderer) -> None:
        self._repo = repo
        self._channel = channel
        self._renderer = renderer  # callable(title, entries, company_names) -> str

    def run(self, title: str, entries: list[Entry],
            company_names: dict[str, str]) -> list[Entry]:
        notified = self._repo.get_notified_job_ids()
        fresh = [(j, s, r) for (j, s, r) in entries if j.id not in notified]
        fresh.sort(key=lambda e: e[1], reverse=True)
        body = self._renderer(title, fresh, company_names)
        self._channel.deliver(title, body)
        self._repo.mark_notified([j.id for j, _, _ in fresh])
        logger.info("digest_delivered", title=title, new=len(fresh))
        return fresh
