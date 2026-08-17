# Copyright 2025 IBM Corp.
# Licensed under the Apache License, Version 2.0

"""
Pydantic request/response models for the Agent API.

Split out of ``agents.py``; re-exported there for backwards compatibility.
"""

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import (
    SUPPORTED_WORKLOAD_TYPES,
    WORKLOAD_TYPE_DEPLOYMENT,
)
from app.models.shipwright import ResourceConfigFromBuild, ShipwrightBuildConfig


class OutboundRoute(BaseModel):
    """A single outbound token exchange route for authproxy-routes ConfigMap."""

    host: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    token_scopes: str = "openid"


class SecretKeyRef(BaseModel):
    """Reference to a key in a Secret."""

    name: str
    key: str


class ConfigMapKeyRef(BaseModel):
    """Reference to a key in a ConfigMap."""

    name: str
    key: str


class EnvVarSource(BaseModel):
    """Source for environment variable value."""

    secretKeyRef: Optional[SecretKeyRef] = None
    configMapKeyRef: Optional[ConfigMapKeyRef] = None


class EnvVar(BaseModel):
    """Environment variable with support for direct values and references."""

    name: str
    value: Optional[str] = None
    valueFrom: Optional[EnvVarSource] = None

    @field_validator("name")
    @classmethod
    def validate_env_var_name(cls, v: str) -> str:
        """Validate environment variable name according to Kubernetes rules.

        Valid env var names must:
        - Contain only letters (A-Z, a-z), digits (0-9), and underscores (_)
        - Not start with a digit
        """
        if not v:
            raise ValueError("Environment variable name cannot be empty")

        # Kubernetes env var name pattern: must start with letter or underscore,
        # followed by any combination of letters, digits, or underscores
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"

        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid environment variable name '{v}'. "
                "Name must start with a letter or underscore and contain only "
                "letters, digits, and underscores (e.g., MY_VAR, API_KEY, var123)."
            )

        return v

    @field_validator("valueFrom")
    @classmethod
    def check_value_or_value_from(cls, v, info):
        """Ensure either value or valueFrom is provided, but not both."""
        values = info.data
        has_value = values.get("value") is not None
        has_value_from = v is not None

        if not has_value and not has_value_from:
            raise ValueError("Either value or valueFrom must be provided")
        if has_value and has_value_from:
            raise ValueError("Cannot specify both value and valueFrom")

        return v


class ServicePort(BaseModel):
    """Service port configuration."""

    name: str = "http"
    port: int = 8080
    targetPort: int = 8000
    protocol: str = "TCP"


class PersistentStorageConfig(BaseModel):
    """Persistent storage configuration for Sandbox and StatefulSet agents."""

    enabled: bool = False
    size: str = "1Gi"


class ContextAttachment(BaseModel):
    """A named Context Service resource mounted into the agent."""

    name: str
    mountPath: str = "/workspace"
    readOnly: bool = False


