# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Kubernetes manifest builders for agent workloads.

Builds the env vars, labels/annotations, resource blocks and the four supported
workload manifests (Deployment, StatefulSet, Job, Sandbox) plus the Service and
AgentRuntime CR that accompany them.

All four workload builders go through the same pair of helpers --
``_build_env_vars`` (defined here) and ``_get_linked_skill_mounts`` (imported
from ``agents_skills``) -- which is why the four builders live together here.

Split out of ``agents.py``; re-exported there for backwards compatibility.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from kubernetes.client import ApiException

from app.core.constants import (
    AGENT_ENDPOINT,
    AGENT_SANDBOX_CRD_GROUP,
    AGENT_SANDBOX_CRD_VERSION,
    AGENT_SKILLS_ANNOTATION,
    AGENTRUNTIMES_PLURAL,
    APP_KUBERNETES_IO_COMPONENT,
    APP_KUBERNETES_IO_MANAGED_BY,
    APP_KUBERNETES_IO_NAME,
    CRD_GROUP,
    CRD_VERSION,
    DEFAULT_ENV_VARS,
    DEFAULT_IMAGE_POLICY,
    DEFAULT_IN_CLUSTER_PORT,
    DEFAULT_OFF_CLUSTER_PORT,
    DEFAULT_RESOURCE_LIMITS,
    DEFAULT_RESOURCE_REQUESTS,
    PROTOCOL_LABEL_PREFIX,
    RESOURCE_TYPE_AGENT,
    ROSSOCTL_DESCRIPTION_ANNOTATION,
    ROSSOCTL_FRAMEWORK_LABEL,
    ROSSOCTL_INBOUND_PORTS_EXCLUDE,
    ROSSOCTL_INJECT_LABEL,
    ROSSOCTL_OUTBOUND_PORTS_EXCLUDE,
    ROSSOCTL_SPIRE_ENABLED_VALUE,
    ROSSOCTL_SPIRE_LABEL,
    ROSSOCTL_TYPE_LABEL,
    ROSSOCTL_UI_CREATOR_LABEL,
    ROSSOCTL_WORKLOAD_TYPE_LABEL,
    WORKLOAD_TYPE_DEPLOYMENT,
    WORKLOAD_TYPE_JOB,
    WORKLOAD_TYPE_SANDBOX,
    WORKLOAD_TYPE_STATEFULSET,
)
from app.core.config import settings
from app.routers.agents_models import (
    ContextAttachment,
    CreateAgentRequest,
)
from app.routers.agents_skills import _get_linked_skill_mounts
from app.services.kubernetes import KubernetesService

CONTEXTS_ANNOTATION = "rossoctl.io/contexts"


def _record_contexts(manifest: Dict[str, Any], contexts: List[Dict[str, Any]]) -> None:
    """Persist declared attachments for GET; this snapshot is not live reconciliation."""
    if contexts:
        manifest.setdefault("metadata", {}).setdefault("annotations", {})[CONTEXTS_ANNOTATION] = (
            json.dumps(contexts, separators=(",", ":"))
        )


from app.utils.routes import get_agent_url

logger = logging.getLogger(__name__)


