from startup_agent.adapters.embedding.openai_embedder import OpenAIEmbedder


class _FakeEmbeddingItem:
    def __init__(self, embedding):
        self.embedding = embedding


class _FakeResponse:
    def __init__(self, vectors):
        self.data = [_FakeEmbeddingItem(v) for v in vectors]


class _FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, model, input):
        self.calls.append((model, input))
        # echo a deterministic vector per text
        return _FakeResponse([[float(len(t)), 1.0] for t in input])


class _FakeClient:
    def __init__(self):
        self.embeddings = _FakeEmbeddings()


def test_embed_returns_one_vector_per_text():
    client = _FakeClient()
    emb = OpenAIEmbedder(model="text-embedding-3-small", client=client)
    out = emb.embed(["ab", "abcd"])
    assert out == [[2.0, 1.0], [4.0, 1.0]]
    assert client.embeddings.calls == [("text-embedding-3-small", ["ab", "abcd"])]


def test_embed_empty_short_circuits_without_api_call():
    client = _FakeClient()
    emb = OpenAIEmbedder(client=client)
    assert emb.embed([]) == []
    assert client.embeddings.calls == []
