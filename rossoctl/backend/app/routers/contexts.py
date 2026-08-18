"""Optional proxy for Context Service context resources."""

import re
from typing import Literal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.core.auth import ROLE_OPERATOR, ROLE_VIEWER, require_roles
from app.core.config import settings

router = APIRouter(prefix="/contexts", tags=["contexts"])

_KUBERNETES_NAME = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")


class ContextStorage(BaseModel):
    backend: Literal["pvc"] = "pvc"
    size: str = "1Gi"
    accessMode: Literal["ReadWriteOnce", "ReadWriteMany"] = "ReadWriteOnce"
    storageClass: str | None = None


class CreateContextRequest(BaseModel):
    name: str
    namespace: str
    type: Literal["workspace", "memory", "knowledge", "artifacts"] = "workspace"
    storage: ContextStorage


def _url(path: str) -> str:
    return f"{settings.context_service_url.rstrip('/')}{path}"


def _path_segment(value: str, field: str, max_length: int = 63) -> str:
    """Validate and encode a Kubernetes-name URL path segment."""
    if len(value) > max_length or not _KUBERNETES_NAME.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field} must be a lowercase Kubernetes name",
        )
    return quote(value, safe="")


async def _request(method: str, path: str, body: dict | None = None) -> httpx.Response:
    if not settings.context_service_url.strip():
        raise HTTPException(status_code=400, detail="Context Service integration is disabled")
    try:
        async with httpx.AsyncClient(timeout=settings.context_service_timeout) as client:
            response = await client.request(method, _url(path), json=body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Context Service unavailable: {exc}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response


@router.post("", dependencies=[Depends(require_roles(ROLE_OPERATOR))])
async def create_context(request: CreateContextRequest) -> dict:
    response = await _request("POST", "/v1/contexts", request.model_dump(exclude_none=True))
    return response.json()


@router.get("/{namespace}", dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR))])
async def list_contexts(namespace: str) -> dict:
    namespace_segment = _path_segment(namespace, "namespace")
    response = await _request("GET", f"/v1/namespaces/{namespace_segment}/contexts")
    return response.json()


@router.get(
    "/{namespace}/{name}", dependencies=[Depends(require_roles(ROLE_VIEWER, ROLE_OPERATOR))]
)
async def get_context(namespace: str, name: str) -> dict:
    namespace_segment = _path_segment(namespace, "namespace")
    name_segment = _path_segment(name, "name", max_length=50)
    response = await _request("GET", f"/v1/namespaces/{namespace_segment}/contexts/{name_segment}")
    return response.json()


@router.delete("/{namespace}/{name}", dependencies=[Depends(require_roles(ROLE_OPERATOR))])
async def delete_context(namespace: str, name: str) -> Response:
    namespace_segment = _path_segment(namespace, "namespace")
    name_segment = _path_segment(name, "name", max_length=50)
    await _request("DELETE", f"/v1/namespaces/{namespace_segment}/contexts/{name_segment}")
    return Response(status_code=204)


async def resolve_context(namespace: str, name: str) -> dict:
    namespace_segment = _path_segment(namespace, "namespace")
    name_segment = _path_segment(name, "name", max_length=50)
    response = await _request("GET", f"/v1/namespaces/{namespace_segment}/contexts/{name_segment}")
    return response.json()