def _build_env_vars(
    request: "CreateAgentRequest",
    local_skills: Optional[List[str]] = None,
    ext_skill_paths: Optional[List[str]] = None,
) -> List[dict]:
    """
    Build environment variables list with support for valueFrom references.

    Args:
        request: The agent creation request containing envVars.
        local_skills: Optional override list of local skill names.
        ext_skill_paths: Optional list of external skill mount paths.

    Returns:
        List of environment variable dictionaries.
    """
    env_vars = list(DEFAULT_ENV_VARS)
    service_port = (
        request.servicePorts[0].port if request.servicePorts else DEFAULT_OFF_CLUSTER_PORT
    )
    env_vars.append(
        {
            "name": AGENT_ENDPOINT,
            "value": get_agent_url(request.name, request.namespace, service_port),
        }
    )

    _, _, local_folders = _get_linked_skill_mounts(request, skills_override=local_skills)
    all_paths = ([local_folders] if local_folders else []) + (ext_skill_paths or [])
    if all_paths:
        env_vars.append({"name": "SKILL_FOLDERS", "value": ",".join(all_paths)})

    if request.envVars:
        for ev in request.envVars:
            if ev.value is not None:
                # Direct value
                env_vars.append({"name": ev.name, "value": ev.value})
            elif ev.valueFrom is not None:
                # Reference to Secret or ConfigMap
                env_entry: Dict[str, Any] = {"name": ev.name, "valueFrom": {}}

                if ev.valueFrom.secretKeyRef:
                    env_entry["valueFrom"]["secretKeyRef"] = {
                        "name": ev.valueFrom.secretKeyRef.name,
                        "key": ev.valueFrom.secretKeyRef.key,
                    }
                elif ev.valueFrom.configMapKeyRef:
                    env_entry["valueFrom"]["configMapKeyRef"] = {
                        "name": ev.valueFrom.configMapKeyRef.name,
                        "key": ev.valueFrom.configMapKeyRef.key,
                    }

                env_vars.append(env_entry)

    # Deduplicate environment variables, keeping the last occurrence.
    # Precedence (last wins): DEFAULT_ENV_VARS < AGENT_ENDPOINT/SKILL_FOLDERS < user envVars.
    # User overrides of AGENT_ENDPOINT or SKILL_FOLDERS are intentional (advanced use).
    seen = {}
    for env in env_vars:
        seen[env["name"]] = env
    return list(seen.values())


def _build_common_labels(
    request: "CreateAgentRequest",
    workload_type: str = WORKLOAD_TYPE_DEPLOYMENT,
) -> Dict[str, str]:
    """
    Build common labels for agent workloads.

    Common labels for agent workloads. The rossoctl.io/type label is applied
    by the rossoctl-operator via AgentRuntime reconciliation, not here.

    Args:
        request: The agent creation request.
        workload_type: The type of workload (deployment, statefulset, job).

    Returns:
        Dictionary of labels.
    """
    labels = {
        APP_KUBERNETES_IO_NAME: request.name,
        ROSSOCTL_FRAMEWORK_LABEL: request.framework,
        ROSSOCTL_WORKLOAD_TYPE_LABEL: workload_type,
        APP_KUBERNETES_IO_MANAGED_BY: ROSSOCTL_UI_CREATOR_LABEL,
        APP_KUBERNETES_IO_COMPONENT: RESOURCE_TYPE_AGENT,
        # AuthBridge sidecar injection control
        ROSSOCTL_INJECT_LABEL: "enabled" if request.authBridgeEnabled else "disabled",
    }
    # Protocol label(s) using new prefix format
    if request.protocol:
        labels[f"{PROTOCOL_LABEL_PREFIX}{request.protocol}"] = ""
    # SPIRE identity label — the operator's webhook reads this to set
    # SPIRE_ENABLED=true on the combined sidecar's spiffe-helper.
    if request.spireEnabled:
        labels[ROSSOCTL_SPIRE_LABEL] = ROSSOCTL_SPIRE_ENABLED_VALUE
    return labels


def _build_common_annotations(request: "CreateAgentRequest") -> Dict[str, str]:
    """Build pod template annotations for port exclusions and other webhook directives."""
    annotations: Dict[str, str] = {}
    if request.outboundPortsExclude:
        annotations[ROSSOCTL_OUTBOUND_PORTS_EXCLUDE] = request.outboundPortsExclude
    if request.inboundPortsExclude:
        annotations[ROSSOCTL_INBOUND_PORTS_EXCLUDE] = request.inboundPortsExclude
    return annotations


def build_container_resources(
    limits: Optional[Dict[str, str]] = None,
    requests: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, str]]:
    """Build a container "resources" block from optional per-workload overrides.

    None means "not specified" and selects the platform default. An empty dict is
    honored as-is, because {} is how Kubernetes spells "no limits" -- it yields an
    unbounded container rather than one capped at DEFAULT_RESOURCE_LIMITS. Testing
    truthiness instead (`limits or DEFAULT_RESOURCE_LIMITS`) would collapse those
    two cases and silently cap a workload the caller asked to leave uncapped.
    """
    return {
        "limits": DEFAULT_RESOURCE_LIMITS if limits is None else limits,
        "requests": DEFAULT_RESOURCE_REQUESTS if requests is None else requests,
    }


