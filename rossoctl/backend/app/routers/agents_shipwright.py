# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Shipwright build endpoints for agents.

Lists cluster build strategies and rossoctl-owned Builds, reports Build/BuildRun
status, triggers rebuilds, and surfaces the resource config recorded on a Build.

Split out of ``agents.py``; re-exported there for backwards compatibility.
Routes are attached to ``shipwright_router`` and composed onto the main agents
router by ``agents.py`` -- see the ordering note there.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from kubernetes.client import ApiException

from app.core.auth import ROLE_OPERATOR, ROLE_VIEWER, require_roles
from app.core.constants import (
    RESOURCE_TYPE_AGENT,
    SHIPWRIGHT_BUILDRUNS_PLURAL,
    SHIPWRIGHT_BUILDS_PLURAL,
    SHIPWRIGHT_CLUSTER_BUILD_STRATEGIES_PLURAL,
    SHIPWRIGHT_CRD_GROUP,
    SHIPWRIGHT_CRD_VERSION,
)
from app.models.shipwright import (
    BuildStatusCondition,
    ClusterBuildStrategiesResponse,
    ClusterBuildStrategyInfo,
    ResourceType,
    ShipwrightBuildListResponse,
    ShipwrightBuildRunStatusResponse,
    ShipwrightBuildStatusResponse,
)
from app.routers.agents_models import AgentShipwrightBuildInfoResponse
from app.routers.agents_skills import _build_agent_shipwright_buildrun_manifest
from app.services.kubernetes import KubernetesService, get_kubernetes_service
from app.services.shipwright import (
    extract_buildrun_info,
    extract_resource_config_from_build,
    get_latest_buildrun,
)
from app.services.shipwright_builds import collect_rossoctl_shipwright_builds
from app.utils.naming import K8S_NAME_MAX_LENGTH, K8S_NAME_PATTERN

logger = logging.getLogger(__name__)

shipwright_router = APIRouter()


