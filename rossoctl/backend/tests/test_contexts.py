"""Tests for optional Context Service resources and agent attachments."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.routers import contexts
from app.routers.agents import (
    ContextAttachment,
    CreateAgentRequest,
    _build_sandbox_manifest,
    _build_statefulset_manifest,
    _resolve_context_mounts,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("context_type", ["workspace", "memory", "knowledge", "artifacts"])
async def test_create_context_proxies_request(context_type: str) -> None:
    response = httpx.Response(
        200,
        json={"name": "research", "namespace": "team1", "status": "Ready"},
    )
    with patch.object(contexts, "_request", new=AsyncMock(return_value=response)) as request:
        result = await contexts.create_context(
            contexts.CreateContextRequest(
                name="research",
                namespace="team1",
                type=context_type,
                storage=contexts.ContextStorage(size="10Gi", accessMode="ReadWriteMany"),
            )
        )

    assert result["name"] == "research"
    request.assert_awaited_once_with(
        "POST",
        "/v1/contexts",
        {
            "name": "research",
            "namespace": "team1",
            "type": context_type,
            "storage": {
                "backend": "pvc",
                "size": "10Gi",
                "accessMode": "ReadWriteMany",
            },
        },
    )


@pytest.mark.asyncio
async def test_list_contexts_proxies_namespace() -> None:
    response = httpx.Response(200, json={"items": [{"name": "research"}]})
    with patch.object(contexts, "_request", new=AsyncMock(return_value=response)) as request:
        result = await contexts.list_contexts("team1")

    assert result["items"][0]["name"] == "research"
    request.assert_awaited_once_with("GET", "/v1/namespaces/team1/contexts")


@pytest.mark.asyncio
async def test_context_attachments_require_service_url() -> None:
    with patch("app.routers.agents.settings.context_service_url", ""):
        with pytest.raises(HTTPException, match="disabled"):
            await _resolve_context_mounts(
                "team1", [ContextAttachment(name="research")], "sandbox"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("context_type", ["workspace", "memory", "knowledge", "artifacts"])
async def test_context_attachments_resolve_pvc_for_sandbox_and_statefulset(
    context_type: str,
) -> None:
    resource = {
        "type": context_type,
        "attachment": {"kind": "pvc", "claimName": "context-research"},
    }
    attachment = ContextAttachment(name="research", mountPath="/workspace")
    with (
        patch("app.routers.agents.settings.context_service_url", "http://context-service:8080"),
        patch("app.routers.agents.settings.rossoctl_feature_flag_agent_sandbox", True),
        patch("app.routers.contexts.resolve_context", new=AsyncMock(return_value=resource)),
    ):
        for workload_type, builder in (
            ("sandbox", _build_sandbox_manifest),
            ("statefulset", _build_statefulset_manifest),
        ):
            volumes, mounts = await _resolve_context_mounts(
                "team1", [attachment], workload_type
            )
            agent_request = CreateAgentRequest(
                name="research-agent",
                namespace="team1",
                workloadType="statefulset",
            )
            # Sandbox availability is injected into SUPPORTED_WORKLOAD_TYPES at
            # process startup. The builder itself accepts the same request shape.
            agent_request.workloadType = workload_type
            manifest = builder(
                agent_request,
                "example/agent:latest",
                ext_volumes=volumes,
                ext_volume_mounts=mounts,
            )
            pod_spec = (
                manifest["spec"]["podTemplate"]["spec"]
                if workload_type == "sandbox"
                else manifest["spec"]["template"]["spec"]
            )
            assert volumes[0]["persistentVolumeClaim"]["claimName"] == "context-research"
            assert pod_spec["containers"][0]["volumeMounts"][-1]["mountPath"] == "/workspace"
            context_volume = next(v for v in pod_spec["volumes"] if v["name"] == "context-0")
            assert context_volume["persistentVolumeClaim"]["claimName"] == "context-research"


@pytest.mark.asyncio
async def test_context_attachments_reject_non_pvc_attachment() -> None:
    resource = {
        "type": "artifacts",
        "attachment": {"kind": "s3", "bucket": "research-results"},
    }
    with (
        patch("app.routers.agents.settings.context_service_url", "http://context-service:8080"),
        patch("app.routers.contexts.resolve_context", new=AsyncMock(return_value=resource)),
        pytest.raises(HTTPException, match="non-PVC"),
    ):
        await _resolve_context_mounts(
            "team1", [ContextAttachment(name="research-results")], "sandbox"
        )


@pytest.mark.asyncio
async def test_context_attachments_reject_deployment() -> None:
    with pytest.raises(HTTPException, match="statefulset or sandbox"):
        await _resolve_context_mounts(
            "team1", [ContextAttachment(name="research")], "deployment"
        )
