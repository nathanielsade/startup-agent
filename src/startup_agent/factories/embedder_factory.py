from startup_agent.ports.embedder import Embedder


def build_embedder(settings) -> Embedder:
    """Pick the embedder from settings.

    "openai" → hosted embeddings (small container, no torch); used in deployment.
    "local"  → sentence-transformers (offline); the default for dev.
    """
    if settings.embedding_provider == "openai":
        from startup_agent.adapters.embedding.openai_embedder import OpenAIEmbedder
        return OpenAIEmbedder(api_key=settings.openai_api_key,
                              model=settings.openai_embedding_model,
                              base_url=settings.openai_base_url)
    from startup_agent.adapters.embedding.local_embedder import LocalEmbedder
    return LocalEmbedder(settings.embedding_model)