def _build_selector_labels(request: "CreateAgentRequest") -> Dict[str, str]:
    """
    Build selector labels for matching pods to workloads and services.

    Args:
        request: The agent creation request.

    Returns:
        Dictionary of selector labels.
    """
    return {
        APP_KUBERNETES_IO_NAME: request.name,
    }


def _agentruntime_supported_workload(workload_type: str) -> bool:
    """Whether a workload type gets an AgentRuntime CR (per-agent AuthBridge
    config). Sandbox, deployment, and statefulset are supported; Job is not —
    a run-to-completion Job doesn't fit the attach / config-rollout model.
    Single source of truth for the two _ensure_agentruntime call sites
    (create_agent and finalize_shipwright_build)."""
    return workload_type not in (WORKLOAD_TYPE_JOB,)


def _build_agentruntime_manifest(
    name: str,
    namespace: str,
    workload_type: str,
    agent_type: str = RESOURCE_TYPE_AGENT,
    auth_bridge_mode: Optional[str] = None,
    mtls_mode: Optional[str] = None,
    tls_bridge_enabled: bool = False,
) -> dict:
    """Build an AgentRuntime CR manifest for the given workload."""
    kind_map = {
        WORKLOAD_TYPE_DEPLOYMENT: "Deployment",
        WORKLOAD_TYPE_STATEFULSET: "StatefulSet",
        WORKLOAD_TYPE_SANDBOX: "Sandbox",
    }
    # Sandbox is an agents.x-k8s.io CR, not apps/v1 — emit the right targetRef
    # apiVersion per kind so the operator's resolveTargetRef finds the workload
    # (a wrong apps/v1 ref for a Sandbox would dangle and never reconcile).
    apiversion_map = {
        WORKLOAD_TYPE_SANDBOX: f"{AGENT_SANDBOX_CRD_GROUP}/{AGENT_SANDBOX_CRD_VERSION}",
    }
    spec: dict = {
        "type": agent_type,
        "targetRef": {
            "apiVersion": apiversion_map.get(workload_type, "apps/v1"),
            "kind": kind_map.get(workload_type, "Deployment"),
            "name": name,
        },
    }
    if auth_bridge_mode:
        spec["authBridgeMode"] = auth_bridge_mode
    if mtls_mode:
        spec["mtlsMode"] = mtls_mode
    # Only set when enabled; unset → operator default "disabled" (also keeps the
    # CRD field off envoy-sidecar agents so the validating webhook doesn't reject).
    if tls_bridge_enabled:
        spec["tlsBridgeMode"] = "enabled"
    return {
        "apiVersion": f"{CRD_GROUP}/{CRD_VERSION}",
        "kind": "AgentRuntime",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                ROSSOCTL_TYPE_LABEL: agent_type,
                APP_KUBERNETES_IO_MANAGED_BY: ROSSOCTL_UI_CREATOR_LABEL,
            },
        },
        "spec": spec,
    }


def _ensure_agentruntime(
    kube: "KubernetesService",
    name: str,
    namespace: str,
    workload_type: str,
    agent_type: str = RESOURCE_TYPE_AGENT,
    auth_bridge_mode: Optional[str] = None,
    mtls_mode: Optional[str] = None,
    tls_bridge_enabled: bool = False,
) -> None:
    """Create an AgentRuntime CR for the workload. Skip if it already exists."""
    manifest = _build_agentruntime_manifest(
        name,
        namespace,
        workload_type,
        agent_type,
        auth_bridge_mode,
        mtls_mode,
        tls_bridge_enabled,
    )
    try:
        kube.create_custom_resource(
            group=CRD_GROUP,
            version=CRD_VERSION,
            namespace=namespace,
            plural=AGENTRUNTIMES_PLURAL,
            body=manifest,
        )
        logger.info("Created AgentRuntime '%s' in namespace '%s'", name, namespace)
    except ApiException as e:
        if e.status == 409:
            logger.info("AgentRuntime '%s' already exists in namespace '%s'", name, namespace)
        else:
            logger.warning("Failed to create AgentRuntime '%s': %s", name, e.reason)


