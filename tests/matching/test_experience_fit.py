import pytest
from startup_agent.matching.experience_fit import experience_penalty

@pytest.mark.parametrize("user,required,expected", [
    (5, 5, 0), (5, 6, 0),          # 0-1 under -> none
    (3, 5, 15), (3, 6, 15),        # 2-3 under -> 15
    (2, 6, 30), (1, 6, 30),        # 4-5 under -> 30
    (1, 7, 50), (0, 10, 50),       # 6+ under -> 50
    (6, 5, 0), (6, 4, 0),          # 0-2 over -> none
    (8, 4, 5), (8, 3, 5),          # 3-5 over -> 5
    (10, 2, 12), (12, 1, 12),      # 6+ over -> 12
])
def test_experience_penalty_bands(user, required, expected):
    assert experience_penalty(user, required) == expected

def test_experience_penalty_none_inputs_are_neutral():
    assert experience_penalty(None, 5) == 0
    assert experience_penalty(5, None) == 0
    assert experience_penalty(None, None) == 0
