"""E2E: an agent cannot bypass the AuthBridge egress guard (#1940).

A NetworkPolicy cannot do this job: it selects pods, and all containers in a pod
share one network namespace, so it cannot allow the sidecar and deny the agent.
The guard is proxy-init ``egressEnforcement: enforce-redirect``, which redirects
all TCP egress to the sidecar. A direct connection is not dropped, it is
captured. The capture is proven with the shared socket table, not with sidecar
logs: the CI sidecar logs a captured host only at debug level.
"""

import pytest

from .conftest import EGRESS_TARGET, agent_pod, exec_in, http_status, kubectl

pytestmark = pytest.mark.kind_only

# TEST-NET-1 (RFC 5737), never routed: the connection stays open while the
# sidecar tries to dial it, which gives time to read the socket table.
BYPASS_IP = "192.0.2.1"
# Little-endian hex as /proc/net/tcp prints it; a v4-mapped tcp6 address ends
# with the same 8 characters.
BYPASS_IP_HEX = "010200C0"
TRANSPARENT_PORT = 8082
NO_PROXY_ENV = "unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY no_proxy NO_PROXY; "


def _require_enforce_redirect(ns: str, pod: dict) -> str:
    """Skip under egressEnforcement: none; else require the guard's report."""
    if "proxy-init" not in [c["name"] for c in pod["spec"].get("initContainers", [])]:
        pytest.skip(
            "egressEnforcement resolved to none: no proxy-init, "
            "HTTP_PROXY routing is cooperative only"
        )
    logs = kubectl(
        "logs", pod["metadata"]["name"], "-n", ns, "-c", "proxy-init", check=False
    )
    assert "enforce-redirect: fail-closed egress capture active" in logs, (
        f"proxy-init did not report the egress guard active:\n{logs[-1500:]}"
    )
    return logs


def _sockets(table: str) -> list[tuple[int, str, int]]:
    """Parse /proc/net/tcp{,6} into (local_port, remote_ip_hex, remote_port)."""
    socks = []
    for line in table.splitlines():
        fields = line.split()
        if len(fields) < 3 or not fields[0].endswith(":"):
            continue  # header line
        local_port = fields[1].rsplit(":", 1)[1]
        remote_ip, remote_port = fields[2].rsplit(":", 1)
        socks.append((int(local_port, 16), remote_ip.upper(), int(remote_port, 16)))
    return socks


def _pod(transparent_agent):
    ns = transparent_agent["namespace"]
    pod = agent_pod(**transparent_agent)
    return ns, pod, pod["metadata"]["name"]


def test_direct_egress_bypass_is_captured(transparent_agent):
    """A connection with every proxy setting removed still reaches the sidecar."""
    ns, pod, name = _pod(transparent_agent)
    _require_enforce_redirect(ns, pod)
    script = (
        NO_PROXY_ENV
        + f"wget -Y off -q -T 20 -O /dev/null 'http://{BYPASS_IP}/' >/dev/null 2>&1 & "
        + "sleep 2; cat /proc/net/tcp /proc/net/tcp6 2>/dev/null; kill $! 2>/dev/null; true"
    )
    table = exec_in(ns, name, "agent", script).stdout
    socks = _sockets(table)
    agent_ports = {
        lp for lp, rip, rp in socks if rp == 80 and rip.endswith(BYPASS_IP_HEX)
    }
    assert agent_ports, (
        f"agent opened no socket to {BYPASS_IP}:80; table:\n{table[-2000:]}"
    )
    # The sidecar's accepted socket has the agent socket's local port as its peer.
    captured = [s for s in socks if s[0] == TRANSPARENT_PORT and s[2] in agent_ports]
    assert captured, (
        f"direct connection to {BYPASS_IP}:80 with proxy settings removed never reached "
        f"the sidecar listener :{TRANSPARENT_PORT} — bypass is open; table:\n{table[-2000:]}"
    )


def test_direct_egress_still_reaches_services(transparent_agent):
    """The captured connection still works end to end."""
    ns, pod, name = _pod(transparent_agent)
    _require_enforce_redirect(ns, pod)
    script = (
        NO_PROXY_ENV
        + f"wget -Y off -q -S -T 15 -O /dev/null '{EGRESS_TARGET}' 2>&1 | head -1"
    )
    status = http_status(exec_in(ns, name, "agent", script).stdout, EGRESS_TARGET)
    assert status in range(100, 600)


def test_proxy_path_still_works(transparent_agent):
    """The cooperative path, with the injected proxy env, still works."""
    ns, _, name = _pod(transparent_agent)
    script = f"wget -Y on -q -S -T 15 -O /dev/null '{EGRESS_TARGET}' 2>&1 | head -1"
    status = http_status(exec_in(ns, name, "agent", script).stdout, EGRESS_TARGET)
    assert status in range(100, 600)


def test_dns_preserved(transparent_agent):
    """The guard exempts DNS, so name resolution still works."""
    ns, _, name = _pod(transparent_agent)
    proc = exec_in(ns, name, "agent", "nslookup kubernetes.default.svc.cluster.local")
    assert proc.returncode == 0, (
        f"nslookup failed ({proc.returncode}):\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


def test_k8s_api_reachable(transparent_agent):
    """The Kubernetes API is reachable through the guard."""
    ns, _, name = _pod(transparent_agent)
    url = "https://kubernetes.default.svc/version"
    script = (
        f"wget -Y off --no-check-certificate -q -S -T 15 -O /dev/null {url} "
        "2>&1 | head -1"
    )
    status = http_status(exec_in(ns, name, "agent", script).stdout, url)
    assert status in (200, 401, 403)


def test_agent_container_unprivileged(transparent_agent):
    """Only the init container may change the network; app containers may not."""
    _, pod, _ = _pod(transparent_agent)
    for c in pod["spec"]["containers"]:
        sc = c.get("securityContext") or {}
        assert sc.get("privileged") is not True, f"container {c['name']} is privileged"
        added = (sc.get("capabilities") or {}).get("add") or []
        assert not {"NET_ADMIN", "NET_RAW"} & set(added), (
            f"container {c['name']} adds {added}"
        )
