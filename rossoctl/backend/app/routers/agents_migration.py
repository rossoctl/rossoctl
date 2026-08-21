# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Migration of legacy Agent CRDs to standard Kubernetes workloads.

Converts ``Agent`` custom resources into Deployments/Services and reports which
agents are still migratable.

Split out of ``agents.py``; re-exported there for backwards compatibility.
Routes are attached to ``migration_router`` and composed onto the main agents
router by ``agents.py`` -- see the ordering note there.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from kubernetes.client import ApiException

from app.core.auth import ROLE_OPERATOR, require_roles
from app.core.constants import (
    AGENTS_PLURAL,
    APP_KUBERNETES_IO_CREATED_BY,
    APP_KUBERNETES_IO_MANAGED_BY,
    APP_KUBERNETES_IO_NAME,
    CRD_GROUP,
    CRD_VERSION,
    DEFAULT_IMAGE_POLICY,
    DEFAULT_IN_CLUSTER_PORT,
    DEFAULT_OFF_CLUSTER_PORT,
    DEFAULT_RESOURCE_LIMITS,
    DEFAULT_RESOURCE_REQUESTS,
    MIGRATION_SOURCE_ANNOTATION,
    MIGRATION_TIMESTAMP_ANNOTATION,
    RESOURCE_TYPE_AGENT,
    ROSSOCTL_DESCRIPTION_ANNOTATION,
    ROSSOCTL_OPERATOR_LABEL_NAME,
    ROSSOCTL_TYPE_LABEL,
    ROSSOCTL_UI_CREATOR_LABEL,
    ROSSOCTL_WORKLOAD_TYPE_LABEL,
    WORKLOAD_TYPE_DEPLOYMENT,
)
from app.routers.agents_models import (
    ListMigratableAgentsResponse,
    MigratableAgentInfo,
    MigrateAgentRequest,
    MigrateAgentResponse,
)
from app.services.kubernetes import KubernetesService, get_kubernetes_service
from app.utils.naming import K8S_NAME_MAX_LENGTH, K8S_NAME_PATTERN

logger = logging.getLogger(__name__)

migration_router = APIRouter()