@shipwright_router.get(
    "/build-strategies",
    response_model=ClusterBuildStrategiesResponse,
    dependencies=[Depends(require_roles(ROLE_VIEWER))],
)
async def list_build_strategies(
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> ClusterBuildStrategiesResponse:
    """List available ClusterBuildStrategies for Shipwright builds.

    Returns the list of ClusterBuildStrategy resources available in the cluster.
    """
    try:
        response = kube.list_cluster_custom_resources(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            plural=SHIPWRIGHT_CLUSTER_BUILD_STRATEGIES_PLURAL,
        )

        strategy_list = []
        for strategy in response.get("items", []):
            metadata = strategy.get("metadata", {})
            spec = strategy.get("spec", {})
            # Get description from annotations or spec
            annotations = metadata.get("annotations", {})
            description = annotations.get("description") or spec.get("description")

            strategy_list.append(
                ClusterBuildStrategyInfo(
                    name=metadata.get("name", ""),
                    description=description,
                )
            )

        return ClusterBuildStrategiesResponse(strategies=strategy_list)

    except ApiException as e:
        logger.error(f"Failed to list ClusterBuildStrategies: {e}")
        raise HTTPException(
            status_code=e.status,
            detail=f"Failed to list build strategies: {e.reason}",
        )


@shipwright_router.get(
    "/shipwright-builds",
    response_model=ShipwrightBuildListResponse,
    dependencies=[Depends(require_roles(ROLE_VIEWER))],
)
async def list_agent_shipwright_builds(
    namespace: str = Query(
        default="",
        description="Kubernetes namespace (required unless all_namespaces=true)",
    ),
    all_namespaces: bool = Query(
        default=False,
        alias="allNamespaces",
        description="If true, list builds in all rossoctl-enabled namespaces",
    ),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> ShipwrightBuildListResponse:
    """List Shipwright Build resources for agents only (rossoctl.io/type=agent)."""
    namespaces_to_scan: List[str] = []
    if all_namespaces:
        namespaces_to_scan = kube.list_enabled_namespaces()
    else:
        if not namespace or not namespace.strip():
            raise HTTPException(
                status_code=400,
                detail="namespace query parameter is required (or use allNamespaces=true)",
            )
        namespaces_to_scan = [namespace.strip()]

    try:
        items = collect_rossoctl_shipwright_builds(
            kube, namespaces_to_scan, RESOURCE_TYPE_AGENT, logger
        )
    except ApiException as e:
        raise HTTPException(status_code=e.status, detail=str(e.reason))

    return ShipwrightBuildListResponse(items=items)


@shipwright_router.get(
    "/{namespace}/{name}/shipwright-build",
    response_model=ShipwrightBuildStatusResponse,
    dependencies=[Depends(require_roles(ROLE_VIEWER))],
)
async def get_shipwright_build_status(
    namespace: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    name: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> ShipwrightBuildStatusResponse:
    """Get the Shipwright Build status for an agent.

    Returns the Build resource status including whether it's registered
    and ready for BuildRuns.
    """
    try:
        build = kube.get_custom_resource(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            namespace=namespace,
            plural=SHIPWRIGHT_BUILDS_PLURAL,
            name=name,
        )

        metadata = build.get("metadata", {})
        status = build.get("status", {})

        # Check if build is registered (strategy validated)
        registered = status.get("registered", False)
        reason = status.get("reason")
        message = status.get("message")

        return ShipwrightBuildStatusResponse(
            name=metadata.get("name", name),
            namespace=metadata.get("namespace", namespace),
            registered=registered,
            reason=reason,
            message=message,
        )

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Shipwright Build '{name}' not found in namespace '{namespace}'",
            )
        raise HTTPException(status_code=e.status, detail=str(e.reason))


@shipwright_router.get(
    "/{namespace}/{name}/shipwright-buildrun",
    response_model=ShipwrightBuildRunStatusResponse,
    dependencies=[Depends(require_roles(ROLE_VIEWER))],
)
async def get_shipwright_buildrun_status(
    namespace: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    name: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> ShipwrightBuildRunStatusResponse:
    """Get the latest Shipwright BuildRun status for an agent build.

    Lists BuildRuns with label selector for the build name and returns
    the most recent one's status.
    """
    try:
        # List BuildRuns with label selector for this build
        items = kube.list_custom_resources(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            namespace=namespace,
            plural=SHIPWRIGHT_BUILDRUNS_PLURAL,
            label_selector=f"rossoctl.io/build-name={name}",
        )

        if not items:
            raise HTTPException(
                status_code=404,
                detail=f"No BuildRuns found for build '{name}' in namespace '{namespace}'",
            )

        # Sort by creation timestamp and get the most recent
        items.sort(
            key=lambda x: x.get("metadata", {}).get("creationTimestamp", ""),
            reverse=True,
        )
        latest_buildrun = items[0]

        metadata = latest_buildrun.get("metadata", {})
        status = latest_buildrun.get("status", {})
        spec = latest_buildrun.get("spec", {})

        # Extract conditions
        conditions = []
        for cond in status.get("conditions") or []:
            conditions.append(
                BuildStatusCondition(
                    type=cond.get("type", ""),
                    status=cond.get("status", ""),
                    reason=cond.get("reason"),
                    message=cond.get("message"),
                    lastTransitionTime=cond.get("lastTransitionTime"),
                )
            )

        # Determine phase from conditions
        phase = "Pending"
        failure_message = None
        for cond in conditions:
            if cond.type == "Succeeded":
                if cond.status == "True":
                    phase = "Succeeded"
                elif cond.status == "False":
                    phase = "Failed"
                    failure_message = cond.message
                else:
                    phase = "Running"
                break

        # Get output image info
        output = status.get("output", {})
        output_image = output.get("image")
        output_digest = output.get("digest")

        return ShipwrightBuildRunStatusResponse(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", namespace),
            buildName=spec.get("build", {}).get("name", name),
            phase=phase,
            startTime=status.get("startTime"),
            completionTime=status.get("completionTime"),
            outputImage=output_image,
            outputDigest=output_digest,
            failureMessage=failure_message,
            conditions=conditions,
        )

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"BuildRun not found for build '{name}' in namespace '{namespace}'",
            )
        raise HTTPException(status_code=e.status, detail=str(e.reason))


@shipwright_router.post(
    "/{namespace}/{name}/shipwright-buildrun", dependencies=[Depends(require_roles(ROLE_OPERATOR))]
)
async def trigger_shipwright_buildrun(
    namespace: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    name: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> Dict[str, Any]:
    """Trigger a new Shipwright BuildRun for an existing Build.

    Creates a new BuildRun resource to start a build execution.
    """
    try:
        # First verify the Build exists
        build = kube.get_custom_resource(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            namespace=namespace,
            plural=SHIPWRIGHT_BUILDS_PLURAL,
            name=name,
        )

        # Get labels from the Build to propagate to BuildRun
        build_labels = build.get("metadata", {}).get("labels", {})
        buildrun_labels = {
            k: v
            for k, v in build_labels.items()
            if k.startswith("rossoctl.io/") or k.startswith("app.kubernetes.io/")
        }

        # Create BuildRun manifest
        buildrun_manifest = _build_agent_shipwright_buildrun_manifest(
            build_name=name,
            namespace=namespace,
            labels=buildrun_labels,
        )

        # Create the BuildRun
        created_buildrun = kube.create_custom_resource(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            namespace=namespace,
            plural=SHIPWRIGHT_BUILDRUNS_PLURAL,
            body=buildrun_manifest,
        )

        return {
            "success": True,
            "buildRunName": created_buildrun.get("metadata", {}).get("name"),
            "namespace": namespace,
            "buildName": name,
            "message": "BuildRun created successfully",
        }

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Build '{name}' not found in namespace '{namespace}'",
            )
        raise HTTPException(status_code=e.status, detail=str(e.reason))


@shipwright_router.get(
    "/{namespace}/{name}/shipwright-build-info",
    response_model=AgentShipwrightBuildInfoResponse,
    dependencies=[Depends(require_roles(ROLE_VIEWER))],
)
async def get_shipwright_build_info(
    namespace: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    name: str = Path(..., pattern=K8S_NAME_PATTERN, max_length=K8S_NAME_MAX_LENGTH),
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> AgentShipwrightBuildInfoResponse:
    """Get full Shipwright Build information including agent config and BuildRun status.

    This endpoint provides all the information needed for the build progress page:
    - Build configuration and status
    - Latest BuildRun status
    - Agent configuration stored in annotations
    """
    try:
        # Get the Build resource
        build = kube.get_custom_resource(
            group=SHIPWRIGHT_CRD_GROUP,
            version=SHIPWRIGHT_CRD_VERSION,
            namespace=namespace,
            plural=SHIPWRIGHT_BUILDS_PLURAL,
            name=name,
        )

        metadata = build.get("metadata", {})
        spec = build.get("spec", {})
        status = build.get("status", {})

        # Extract build info
        source = spec.get("source", {})
        git_info = source.get("git", {})
        strategy = spec.get("strategy", {})
        output = spec.get("output", {})

        # Parse agent config from annotations using shared utility
        agent_config = extract_resource_config_from_build(build, ResourceType.AGENT)

        # Build response with basic build info
        response = AgentShipwrightBuildInfoResponse(
            name=metadata.get("name", name),
            namespace=metadata.get("namespace", namespace),
            buildRegistered=status.get("registered", False),
            buildReason=status.get("reason"),
            buildMessage=status.get("message"),
            outputImage=output.get("image", ""),
            strategy=strategy.get("name", ""),
            gitUrl=git_info.get("url", ""),
            gitRevision=git_info.get("revision", ""),
            contextDir=source.get("contextDir", ""),
            agentConfig=agent_config,
        )

        # Try to get the latest BuildRun
        try:
            items = kube.list_custom_resources(
                group=SHIPWRIGHT_CRD_GROUP,
                version=SHIPWRIGHT_CRD_VERSION,
                namespace=namespace,
                plural=SHIPWRIGHT_BUILDRUNS_PLURAL,
                label_selector=f"rossoctl.io/build-name={name}",
            )

            if items:
                latest_buildrun = get_latest_buildrun(items)
                if latest_buildrun:
                    buildrun_info = extract_buildrun_info(latest_buildrun)

                    response.hasBuildRun = True
                    response.buildRunName = buildrun_info["name"]
                    response.buildRunPhase = buildrun_info["phase"]
                    response.buildRunStartTime = buildrun_info["startTime"]
                    response.buildRunCompletionTime = buildrun_info["completionTime"]
                    response.buildRunOutputImage = buildrun_info["outputImage"]
                    response.buildRunOutputDigest = buildrun_info["outputDigest"]
                    response.buildRunFailureMessage = buildrun_info["failureMessage"]

        except ApiException as e:
            # BuildRun not found is OK, just means no build has been triggered
            if e.status != 404:
                logger.warning(f"Failed to get BuildRun for build '{name}': {e}")

        return response

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Shipwright Build '{name}' not found in namespace '{namespace}'",
            )
        raise HTTPException(status_code=e.status, detail=str(e.reason))
