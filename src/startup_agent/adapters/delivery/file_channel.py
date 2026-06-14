from pathlib import Path

from startup_agent.ports.delivery import DeliveryChannel


class FileChannel(DeliveryChannel):
    def __init__(self, directory: str = "digests") -> None:
        self._dir = Path(directory)

    def path_for(self, title: str) -> Path:
        return self._dir / f"{self._safe(title)}.md"

    @staticmethod
    def _safe(title: str) -> str:
        return title.replace("/", "-").replace(" ", "_")

    def deliver(self, title: str, body: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        self.path_for(title).write_text(body)
