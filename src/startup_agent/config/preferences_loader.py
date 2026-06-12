from pathlib import Path

import yaml

from startup_agent.domain.preferences import Preferences


def load_preferences(path: str) -> Preferences:
    data = yaml.safe_load(Path(path).read_text()) or {}
    return Preferences(**{k: data.get(k, []) for k in
                          ("roles", "seniority", "locations", "must_have", "exclude", "title_include")})
