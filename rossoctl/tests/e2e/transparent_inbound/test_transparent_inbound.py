"""Transparent inbound interception E2E (rossoctl/cortex#330).

The load-bearing test here is ``test_direct_pod_dial_is_validated``: the reason
the feature exists is that JWT validation must not be sidestepped by another pod
dialing the agent's real port. Everything else either proves the shape under
test is actually the transparent one, or guards against the feature breaking
what it runs alongside.
"""

import pytest

from .conftest import (
    AGENT_PORT,
    agent_pod,
    container,
    curl_from_probe,
    env_of,
    kubectl,
)

pytestmark = pytest.mark.kind_only


# ---------------------------------------------------------------------------
# Shape: is the thing we deployed actually the transparent mechanism?
# ---------------------------------------------------------------------------


def test_agent_keeps_its_own_port(transparent_agent):
    """No port stealing.

    This is what removes the two failure modes of the reverse-proxy mechanism:
    an agent that hardcodes its listen port (which collides with AuthBridge on
    the stolen port) and the relocated port that nothing validates.
    """
    pod = agent_pod(**transparent_agent)
    agent = container(pod, "agent")

    assert agent["ports"][0]["containerPort"] == AGENT_PORT, (
        "transparent interception must leave the agent on its own port; "
        f"got {agent['ports'][0]['containerPort']}"
    )
    # Assert the operator did not REWRITE PORT, not that PORT is absent: the
    # stand-in agent declares PORT itself (it must, or the reverse-proxy control
    # cannot be exercised). Under port stealing the operator overwrites it with
    # originalPort+1, so an unchanged value is the discriminator.
    port_env = env_of(agent, "PORT")
    if port_env is not None:
        assert port_env.get("value") == str(AGENT_PORT), (
            f"PORT was rewritten to {port_env.get('value')}; transparent "
            f"interception must leave it at {AGENT_PORT}"
        )


def test_sidecar_binds_transparent_inbound_port(transparent_agent):
    pod = agent_pod(**transparent_agent)
    proxy = container(pod, "authbridge-proxy")

    names = {p.get("name"): p["containerPort"] for p in proxy.get("ports", [])}
    assert "transparent-in" in names, (
        f"sidecar should declare a transparent-in port; got {names}"
    )
    assert AGENT_PORT not in names.values(), (
        "sidecar must not claim the agent's port under transparent interception"
    )


def test_proxy_init_configured_for_inbound_capture(transparent_agent):
    """Both env vars are load-bearing.

    INBOUND_TRANSPARENT_PORT arms the PREROUTING chain; POD_IP is the DNAT
    target for the Istio ambient path, which arrives through OUTPUT and would
    otherwise bypass inbound validation entirely.
    """
    pod = agent_pod(**transparent_agent)
    init = container(pod, "proxy-init")

    port = env_of(init, "INBOUND_TRANSPARENT_PORT")
    assert port is not None and port.get("value"), (
        "proxy-init has no INBOUND_TRANSPARENT_PORT — inbound capture is inert"
    )

    pod_ip = env_of(init, "POD_IP")
    assert pod_ip is not None, (
        "proxy-init has no POD_IP — the ambient inbound path cannot be captured"
    )
    assert (
        pod_ip.get("valueFrom", {}).get("fieldRef", {}).get("fieldPath")
        == "status.podIP"
    ), f"POD_IP must come from the downward API; got {pod_ip}"


def test_ab_inbound_chain_installed(transparent_agent):
    """proxy-init reports having installed the inbound capture.

    Asserted from proxy-init's output rather than by running iptables-save in the
    sidecar: that image has no iptables binary, so an exec-based check can only
    skip — which silently drops the assertion. The init container states exactly
    what it programmed, and it runs with require_jump guards that abort on a rule
    that did not land, so its success line is a real signal rather than a log
    scrape.
    """
    pod = agent_pod(**transparent_agent)
    logs = kubectl(
        "logs",
        pod["metadata"]["name"],
        "-n",
        transparent_agent["namespace"],
        "-c",
        "proxy-init",
        check=False,
    )
    assert logs.strip(), "proxy-init produced no output — did it run?"
    assert "transparent-inbound: hard inbound boundary active" in logs, (
        f"proxy-init did not complete inbound setup:\n{logs[-1500:]}"
    )
    assert "IPv4 inbound capture configured" in logs, (
        f"IPv4 inbound capture not configured:\n{logs[-1500:]}"
    )
    # Parse the exemption line rather than substring-matching the whole log:
    # "9091" appears in plenty of other contexts (ports, URLs, timestamps), so a
    # whole-log check would pass even if the port were never exempted — and a
    # JWT-gated :9091 crash-loops the pod.
    exempt_line = next(
        (ln for ln in logs.splitlines() if "exempt sidecar ports" in ln), ""
    )
    assert exempt_line, f"proxy-init did not report its exemptions:\n{logs[-1500:]}"
    assert "9091" in exempt_line.split("exempt sidecar ports=", 1)[-1], (
        f"health port 9091 missing from the exempt set: {exempt_line!r}"
    )


