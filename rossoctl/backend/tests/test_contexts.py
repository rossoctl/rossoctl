"""Tests for optional Context Service resources and agent attachments."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from kubernetes.client import ApiException

from app.routers import contexts
from app.routers.agents import (
    ContextAttachment,
    CreateAgentRequest,
    _build_sandbox_manifest,
    _build_statefulset_manifest,
    _resolve_context_mounts,
    get_agent,
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
async def test_context_proxy_requires_service_url() -> None:
    with (
        patch("app.routers.contexts.settings.context_service_url", ""),
        patch("app.routers.contexts.httpx.AsyncClient") as client,
        pytest.raises(HTTPException, match="integration is disabled"),
    ):
        await contexts.list_contexts("team1")

    client.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "args", "message"),
    [
        (contexts.list_contexts, ("../master",), "namespace"),
        (contexts.get_context, ("team1", "research/../../admin"), "name"),
        (contexts.delete_context, ("Team1", "research"), "namespace"),
        (contexts.resolve_context, ("team1", "x" * 51), "name"),
    ],
)
async def test_context_paths_reject_invalid_kubernetes_names(
    operation, args: tuple[str, ...], message: str
) -> None:
    with (
        patch.object(contexts, "_request", new=AsyncMock()) as request,
        pytest.raises(HTTPException, match=message),
    ):
        await operation(*args)

    request.assert_not_awaited()


@pytest.mark.asyncio
async def test_context_attachments_require_service_url() -> None:
    with patch("app.routers.agents.settings.context_service_url", ""):
        with pytest.raises(HTTPException, match="disabled"):
            await _resolve_context_mounts("team1", [ContextAttachment(name="research")], "sandbox")


@pytest.mark.asyncio
async def test_context_attachments_reject_missing_context() -> None:
    with (
        patch("app.routers.agents.settings.context_service_url", "http://context-service:8080"),
        patch(
            "app.routers.contexts.resolve_context",
            new=AsyncMock(side_effect=HTTPException(status_code=404, detail="context not found")),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _resolve_context_mounts(
            "team1", [ContextAttachment(name="does-not-exist")], "sandbox"
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "context not found"


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
            volumes, mounts, resolved = await _resolve_context_mounts(
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
            assert resolved == [
                {
                    "name": "research",
                    "type": context_type,
                    "mountPath": "/workspace",
                    "readOnly": False,
                    "claimName": "context-research",
                }
            ]


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
async def test_context_attachments_reject_missing_type() -> None:
    resource = {
        "attachment": {"kind": "pvc", "claimName": "context-research"},
    }
    with (
        patch("app.routers.agents.settings.context_service_url", "http://context-service:8080"),
        patch("app.routers.contexts.resolve_context", new=AsyncMock(return_value=resource)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await _resolve_context_mounts("team1", [ContextAttachment(name="research")], "sandbox")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Context Service returned no type"


@pytest.mark.asyncio
async def test_context_attachments_reject_deployment() -> None:
    with pytest.raises(HTTPException, match="statefulset or sandbox"):
        await _resolve_context_mounts("team1", [ContextAttachment(name="research")], "deployment")


@pytest.mark.asyncio
async def test_get_statefulset_agent_reports_context_attachments() -> None:
    attachments = [
        {
            "name": "research",
            "type": "workspace",
            "mountPath": "/workspace",
            "readOnly": False,
            "claimName": "context-research",
        }
    ]
    kube = MagicMock()
    kube.get_deployment.side_effect = ApiException(status=404)
    kube.get_statefulset.return_value = {
        "metadata": {
            "name": "research-agent",
            "namespace": "team1",
            "labels": {},
            "annotations": {"rossoctl.io/contexts": json.dumps(attachments)},
        },
        "spec": {},
        "status": {},
    }
    kube.get_service.side_effect = ApiException(status=404)

    result = await get_agent("team1", "research-agent", kube)

    assert result["contexts"] == attachments


@pytest.mark.asyncio
async def test_get_agent_without_contexts_omits_field() -> None:
    kube = MagicMock()
    kube.get_deployment.return_value = {
        "metadata": {"name": "plain-agent", "namespace": "team1", "labels": {}},
        "spec": {},
        "status": {},
    }
    kube.get_service.side_effect = ApiException(status=404)

    result = await get_agent("team1", "plain-agent", kube)

    assert "contexts" not in result
