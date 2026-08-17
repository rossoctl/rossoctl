# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Agent skill wiring and Shipwright build manifests.

Resolves linked skills into init-containers/volume mounts (including external
skill-registry fetches via the skill-fetcher image) and builds the Shipwright
Build/BuildRun manifests used when an agent is built from source.

Split out of ``agents.py``; re-exported there for backwards compatibility.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import kubernetes.client as k8s_client
from kubernetes.client import ApiException

from app.core.constants import (
    AGENT_SKILLS_MOUNT_ROOT,
    DEFAULT_IN_CLUSTER_PORT,
    DEFAULT_INTERNAL_REGISTRY,
    SKILL_DESCRIPTION_ANNOTATION,
    SKILL_DISPLAY_NAME_ANNOTATION,
    SKILL_FETCHER_IMAGE,
    SKILL_FETCHER_SCRIPTS_CM,
    SKILL_REGISTRY_SKILL_NAME_ANNOTATION,
    SKILL_REGISTRY_SKILL_VERSION_ANNOTATION,
    SKILL_REGISTRY_TYPE_LABEL,
    SKILL_REGISTRY_URL_ANNOTATION,
    SKILL_SOURCE_EXTERNAL,
    SKILL_SOURCE_LABEL,
    SKILL_TYPE_LABEL,
    SKILL_TYPE_VALUE,
)
from app.models.shipwright import (
    BuildOutputConfig,
    BuildSourceConfig,
    ResourceType,
)
from app.routers.agents_models import CreateAgentRequest
from app.services.kubernetes import KubernetesService
from app.services.shipwright import (
    build_shipwright_build_manifest,
    build_shipwright_buildrun_manifest,
)
from app.utils.naming import sanitize_k8s_name

logger = logging.getLogger(__name__)


def _load_agent_skill_summaries(
    kube: KubernetesService,
    namespace: str,
    skill_names: List[str],
) -> List[Dict[str, Any]]:
    """Load skill metadata from ConfigMaps referenced by an agent.

    The agent annotation stores user-facing skill names. For each skill, look up
    the matching skill ConfigMap by either display-name annotation or resource name.
    Missing skills are ignored so agent creation does not fail when a referenced
    skill is deleted later.
    """
    if not skill_names:
        return []

    try:
        cms = kube.core_api.list_namespaced_config_map(
            namespace=namespace,
            label_selector=f"{SKILL_TYPE_LABEL}={SKILL_TYPE_VALUE}",
        )
    except ApiException as exc:
        # Sanitize namespace to prevent log injection
        safe_namespace = namespace.replace("\n", "\\n").replace("\r", "\\r")
        logger.warning(
            "Failed to list skills for agent card generation: %s",
            exc,
            extra={"namespace": safe_namespace},
        )
        return []

    requested = {skill_name.strip() for skill_name in skill_names if skill_name.strip()}
    if not requested:
        return []

    summaries: List[Dict[str, Any]] = []
    for cm in cms.items:
        annotations = cm.metadata.annotations or {}
        display_name = annotations.get(SKILL_DISPLAY_NAME_ANNOTATION) or cm.metadata.name
        if display_name not in requested and cm.metadata.name not in requested:
            continue

        summaries.append(
            {
                "id": cm.metadata.name,
                "name": display_name,
                "description": annotations.get(SKILL_DESCRIPTION_ANNOTATION, ""),
                "examples": [],
            }
        )

    summaries.sort(key=lambda skill: skill["name"].lower())
    return summaries


def _ensure_card_unsigned_configmap(
    kube: KubernetesService,
    name: str,
    namespace: str,
    service_port: int = DEFAULT_IN_CLUSTER_PORT,
    description: Optional[str] = None,
    skill_names: Optional[List[str]] = None,
) -> None:
    """Create the <agent>-card-unsigned ConfigMap if it does not exist.

    The Rossoctl operator webhook checks for this ConfigMap when a
    Deployment is admitted.  If it exists, the webhook injects a
    ``sign-agentcard`` init container that signs the agent card with
    the workload's SPIRE SVID.  The ConfigMap must therefore be
    created **before** the Deployment.
    """
    agent_url = f"http://{name}.{namespace}.svc.cluster.local:{service_port}"
    skills = _load_agent_skill_summaries(kube, namespace, skill_names or [])
    agent_card = json.dumps(
        {
            "name": name,
            "description": description,
            "url": agent_url,
            "version": "1.0.0",
            "capabilities": {},
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["text/plain"],
            "skills": skills,
        },
        indent=2,
    )
    kube.ensure_configmap(
        namespace=namespace,
        name=f"{name}-card-unsigned",
        data={"agent.json": agent_card},
    )