def _build_deployment_manifest(
    request: "CreateAgentRequest",
    image: str,
    shipwright_build_name: Optional[str] = None,
    local_skills: Optional[List[str]] = None,
    ext_init_containers: Optional[List[Dict[str, Any]]] = None,
    ext_volumes: Optional[List[Dict[str, Any]]] = None,
    ext_volume_mounts: Optional[List[Dict[str, Any]]] = None,
    ext_skill_paths: Optional[List[str]] = None,
) -> dict:
    """
    Build a Kubernetes Deployment manifest for an agent.

    Args:
        request: The agent creation request.
        image: The container image URL.
        shipwright_build_name: Optional name of the Shipwright Build that created
            this agent (for annotation tracking).

    Returns:
        Deployment manifest dictionary.
    """
    ext_init_containers = ext_init_containers or []
    ext_volumes = ext_volumes or []
    ext_volume_mounts = ext_volume_mounts or []
    ext_skill_paths = ext_skill_paths or []
    env_vars = _build_env_vars(request, local_skills=local_skills, ext_skill_paths=ext_skill_paths)
    skill_volumes, skill_volume_mounts, _ = _get_linked_skill_mounts(
        request, skills_override=local_skills
    )
    labels = _build_common_labels(request, WORKLOAD_TYPE_DEPLOYMENT)
    selector_labels = _build_selector_labels(request)

    # Build annotations
    annotations: Dict[str, str] = {
        ROSSOCTL_DESCRIPTION_ANNOTATION: f"Agent '{request.name}' deployed from UI.",
    }
    if request.skills:
        annotations[AGENT_SKILLS_ANNOTATION] = json.dumps(request.skills)
    if shipwright_build_name:
        annotations["rossoctl.io/shipwright-build"] = shipwright_build_name

    # Build container ports
    container_port = DEFAULT_IN_CLUSTER_PORT
    if request.servicePorts and len(request.servicePorts) > 0:
        container_port = request.servicePorts[0].targetPort

    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": request.name,
            "namespace": request.namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "replicas": 1,
            "selector": {
                "matchLabels": selector_labels,
            },
            "template": {
                "metadata": {
                    "labels": {
                        **labels,
                    },
                    "annotations": _build_common_annotations(request),
                },
                "spec": {
                    "serviceAccountName": request.name,
                    "containers": [
                        {
                            "name": "agent",
                            "image": image,
                            "imagePullPolicy": DEFAULT_IMAGE_POLICY,
                            "resources": build_container_resources(
                                request.k8sResourceLimits, request.k8sResourceRequests
                            ),
                            "env": env_vars,
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": container_port,
                                    "protocol": "TCP",
                                },
                            ],
                            "volumeMounts": [
                                {"name": "cache", "mountPath": "/app/.cache"},
                                {"name": "marvin", "mountPath": "/.marvin"},
                                {"name": "shared-data", "mountPath": "/shared"},
                                *skill_volume_mounts,
                                *ext_volume_mounts,
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "cache", "emptyDir": {}},
                        {"name": "marvin", "emptyDir": {}},
                        {"name": "shared-data", "emptyDir": {}},
                        *skill_volumes,
                        *ext_volumes,
                    ],
                },
            },
        },
    }

    # Add init containers for external skills
    if ext_init_containers:
        manifest["spec"]["template"]["spec"]["initContainers"] = ext_init_containers

    # Add image pull secrets if specified
    if request.imagePullSecret:
        manifest["spec"]["template"]["spec"]["imagePullSecrets"] = [
            {"name": request.imagePullSecret}
        ]

    return manifest


