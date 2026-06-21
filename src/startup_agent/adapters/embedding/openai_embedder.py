from startup_agent.ports.embedder import Embedder


class OpenAIEmbedder(Embedder):
    """Embedder backed by a hosted OpenAI embedding model (no torch dependency).

    Used in deployment so the API/batch container stays small. The model name is
    stored alongside each vector, so switching models triggers a re-embed.
    """

    def __init__(self, api_key: str = "", model: str = "text-embedding-3-small",
                 base_url: str = "", client: object | None = None) -> None:
        if client is not None:
            self._client = client
        else:
            from openai import OpenAI
            kwargs = {}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]