def _build_agent_shipwright_build_manifest(
    request: CreateAgentRequest, clone_secret_name: Optional[str] = None
) -> dict:
    """
    Build a Shipwright Build CRD manifest for building an agent from source.

    This is a wrapper around the shared build_shipwright_build_manifest function
    that converts CreateAgentRequest to the shared function's parameters.
    """
    # Determine registry URL
    registry_url = request.registryUrl or DEFAULT_INTERNAL_REGISTRY

    # Build source config
    source_config = BuildSourceConfig(
        gitUrl=request.gitUrl,
        gitRevision=request.gitBranch,
        contextDir=request.gitPath or ".",
        gitSecretName=clone_secret_name,
    )

    # Build output config
    output_config = BuildOutputConfig(
        registry=registry_url,
        imageName=request.name,
        imageTag=request.imageTag,
        pushSecretName=request.registrySecret,
    )

    # Build resource configuration to store in annotation
    resource_config: Dict[str, Any] = {
        "protocol": request.protocol,
        "framework": request.framework,
        "createHttpRoute": request.createHttpRoute,
        "registrySecret": request.registrySecret,
        "workloadType": request.workloadType,  # Store workload type for finalization
        "authBridgeEnabled": request.authBridgeEnabled,
        "spireEnabled": request.spireEnabled,
        "authBridgeMode": request.authBridgeMode,
        "gitPath": request.gitPath,
    }
    if request.outboundRoutes:
        resource_config["outboundRoutes"] = [r.model_dump() for r in request.outboundRoutes]
    if request.outboundPortsExclude:
        resource_config["outboundPortsExclude"] = request.outboundPortsExclude
    if request.inboundPortsExclude:
        resource_config["inboundPortsExclude"] = request.inboundPortsExclude
    if request.defaultOutboundPolicy:
        resource_config["defaultOutboundPolicy"] = request.defaultOutboundPolicy
    if request.mtlsMode:
        resource_config["mtlsMode"] = request.mtlsMode
    if request.tlsBridgeEnabled:
        resource_config["tlsBridgeEnabled"] = True
    if request.persistentStorage:
        resource_config["persistentStorage"] = request.persistentStorage.model_dump()
    if request.k8sResourceLimits is not None:
        resource_config["k8sResourceLimits"] = request.k8sResourceLimits
    if request.k8sResourceRequests is not None:
        resource_config["k8sResourceRequests"] = request.k8sResourceRequests
    if request.contexts:
        resource_config["contexts"] = [attachment.model_dump() for attachment in request.contexts]
    # Add env vars if present
    if request.envVars:
        resource_config["envVars"] = [ev.model_dump(exclude_none=True) for ev in request.envVars]
    if request.mcpToolName:
        resource_config["mcpToolName"] = request.mcpToolName
    if request.llmPreset:
        resource_config["llmPreset"] = request.llmPreset
    if request.llmModel:
        resource_config["llmModel"] = request.llmModel
    if request.skills:
        resource_config["skills"] = request.skills
    # Add service ports if present
    if request.servicePorts:
        resource_config["servicePorts"] = [sp.model_dump() for sp in request.servicePorts]

    return build_shipwright_build_manifest(
        name=request.name,
        namespace=request.namespace,
        resource_type=ResourceType.AGENT,
        source_config=source_config,
        output_config=output_config,
        build_config=request.shipwrightConfig,
        resource_config=resource_config,
        protocol=request.protocol,
        framework=request.framework,
    )


def _build_agent_shipwright_buildrun_manifest(
    build_name: str, namespace: str, labels: Optional[Dict[str, str]] = None
) -> dict:
    """
    Build a Shipwright BuildRun CRD manifest to trigger an agent build.

    This is a wrapper around the shared build_shipwright_buildrun_manifest function.
    """
    return build_shipwright_buildrun_manifest(
        build_name=build_name,
        namespace=namespace,
        resource_type=ResourceType.AGENT,
        labels=labels,
    )


