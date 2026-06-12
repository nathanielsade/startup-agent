from startup_agent.adapters.embedding.serialization import to_bytes, from_bytes


def test_vector_round_trips():
    vec = [0.1, -0.2, 0.3, 0.4]
    restored = from_bytes(to_bytes(vec))
    assert len(restored) == 4
    assert abs(restored[0] - 0.1) < 1e-6
