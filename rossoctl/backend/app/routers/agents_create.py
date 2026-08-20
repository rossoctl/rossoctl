# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Agent creation endpoint.

Handles both deployment methods: ``image`` (deploy a prebuilt image directly)
and ``source`` (kick off a Shipwright Build/BuildRun and let
``finalize_shipwright_build`` create the workload once the image exists).

Split out of ``agents.py``; re-exported there for backwards compatibility.
``agents.py`` registers ``create_agent`` onto the main agents router directly --
see the note above the function for why it has no decorator here.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException
from kubernetes.client import ApiException

from app.core.config import settings
from app.core.constants import (
    DEFAULT_IN_CLUSTER_PORT,
    DEFAULT_OFF_CLUSTER_PORT,
    SHIPWRIGHT_BUILDRUNS_PLURAL,
    SHIPWRIGHT_BUILDS_PLURAL,
    SHIPWRIGHT_CRD_GROUP,
    SHIPWRIGHT_CRD_VERSION,
    WORKLOAD_TYPE_DEPLOYMENT,
    WORKLOAD_TYPE_JOB,
    WORKLOAD_TYPE_SANDBOX,
    WORKLOAD_TYPE_STATEFULSET,
)
from app.routers.agents_authbridge import (
    _ensure_authbridge_configmaps,
    _ensure_authbridge_scc_rolebinding,
    _ensure_authproxy_routes,
)
from app.routers.agents_manifests import (
    _agentruntime_supported_workload,
    _build_deployment_manifest,
    _build_job_manifest,
    _build_sandbox_manifest,
    _build_service_manifest,
    _build_statefulset_manifest,
    _create_or_replace_service,
    _ensure_agentruntime,
    _record_contexts,
    _resolve_context_mounts,
)
from app.routers.agents_models import CreateAgentRequest, CreateAgentResponse
from app.routers.agents_skills import (
    _build_agent_shipwright_build_manifest,
    _build_agent_shipwright_buildrun_manifest,
    _ensure_card_unsigned_configmap,
    _ensure_fetcher_scripts_cm,
    _get_external_skill_data,
    _is_skill_external,
)
from app.services.agent_env_defaults import apply_agent_import_defaults
from app.services.kubernetes import KubernetesService, get_kubernetes_service
from app.services.shipwright import resolve_clone_secret
from app.services.shipwright_builds import cleanup_existing_build
from app.utils.routes import (
    create_route_for_agent_or_tool,
    rollback_workload_resources,
    sanitize_log,
    select_route_port,
)

logger = logging.getLogger(__name__)