def _create_or_replace_service(
    kube: "KubernetesService",
    namespace: str,
    name: str,
    service_manifest: dict,
    workload_type: str,
) -> None:
    """Create the Service for an agent / tool.

    Returns silently for ``WORKLOAD_TYPE_JOB`` since Jobs don't need a Service.
    Sandbox agents get a backend-managed ClusterIP Service for port translation
    (8080→8000); the agent-sandbox controller's own Service is suppressed via
    ``spec.service: false`` on the Sandbox CR (v0.4.6+).
    """
    if workload_type == WORKLOAD_TYPE_JOB:
        return
    # Strip CR/LF before logging — name and namespace come from the FastAPI
    # request body. Kubernetes will reject non-DNS-1123 names so this is
    # belt-and-suspenders, but the explicit sanitization satisfies CodeQL's
    # py/log-injection taint analysis on the user-input → log-sink flow.
    safe_name = name.replace("\n", "").replace("\r", "")
    safe_namespace = namespace.replace("\n", "").replace("\r", "")
    kube.create_service(namespace=namespace, body=service_manifest)
    logger.info("Created Service '%s' in namespace '%s'", safe_name, safe_namespace)


def _build_service_manifest(request: "CreateAgentRequest") -> dict:
    """
    Build a Kubernetes Service manifest for an agent.

    Args:
        request: The agent creation request.

    Returns:
        Service manifest dictionary.
    """
    labels = _build_common_labels(request, request.workloadType)
    selector_labels = _build_selector_labels(request)

    # Build service ports
    if request.servicePorts:
        service_ports = [
            {
                "name": sp.name,
                "port": sp.port,
                "targetPort": sp.targetPort,
                "protocol": sp.protocol,
            }
            for sp in request.servicePorts
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
            "name": request.name,
            "namespace": request.namespace,
            "labels": labels,
        },
        "spec": {
            "type": "ClusterIP",
            "selector": selector_labels,
            "ports": service_ports,
        },
    }


def _build_statefulset_manifest(
    request: "CreateAgentRequest",
    image: str,
    shipwright_build_name: Optional[str] = None,
    local_skills: Optional[List[str]] = None,
    ext_init_containers: Optional[List[Dict[str, Any]]] = None,
    ext_volumes: Optional[List[Dict[str, Any]]] = None,
    ext_volume_mounts: Optional[List[Dict[str, Any]]] = None,
    ext_skill_paths: Optional[List[str]] = None,
) -> dict:
    """
    Build a Kubernetes StatefulSet manifest for an agent.

    StatefulSets are useful for agents that require:
    - Stable, unique network identifiers
    - Stable, persistent storage
    - Ordered, graceful deployment and scaling
    - Ordered, automated rolling updates

    Args:
        request: The agent creation request.
        image: The container image URL.
        shipwright_build_name: Optional name of the Shipwright Build.

    Returns:
        StatefulSet manifest dictionary.
    """
    ext_init_containers = ext_init_containers or []
    ext_volumes = ext_volumes or []
    ext_volume_mounts = ext_volume_mounts or []
    ext_skill_paths = ext_skill_paths or []
    env_vars = _build_env_vars(request, local_skills=local_skills, ext_skill_paths=ext_skill_paths)
    skill_volumes, skill_volume_mounts, _ = _get_linked_skill_mounts(
        request, skills_override=local_skills
    )
    labels = _build_common_labels(request, WORKLOAD_TYPE_STATEFULSET)
    selector_labels = _build_selector_labels(request)

    # Build annotations
    annotations: Dict[str, str] = {
        ROSSOCTL_DESCRIPTION_ANNOTATION: f"Agent '{request.name}' deployed as StatefulSet from UI.",
    }
    if request.skills:
        annotations[AGENT_SKILLS_ANNOTATION] = json.dumps(request.skills)
    if shipwright_build_name:
        annotations["rossoctl.io/shipwright-build"] = shipwright_build_name

    # Build container ports
    container_port = DEFAULT_IN_CLUSTER_PORT
    if request.servicePorts and len(request.servicePorts) > 0:
        container_port = request.servicePorts[0].targetPort

    manifest = {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {
            "name": request.name,
            "namespace": request.namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "serviceName": request.name,  # StatefulSet requires a headless service name
            "replicas": 1,
            "selector": {
                "matchLabels": selector_labels,
            },
            "template": {
                "metadata": {
                    "labels": {
                        **labels,
                    },
                    "annotations": _build_common_annotations(request),
                },
                "spec": {
                    "serviceAccountName": request.name,
                    "containers": [
                        {
                            "name": "agent",
                            "image": image,
                            "imagePullPolicy": DEFAULT_IMAGE_POLICY,
                            "resources": build_container_resources(
                                request.k8sResourceLimits, request.k8sResourceRequests
                            ),
                            "env": env_vars,
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": container_port,
                                    "protocol": "TCP",
                                },
                            ],
                            "volumeMounts": [
                                {"name": "cache", "mountPath": "/app/.cache"},
                                {"name": "marvin", "mountPath": "/.marvin"},
                                {"name": "shared-data", "mountPath": "/shared"},
                                *skill_volume_mounts,
                                *ext_volume_mounts,
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "cache", "emptyDir": {}},
                        {"name": "marvin", "emptyDir": {}},
                        *skill_volumes,
                        *ext_volumes,
                    ]
                    + (
                        []
                        if request.persistentStorage and request.persistentStorage.enabled
                        else [{"name": "shared-data", "emptyDir": {}}]
                    ),
                },
            },
        },
    }

    # Add init containers for external skills
    if ext_init_containers:
        manifest["spec"]["template"]["spec"]["initContainers"] = ext_init_containers

    # When persistent storage is requested, declare a volumeClaimTemplate so the
    # StatefulSet provisions a PVC bound to the pod's stable identity; the
    # shared-data volume above is omitted from `volumes` in that case because
    # the template name (shared-data) becomes the volume.
    if request.persistentStorage and request.persistentStorage.enabled:
        manifest["spec"]["volumeClaimTemplates"] = [
            {
                "metadata": {
                    "name": "shared-data",
                    "labels": {APP_KUBERNETES_IO_NAME: request.name},
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": request.persistentStorage.size}},
                },
            }
        ]

    # Add image pull secrets if specified
    if request.imagePullSecret:
        manifest["spec"]["template"]["spec"]["imagePullSecrets"] = [
            {"name": request.imagePullSecret}
        ]

    return manifest


