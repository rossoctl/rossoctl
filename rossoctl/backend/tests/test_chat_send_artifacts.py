# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Tests for send_message content extraction from A2A responses.

A completed A2A Task carries its output in ``result.artifacts[].parts[]`` and
commonly leaves ``status.message`` unset. These tests pin that shape (plus the
in-status and direct-message shapes) so ``/chat/{ns}/{name}/send`` no longer
falls through to "No response from agent".
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.routers.chat import ChatRequest, send_message


@pytest.fixture
def mock_kube():
    return MagicMock()


@pytest.fixture
def mock_user():
    return MagicMock(username="tester")


@pytest.fixture
def mock_http_request():
    return MagicMock(headers={})


@pytest.fixture(autouse=True)
def mock_invoke_url():
    with patch(
        "app.routers.chat._resolve_invoke_url",
        new_callable=AsyncMock,
        return_value="http://myagent.ns.svc.cluster.local:8080",
    ) as m:
        yield m


def _agent_response(result: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": "1", "result": result},
        request=httpx.Request("POST", "http://x"),
    )


async def _send(mock_response, mock_http_request, mock_user, mock_kube, session_id=None):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        return await send_message(
            namespace="ns",
            name="myagent",
            request=ChatRequest(message="what is the weather in Rome?", session_id=session_id),
            http_request=mock_http_request,
            user=mock_user,
            kube=mock_kube,
        )


class TestSendMessageContentExtraction:
    @pytest.mark.asyncio
    async def test_extracts_text_from_completed_task_artifacts(
        self, mock_http_request, mock_user, mock_kube
    ):
        """A completed Task answers via artifacts, with no status.message."""
        result = {
            "id": "task-1",
            "contextId": "ctx-1",
            "kind": "task",
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "artifactId": "a-1",
                    "parts": [{"kind": "text", "text": "The weather in Rome is 20C."}],
                }
            ],
        }

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "The weather in Rome is 20C."
        assert response.session_id == "ctx-1"

    @pytest.mark.asyncio
    async def test_concatenates_multiple_artifacts(self, mock_http_request, mock_user, mock_kube):
        """Multi-artifact tasks contribute all their text parts, in order."""
        result = {
            "status": {"state": "completed"},
            "artifacts": [
                {"parts": [{"kind": "text", "text": "first."}]},
                {"parts": [{"kind": "text", "text": "second."}]},
            ],
        }

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "first.second."

    @pytest.mark.asyncio
    async def test_status_message_still_extracted(self, mock_http_request, mock_user, mock_kube):
        """Agents that answer in status.message keep working (no regression)."""
        result = {
            "status": {
                "state": "completed",
                "message": {"role": "agent", "parts": [{"kind": "text", "text": "in-status."}]},
            }
        }

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "in-status."

    @pytest.mark.asyncio
    async def test_null_status_message_does_not_error(
        self, mock_http_request, mock_user, mock_kube
    ):
        """An explicit status.message=null must not raise; artifacts win."""
        result = {
            "status": {"state": "completed", "message": None},
            "artifacts": [{"parts": [{"kind": "text", "text": "from artifact."}]}],
        }

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "from artifact."

    @pytest.mark.asyncio
    async def test_direct_message_response(self, mock_http_request, mock_user, mock_kube):
        """Agents replying with a bare Message keep working (no regression)."""
        result = {
            "kind": "message",
            "role": "agent",
            "parts": [{"kind": "text", "text": "direct reply."}],
        }

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "direct reply."

    @pytest.mark.asyncio
    async def test_empty_result_falls_back_to_placeholder(
        self, mock_http_request, mock_user, mock_kube
    ):
        """A genuinely empty result still reports the placeholder."""
        result = {"status": {"state": "working"}}

        response = await _send(_agent_response(result), mock_http_request, mock_user, mock_kube)

        assert response.content == "No response from agent"
