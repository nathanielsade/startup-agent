from startup_agent.matching.similarity import cosine


def test_cosine_identical_is_one():
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6


def test_cosine_orthogonal_is_zero():
    assert abs(cosine([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_handles_zero_vector():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