def _build_job_manifest(
    request: "CreateAgentRequest",
    image: str,
    shipwright_build_name: Optional[str] = None,
    local_skills: Optional[List[str]] = None,
    ext_init_containers: Optional[List[Dict[str, Any]]] = None,
    ext_volumes: Optional[List[Dict[str, Any]]] = None,
    ext_volume_mounts: Optional[List[Dict[str, Any]]] = None,
    ext_skill_paths: Optional[List[str]] = None,
) -> dict:
    """
    Build a Kubernetes Job manifest for an agent.

    Jobs are useful for agents that:
    - Run to completion (batch processing)
    - Should not be restarted automatically
    - Perform one-time tasks or scheduled workloads

    Args:
        request: The agent creation request.
        image: The container image URL.
        shipwright_build_name: Optional name of the Shipwright Build.

    Returns:
        Job manifest dictionary.
    """
    ext_init_containers = ext_init_containers or []
    ext_volumes = ext_volumes or []
    ext_volume_mounts = ext_volume_mounts or []
    ext_skill_paths = ext_skill_paths or []
    env_vars = _build_env_vars(request, local_skills=local_skills, ext_skill_paths=ext_skill_paths)
    skill_volumes, skill_volume_mounts, _ = _get_linked_skill_mounts(
        request, skills_override=local_skills
    )
    labels = _build_common_labels(request, WORKLOAD_TYPE_JOB)

    # Build annotations
    annotations: Dict[str, str] = {
        ROSSOCTL_DESCRIPTION_ANNOTATION: f"Agent '{request.name}' deployed as Job from UI.",
    }
    if request.skills:
        annotations[AGENT_SKILLS_ANNOTATION] = json.dumps(request.skills)
    if shipwright_build_name:
        annotations["rossoctl.io/shipwright-build"] = shipwright_build_name

    # Build container ports
    container_port = DEFAULT_IN_CLUSTER_PORT
    if request.servicePorts and len(request.servicePorts) > 0:
        container_port = request.servicePorts[0].targetPort

    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": request.name,
            "namespace": request.namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "backoffLimit": 3,  # Number of retries before considering the job failed
            "template": {
                "metadata": {
                    "labels": {
                        **labels,
                    },
                    "annotations": _build_common_annotations(request),
                },
                "spec": {
                    "serviceAccountName": request.name,
                    "restartPolicy": "OnFailure",
                    "containers": [
                        {
                            "name": "agent",
                            "image": image,
                            "imagePullPolicy": DEFAULT_IMAGE_POLICY,
                            "resources": build_container_resources(
                                request.k8sResourceLimits, request.k8sResourceRequests
                            ),
                            "env": env_vars,
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": container_port,
                                    "protocol": "TCP",
                                },
                            ],
                            "volumeMounts": [
                                {"name": "cache", "mountPath": "/app/.cache"},
                                {"name": "marvin", "mountPath": "/.marvin"},
                                {"name": "shared-data", "mountPath": "/shared"},
                                *skill_volume_mounts,
                                *ext_volume_mounts,
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "cache", "emptyDir": {}},
                        {"name": "marvin", "emptyDir": {}},
                        {"name": "shared-data", "emptyDir": {}},
                        *skill_volumes,
                        *ext_volumes,
                    ],
                },
            },
        },
    }

    # Add init containers for external skills
    if ext_init_containers:
        manifest["spec"]["template"]["spec"]["initContainers"] = ext_init_containers

    # Add image pull secrets if specified
    if request.imagePullSecret:
        manifest["spec"]["template"]["spec"]["imagePullSecrets"] = [
            {"name": request.imagePullSecret}
        ]

    return manifest


