# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Readiness/status derivation helpers for agent workloads.

Maps Kubernetes Deployment/StatefulSet/Job/Sandbox status into the short
status strings and descriptions the Agent API reports.

Split out of ``agents.py``; re-exported there for backwards compatibility.
"""

from typing import Optional

from app.core.constants import (
    PROTOCOL_LABEL_PREFIX,
    ROSSOCTL_DESCRIPTION_ANNOTATION,
)
from app.models.responses import ResourceLabels


def _is_deployment_ready(resource_data: dict) -> str:
    """Check if a Kubernetes Deployment is ready based on status.

    For Deployments, checks:
    1. conditions array for type="Available" with status="True"
    2. replicas vs readyReplicas count

    Also maintains backward compatibility with Agent CRD status format.
    """
    status = resource_data.get("status", {})
    conditions = status.get("conditions") or []

    # Check for Kubernetes Deployment conditions (type=Available)
    for condition in conditions:
        cond_type = condition.get("type")
        cond_status = condition.get("status")

        # Kubernetes Deployment uses "Available" condition
        if cond_type == "Available" and cond_status == "True":
            return "Ready"

        # Agent CRD uses "Ready" condition (backward compatibility)
        if cond_type == "Ready" and cond_status == "True":
            return "Ready"

    # Check replica counts for Deployments
    replicas = status.get("replicas") or 0
    ready_replicas = status.get("ready_replicas") or status.get("readyReplicas", 0)
    if 0 < replicas <= ready_replicas:
        return "Ready"

    # Fallback: check deploymentStatus.phase for older Agent CRD versions
    deployment_status = status.get("deploymentStatus", {})
    phase = deployment_status.get("phase", "")
    if phase in ("Ready", "Running"):
        return "Ready"

    return "Not Ready"


def _get_deployment_description(deployment: dict) -> str:
    """Extract description from Deployment annotations."""
    annotations = deployment.get("metadata", {}).get("annotations", {})
    return annotations.get(
        ROSSOCTL_DESCRIPTION_ANNOTATION,
        annotations.get("description", "No description"),
    )


def _is_statefulset_ready(resource_data: dict) -> str:
    """Check if a Kubernetes StatefulSet is ready based on status."""
    status = resource_data.get("status", {})

    # Check replica counts for StatefulSets
    replicas = status.get("replicas") or 0
    ready_replicas = status.get("ready_replicas") or status.get("readyReplicas", 0)

    if replicas == 0:
        return "Not Ready"
    if ready_replicas >= replicas:
        return "Ready"
    if ready_replicas > 0:
        return "Progressing"
    return "Not Ready"


def _get_statefulset_description(statefulset: dict) -> str:
    """Extract description from StatefulSet annotations."""
    annotations = statefulset.get("metadata", {}).get("annotations", {})
    return annotations.get(
        ROSSOCTL_DESCRIPTION_ANNOTATION,
        annotations.get("description", "No description"),
    )


def _get_job_status(job: dict) -> str:
    """Get the status of a Kubernetes Job.

    Returns status values consistent with Deployments and StatefulSets:
    - "Ready": Job completed successfully (equivalent to Job condition "Complete")
    - "Failed": Job failed (equivalent to Job condition "Failed")
    - "Progressing": Job is actively running (has active pods)
    - "Not Ready": Job is pending/not yet started

    This mapping ensures UI consistency across all workload types.
    """
    status = job.get("status", {})
    conditions = status.get("conditions") or []

    # Check conditions for completed or failed
    for condition in conditions:
        cond_type = condition.get("type")
        cond_status = condition.get("status")

        if cond_type == "Complete" and cond_status == "True":
            return "Ready"  # Job completed successfully
        if cond_type == "Failed" and cond_status == "True":
            return "Failed"

    # Check active/succeeded/failed counts
    active = status.get("active") or 0
    succeeded = status.get("succeeded") or 0
    failed = status.get("failed") or 0

    if succeeded > 0:
        return "Ready"  # Job completed successfully
    if failed > 0:
        return "Failed"
    if active > 0:
        return "Progressing"  # Job is actively running
    return "Not Ready"  # Job pending/not started


def _get_job_description(job: dict) -> str:
    """Extract description from Job annotations."""
    annotations = job.get("metadata", {}).get("annotations", {})
    return annotations.get(
        ROSSOCTL_DESCRIPTION_ANNOTATION,
        annotations.get("description", "No description"),
    )


def _is_sandbox_ready(sandbox: dict) -> str:
    """Check if a Sandbox is ready by examining its status conditions."""
    status = sandbox.get("status", {})
    conditions = status.get("conditions", [])
    for cond in conditions:
        if cond.get("type") == "Ready":
            if cond.get("status") == "True":
                return "Ready"
            return "Not Ready"
    return "Pending"


def _get_sandbox_description(sandbox: dict) -> str:
    """Extract description from a Sandbox resource."""
    metadata = sandbox.get("metadata", {})
    annotations = metadata.get("annotations", {})
    return annotations.get(ROSSOCTL_DESCRIPTION_ANNOTATION, "No description")


def _format_timestamp(timestamp) -> Optional[str]:
    """Convert a timestamp to ISO format string.

    The Kubernetes Python client returns datetime objects for timestamp fields,
    but our Pydantic models expect strings.
    """
    if timestamp is None:
        return None
    if isinstance(timestamp, str):
        return timestamp
    # Handle datetime objects from K8s Python client
    if hasattr(timestamp, "isoformat"):
        return timestamp.isoformat()
    return str(timestamp)


def _extract_labels(labels: dict) -> ResourceLabels:
    """Extract rossoctl labels from Kubernetes labels."""
    # Extract protocols from protocol.rossoctl.io/<name> prefix labels.
    protocols = [
        k[len(PROTOCOL_LABEL_PREFIX) :]
        for k in labels
        if k.startswith(PROTOCOL_LABEL_PREFIX) and len(k) > len(PROTOCOL_LABEL_PREFIX)
    ]
    # Fall back to deprecated rossoctl.io/protocol single-value label.
    if not protocols:
        legacy = labels.get("rossoctl.io/protocol")
        if legacy:
            protocols = [legacy]

    return ResourceLabels(
        protocol=protocols or None,
        framework=labels.get("rossoctl.io/framework"),
        type=labels.get("rossoctl.io/type"),
    )
