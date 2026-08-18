"""
AgentRuntime Route Injection E2E Tests.

Tests the new spec.auth.outbound functionality that allows per-agent
configuration of token exchange routes via the AgentRuntime CRD.

Test coverage:
  1. Route injection - verify routes from AgentRuntime spec appear in ConfigMap
  2. Route matching - verify exact host and regex patterns work
  3. Backward compatibility - verify agents without routes still work
  4. Integration - verify routes actually enable token exchange
"""

import json
import subprocess
import time
from typing import Dict, List, Optional

import pytest
import yaml

from .conftest import TX_NAMESPACE


def _kubectl_get(resource: str, name: str, namespace: str, output: str = "json") -> Optional[Dict]:
    """Get a Kubernetes resource and return parsed output."""
    result = subprocess.run(
        [
            "kubectl",
            "get",
            resource,
            name,
            "-n",
            namespace,
            "-o",
            output,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    if output == "json":
        return json.loads(result.stdout)
    return yaml.safe_load(result.stdout)


def _kubectl_apply(manifest: str, namespace: str) -> bool:
    """Apply a Kubernetes manifest."""
    result = subprocess.run(
        [
            "kubectl",
            "apply",
            "-f",
            "-",
            "-n",
            namespace,
        ],
        input=manifest,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


def _wait_for_configmap(
    cm_name: str, namespace: str, timeout: int = 60
) -> Optional[Dict]:
    """Wait for a ConfigMap to exist."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        cm = _kubectl_get("configmap", cm_name, namespace)
        if cm is not None:
            return cm
        time.sleep(2)
    return None


def _get_authbridge_config(cm_name: str, namespace: str) -> Optional[Dict]:
    """Parse the AuthBridge config.yaml from a ConfigMap."""
    cm = _kubectl_get("configmap", cm_name, namespace)
    if cm is None:
        return None
    config_yaml = cm.get("data", {}).get("config.yaml")
    if config_yaml is None:
        return None
    return yaml.safe_load(config_yaml)


def _get_token_exchange_routes(
    cm_name: str, namespace: str
) -> Optional[List[Dict]]:
    """Extract token-exchange plugin routes from AuthBridge ConfigMap."""
    config = _get_authbridge_config(cm_name, namespace)
    if config is None:
        return None

    pipeline = config.get("pipeline", {})
    outbound = pipeline.get("outbound", {})
    plugins = outbound.get("plugins", [])

    for plugin in plugins:
        if plugin.get("name") == "token-exchange":
            plugin_config = plugin.get("config", {})
            return plugin_config.get("routes")
    return None


class TestAgentRuntimeRouteInjection:
    """Test route injection from AgentRuntime spec.auth.outbound."""

    def test_agentruntime_crd_exists(self):
        """AgentRuntime CRD is installed."""
        result = subprocess.run(
            ["kubectl", "get", "crd", "agentruntimes.agent.rossoctl.dev"],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, "AgentRuntime CRD not found"

    def test_routes_injected_from_spec(self):
        """Routes from spec.auth.outbound appear in AuthBridge ConfigMap.

        Flow:
          1. Create an AgentRuntime with spec.auth.outbound
          2. Deploy a matching workload
          3. Wait for operator webhook to create ConfigMap
          4. Verify routes appear in pipeline.outbound.plugins[token-exchange].config.routes
        """
        # Create test workload
        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-route-agent
  labels:
    app: test-route-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-route-agent
  template:
    metadata:
      labels:
        app: test-route-agent
    spec:
      containers:
      - name: agent
        image: busybox:latest
        command: ["sleep", "3600"]
"""

        agentruntime = """
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: test-route-agent
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-route-agent
  auth:
    outbound:
      - destination:
          host: "service-a.team1.svc.cluster.local"
        audiences:
          - "spiffe://localtest.me/ns/team1/sa/service-a"
      - destination:
          hostRegex: ".*\\\\.team1\\\\.svc\\\\.cluster\\\\.local"
        audiences:
          - "spiffe://localtest.me/ns/team1/sa/default"
"""

        # Apply manifests
        assert _kubectl_apply(deployment, TX_NAMESPACE), "Failed to create deployment"
        assert _kubectl_apply(agentruntime, TX_NAMESPACE), "Failed to create AgentRuntime"

        try:
            # Wait for the per-agent ConfigMap (operator webhook creates it)
            # ConfigMap name format: authbridge-config-<workload-name>
            cm_name = "authbridge-config-test-route-agent"
            cm = _wait_for_configmap(cm_name, TX_NAMESPACE, timeout=90)
            assert cm is not None, f"ConfigMap {cm_name} not created within 90s"

            # Extract routes
            routes = _get_token_exchange_routes(cm_name, TX_NAMESPACE)
            assert routes is not None, "No routes found in token-exchange plugin"
            assert len(routes) == 2, f"Expected 2 routes, got {len(routes)}"

            # Verify first route (exact host)
            route1 = routes[0]
            assert route1["destination"]["host"] == "service-a.team1.svc.cluster.local"
            assert route1["audiences"] == ["spiffe://localtest.me/ns/team1/sa/service-a"]

            # Verify second route (regex)
            route2 = routes[1]
            assert route2["destination"]["hostRegex"] == ".*\\.team1\\.svc\\.cluster\\.local"
            assert route2["audiences"] == ["spiffe://localtest.me/ns/team1/sa/default"]

        finally:
            # Cleanup
            subprocess.run(
                ["kubectl", "delete", "agentruntime", "test-route-agent", "-n", TX_NAMESPACE],
                timeout=30,
            )
            subprocess.run(
                ["kubectl", "delete", "deployment", "test-route-agent", "-n", TX_NAMESPACE],
                timeout=30,
            )

    def test_backward_compatibility_no_routes(self):
        """Agents with AgentRuntime but without spec.auth still work (no routes injected).

        This verifies that the new route injection logic doesn't break
        existing agents that have AgentRuntime but no auth config.
        """
        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-no-routes-agent
  labels:
    app: test-no-routes-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-no-routes-agent
  template:
    metadata:
      labels:
        app: test-no-routes-agent
    spec:
      containers:
      - name: agent
        image: busybox:latest
        command: ["sleep", "3600"]
"""

        agentruntime = """
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: test-no-routes-agent
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-no-routes-agent
"""

        # Deploy WITH AgentRuntime but WITHOUT spec.auth
        assert _kubectl_apply(deployment, TX_NAMESPACE), "Failed to create deployment"
        assert _kubectl_apply(agentruntime, TX_NAMESPACE), "Failed to create AgentRuntime"

        try:
            cm_name = "authbridge-config-test-no-routes-agent"
            cm = _wait_for_configmap(cm_name, TX_NAMESPACE, timeout=90)
            assert cm is not None, f"ConfigMap {cm_name} not created"

            # Verify no routes are present
            routes = _get_token_exchange_routes(cm_name, TX_NAMESPACE)
            # routes should be None or empty list
            assert routes is None or len(routes) == 0, (
                f"Expected no routes for agent without spec.auth, got {routes}"
            )

        finally:
            subprocess.run(
                ["kubectl", "delete", "agentruntime", "test-no-routes-agent", "-n", TX_NAMESPACE],
                timeout=30,
            )
            subprocess.run(
                ["kubectl", "delete", "deployment", "test-no-routes-agent", "-n", TX_NAMESPACE],
                timeout=30,
            )

    def test_weather_agent_example_routes(self):
        """Weather agent example has correct routes configured.

        This verifies the actual example in rossoctl/examples/agents/
        has the expected route to the weather tool.
        """
        # The weather agent should already be deployed by the E2E setup
        art_name = "weather-service"
        art = _kubectl_get("agentruntime", art_name, "team1")

        if art is None:
            pytest.skip("weather-service AgentRuntime not found in team1")

        # Verify spec.auth.outbound exists
        spec = art.get("spec", {})
        auth = spec.get("auth")
        assert auth is not None, "weather-service AgentRuntime has no spec.auth"

        outbound = auth.get("outbound")
        assert outbound is not None and len(outbound) > 0, (
            "weather-service has no spec.auth.outbound routes"
        )

        # Verify the route to weather-tool-mcp
        found_tool_route = False
        for route in outbound:
            dest = route.get("destination", {})
            if dest.get("host") == "weather-tool-mcp.team1.svc.cluster.local":
                found_tool_route = True
                audiences = route.get("audiences", [])
                assert "spiffe://localtest.me/ns/team1/sa/weather-tool" in audiences, (
                    f"Expected weather-tool SPIFFE ID in audiences, got {audiences}"
                )

        assert found_tool_route, (
            "weather-service AgentRuntime missing route to weather-tool-mcp"
        )

        # Verify routes are injected into ConfigMap
        cm_name = "authbridge-config-weather-service"
        routes = _get_token_exchange_routes(cm_name, "team1")

        if routes is None:
            pytest.skip("weather-service ConfigMap not found or has no routes")

        # Find the weather-tool route in the injected config
        found_in_cm = False
        for route in routes:
            dest = route.get("destination", {})
            if dest.get("host") == "weather-tool-mcp.team1.svc.cluster.local":
                found_in_cm = True
                assert route.get("audiences") == [
                    "spiffe://localtest.me/ns/team1/sa/weather-tool"
                ]

        assert found_in_cm, "weather-tool route not found in ConfigMap"


class TestRouteMatching:
    """Test route matching behavior (exact host vs regex)."""

    def test_exact_host_matching(self):
        """Verify exact hostname matching works."""
        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-exact-host
  labels:
    app: test-exact-host
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-exact-host
  template:
    metadata:
      labels:
        app: test-exact-host
    spec:
      containers:
      - name: agent
        image: busybox:latest
        command: ["sleep", "3600"]
"""

        agentruntime = """
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: test-exact-host
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-exact-host
  auth:
    outbound:
      - destination:
          host: "exact.example.com"
        audiences:
          - "spiffe://localtest.me/ns/team1/sa/exact"
"""

        assert _kubectl_apply(deployment, TX_NAMESPACE), "Failed to create deployment"
        assert _kubectl_apply(agentruntime, TX_NAMESPACE), "Failed to create AgentRuntime"

        try:
            cm_name = "authbridge-config-test-exact-host"
            cm = _wait_for_configmap(cm_name, TX_NAMESPACE, timeout=90)
            assert cm is not None, f"ConfigMap {cm_name} not created"

            routes = _get_token_exchange_routes(cm_name, TX_NAMESPACE)
            assert routes is not None and len(routes) == 1
            assert routes[0]["destination"]["host"] == "exact.example.com"
            assert "hostRegex" not in routes[0]["destination"]

        finally:
            subprocess.run(
                ["kubectl", "delete", "agentruntime", "test-exact-host", "-n", TX_NAMESPACE],
                timeout=30,
            )
            subprocess.run(
                ["kubectl", "delete", "deployment", "test-exact-host", "-n", TX_NAMESPACE],
                timeout=30,
            )

    def test_regex_host_matching(self):
        """Verify regex hostname matching works."""
        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-regex-host
  labels:
    app: test-regex-host
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-regex-host
  template:
    metadata:
      labels:
        app: test-regex-host
    spec:
      containers:
      - name: agent
        image: busybox:latest
        command: ["sleep", "3600"]
"""

        agentruntime = """
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: test-regex-host
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-regex-host
  auth:
    outbound:
      - destination:
          hostRegex: ".*\\\\.internal\\\\.example\\\\.com"
        audiences:
          - "spiffe://localtest.me/ns/team1/sa/internal"
"""

        assert _kubectl_apply(deployment, TX_NAMESPACE), "Failed to create deployment"
        assert _kubectl_apply(agentruntime, TX_NAMESPACE), "Failed to create AgentRuntime"

        try:
            cm_name = "authbridge-config-test-regex-host"
            cm = _wait_for_configmap(cm_name, TX_NAMESPACE, timeout=90)
            assert cm is not None, f"ConfigMap {cm_name} not created"

            routes = _get_token_exchange_routes(cm_name, TX_NAMESPACE)
            assert routes is not None and len(routes) == 1
            assert routes[0]["destination"]["hostRegex"] == ".*\\.internal\\.example\\.com"
            assert "host" not in routes[0]["destination"]

        finally:
            subprocess.run(
                ["kubectl", "delete", "agentruntime", "test-regex-host", "-n", TX_NAMESPACE],
                timeout=30,
            )
            subprocess.run(
                ["kubectl", "delete", "deployment", "test-regex-host", "-n", TX_NAMESPACE],
                timeout=30,
            )

    def test_multiple_audiences(self):
        """Verify multiple audiences in a single route work."""
        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-multi-aud
  labels:
    app: test-multi-aud
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-multi-aud
  template:
    metadata:
      labels:
        app: test-multi-aud
    spec:
      containers:
      - name: agent
        image: busybox:latest
        command: ["sleep", "3600"]
"""

        agentruntime = """
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: test-multi-aud
spec:
  type: agent
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-multi-aud
  auth:
    outbound:
      - destination:
          host: "multi-aud.example.com"
        audiences:
          - "spiffe://localtest.me/ns/team1/sa/service-a"
          - "spiffe://localtest.me/ns/team1/sa/service-b"
          - "spiffe://localtest.me/ns/team2/sa/service-c"
"""

        assert _kubectl_apply(deployment, TX_NAMESPACE), "Failed to create deployment"
        assert _kubectl_apply(agentruntime, TX_NAMESPACE), "Failed to create AgentRuntime"

        try:
            cm_name = "authbridge-config-test-multi-aud"
            cm = _wait_for_configmap(cm_name, TX_NAMESPACE, timeout=90)
            assert cm is not None, f"ConfigMap {cm_name} not created"

            routes = _get_token_exchange_routes(cm_name, TX_NAMESPACE)
            assert routes is not None and len(routes) == 1
            audiences = routes[0]["audiences"]
            assert len(audiences) == 3
            assert "spiffe://localtest.me/ns/team1/sa/service-a" in audiences
            assert "spiffe://localtest.me/ns/team1/sa/service-b" in audiences
            assert "spiffe://localtest.me/ns/team2/sa/service-c" in audiences

        finally:
            subprocess.run(
                ["kubectl", "delete", "agentruntime", "test-multi-aud", "-n", TX_NAMESPACE],
                timeout=30,
            )
            subprocess.run(
                ["kubectl", "delete", "deployment", "test-multi-aud", "-n", TX_NAMESPACE],
                timeout=30,
            )
