"""Bring your own key: the owner's model API key. The key goes straight to the broker's encrypted store;
this service only ever sees it in the request that saves it, and answers with a hint such as "…1234"."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from opa.api.deps import OwnerDep
from opa.api.routers.browser import _broker, _vault
from opa.api.schemas import ModelKeyOut

router = APIRouter(prefix="/api/model-key", tags=["model"])


class ModelKeyIn(BaseModel):
    provider: Literal["anthropic", "zenmux", "custom"]
    base_url: str | None = Field(default=None, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1, max_length=500)


@router.get("", response_model=ModelKeyOut | None)
async def get_model_key(request: Request, owner: OwnerDep) -> ModelKeyOut | None:
    r = await _vault(_broker(request).get_model_key(owner.id))
    return ModelKeyOut(**r) if r else None


@router.put("", response_model=ModelKeyOut)
async def put_model_key(body: ModelKeyIn, request: Request, owner: OwnerDep) -> ModelKeyOut:
    """Checks the key with one tiny request to the provider, then stores it encrypted. Replaces any earlier key."""
    r = await _vault(_broker(request).save_model_key(owner.id, body.provider, body.base_url, body.model, body.api_key))
    return ModelKeyOut(**r)


@router.delete("", status_code=204)
async def delete_model_key(request: Request, owner: OwnerDep) -> Response:
    await _vault(_broker(request).delete_model_key(owner.id))
    return Response(status_code=204)
