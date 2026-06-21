from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_settings
from api.llm_config import clear_config, get_config, set_config

router = APIRouter()


def _server_side_llm(settings) -> str | None:
    """The LLM provider configured via server env (cloud), or None."""
    provider = (settings.llm_provider or "anthropic").lower()
    key = settings.openai_api_key if provider == "openai" else settings.anthropic_api_key
    return provider if key else None


class LlmConfigIn(BaseModel):
    provider: Literal["anthropic", "openai"]
    api_key: str = Field(min_length=1)
    model: str | None = None


@router.put("/llm-config")
def put_llm_config(body: LlmConfigIn) -> dict:
    set_config(body.provider, body.api_key, body.model or "")
    return {"configured": True, "provider": body.provider}


@router.get("/llm-config")
def get_llm_config(settings=Depends(get_settings)) -> dict:
    # A user-pasted key takes precedence; otherwise reflect the server-side env key.
    cfg = get_config()
    if cfg is not None:
        return {"configured": True, "provider": cfg["provider"]}
    provider = _server_side_llm(settings)
    return {"configured": provider is not None, "provider": provider}


@router.delete("/llm-config")
def delete_llm_config() -> dict:
    clear_config()
    return {"configured": False}
