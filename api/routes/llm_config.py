from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.llm_config import clear_config, get_config, set_config

router = APIRouter()


class LlmConfigIn(BaseModel):
    provider: Literal["anthropic", "openai"]
    api_key: str = Field(min_length=1)
    model: str | None = None


@router.put("/llm-config")
def put_llm_config(body: LlmConfigIn) -> dict:
    set_config(body.provider, body.api_key, body.model or "")
    return {"configured": True, "provider": body.provider}


@router.get("/llm-config")
def get_llm_config() -> dict:
    cfg = get_config()
    return {"configured": cfg is not None,
            "provider": cfg["provider"] if cfg else None}


@router.delete("/llm-config")
def delete_llm_config() -> dict:
    clear_config()
    return {"configured": False}