# NOTE: `list_migratable_agents` is intentionally NOT an HTTP endpoint.
# It previously carried `@router.get("/migration/migratable")`, but that route
# was unreachable: it was registered after `GET /{namespace}/{name}`, which
# matches the same two path segments, so requests resolved to `get_agent` with
# namespace="migration", name="migratable". The dead decorator was removed; the
# function remains because `migrate_all_agents` below calls it directly.
async def list_migratable_agents(
    namespace: str = Query(default="default", description="Kubernetes namespace"),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> ListMigratableAgentsResponse:
    """
    List all Agent CRDs in a namespace that can be migrated to Deployments.

    Returns information about each agent including whether a Deployment
    already exists (indicating migration is complete).
    """
    try:
        # List legacy Agent CRDs
        agent_crds = kube.list_custom_resources(
            group=CRD_GROUP,
            version=CRD_VERSION,
            namespace=namespace,
            plural=AGENTS_PLURAL,
        )
    except ApiException as e:
        if e.status == 404:
            # CRD not installed
            return ListMigratableAgentsResponse(agents=[], total=0, already_migrated=0)
        raise HTTPException(status_code=e.status, detail=str(e.reason))

    # Get list of existing Deployments to check for already-migrated agents
    try:
        existing_deployments = kube.list_deployments(
            namespace=namespace,
            label_selector=f"{ROSSOCTL_TYPE_LABEL}={RESOURCE_TYPE_AGENT}",
        )
        existing_names = {d.get("metadata", {}).get("name") for d in existing_deployments}
    except ApiException:
        existing_names = set()

    agents = []
    already_migrated = 0

    for agent in agent_crds:
        metadata = agent.get("metadata", {})
        name = metadata.get("name", "")
        labels = metadata.get("labels", {})
        has_deployment = name in existing_names

        if has_deployment:
            already_migrated += 1

        # Get description from spec or annotations
        spec = agent.get("spec", {})
        description = spec.get("description") or metadata.get("annotations", {}).get(
            ROSSOCTL_DESCRIPTION_ANNOTATION, ""
        )

        # Determine status
        status = agent.get("status", {})
        agent_status = "Unknown"
        for cond in status.get("conditions") or []:
            if cond.get("type") == "Ready":
                agent_status = "Ready" if cond.get("status") == "True" else "Not Ready"
                break

        agents.append(
            MigratableAgentInfo(
                name=name,
                namespace=namespace,
                status=agent_status,
                has_deployment=has_deployment,
                labels=labels,
                description=description,
            )
        )

    return ListMigratableAgentsResponse(
        agents=agents,
        total=len(agents),
        already_migrated=already_migrated,
    )


@migration_router.post(
    "/{namespace}/{name}/migrate",
    response_model=MigrateAgentResponse,
    summary="Migrate an Agent CRD to a Deployment",
    tags=["migration"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)
async def migrate_agent(
    namespace: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    name: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    request: MigrateAgentRequest = MigrateAgentRequest(),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> MigrateAgentResponse:
    """
    Migrate an Agent CRD to a Deployment.

    This endpoint:
    1. Reads the existing Agent CRD specification
    2. Creates a Deployment with the same pod template
    3. Creates a Service for the Deployment
    4. Optionally deletes the Agent CRD (if delete_old=True)

    If a Deployment already exists with the same name, the migration will fail
    unless the existing Deployment was created by rossoctl-operator (in which
    case we just need to clean up the Agent CRD).
    """
    logger.info(f"Starting migration of Agent CRD '{name}' in namespace '{namespace}'")

    deployment_created = False
    service_created = False
    agent_crd_deleted = False

    # Step 1: Get the Agent CRD
    try:
        agent = kube.get_custom_resource(
            group=CRD_GROUP,
            version=CRD_VERSION,
            namespace=namespace,
            plural=AGENTS_PLURAL,
            name=name,
        )
    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Agent CRD '{name}' not found in namespace '{namespace}'",
            )
        raise HTTPException(status_code=e.status, detail=str(e.reason))

    # Step 2: Check if Deployment already exists
    deployment_exists = False
    deployment_managed_by_operator = False
    try:
        existing_deployment = kube.get_deployment(namespace=namespace, name=name)
        deployment_exists = True
        # Check if it was created by rossoctl-operator
        dep_labels = existing_deployment.get("metadata", {}).get("labels", {})
        deployment_managed_by_operator = (
            dep_labels.get(APP_KUBERNETES_IO_CREATED_BY) == ROSSOCTL_OPERATOR_LABEL_NAME
            or dep_labels.get(APP_KUBERNETES_IO_MANAGED_BY) == ROSSOCTL_OPERATOR_LABEL_NAME
        )
        logger.info(
            f"Deployment '{name}' already exists, managed_by_operator={deployment_managed_by_operator}"
        )
    except ApiException as e:
        if e.status != 404:
            raise HTTPException(status_code=e.status, detail=str(e.reason))

    # Step 3: Check if Service already exists
    service_exists = False
    try:
        kube.get_service(namespace=namespace, name=name)
        service_exists = True
        logger.info(f"Service '{name}' already exists")
    except ApiException as e:
        if e.status != 404:
            raise HTTPException(status_code=e.status, detail=str(e.reason))

    # Step 4: Build and create Deployment (if needed)
    if deployment_exists:
        if deployment_managed_by_operator:
            # Deployment was created by operator, we just need to update labels
            # to mark it as migrated (managed by rossoctl-ui now)
            try:
                patch = {
                    "metadata": {
                        "labels": {
                            APP_KUBERNETES_IO_MANAGED_BY: ROSSOCTL_UI_CREATOR_LABEL,
                        },
                        "annotations": {
                            MIGRATION_SOURCE_ANNOTATION: "agent-crd",
                            MIGRATION_TIMESTAMP_ANNOTATION: datetime.now(timezone.utc).isoformat(),
                        },
                    }
                }
                kube.patch_deployment(namespace=namespace, name=name, body=patch)
                logger.info(f"Patched Deployment '{name}' with migration annotations")
            except ApiException as e:
                logger.warning(f"Failed to patch Deployment '{name}': {e.reason}")
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Deployment '{name}' already exists and was not created by rossoctl-operator. "
                "Cannot migrate. Delete the existing Deployment first or use a different name.",
            )
    else:
        # Create new Deployment from Agent CRD spec
        deployment_manifest = _build_deployment_from_agent_crd(agent)
        kube.ensure_service_account(namespace=namespace, name=name)
        try:
            kube.create_deployment(namespace=namespace, body=deployment_manifest)
            deployment_created = True
            logger.info(f"Created Deployment '{name}' from Agent CRD")
        except ApiException as e:
            raise HTTPException(
                status_code=e.status,
                detail=f"Failed to create Deployment: {e.reason}",
            )

    # Step 5: Build and create Service (if needed)
    if not service_exists:
        service_manifest = _build_service_from_agent_crd(agent)
        try:
            kube.create_service(namespace=namespace, body=service_manifest)
            service_created = True
            logger.info(f"Created Service '{name}' from Agent CRD")
        except ApiException as e:
            # If Deployment was created, try to clean up
            if deployment_created:
                try:
                    kube.delete_deployment(namespace=namespace, name=name)
                except Exception as cleanup_error:
                    logger.warning(
                        "Failed to clean up Deployment '%s' after Service creation error: %s",
                        name,
                        cleanup_error,
                    )
            raise HTTPException(
                status_code=e.status,
                detail=f"Failed to create Service: {e.reason}",
            )

    # Step 6: Delete the Agent CRD (if requested)
    if request.delete_old:
        try:
            kube.delete_custom_resource(
                group=CRD_GROUP,
                version=CRD_VERSION,
                namespace=namespace,
                plural=AGENTS_PLURAL,
                name=name,
            )
            agent_crd_deleted = True
            logger.info(f"Deleted Agent CRD '{name}'")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete Agent CRD '{name}': {e.reason}")

    # Build response message
    messages = []
    if deployment_created:
        messages.append("Deployment created")
    elif deployment_exists and deployment_managed_by_operator:
        messages.append("Deployment updated (was created by operator)")
    if service_created:
        messages.append("Service created")
    elif service_exists:
        messages.append("Service already exists")
    if agent_crd_deleted:
        messages.append("Agent CRD deleted")
    elif request.delete_old:
        messages.append("Agent CRD deletion requested but skipped")

    return MigrateAgentResponse(
        success=True,
        migrated=True,
        name=name,
        namespace=namespace,
        message="; ".join(messages) if messages else "Migration completed",
        deployment_created=deployment_created,
        service_created=service_created,
        agent_crd_deleted=agent_crd_deleted,
    )


@migration_router.post(
    "/migration/migrate-all",
    response_model=Dict[str, Any],
    summary="Migrate all Agent CRDs in a namespace to Deployments",
    tags=["migration"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR))],
)
async def migrate_all_agents(
    namespace: str = Query(default="default", description="Kubernetes namespace"),
    delete_old: bool = Query(default=False, description="Delete Agent CRDs after migration"),
    dry_run: bool = Query(default=True, description="If True, only show what would be migrated"),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> Dict[str, Any]:
    """
    Migrate all Agent CRDs in a namespace to Deployments.

    Use dry_run=True (default) to see what would be migrated before actually performing
    the migration. Set dry_run=False to execute the migration.
    """
    # First, get the list of migratable agents
    migratable = await list_migratable_agents(namespace=namespace, kube=kube)

    results = {
        "namespace": namespace,
        "dry_run": dry_run,
        "delete_old": delete_old,
        "total_agents": migratable.total,
        "already_migrated": migratable.already_migrated,
        "to_migrate": migratable.total - migratable.already_migrated,
        "migrated": [],
        "skipped": [],
        "failed": [],
    }

    for agent_info in migratable.agents:
        if agent_info.has_deployment:
            results["skipped"].append(
                {
                    "name": agent_info.name,
                    "reason": "Deployment already exists",
                }
            )
            continue

        if dry_run:
            results["migrated"].append(
                {
                    "name": agent_info.name,
                    "status": "would be migrated (dry-run)",
                }
            )
        else:
            try:
                result = await migrate_agent(
                    namespace=namespace,
                    name=agent_info.name,
                    request=MigrateAgentRequest(delete_old=delete_old),
                    kube=kube,
                )
                results["migrated"].append(
                    {
                        "name": agent_info.name,
                        "status": "migrated",
                        "message": result.message,
                    }
                )
            except HTTPException as e:
                results["failed"].append(
                    {
                        "name": agent_info.name,
                        "error": e.detail,
                    }
                )
            except Exception as e:
                results["failed"].append(
                    {
                        "name": agent_info.name,
                        "error": str(e),
                    }
                )

    return results


def _build_deployment_from_agent_crd(agent: dict) -> dict:
    """
    Build a Kubernetes Deployment manifest from an Agent CRD.

    Args:
        agent: The Agent CRD resource dictionary.

    Returns:
        Deployment manifest dictionary.
    """
    metadata = agent.get("metadata", {})
    spec = agent.get("spec", {})
    name = metadata.get("name", "")
    namespace = metadata.get("namespace", "default")

    # Get labels from Agent CRD and update for Deployment
    labels = metadata.get("labels", {}).copy()
    labels[ROSSOCTL_WORKLOAD_TYPE_LABEL] = WORKLOAD_TYPE_DEPLOYMENT
    labels[APP_KUBERNETES_IO_MANAGED_BY] = ROSSOCTL_UI_CREATOR_LABEL

    # Get annotations
    annotations = metadata.get("annotations", {}).copy()
    annotations[MIGRATION_SOURCE_ANNOTATION] = "agent-crd"
    annotations[MIGRATION_TIMESTAMP_ANNOTATION] = datetime.now(timezone.utc).isoformat()

    # Description
    description = spec.get("description", "")
    if description:
        annotations[ROSSOCTL_DESCRIPTION_ANNOTATION] = description

    # Extract pod template from Agent CRD
    pod_template_spec = spec.get("podTemplateSpec", {})
    pod_spec = pod_template_spec.get("spec", {})

    # If no pod template, try to build one from imageSource
    if not pod_spec:
        image_source = spec.get("imageSource", {})
        image = image_source.get("image", "")
        if not image:
            raise HTTPException(
                status_code=400,
                detail=f"Agent CRD '{name}' has no podTemplateSpec or imageSource.image",
            )

        pod_spec = {
            "serviceAccountName": name,
            "containers": [
                {
                    "name": "agent",
                    "image": image,
                    "imagePullPolicy": DEFAULT_IMAGE_POLICY,
                    "resources": {
                        "limits": DEFAULT_RESOURCE_LIMITS,
                        "requests": DEFAULT_RESOURCE_REQUESTS,
                    },
                    "ports": [
                        {
                            "name": "http",
                            "containerPort": DEFAULT_IN_CLUSTER_PORT,
                            "protocol": "TCP",
                        }
                    ],
                    "volumeMounts": [
                        {"name": "cache", "mountPath": "/app/.cache"},
                        {"name": "shared-data", "mountPath": "/shared"},
                    ],
                }
            ],
            "volumes": [
                {"name": "cache", "emptyDir": {}},
                {"name": "shared-data", "emptyDir": {}},
            ],
        }

    # Ensure serviceAccountName is set so the webhook's SPIFFE identity
    # derivation uses the workload name rather than the ReplicaSet hash.
    pod_spec.setdefault("serviceAccountName", name)

    # Build selector labels (type label is applied by the operator via AgentRuntime)
    selector_labels = {
        APP_KUBERNETES_IO_NAME: name,
    }

    # Build pod template labels (merge selector labels with other labels)
    pod_labels = labels.copy()

    # Get replicas
    replicas = spec.get("replicas", 1)

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "replicas": replicas,
            "selector": {
                "matchLabels": selector_labels,
            },
            "template": {
                "metadata": {
                    "labels": pod_labels,
                },
                "spec": pod_spec,
            },
        },
    }


