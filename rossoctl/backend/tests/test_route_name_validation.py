# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Boundary-validation tests for agent route path params (rossoctl/rossoctl#2395).

The `namespace` / `name` path params on the migration + shipwright handlers are
constrained to an RFC-1123 DNS label via FastAPI ``Path(pattern=..., max_length=63)``,
so injection characters (e.g. an encoded newline) are rejected with 422 before any
handler code — and can't reach the loggers CodeQL flagged (py/log-injection).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import agents_migration, agents_shipwright
from app.services.kubernetes import get_kubernetes_service


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(agents_migration.migration_router, prefix="/api/v1")
    app.include_router(agents_shipwright.shipwright_router, prefix="/api/v1")
    # Handlers never run for the invalid cases (422 at validation), but override the
    # kube dep so the valid-name case doesn't touch a real cluster.
    app.dependency_overrides[get_kubernetes_service] = lambda: MagicMock()
    with patch("app.core.auth.settings") as mock_auth:
        # Disable auth so the only thing that can fail is path-param validation.
        mock_auth.enable_auth = False
        yield TestClient(app)


# Names that violate the RFC-1123 DNS label (all must be rejected with 422).
_INVALID = {
    "newline": "bad%0Aname",  # the log-injection vector (encoded \n)
    "uppercase": "BadName",
    "dotted": "a.b",
    "underscore": "bad_name",
    "leading-hyphen": "-bad",
    "too-long": "a" * 64,
}


@pytest.mark.parametrize("label,bad", _INVALID.items(), ids=list(_INVALID))
def test_migrate_rejects_invalid_name(client, label, bad):
    r = client.post(f"/api/v1/default/{bad}/migrate")
    assert r.status_code == 422, f"{label}: expected 422, got {r.status_code}"


@pytest.mark.parametrize("label,bad", _INVALID.items(), ids=list(_INVALID))
def test_migrate_rejects_invalid_namespace(client, label, bad):
    r = client.post(f"/api/v1/{bad}/my-agent/migrate")
    assert r.status_code == 422, f"{label}: expected 422, got {r.status_code}"


@pytest.mark.parametrize("label,bad", _INVALID.items(), ids=list(_INVALID))
def test_shipwright_build_info_rejects_invalid_name(client, label, bad):
    r = client.get(f"/api/v1/default/{bad}/shipwright-build-info")
    assert r.status_code == 422, f"{label}: expected 422, got {r.status_code}"


def test_valid_name_passes_validation(client):
    # A well-formed RFC-1123 name must NOT be rejected by the pattern (422). It may
    # succeed or fail downstream on the mocked kube call, but validation must pass.
    r = client.post("/api/v1/default/my-agent-1/migrate")
    assert r.status_code != 422, f"valid name wrongly rejected: {r.status_code}"