def _build_sandbox_manifest(
    request: "CreateAgentRequest",
    image: str,
    shipwright_build_name: Optional[str] = None,
    local_skills: Optional[List[str]] = None,
    ext_init_containers: Optional[List[Dict[str, Any]]] = None,
    ext_volumes: Optional[List[Dict[str, Any]]] = None,
    ext_volume_mounts: Optional[List[Dict[str, Any]]] = None,
    ext_skill_paths: Optional[List[str]] = None,
) -> dict:
    """Build a Sandbox manifest (agents.x-k8s.io/v1alpha1) for direct creation.

    Includes skill volume mounts and persistent storage support.
    """
    ext_init_containers = ext_init_containers or []
    ext_volumes = ext_volumes or []
    ext_volume_mounts = ext_volume_mounts or []
    ext_skill_paths = ext_skill_paths or []
    env_vars = _build_env_vars(request, local_skills=local_skills, ext_skill_paths=ext_skill_paths)
    skill_volumes, skill_volume_mounts, _ = _get_linked_skill_mounts(
        request, skills_override=local_skills
    )
    labels = _build_common_labels(request, WORKLOAD_TYPE_SANDBOX)

    annotations: Dict[str, str] = {
        ROSSOCTL_DESCRIPTION_ANNOTATION: f"Agent '{request.name}' deployed from UI.",
    }
    if request.skills:
        annotations[AGENT_SKILLS_ANNOTATION] = json.dumps(request.skills)
    if shipwright_build_name:
        annotations["rossoctl.io/shipwright-build"] = shipwright_build_name

    container_port = DEFAULT_IN_CLUSTER_PORT
    if request.servicePorts and len(request.servicePorts) > 0:
        container_port = request.servicePorts[0].targetPort

    manifest = {
        "apiVersion": f"{AGENT_SANDBOX_CRD_GROUP}/{AGENT_SANDBOX_CRD_VERSION}",
        "kind": "Sandbox",
        "metadata": {
            "name": request.name,
            "namespace": request.namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "replicas": 1,
            "service": False,
            "podTemplate": {
                "metadata": {
                    "labels": {
                        **labels,
                    },
                    "annotations": _build_common_annotations(request),
                },
                "spec": {
                    "automountServiceAccountToken": False,
                    "serviceAccountName": request.name,
                    "containers": [
                        {
                            "name": "agent",
                            "image": image,
                            "imagePullPolicy": DEFAULT_IMAGE_POLICY,
                            "resources": build_container_resources(
                                request.k8sResourceLimits, request.k8sResourceRequests
                            ),
                            "env": env_vars,
                            "ports": [
                                {
                                    "name": "http",
                                    "containerPort": container_port,
                                    "protocol": "TCP",
                                },
                            ],
                            "volumeMounts": [
                                {"name": "cache", "mountPath": "/app/.cache"},
                                {"name": "marvin", "mountPath": "/.marvin"},
                                {"name": "shared-data", "mountPath": "/shared"},
                                *skill_volume_mounts,
                                *ext_volume_mounts,
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "cache", "emptyDir": {}},
                        {"name": "marvin", "emptyDir": {}},
                        *skill_volumes,
                        *ext_volumes,
                    ]
                    + (
                        []
                        if request.persistentStorage and request.persistentStorage.enabled
                        else [{"name": "shared-data", "emptyDir": {}}]
                    ),
                },
            },
        },
    }

    # Add init containers for external skills
    if ext_init_containers:
        manifest["spec"]["podTemplate"]["spec"]["initContainers"] = ext_init_containers

    if request.persistentStorage and request.persistentStorage.enabled:
        manifest["spec"]["volumeClaimTemplates"] = [
            {
                "metadata": {
                    "name": "shared-data",
                    "labels": {APP_KUBERNETES_IO_NAME: request.name},
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": request.persistentStorage.size}},
                },
            }
        ]

    if request.imagePullSecret:
        manifest["spec"]["podTemplate"]["spec"]["imagePullSecrets"] = [
            {"name": request.imagePullSecret}
        ]

    return manifest


async def _resolve_context_mounts(
    namespace: str,
    attachments: Optional[List[ContextAttachment]],
    workload_type: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Resolve named contexts into Kubernetes PVC volumes and mounts."""
    if not attachments:
        return [], [], []
    if workload_type not in {WORKLOAD_TYPE_STATEFULSET, WORKLOAD_TYPE_SANDBOX}:
        raise HTTPException(
            status_code=400,
            detail="context attachments require a statefulset or sandbox workload",
        )
    if not settings.context_service_url.strip():
        raise HTTPException(status_code=400, detail="Context Service integration is disabled")

    from app.routers.contexts import resolve_context  # pylint: disable=import-outside-toplevel

    volumes: List[Dict[str, Any]] = []
    mounts: List[Dict[str, Any]] = []
    resolved: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, attachment in enumerate(attachments):
        if not attachment.mountPath.startswith("/"):
            raise HTTPException(status_code=400, detail="context mountPath must be absolute")
        if attachment.mountPath in seen_paths:
            raise HTTPException(status_code=400, detail="context mountPath values must be unique")
        seen_paths.add(attachment.mountPath)
        resource = await resolve_context(namespace, attachment.name)
        resource_attachment = resource.get("attachment", {})
        if resource_attachment.get("kind") != "pvc":
            raise HTTPException(
                status_code=502, detail="Context Service returned a non-PVC attachment"
            )
        claim_name = resource_attachment.get("claimName")
        if not claim_name:
            raise HTTPException(status_code=502, detail="Context Service returned no PVC claim")
        context_type = resource.get("type")
        if not context_type:
            raise HTTPException(status_code=502, detail="Context Service returned no type")
        volume_name = f"context-{index}"
        volumes.append(
            {
                "name": volume_name,
                "persistentVolumeClaim": {
                    "claimName": claim_name,
                    "readOnly": attachment.readOnly,
                },
            }
        )
        mounts.append(
            {
                "name": volume_name,
                "mountPath": attachment.mountPath,
                "readOnly": attachment.readOnly,
            }
        )
        resolved.append(
            {
                "name": attachment.name,
                "type": context_type,
                "mountPath": attachment.mountPath,
                "readOnly": attachment.readOnly,
                "claimName": claim_name,
            }
        )
    return volumes, mounts, resolved