def _build_service_from_agent_crd(agent: dict) -> dict:
    """
    Build a Kubernetes Service manifest from an Agent CRD.

    Args:
        agent: The Agent CRD resource dictionary.

    Returns:
        Service manifest dictionary.
    """
    metadata = agent.get("metadata", {})
    spec = agent.get("spec", {})
    name = metadata.get("name", "")
    namespace = metadata.get("namespace", "default")

    # Get labels
    labels = metadata.get("labels", {}).copy()
    labels[APP_KUBERNETES_IO_MANAGED_BY] = ROSSOCTL_UI_CREATOR_LABEL

    # Build selector labels (type label is applied by the operator via AgentRuntime)
    selector_labels = {
        APP_KUBERNETES_IO_NAME: name,
    }

    # Get service ports from Agent CRD
    service_ports_spec = spec.get("servicePorts", [])
    if service_ports_spec:
        service_ports = [
            {
                "name": sp.get("name", "http"),
                "port": sp.get("port", DEFAULT_OFF_CLUSTER_PORT),
                "targetPort": sp.get("targetPort", DEFAULT_IN_CLUSTER_PORT),
                "protocol": sp.get("protocol", "TCP"),
            }
            for sp in service_ports_spec
        ]
    else:
        service_ports = [
            {
                "name": "http",
                "port": DEFAULT_OFF_CLUSTER_PORT,
                "targetPort": DEFAULT_IN_CLUSTER_PORT,
                "protocol": "TCP",
            }
        ]

    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "type": "ClusterIP",
            "selector": selector_labels,
            "ports": service_ports,
        },
    }