class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""

    name: str
    namespace: str
    protocol: str = "a2a"
    framework: str = "LangGraph"
    envVars: Optional[List[EnvVar]] = None
    skills: Optional[List[str]] = None
    # Optional MCP tool link — when agent import defaults are enabled, MCP_URL is injected
    mcpToolName: Optional[str] = None
    # LLM preset: openai, ollama, openrouter (used with agent import defaults)
    llmPreset: Optional[str] = None
    llmModel: Optional[str] = None

    # Workload type: 'deployment', 'statefulset', or 'job'
    workloadType: str = WORKLOAD_TYPE_DEPLOYMENT

    # Deployment method: 'source' (build from git) or 'image' (use existing image)
    deploymentMethod: str = "source"

    # Build from source fields
    gitUrl: str = ""
    gitPath: str = ""
    gitBranch: str = "main"
    imageTag: str = "v0.0.1"
    registryUrl: Optional[str] = None
    registrySecret: Optional[str] = None
    startCommand: Optional[str] = None

    # Deploy from existing image fields
    containerImage: Optional[str] = None
    imagePullSecret: Optional[str] = None

    # Pod configuration
    servicePorts: Optional[List[ServicePort]] = None

    # HTTPRoute/Route creation
    createHttpRoute: bool = False

    # AuthBridge sidecar injection (default enabled for agents)
    authBridgeEnabled: bool = True
    # SPIRE identity (gates spiffe-helper inside the combined authbridge container)
    spireEnabled: bool = False

    # Per-workload AuthBridge mode override. Maps to
    # AgentRuntime.Spec.AuthBridgeMode; when None the operator falls
    # back through namespace ConfigMap → cluster default
    # (proxy-sidecar). The lite/waypoint shapes are accepted by the
    # operator but not surfaced through the UI today.
    authBridgeMode: Optional[Literal["proxy-sidecar", "envoy-sidecar", "lite", "waypoint"]] = None

    # Per-workload mTLS posture between AuthBridge sidecars. Maps to
    # AgentRuntime.Spec.MTLSMode. The rossoctl UI sends an explicit
    # value (default "disabled") so users always see what they get;
    # this means UI-created agents opt out of any namespace-level
    # mtls.mode setting (CR-pin semantic in the operator). The
    # operator's validating webhook rejects the envoy-sidecar +
    # non-disabled combo because Envoy SDS isn't currently configured
    # by the rossoctl envoy-config — we mirror that check below as a
    # model_validator so the form gets a fast 422 instead of a
    # webhook denial after the manifest is built.
    mtlsMode: Optional[Literal["disabled", "permissive", "strict"]] = None

    # Per-workload TLS bridge: decrypt the agent's outbound HTTPS so AuthBridge's
    # pipeline can inspect it. Maps to AgentRuntime.Spec.TLSBridgeMode (enabled
    # when True; left unset → operator default "disabled"). Like mtlsMode, it's a
    # plain per-agent field — no operator feature gate and no UI feature flag; the
    # import-form checkbox shows whenever AuthBridge is enabled. The bridge lives
    # in the Go forward proxy, so it requires proxy-sidecar/lite mode — the
    # validator below mirrors the operator webhook's reject of envoy-sidecar. It
    # also needs cert-manager and an operator build that supports the bridge.
    tlsBridgeEnabled: bool = False

    # Port exclusion annotations
    outboundPortsExclude: Optional[str] = None
    inboundPortsExclude: Optional[str] = None

    # AuthBridge config overrides (authbridge-config ConfigMap)
    defaultOutboundPolicy: Optional[Literal["passthrough", "exchange"]] = None

    # Outbound routing rules (authproxy-routes ConfigMap)
    outboundRoutes: Optional[List["OutboundRoute"]] = None

    # Persistent storage (for Sandbox and StatefulSet workloads)
    persistentStorage: Optional[PersistentStorageConfig] = None

    # Named Context Service resources. Requires CONTEXT_SERVICE_URL.
    contexts: Optional[List[ContextAttachment]] = None

    # Shipwright build configuration
    shipwrightConfig: Optional[ShipwrightBuildConfig] = None

    # Optional per-agent overrides for container resource limits/requests
    # (falls back to DEFAULT_RESOURCE_LIMITS / DEFAULT_RESOURCE_REQUESTS).
    #
    # Note: The keys and quantity strings are not validated. This is
    # deliberate: validating them here would mean testing Kubernetes
    # shapes (including extended resources such as nvidia.com/gpu),
    # a complex validation path that would still have to be kept in sync
    # with the API server.
    k8sResourceLimits: Optional[Dict[str, str]] = None
    k8sResourceRequests: Optional[Dict[str, str]] = None

    @field_validator("workloadType")
    @classmethod
    def validate_workload_type(cls, v: str) -> str:
        """Validate that workload type is supported."""
        if v not in SUPPORTED_WORKLOAD_TYPES:
            raise ValueError(
                f"Unsupported workload type: {v}. "
                f"Supported types: {', '.join(SUPPORTED_WORKLOAD_TYPES)}"
            )
        return v

    @model_validator(mode="after")
    def _check_mtls_compatible_with_mode(self) -> "CreateAgentRequest":
        """Hook for cross-field rejections of authBridgeMode +
        mtlsMode combinations the operator's AgentRuntime validating
        webhook would also reject.

        envoy-sidecar + non-disabled mtlsMode used to be rejected here
        as defense-in-depth in front of the operator's webhook gate.
        Both have been lifted now that the operator + extensions
        support the full matrix (rossoctl-operator#381,
        cortex#441), so today there are no rejected
        combinations.

        TODO(future-incompatibility): re-enable cross-field rejections
        here when a new authBridgeMode (e.g. waypoint, sidecarless)
        lands that needs different mTLS semantics. The function
        intentionally stays as a single grep-target so the rejection
        can land here instead of getting scattered across the request
        model. Mirrors the operator's checkMTLSCompatibleWithMode
        pattern in agentruntime_webhook.go.

        SPIRE-vs-mTLS coupling is intentionally NOT enforced here:
        rossoctl-operator's pod_mutator auto-enables SPIRE when
        mtlsMode != disabled (pod_mutator.go:288-302), so a request
        with mtlsMode=strict + spireEnabled=false is handled at the
        operator data-plane layer rather than rejected at the API
        boundary. The UI form still locks the mTLS dropdown when
        SPIRE is off as a UX hint, but a non-UI client (CLI, direct
        API call) submitting that combination is valid and the
        operator turns SPIRE on for them.
        """
        return self

    @model_validator(mode="after")
    def _check_tlsbridge_compatible_with_mode(self) -> "CreateAgentRequest":
        """Reject tlsBridgeEnabled with an authBridgeMode that can't host the
        bridge, mirroring the operator's checkTLSBridgeCompatibleWithMode
        (agentruntime_webhook.go). The TLS bridge lives in the Go forward proxy,
        which only exists in proxy-sidecar / lite. Uses the same ALLOWLIST as the
        operator (empty → defaults to proxy-sidecar) rather than a denylist, so a
        future authBridgeMode can't slip past this fast-422 and only get rejected
        at the webhook.
        """
        allowed = (None, "", "proxy-sidecar", "lite")
        if self.tlsBridgeEnabled and self.authBridgeMode not in allowed:
            raise ValueError(
                "tlsBridgeEnabled requires authBridgeMode proxy-sidecar or lite "
                f"(the TLS bridge lives in the Go forward proxy); got {self.authBridgeMode!r}"
            )
        return self


