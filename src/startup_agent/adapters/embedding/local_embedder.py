from startup_agent.ports.embedder import Embedder


class LocalEmbedder(Embedder):
    """Embedder backed by a local sentence-transformers model (no API, offline)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self._model_name = model_name
        self._model = None  # lazy: don't load the model until first use

    def _ensure(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure()
        vectors = model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
