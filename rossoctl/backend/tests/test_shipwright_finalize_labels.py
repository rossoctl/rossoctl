# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""Tests for _carryover_workload_labels — the rossoctl.io/* labels copied from
a Shipwright Build onto a raw workload (Deployment/StatefulSet/Job) in
finalize_shipwright_build.

Regression for #2489: the carry-over must exclude rossoctl.io/type. That label
is guarded by the agent-label-protection ValidatingAdmissionPolicy, which only
lets the rossoctl-operator set it (via AgentRuntime reconciliation). Copying it
onto a raw Deployment made the finalize path get a 403 and silently create no
workload. _build_common_labels omits the label for the same reason; this helper
mirrors that when re-applying Build labels.
"""

from app.core.config import settings
from app.routers.agents_manifests import _carryover_workload_labels

TYPE_LABEL = settings.rossoctl_type_label  # "rossoctl.io/type"


def test_type_label_stripped_from_carryover():
    """rossoctl.io/type must never be carried onto a raw workload (the #2489 bug)."""
    result = _carryover_workload_labels({TYPE_LABEL: "agent"})
    assert TYPE_LABEL not in result
    assert result == {}


def test_other_rossoctl_labels_preserved():
    """Every other rossoctl.io/* label survives the carry-over unchanged."""
    build_labels = {
        TYPE_LABEL: "agent",
        "rossoctl.io/framework": "langgraph",
        "rossoctl.io/workload-type": "deployment",
        "rossoctl.io/protocol-a2a": "",
        "rossoctl.io/inject": "enabled",
        "rossoctl.io/spire": "enabled",
    }
    result = _carryover_workload_labels(build_labels)
    assert TYPE_LABEL not in result
    assert result == {
        "rossoctl.io/framework": "langgraph",
        "rossoctl.io/workload-type": "deployment",
        "rossoctl.io/protocol-a2a": "",
        "rossoctl.io/inject": "enabled",
        "rossoctl.io/spire": "enabled",
    }


def test_non_rossoctl_labels_excluded():
    """Only rossoctl.io/* labels are carried; other prefixes are dropped
    (matches the original prefix-filter behavior)."""
    build_labels = {
        "rossoctl.io/framework": "crewai",
        "app.kubernetes.io/name": "weather-service",
        "app.kubernetes.io/managed-by": "rossoctl-ui",
        "example.com/team": "team1",
    }
    result = _carryover_workload_labels(build_labels)
    assert result == {"rossoctl.io/framework": "crewai"}


def test_empty_build_labels():
    """Empty in -> empty out, no crash."""
    assert _carryover_workload_labels({}) == {}


def test_finalize_request_has_contexts_field():
    """finalize_shipwright_build reads request.contexts unconditionally.

    The finalize model must carry the field or that access raises
    AttributeError -> 500 before any workload is created, blocking every
    Deployment/StatefulSet/Job finalize (issue #2489). Defaults to None so the
    stored-config fallback kicks in.
    """
    from app.routers.agents import FinalizeShipwrightBuildRequest

    req = FinalizeShipwrightBuildRequest()
    # Access mirrors line ~398 of agents_finalize.py; must not raise.
    assert req.contexts is None