class CreateAgentResponse(BaseModel):
    """Response after creating an agent."""

    success: bool
    name: str
    namespace: str
    message: str


class AgentShipwrightBuildInfoResponse(BaseModel):  # pylint: disable=too-many-instance-attributes
    """Full Shipwright Build information for agents.

    This is an agent-specific wrapper that includes agentConfig for backwards compatibility.
    """

    # Build info
    name: str
    namespace: str
    buildRegistered: bool
    buildReason: Optional[str] = None
    buildMessage: Optional[str] = None
    outputImage: str
    strategy: str
    gitUrl: str
    gitRevision: str
    contextDir: str

    # Latest BuildRun info (if any)
    hasBuildRun: bool = False
    buildRunName: Optional[str] = None
    buildRunPhase: Optional[str] = None  # Pending, Running, Succeeded, Failed
    buildRunStartTime: Optional[str] = None
    buildRunCompletionTime: Optional[str] = None
    buildRunOutputImage: Optional[str] = None
    buildRunOutputDigest: Optional[str] = None
    buildRunFailureMessage: Optional[str] = None

    # Agent configuration from annotations (agent-specific)
    agentConfig: Optional[ResourceConfigFromBuild] = None


# Migration Models (Phase 4: Agent CRD to Deployment migration)


class MigrateAgentRequest(BaseModel):
    """Request to migrate an Agent CRD to a Deployment."""

    delete_old: bool = False  # Whether to delete the Agent CRD after successful migration


class MigrateAgentResponse(BaseModel):
    """Response after migrating an agent."""

    success: bool
    migrated: bool
    name: str
    namespace: str
    message: str
    deployment_created: bool = False
    service_created: bool = False
    agent_crd_deleted: bool = False


class MigratableAgentInfo(BaseModel):
    """Information about an agent that can be migrated."""

    name: str
    namespace: str
    status: str
    has_deployment: bool  # True if a Deployment already exists with same name
    labels: Dict[str, str]
    description: Optional[str] = None


class ListMigratableAgentsResponse(BaseModel):
    """Response containing list of agents that can be migrated."""

    agents: List[MigratableAgentInfo]
    total: int
    already_migrated: int  # Count of agents that already have Deployments


