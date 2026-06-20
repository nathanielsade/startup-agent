_config: dict | None = None


def set_config(provider: str, api_key: str, model: str = "") -> None:
    global _config
    _config = {"provider": provider, "api_key": api_key, "model": model}


def get_config() -> dict | None:
    return _config


def clear_config() -> None:
    global _config
    _config = None