# ---------------------------------------------------------------------------
# The boundary property
# ---------------------------------------------------------------------------


def test_direct_pod_dial_is_validated(transparent_agent):
    """THE test: pod-to-pod on the agent's real port must be validated.

    The probe sends no Authorization header, so a compliant boundary rejects it.
    A 200 here means the request reached the agent without passing through the
    inbound pipeline — exactly the bypass this feature closes.
    """
    pod = agent_pod(**transparent_agent)
    pod_ip = pod["status"]["podIP"]

    status = curl_from_probe(
        transparent_agent["namespace"], f"http://{pod_ip}:{AGENT_PORT}/"
    )
    assert status != 200, (
        f"pod-to-pod dial to {pod_ip}:{AGENT_PORT} returned 200 without a token — "
        "inbound validation was bypassed"
    )
    assert status in (401, 403), (
        f"expected an auth denial for an unauthenticated direct dial, got {status}"
    )


def test_service_routed_request_is_validated(transparent_agent):
    """Service-routed traffic must be validated too, not just direct dials."""
    ns, name = transparent_agent["namespace"], transparent_agent["name"]
    status = curl_from_probe(ns, f"http://{name}.{ns}.svc.cluster.local:{AGENT_PORT}/")
    assert status in (401, 403), (
        f"expected an auth denial through the Service, got {status}"
    )


def test_reverse_proxy_control_bypass_is_reachable(reverse_proxy_agent):
    """Control: the default mechanism still has the bypass this feature closes.

    Documents current behavior rather than endorsing it. If this starts failing
    because the bypass is gone, the default changed — retire this test with it.
    """
    pod = agent_pod(**reverse_proxy_agent)
    agent = container(pod, "agent")
    relocated = agent["ports"][0]["containerPort"]

    assert relocated != AGENT_PORT, (
        "expected the reverse-proxy mechanism to relocate the agent; "
        "the control is not exercising port stealing"
    )

    status = curl_from_probe(
        reverse_proxy_agent["namespace"],
        f"http://{pod['status']['podIP']}:{relocated}/",
    )
    # Asserts success, not merely "not 401": if the bypass were ever closed with a
    # 403, or the port stopped answering at all, `!= 401` would keep this green and
    # the control would silently stop being a control.
    assert status == 200, (
        f"relocated port {relocated} returned {status}, want 200. The bypass this "
        "feature closes appears to be gone under reverse-proxy — if that is "
        "intentional, the default changed and this control test should be retired "
        "with it."
    )


# ---------------------------------------------------------------------------
# Don't break the neighbours
# ---------------------------------------------------------------------------


def test_health_port_not_gated(transparent_agent):
    """A JWT-gated :9091 would fail kubelet probes and crash-loop the pod.

    The pod being Ready is itself partial evidence; this asserts the port
    directly so the reason is unambiguous if it regresses.
    """
    pod = agent_pod(**transparent_agent)
    status = curl_from_probe(
        transparent_agent["namespace"], f"http://{pod['status']['podIP']}:9091/healthz"
    )
    assert status not in (401, 403), (
        f"health port is behind auth (got {status}) — probes would fail"
    )


def test_session_api_not_gated(transparent_agent):
    """agentop consumes :9094; gating it would break session observability."""
    pod = agent_pod(**transparent_agent)
    status = curl_from_probe(
        transparent_agent["namespace"], f"http://{pod['status']['podIP']}:9094/sessions"
    )
    assert status not in (401, 403), f"session-events API is behind auth (got {status})"


def test_egress_enforcement_still_active(transparent_agent):
    """Inbound capture must not have disturbed the egress guard.

    Same reasoning as the chain test: read proxy-init's report rather than exec
    iptables in an image that has none.
    """
    pod = agent_pod(**transparent_agent)
    logs = kubectl(
        "logs",
        pod["metadata"]["name"],
        "-n",
        transparent_agent["namespace"],
        "-c",
        "proxy-init",
        check=False,
    )
    assert "enforce-redirect: fail-closed egress capture active" in logs, (
        f"egress guard not active after enabling inbound capture:\n{logs[-1500:]}"
    )
    # Ordering matters: the ambient inbound DNAT is installed at the head of the
    # egress chain, so egress setup must complete before inbound setup begins.
    # find(), not index(): index() raises ValueError when a marker is absent, so
    # the assertion message would never print and the failure would surface as an
    # unrelated traceback.
    egress_at = logs.find("fail-closed egress capture active")
    inbound_at = logs.find("installing inbound capture")
    assert egress_at >= 0 and inbound_at >= 0, (
        f"expected both setup markers in proxy-init output; "
        f"egress={egress_at} inbound={inbound_at}\n{logs[-1500:]}"
    )
    assert egress_at < inbound_at, (
        "inbound setup ran before the egress chain existed, so the ambient DNAT "
        f"had no chain to be inserted at the head of (egress={egress_at} "
        f"inbound={inbound_at})"
    )
