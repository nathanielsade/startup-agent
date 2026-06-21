from startup_agent.ports.embedder import Embedder


class OpenAIEmbedder(Embedder):
    """Embedder backed by a hosted OpenAI embedding model (no torch dependency).

    Used in deployment so the API/batch container stays small. The model name is
    stored alongside each vector, so switching models triggers a re-embed.
    """

    def __init__(self, api_key: str = "", model: str = "text-embedding-3-small",
                 base_url: str = "", client: object | None = None) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._client = client  # lazy: only build (and require a key) on first embed

    def _ensure(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._ensure().embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]