class FinalizeShipwrightBuildRequest(BaseModel):
    """Request to finalize a Shipwright build and create the Agent.

    All fields are optional. If not provided, the values stored in the Build's
    rossoctl.io/agent-config annotation will be used.
    """

    # These fields mirror CreateAgentRequest for Agent creation
    # All optional - will use values from Build annotation if not provided
    protocol: Optional[str] = None
    framework: Optional[str] = None
    envVars: Optional[List[EnvVar]] = None
    skills: Optional[List[str]] = None
    servicePorts: Optional[List[ServicePort]] = None
    createHttpRoute: Optional[bool] = None
    authBridgeEnabled: Optional[bool] = None
    imagePullSecret: Optional[str] = None
    authBridgeMode: Optional[Literal["proxy-sidecar", "envoy-sidecar", "lite", "waypoint"]] = None
    # Mirrors CreateAgentRequest.mtlsMode. Threaded through the
    # finalize flow so a build-from-source agent inherits the mtlsMode
    # the user picked at form-submit time (stashed on the BuildRun via
    # rossoctl.io/agent-config annotation).
    mtlsMode: Optional[Literal["disabled", "permissive", "strict"]] = None
    # Mirrors CreateAgentRequest.tlsBridgeEnabled. None → inherit the value
    # stashed on the BuildRun annotation at form-submit time.
    tlsBridgeEnabled: Optional[bool] = None
    outboundRoutes: Optional[List[OutboundRoute]] = None
    outboundPortsExclude: Optional[str] = None
    inboundPortsExclude: Optional[str] = None
    defaultOutboundPolicy: Optional[Literal["passthrough", "exchange"]] = None
    persistentStorage: Optional[PersistentStorageConfig] = None
    mcpToolName: Optional[str] = None
    llmPreset: Optional[str] = None
    llmModel: Optional[str] = None
    # Mirror CreateAgentRequest.k8sResourceLimits/k8sResourceRequests. None →
    # inherit the value stashed on the BuildRun annotation at form-submit time,
    # so a build-from-source agent gets the same resources as a direct-image one.
    k8sResourceLimits: Optional[Dict[str, str]] = None
    k8sResourceRequests: Optional[Dict[str, str]] = None

    @model_validator(mode="after")
    def _check_mtls_compatible_with_mode(self) -> "FinalizeShipwrightBuildRequest":
        """Mirror of CreateAgentRequest._check_mtls_compatible_with_mode
        at the Shipwright finalize boundary. Today there are no
        rejected combinations.

        TODO(future-incompatibility): re-enable cross-field rejections
        here when a new authBridgeMode lands that needs different mTLS
        semantics. See CreateAgentRequest._check_mtls_compatible_with_mode
        for the full rationale (including why SPIRE-vs-mTLS coupling
        is handled at the operator data-plane layer rather than here).
        """
        return self

    @model_validator(mode="after")
    def _check_tlsbridge_compatible_with_mode(self) -> "FinalizeShipwrightBuildRequest":
        """Mirror of CreateAgentRequest._check_tlsbridge_compatible_with_mode at
        the Shipwright finalize boundary, so a direct finalize caller (or a combo
        inherited from the BuildRun's stored config) with tlsBridgeEnabled +
        envoy-sidecar/waypoint gets the same fast 422 instead of a later webhook
        denial. Same allowlist as the operator (empty → defaults to proxy-sidecar).
        """
        allowed = (None, "", "proxy-sidecar", "lite")
        if self.tlsBridgeEnabled and self.authBridgeMode not in allowed:
            raise ValueError(
                "tlsBridgeEnabled requires authBridgeMode proxy-sidecar or lite "
                f"(the TLS bridge lives in the Go forward proxy); got {self.authBridgeMode!r}"
            )
        return self


# New models for env parsing
class ParseEnvRequest(BaseModel):
    """Request to parse .env file content."""

    content: str


class ParseEnvResponse(BaseModel):
    """Response with parsed environment variables."""

    envVars: List[Dict[str, Any]]
    warnings: Optional[List[str]] = None


class FetchEnvUrlRequest(BaseModel):
    """Request to fetch .env file from URL."""

    url: str


class FetchEnvUrlResponse(BaseModel):
    """Response with fetched .env file content."""

    content: str
    url: str