# -----------------------------------------------------------------------------
# Workload Manifest Builders (Phase 1 - Migration to Standard K8s Workloads)
# -----------------------------------------------------------------------------


def _get_linked_skill_mounts(
    request: "CreateAgentRequest",
    skills_override: Optional[List[str]] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """Build volume and mount definitions for linked skill ConfigMaps (local only)."""
    skills = skills_override if skills_override is not None else (request.skills or [])
    if not skills:
        return [], [], None

    volumes: List[Dict[str, Any]] = []
    volume_mounts: List[Dict[str, Any]] = []
    skill_paths: List[str] = []

    for index, skill_name in enumerate(skills):
        if not skill_name:
            continue
        cm_name = sanitize_k8s_name(skill_name)
        volume_name = f"skill-{index}"
        mount_path = f"{AGENT_SKILLS_MOUNT_ROOT}/{cm_name}"
        volumes.append(
            {
                "name": volume_name,
                "configMap": {
                    "name": cm_name,
                },
            }
        )
        volume_mounts.append(
            {
                "name": volume_name,
                "mountPath": mount_path,
                "readOnly": True,
            }
        )
        skill_paths.append(mount_path)

    if not skill_paths:
        return [], [], None

    return volumes, volume_mounts, ",".join(skill_paths)


def _is_skill_external(kube: "KubernetesService", namespace: str, skill_name: str) -> bool:
    """Return True if the named skill ConfigMap is an external registry reference."""
    try:
        cm = kube.core_api.read_namespaced_config_map(
            name=sanitize_k8s_name(skill_name), namespace=namespace
        )
        labels = cm.metadata.labels or {}
        return labels.get(SKILL_SOURCE_LABEL) == SKILL_SOURCE_EXTERNAL
    except ApiException:
        return False


_SKILLBERRY_SH = """\
#!/bin/sh
set -e

apk add -q --no-cache curl unzip 2>/dev/null || true

URL="${REGISTRY_URL}/skills/${SKILL_NAME}/export-anthropic"

echo "Fetching ${SKILL_NAME} from ${URL}"

RETRIES=3
DELAY=2
for i in $(seq 1 $RETRIES); do
    if curl -fsSL --max-filesize 52428800 -o /tmp/skill.zip "${URL}"; then
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "FATAL: fetch failed after ${RETRIES} attempts"
        exit 1
    fi
    echo "Attempt ${i} failed; retrying in ${DELAY}s..."
    sleep $DELAY
done

mkdir -p "${TARGET_DIR}" /tmp/skill-extract
unzip -q /tmp/skill.zip -d /tmp/skill-extract/
SKILL_DIR=$(ls /tmp/skill-extract/ | head -1)
cp -r "/tmp/skill-extract/${SKILL_DIR}/." "${TARGET_DIR}/"
echo "OK: ${SKILL_NAME} -> ${TARGET_DIR}"
"""

_GENERIC_SH = """\
#!/bin/sh
set -e

apk add -q --no-cache curl 2>/dev/null || true
echo "Fetching skill from ${REGISTRY_URL}"

RETRIES=3
DELAY=2
for i in $(seq 1 $RETRIES); do
    if curl -fsSL --max-filesize 52428800 -o /tmp/skill.tar.gz "${REGISTRY_URL}"; then
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "FATAL: fetch failed after ${RETRIES} attempts"
        exit 1
    fi
    echo "Attempt ${i} failed; retrying in ${DELAY}s..."
    sleep $DELAY
done

mkdir -p "${TARGET_DIR}"
tar -xzf /tmp/skill.tar.gz -C "${TARGET_DIR}"
echo "OK: ${REGISTRY_URL} -> ${TARGET_DIR}"
"""


def _build_fetcher_scripts_data() -> Dict[str, str]:
    """Return ConfigMap data dict containing per-registry-type fetch scripts."""
    return {"skillberry.sh": _SKILLBERRY_SH, "generic.sh": _GENERIC_SH}


def _ensure_fetcher_scripts_cm(kube: "KubernetesService", namespace: str) -> None:
    """Create or replace the rossoctl-skill-fetcher-scripts ConfigMap in namespace."""
    body = k8s_client.V1ConfigMap(
        metadata=k8s_client.V1ObjectMeta(
            name=SKILL_FETCHER_SCRIPTS_CM,
            namespace=namespace,
            labels={"app.kubernetes.io/managed-by": "rossoctl"},
        ),
        data=_build_fetcher_scripts_data(),
    )
    try:
        kube.core_api.read_namespaced_config_map(name=SKILL_FETCHER_SCRIPTS_CM, namespace=namespace)
        kube.core_api.replace_namespaced_config_map(
            name=SKILL_FETCHER_SCRIPTS_CM, namespace=namespace, body=body
        )
    except ApiException as e:
        if e.status == 404:
            kube.core_api.create_namespaced_config_map(namespace=namespace, body=body)
        else:
            raise


def _get_external_skill_data(
    kube: "KubernetesService",
    namespace: str,
    all_skills: List[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Build init containers, volumes, and mounts for external-registry skills.

    Returns (init_containers, volumes, main_volume_mounts, skill_paths).
    One fetcher-scripts-vol is shared across all init containers in the pod.
    """
    init_containers: List[Dict[str, Any]] = []
    volumes: List[Dict[str, Any]] = []
    main_mounts: List[Dict[str, Any]] = []
    skill_paths: List[str] = []
    fetcher_vol_added = False

    for index, skill_name in enumerate(all_skills):
        if not skill_name:
            continue
        if not _is_skill_external(kube, namespace, skill_name):
            continue

        try:
            cm = kube.core_api.read_namespaced_config_map(
                name=sanitize_k8s_name(skill_name), namespace=namespace
            )
        except ApiException:
            continue

        cm_labels = cm.metadata.labels or {}
        cm_annotations = cm.metadata.annotations or {}
        registry_type = cm_labels.get(SKILL_REGISTRY_TYPE_LABEL, "generic")
        registry_url = cm_annotations.get(SKILL_REGISTRY_URL_ANNOTATION, "")
        registry_skill_name = cm_annotations.get(SKILL_REGISTRY_SKILL_NAME_ANNOTATION, skill_name)
        registry_skill_version = cm_annotations.get(
            SKILL_REGISTRY_SKILL_VERSION_ANNOTATION, "latest"
        )

        cm_name = sanitize_k8s_name(skill_name)
        emptydir_vol_name = f"skill-ext-{index}"
        mount_path = f"{AGENT_SKILLS_MOUNT_ROOT}/{cm_name}"

        if not fetcher_vol_added:
            volumes.append(
                {
                    "name": "fetcher-scripts-vol",
                    "configMap": {"name": SKILL_FETCHER_SCRIPTS_CM},
                }
            )
            fetcher_vol_added = True

        volumes.append({"name": emptydir_vol_name, "emptyDir": {}})

        init_containers.append(
            {
                "name": f"fetch-skill-{index}",
                "image": SKILL_FETCHER_IMAGE,
                "command": [
                    "/bin/sh",
                    "-c",
                    (
                        "SCRIPT=/fetcher-scripts/${REGISTRY_TYPE}.sh; "
                        '[ -f "$SCRIPT" ] || SCRIPT=/fetcher-scripts/generic.sh; '
                        '/bin/sh "$SCRIPT"'
                    ),
                ],
                "env": [
                    {"name": "REGISTRY_TYPE", "value": registry_type},
                    {"name": "REGISTRY_URL", "value": registry_url},
                    {"name": "SKILL_NAME", "value": registry_skill_name},
                    {"name": "SKILL_VERSION", "value": registry_skill_version},
                    {"name": "TARGET_DIR", "value": mount_path},
                ],
                "resources": {
                    "requests": {"memory": "32Mi", "cpu": "50m"},
                    "limits": {"memory": "128Mi", "cpu": "200m"},
                },
                "volumeMounts": [
                    {"name": emptydir_vol_name, "mountPath": mount_path},
                    {
                        "name": "fetcher-scripts-vol",
                        "mountPath": "/fetcher-scripts",
                        "readOnly": True,
                    },
                ],
            }
        )

        main_mounts.append(
            {
                "name": emptydir_vol_name,
                "mountPath": mount_path,
                "readOnly": True,
            }
        )
        skill_paths.append(mount_path)

    return init_containers, volumes, main_mounts, skill_paths
