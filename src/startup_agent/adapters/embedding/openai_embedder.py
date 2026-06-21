from startup_agent.ports.embedder import Embedder

# OpenAI's embeddings endpoint caps each request at 2048 inputs, and has a total
# token budget per request — so embed in conservative chunks to stay well under both.
_MAX_BATCH = 256


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
        client = self._ensure()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            chunk = texts[start:start + _MAX_BATCH]
            resp = client.embeddings.create(model=self._model, input=chunk)
            vectors.extend(item.embedding for item in resp.data)
        return vectors