# NOTE: no decorator here. This endpoint's path is "" (i.e. exactly /agents),
# which FastAPI rejects on a prefix-less sub-router ("Prefix and path cannot be
# both empty"). `agents.py` therefore registers it directly onto the prefixed
# main router, at the same position it occupied before the split.
async def create_agent(
    request: CreateAgentRequest,
    kube: KubernetesService = Depends(get_kubernetes_service),
) -> CreateAgentResponse:
    """
    Create a new agent.

    Supports two deployment methods:
    - 'source': Build from git repository using Shipwright Build + BuildRun
    - 'image': Deploy from existing container image as workload + Service

    Supports four workload types:
    - 'deployment': Standard Kubernetes Deployment (default)
    - 'statefulset': StatefulSet for stateful agents
    - 'job': Job for batch/one-time agents
    - 'sandbox': Sandbox CR for isolated agents (requires feature flag)
    """
    logger.info(
        f"Creating agent '{request.name}' in namespace '{request.namespace}', "
        f"workloadType={request.workloadType}, "
        f"createHttpRoute={request.createHttpRoute}"
    )

    # Feature flag: reject skill linking if feature is disabled
    if request.skills and not settings.rossoctl_feature_flag_skills:
        raise HTTPException(
            status_code=400,
            detail="Skill linking is disabled. Enable ROSSOCTL_FEATURE_FLAG_SKILLS to use this feature.",
        )

    # Compute external skill data when feature is enabled
    local_skills: Optional[List[str]] = None
    ext_init_containers: List[Dict[str, Any]] = []
    ext_volumes: List[Dict[str, Any]] = []
    ext_volume_mounts: List[Dict[str, Any]] = []
    ext_skill_paths: List[str] = []

    if request.skills and settings.rossoctl_feature_flag_external_skills:
        _ensure_fetcher_scripts_cm(kube, request.namespace)
        ext_init_containers, ext_volumes, ext_volume_mounts, ext_skill_paths = (
            _get_external_skill_data(kube, request.namespace, request.skills)
        )
        local_skills = [
            s for s in request.skills if s and not _is_skill_external(kube, request.namespace, s)
        ]

    context_volumes, context_mounts, resolved_contexts = await _resolve_context_mounts(
        request.namespace, request.contexts, request.workloadType
    )
    ext_volumes.extend(context_volumes)
    ext_volume_mounts.extend(context_mounts)

    request = apply_agent_import_defaults(request, kube)

    # Persistent resources created during this call, tracked so we can roll them
    # back if a later creation step fails (avoids leaking a workload, Service,
    # AgentRuntime, or route). Only used by the image-deployment path below.
    created: List[Tuple[str, str]] = []
    try:
        if request.deploymentMethod == "image":
            # Deploy from existing container image
            if not request.containerImage:
                raise HTTPException(
                    status_code=400,
                    detail="containerImage is required for image deployment",
                )

            # Ensure a dedicated ServiceAccount exists so the webhook's
            # SPIFFE identity uses the workload name, not the ReplicaSet hash.
            kube.ensure_service_account(namespace=request.namespace, name=request.name)

            # Ensure AuthBridge ConfigMaps exist in the target namespace
            if request.authBridgeEnabled:
                _ensure_authbridge_configmaps(
                    kube=kube,
                    namespace=request.namespace,
                    spire_enabled=request.spireEnabled,
                )
                if request.outboundRoutes:
                    _ensure_authproxy_routes(
                        kube=kube,
                        namespace=request.namespace,
                        routes=request.outboundRoutes,
                    )
                if request.defaultOutboundPolicy:
                    extra_config = {
                        "DEFAULT_OUTBOUND_POLICY": request.defaultOutboundPolicy,
                    }
                    kube.upsert_configmap(
                        namespace=request.namespace,
                        name="authbridge-config",
                        data=extra_config,
                    )

            # On OpenShift, ensure the AuthBridge SCC RoleBinding exists
            if request.authBridgeEnabled:
                _ensure_authbridge_scc_rolebinding(kube=kube, namespace=request.namespace)

            # Create card-unsigned ConfigMap so the webhook injects
            # the sign-agentcard init container at Deployment admission.
            if request.spireEnabled:
                service_port = (
                    request.servicePorts[0].port
                    if request.servicePorts
                    else DEFAULT_IN_CLUSTER_PORT
                )
                _ensure_card_unsigned_configmap(
                    kube=kube,
                    name=request.name,
                    namespace=request.namespace,
                    service_port=service_port,
                    description=f"Agent '{request.name}' deployed from UI.",
                    skill_names=request.skills,
                )

            # Create workload based on workloadType
            if request.workloadType == WORKLOAD_TYPE_DEPLOYMENT:
                workload_manifest = _build_deployment_manifest(
                    request=request,
                    image=request.containerImage,
                    local_skills=local_skills,
                    ext_init_containers=ext_init_containers,
                    ext_volumes=ext_volumes,
                    ext_volume_mounts=ext_volume_mounts,
                    ext_skill_paths=ext_skill_paths,
                )
                _record_contexts(workload_manifest, resolved_contexts)
                kube.create_deployment(
                    namespace=request.namespace,
                    body=workload_manifest,
                )
                created.append(("Deployment", request.name))
                logger.info(
                    f"Created Deployment '{request.name}' in namespace '{request.namespace}'"
                )
            elif request.workloadType == WORKLOAD_TYPE_STATEFULSET:
                workload_manifest = _build_statefulset_manifest(
                    request=request,
                    image=request.containerImage,
                    local_skills=local_skills,
                    ext_init_containers=ext_init_containers,
                    ext_volumes=ext_volumes,
                    ext_volume_mounts=ext_volume_mounts,
                    ext_skill_paths=ext_skill_paths,
                )
                _record_contexts(workload_manifest, resolved_contexts)
                kube.create_statefulset(
                    namespace=request.namespace,
                    body=workload_manifest,
                )
                created.append(("StatefulSet", request.name))
                logger.info(
                    f"Created StatefulSet '{request.name}' in namespace '{request.namespace}'"
                )
            elif request.workloadType == WORKLOAD_TYPE_JOB:
                workload_manifest = _build_job_manifest(
                    request=request,
                    image=request.containerImage,
                    local_skills=local_skills,
                    ext_init_containers=ext_init_containers,
                    ext_volumes=ext_volumes,
                    ext_volume_mounts=ext_volume_mounts,
                    ext_skill_paths=ext_skill_paths,
                )
                _record_contexts(workload_manifest, resolved_contexts)
                kube.create_job(
                    namespace=request.namespace,
                    body=workload_manifest,
                )
                created.append(("Job", request.name))
                logger.info(f"Created Job '{request.name}' in namespace '{request.namespace}'")
            elif request.workloadType == WORKLOAD_TYPE_SANDBOX:
                sandbox_manifest = _build_sandbox_manifest(
                    request=request,
                    image=request.containerImage,
                    local_skills=local_skills,
                    ext_init_containers=ext_init_containers,
                    ext_volumes=ext_volumes,
                    ext_volume_mounts=ext_volume_mounts,
                    ext_skill_paths=ext_skill_paths,
                )
                _record_contexts(sandbox_manifest, resolved_contexts)
                kube.create_sandbox(
                    namespace=request.namespace,
                    body=sandbox_manifest,
                )
                created.append(("Sandbox", request.name))
                logger.info(f"Created Sandbox '{request.name}' in namespace '{request.namespace}'")

            # Create Service (not needed for Jobs).
            if request.workloadType != WORKLOAD_TYPE_JOB:
                service_manifest = _build_service_manifest(request)
                _create_or_replace_service(
                    kube,
                    request.namespace,
                    request.name,
                    service_manifest,
                    request.workloadType,
                )
                created.append(("Service", request.name))

            # Create AgentRuntime CR so the per-agent AuthBridge config (mtls /
            # authBridgeMode / tlsBridgeMode) is applied. Sandbox is included
            # (targetRef -> agents.x-k8s.io Sandbox); only Job is excluded —
            # a run-to-completion Job doesn't fit the attach/restart model.
            if _agentruntime_supported_workload(request.workloadType):
                _ensure_agentruntime(
                    kube=kube,
                    name=request.name,
                    namespace=request.namespace,
                    workload_type=request.workloadType,
                    auth_bridge_mode=request.authBridgeMode,
                    mtls_mode=request.mtlsMode,
                    tls_bridge_enabled=request.tlsBridgeEnabled,
                )
                created.append(("AgentRuntime", request.name))

            message = f"Agent '{request.name}' deployed as {request.workloadType} successfully."

            # Create HTTPRoute/Route if requested (not applicable for Jobs or Sandboxes)
            if request.createHttpRoute and request.workloadType not in (
                WORKLOAD_TYPE_JOB,
                WORKLOAD_TYPE_SANDBOX,
            ):
                service_port = select_route_port(
                    request.servicePorts,
                    default_port=DEFAULT_OFF_CLUSTER_PORT,
                )
                create_route_for_agent_or_tool(
                    kube=kube,
                    name=request.name,
                    namespace=request.namespace,
                    service_name=request.name,
                    service_port=service_port,
                )
                # create_route_for_agent_or_tool makes an HTTPRoute or an OpenShift
                # Route depending on platform; track both so rollback deletes the
                # right one (the other 404s and is swallowed).
                created.append(("HTTPRoute", request.name))
                created.append(("Route", request.name))
                message += " HTTPRoute/Route created for external access."

        else:
            # Build from source using Shipwright Build + BuildRun
            if not request.gitUrl:
                raise HTTPException(
                    status_code=400,
                    detail="gitUrl is required for source deployment",
                )

            # Clean up any existing Build/BuildRuns to prevent 409 on re-import
            cleanup_existing_build(kube, namespace=request.namespace, build_name=request.name)

            # Step 1: Create Shipwright Build CR
            clone_secret = resolve_clone_secret(kube.core_api, request.namespace)
            build_manifest = _build_agent_shipwright_build_manifest(
                request, clone_secret_name=clone_secret
            )
            kube.create_custom_resource(
                group=SHIPWRIGHT_CRD_GROUP,
                version=SHIPWRIGHT_CRD_VERSION,
                namespace=request.namespace,
                plural=SHIPWRIGHT_BUILDS_PLURAL,
                body=build_manifest,
            )
            logger.info(
                f"Created Shipwright Build '{request.name}' in namespace '{request.namespace}'"
            )

            # Step 2: Create BuildRun CR to trigger the build
            # Get labels from the Build manifest to propagate to BuildRun
            build_labels = build_manifest.get("metadata", {}).get("labels", {})
            buildrun_manifest = _build_agent_shipwright_buildrun_manifest(
                build_name=request.name,
                namespace=request.namespace,
                labels=build_labels,
            )
            created_buildrun = kube.create_custom_resource(
                group=SHIPWRIGHT_CRD_GROUP,
                version=SHIPWRIGHT_CRD_VERSION,
                namespace=request.namespace,
                plural=SHIPWRIGHT_BUILDRUNS_PLURAL,
                body=buildrun_manifest,
            )
            buildrun_name = created_buildrun.get("metadata", {}).get("name", "")
            logger.info(
                f"Created Shipwright BuildRun '{buildrun_name}' in namespace '{request.namespace}'"
            )

            message = (
                f"Shipwright build started for agent '{request.name}'. "
                f"BuildRun: '{buildrun_name}'. "
                f"Poll the build status and create the Agent after the build completes."
            )

            # Note: For Shipwright builds, HTTPRoute is NOT created here.
            # It will be created when the Agent is finalized after build completion.
            if request.createHttpRoute:
                message += " HTTPRoute will be created after the build completes."

        return CreateAgentResponse(
            success=True,
            name=request.name,
            namespace=request.namespace,
            message=message,
        )

    except ApiException as e:
        # Roll back only what THIS call created (tracked in `created`); if the very
        # first create 409'd, `created` is empty and rollback is a no-op, so a
        # pre-existing agent is never deleted.
        rollback_workload_resources(kube, request.namespace, created)
        if e.status == 409:
            raise HTTPException(
                status_code=409,
                detail=f"Agent '{request.name}' already exists in namespace '{request.namespace}'",
            )
        if e.status == 404:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Required CRD or resource not found for workload type "
                    f"'{request.workloadType}'. Ensure the necessary controllers "
                    f"are installed (e.g. Shipwright for source builds, "
                    f"agent-sandbox controller for sandbox workloads)."
                ),
            )
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=e.status, detail=str(e.reason))
    except HTTPException:
        # Validation errors (400) raised above — nothing created yet, re-raise as-is.
        raise
    except Exception as e:
        # Non-API failure (e.g. platform detection in route creation) after some
        # resources were already created — roll back before surfacing a 500.
        rollback_workload_resources(kube, request.namespace, created)
        logger.error(
            "Unexpected error creating agent '%s': %s",
            sanitize_log(request.name),
            sanitize_log(str(e)),
        )
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {e}")
