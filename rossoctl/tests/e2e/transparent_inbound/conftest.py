"""Fixtures for the transparent-inbound E2E suite.

Deploys two agents into a scratch namespace — one with
``inboundInterception: transparent``, one with the default ``reverse-proxy`` —
so the bypass property can be asserted against a control rather than in
isolation. A single-shape run cannot distinguish "validation works" from
"nothing reached the agent at all".
"""

import json
import os
import pathlib
import re
import subprocess
import tempfile
import time

import pytest

# Pre-onboarded namespaces rather than fresh ones. A new namespace lacks the
# platform's per-namespace plumbing (authbridge-config, and the Keycloak client
# registration that produces each agent's credentials Secret), so an injected pod
# there never starts — for reasons that have nothing to do with this feature. The
# installer creates team1/team2 already onboarded; use those.
NS_TRANSPARENT = os.environ.get("TI_NS_TRANSPARENT", "team1")
NS_CONTROL = os.environ.get("TI_NS_CONTROL", "team2")
# A stand-in agent, not a real one: the suite tests the interception boundary,
# not agent behavior. nginx-unprivileged is Alpine-based (so the same image
# doubles as the probe, via busybox wget) and is already cached on Kind nodes.
AGENT_IMAGE = os.environ.get(
    "TI_AGENT_IMAGE", "docker.io/nginxinc/nginx-unprivileged:1.29.1-alpine"
)
PROBE_IMAGE = os.environ.get("TI_PROBE_IMAGE", AGENT_IMAGE)
# The port the agent binds. Under transparent interception it must stay this;
# under reverse-proxy the operator relocates the agent off it.
AGENT_PORT = int(os.environ.get("TI_AGENT_PORT", "8000"))
READY_TIMEOUT = int(os.environ.get("TI_READY_TIMEOUT", "180"))
# Secret holding a staged SVID for the mTLS module's probe pod.
SVID_SECRET_NAME = "ti-e2e-mtls-svid"
# In-cluster HTTP target for the egress reach tests; always deployed on Kind.
EGRESS_TARGET = os.environ.get(
    "TI_EGRESS_TARGET", "http://rossoctl-ui.rossoctl-system.svc.cluster.local:8080/"
)


def kubectl_run(*args, stdin=None):
    """Run kubectl and return the CompletedProcess (returncode, stdout, stderr).

    The full result matters to any caller that must tell "the command failed" apart
    from "the command succeeded and produced nothing" — kubectl() collapses both to
    an empty string.
    """
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        input=stdin,
        timeout=120,
    )


def kubectl(*args, check=True, stdin=None):
    """Run kubectl and return stdout. Raises on non-zero unless check=False."""
    proc = kubectl_run(*args, stdin=stdin)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"kubectl {' '.join(args)} failed ({proc.returncode}):\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc.stdout


def kubectl_rc(*args) -> int:
    """Run kubectl and return only its exit code.

    Needed because kubectl reports conditions like "already exists" on STDERR,
    which kubectl() drops — so a caller that must distinguish "created" from
    "already satisfied" cannot do it by inspecting stdout.
    """
    return kubectl_run(*args).returncode


# Secrets this suite created, so teardown can remove them. Module-level because
# the fixture that creates them is not the one that cleans up.
_stubbed: list = []


def kubectl_json(*args):
    return json.loads(kubectl(*args, "-o", "json"))


def _stub_credentials(namespace: str, name: str) -> bool:
    """Create a placeholder for the per-agent Keycloak credentials Secret.

    Opt-in via TI_STUB_CREDENTIALS=1, and deliberately NOT the default: stubbing
    by default would let this suite pass on a cluster whose Keycloak client
    registration is broken, hiding a real platform failure behind a green run.

    Anything created is recorded in _stubbed so teardown removes it: a placeholder
    credential Secret must not outlive the run in a shared namespace.

    The stub is sound for what this suite asserts. The Secret is mounted for
    OUTBOUND token-exchange; inbound validation rejects a request with no
    Authorization header before any IdP contact, so its contents cannot influence
    the 401 assertions. It would NOT be sound for a test that needs a valid token.
    """
    if os.environ.get("TI_STUB_CREDENTIALS") != "1":
        return False
    secret = kubectl(
        "get",
        "pods",
        "-n",
        namespace,
        "-l",
        f"app={name}",
        "-o",
        r"jsonpath={.items[*].metadata.annotations.rossoctl\.io/keycloak-client-credentials-secret-name}",
        check=False,
    ).split()
    created = False
    for sn in {s for s in secret if s}:
        # Keyed on the exit code, not on stdout: kubectl writes "already exists"
        # to stderr, which kubectl() drops — so matching stdout would report
        # failure forever and re-attempt the create on every poll.
        rc = kubectl_rc(
            "create",
            "secret",
            "generic",
            sn,
            "-n",
            namespace,
            "--from-literal=client-id.txt=" + name,
            "--from-literal=client-secret.txt=stub-not-used-for-inbound-denial",
        )
        # Recorded either way: if it already exists, a previous run of THIS suite
        # created it and it still needs removing.
        if (namespace, sn) not in _stubbed:
            _stubbed.append((namespace, sn))
        if rc == 0:
            created = True
    return created


def _wait_ready(namespace: str, name: str, timeout: int):
    """Block until the deployment reports all replicas ready."""
    deadline = time.monotonic() + timeout
    last = ""
    stubbed = False
    while time.monotonic() < deadline:
        out = kubectl(
            "get",
            "deployment",
            name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.readyReplicas}/{.status.replicas}",
            check=False,
        )
        last = out
        if out.strip() == "1/1":
            # Ready alone is not enough: the AgentRuntime controller labels the
            # pod template after the Deployment exists, so the FIRST ready pod
            # may predate injection. Require the sidecar to be present.
            pods = kubectl(
                "get",
                "pods",
                "-n",
                namespace,
                "-l",
                f"app={name}",
                "-o",
                "jsonpath={.items[*].spec.containers[*].name}",
                check=False,
            )
            if "authbridge-proxy" in pods:
                return
        if not stubbed:
            stubbed = _stub_credentials(namespace, name)
        time.sleep(3)
    pods = kubectl("get", "pods", "-n", namespace, "-o", "wide", check=False)
    events = kubectl(
        "get", "events", "-n", namespace, "--sort-by=.lastTimestamp", check=False
    )
    # A missing per-agent Keycloak credentials Secret blocks EVERY injected pod,
    # including default reverse-proxy ones, so it says nothing about this feature.
    # Skip with the cause named rather than fail and point suspicion at the
    # interception rules.
    if "rossoctl-keycloak-client-credentials" in events and "not found" in events:
        pytest.skip(
            "(set TI_STUB_CREDENTIALS=1 to stub the Secret and test the "
            "interception boundary anyway) "
            "platform gap, not a feature failure: the per-agent Keycloak "
            "client-credentials Secret was never created, so the injected pod "
            "cannot mount it. This blocks EVERY injected pod, including default "
            "reverse-proxy ones, so it says nothing about interception. The "
            "operator's ClientRegistration controller creates that Secret and "
            "logs its exact reason for not doing so, then requeues every 30s — "
            "so read the log rather than guessing:\n"
            "  kubectl logs -n rossoctl-system deployment/rossoctl-controller-manager "
            "| grep -E 'cannot resolve|waiting for|registration failed|skipping'\n"
            "Known reasons, all of which it prints verbatim: the pod template's "
            "serviceAccountName is 'default' while SPIRE is on (this suite sets a "
            "dedicated SA precisely to avoid it — check the manifest still does); "
            "KEYCLOAK_URL/KEYCLOAK_REALM absent from the namespace's "
            "authbridge-config; the Keycloak admin Secret missing from "
            "rossoctl-system; or the cluster feature gates disabling "
            "clientRegistration. Note the k8s.keycloak.org CRD is NOT in this "
            "path — the controller uses Keycloak's admin REST API directly."
        )
    raise AssertionError(
        f"deployment {namespace}/{name} not ready within {timeout}s "
        f"(readyReplicas={last})\npods:\n{pods}\nevents (tail):\n{events[-2000:]}"
    )


def _agent_manifest(namespace: str, name: str) -> str:
    """A minimal HTTP agent Deployment + Service.

    Declares containerPort explicitly: the reverse-proxy mechanism relocates
    Ports[0], so the declared value is what the test inspects to tell the two
    mechanisms apart.
    """
    return f"""
# A dedicated ServiceAccount, named after the workload, is a hard requirement
# rather than tidiness. With SPIRE enabled the operator's ClientRegistration
# controller derives the Keycloak client ID from the pod template's
# serviceAccountName; on "default" it refuses -- "SPIRE enabled: set
# spec.template.spec.serviceAccountName to a dedicated ServiceAccount" -- and
# requeues every 30s forever, so the per-agent credentials Secret is never
# created and the injected pod never leaves FailedMount. The AuthBridge webhook
# does create such an SA and sets it on the *pod*, but the controller reads the
# *Deployment template*, which the webhook never touches, so the webhook's fixup
# is invisible to it. Creating the SA explicitly is what the platform's own
# agent deploy scripts do, and it is the only half of that pair we control here.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {name}
  namespace: {namespace}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      serviceAccountName: {name}
      containers:
        - name: agent
          image: {AGENT_IMAGE}
          imagePullPolicy: IfNotPresent
          # Rewrite nginx's listen directive from PORT so this stand-in behaves
          # like a PORT-honoring agent framework. Without that the reverse-proxy
          # control could not be exercised: an agent that ignores PORT collides
          # with AuthBridge on the stolen port and the pod never starts (which is
          # itself one of the failure modes transparent interception removes).
          command: ["/bin/sh", "-c"]
          args:
            - |
              sed -i "s/listen  *8080/listen ${{PORT:-{AGENT_PORT}}}/" /etc/nginx/conf.d/default.conf
              exec nginx -g 'daemon off;'
          env:
            - name: PORT
              value: "{AGENT_PORT}"
          ports:
            - containerPort: {AGENT_PORT}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
  namespace: {namespace}
spec:
  selector:
    app: {name}
  ports:
    - port: {AGENT_PORT}
      targetPort: {AGENT_PORT}
---
# The AgentRuntime is what marks this workload as an agent. The platform's
# agent-label-protection ValidatingAdmissionPolicy rejects a hand-applied
# rossoctl.io/type label, so injection must be driven through the CR — which is
# also how agents are deployed for real.
apiVersion: agent.rossoctl.dev/v1alpha1
kind: AgentRuntime
metadata:
  name: {name}
  namespace: {namespace}
spec:
  type: agent
  mtlsMode: disabled
  tlsBridgeMode: disabled
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {name}
"""


def _strip_top_level(body: str, keys: tuple, with_children: bool = False) -> str:
    """Drop the given top-level YAML keys, optionally with their indented children."""
    out, skipping = [], False
    for line in body.splitlines():
        if skipping:
            # A blank line or any non-indented line ends the block.
            if line.strip() and line[:1].isspace():
                continue
            skipping = False
        if any(re.match(rf"^{k}\s*:", line) for k in keys):
            skipping = with_children
            continue
        out.append(line)
    return "\n".join(out)


def _read_namespace_config(namespace: str) -> str:
    return kubectl(
        "get",
        "configmap",
        "authbridge-runtime-config",
        "-n",
        namespace,
        "-o",
        r"jsonpath={.data.config\.yaml}",
        check=False,
    )


def _write_namespace_config(namespace: str, body: str):
    cm = kubectl(
        "create",
        "configmap",
        "authbridge-runtime-config",
        "-n",
        namespace,
        f"--from-literal=config.yaml={body}",
        "--dry-run=client",
        "-o",
        "yaml",
    )
    kubectl("apply", "-f", "-", stdin=cm)


# The namespace config as it was before this suite touched it, captured once per
# namespace. Fixtures restore from here rather than from whatever they observed,
# so adding a second module that flips the same namespace cannot make restoration
# order-dependent.
_baseline: dict = {}


def _set_mechanism(namespace: str, mechanism: str, mtls: str = "") -> str:
    """Prepend the inbound mechanism to the namespace config; return the original.

    Edits in place rather than replacing the ConfigMap: the existing body carries
    the namespace's real jwt-validation issuer and token-exchange settings, and a
    synthetic replacement would exercise a pipeline no real deployment runs.
    """
    original = _read_namespace_config(namespace)
    _baseline.setdefault(namespace, original)
    if not original.strip():
        pytest.skip(
            f"namespace {namespace} has no authbridge-runtime-config — not an "
            "onboarded rossoctl namespace (set TI_NS_TRANSPARENT / TI_NS_CONTROL)"
        )
    # Strip keys a previous run may have left before prepending. Prepending blind
    # is not idempotent: with TI_KEEP=1, or after a killed run that skipped
    # teardown, the next run would emit duplicate top-level YAML keys.
    stripped = _strip_top_level(original, ("inboundInterception", "egressEnforcement"))
    prefix = f"inboundInterception: {mechanism}\negressEnforcement: enforce-redirect\n"
    if mtls:
        # mtls is a nested block, so it cannot be prepended as a bare line the way
        # the scalar keys are — and an existing block has to be removed with its
        # indented children or the two would merge into one malformed mapping.
        stripped = _strip_top_level(stripped, ("mtls",), with_children=True)
        prefix += f"mtls:\n  mode: {mtls}\n"
    body = prefix + stripped.lstrip("\n")
    _write_namespace_config(namespace, body)
    return original


@pytest.fixture(scope="session")
def linux_nodes():
    """Skip the suite where iptables interception cannot work."""
    nodes = kubectl_json("get", "nodes")
    for node in nodes.get("items", []):
        if node["status"]["nodeInfo"]["operatingSystem"] != "linux":
            pytest.skip("transparent inbound is Linux/iptables only")
    return True


def _deploy(ns: str, name: str, mechanism: str, mtls: str = "") -> str:
    original = _set_mechanism(ns, mechanism, mtls)
    kubectl("apply", "-f", "-", stdin=_agent_manifest(ns, name))
    try:
        _wait_ready(ns, name, READY_TIMEOUT)
        _require_platform_support(ns, name, mechanism)
    except BaseException:
        _teardown(ns, name, original)
        raise
    return original


def _require_platform_support(ns: str, name: str, mechanism: str):
    """Skip when the deployed platform predates transparent inbound.

    This suite runs in the shared e2e target list, so it executes against whatever
    images a cluster happens to have. An operator that does not know
    `inboundInterception` silently ignores the namespace flip and port-steals
    instead — which would fail the transparent assertions for a reason that has
    nothing to do with the code under test. Detect it from the injected pod (the
    sidecar declares `transparent-in` only when the feature is present) and skip
    with the cause named.
    """
    if mechanism != "transparent":
        return
    pod = agent_pod(ns, name)
    proxy = next(
        (c for c in pod["spec"]["containers"] if c["name"] == "authbridge-proxy"),
        None,
    )
    if proxy is None:
        return  # a missing sidecar is a real failure; let the tests report it
    if not any(p.get("name") == "transparent-in" for p in proxy.get("ports", [])):
        pytest.skip(
            "deployed platform predates transparent inbound interception: the "
            "injected sidecar declares no transparent-in port, so the namespace's "
            "inboundInterception was ignored. Needs an operator and authbridge "
            "built with rossoctl/cortex#330."
        )


def _teardown(ns: str, name: str, original: str):
    if os.environ.get("TI_KEEP") == "1":
        return
    # The ServiceAccount is deleted explicitly because nothing garbage-collects it:
    # the AuthBridge webhook creates per-agent SAs with no ownerReference, so they
    # outlive the workload. Ours is in the manifest, but the delete also sweeps one
    # a pre-fix run of this suite left behind. The credentials Secret needs no entry
    # here -- the controller owner-references it to the Deployment, so it GCs itself.
    for kind in ("deployment", "service", "agentruntime", "serviceaccount"):
        kubectl("delete", kind, name, "-n", ns, "--wait=false", check=False)
    # Restoring the namespace config matters: these are SHARED namespaces, so
    # leaving one flipped to transparent would silently change every other agent
    # in it on its next pod recreation.
    restore = _baseline.get(ns, original)
    if restore.strip():
        _write_namespace_config(ns, restore)
    # Remove any placeholder credentials Secret this suite created. Leaving a fake
    # credential in a shared namespace is worse than the gap it papered over.
    for entry in [t for t in _stubbed if t[0] == ns]:
        kubectl(
            "delete", "secret", entry[1], "-n", entry[0], "--wait=false", check=False
        )
        _stubbed.remove(entry)


@pytest.fixture(scope="session")
def transparent_agent(linux_nodes):
    """Agent deployed with inboundInterception: transparent."""
    ns, name = NS_TRANSPARENT, "ti-e2e-agent"
    original = _deploy(ns, name, "transparent")
    yield {"namespace": ns, "name": name}
    _teardown(ns, name, original)


@pytest.fixture(scope="module")
def mtls_strict_agent(linux_nodes):
    """Transparent agent with mTLS strict.

    Module-scoped, not session-scoped: it flips the same namespace the permissive
    fixture uses, so it must set up and tear down within its own module rather
    than persisting for the session. Restoration comes from _baseline, so the
    order the two modules run in cannot change the namespace's final state.
    """
    ns, name = NS_TRANSPARENT, "ti-e2e-mtls"
    original = _deploy(ns, name, "transparent", mtls="strict")
    yield {"namespace": ns, "name": name}
    _teardown(ns, name, original)


def _skip_or_fail_svid(filename: str, pod: str, proc) -> None:
    """Decide whether an unreadable SVID file is a legitimate skip or a failure.

    Only one cause justifies skipping the completed-handshake test: SPIRE genuinely
    supplied no SVID, which surfaces as ``cat`` reporting the file does not exist.
    Everything else — a renamed container, a moved path, a pod mid-restart, a
    transient API error — is an infrastructure regression, and skipping on it would
    silently green the one security-critical case in this module. So: skip on
    proven absence, raise on anything unexplained.
    """
    stderr = (proc.stderr or "").strip()
    # Matches both coreutils ("cat: /opt/x: No such file or directory") and busybox
    # ("cat: can't open '/opt/x': No such file or directory"). Deliberately not the
    # broader "not found", which also matches "executable file not found" (no cat in
    # the image) and "container not found" — neither of which is an absent SVID.
    if "no such file" in stderr.lower():
        pytest.skip(
            f"sidecar has no /opt/{filename}: SPIRE is not supplying SVIDs on this "
            "cluster, so a completed-handshake test is not possible here"
        )
    raise RuntimeError(
        f"could not read /opt/{filename} from {pod}/authbridge-proxy "
        f"(exit {proc.returncode}) — refusing to skip the mTLS handshake test on an "
        f"unexplained failure:\nstdout: {proc.stdout!r}\nstderr: {stderr!r}"
    )


@pytest.fixture(scope="module")
def svid_secret(mtls_strict_agent):
    """Stage the agent sidecar's own SVID as a Secret a probe pod can mount.

    Reuses the workload's real SVID rather than minting one: any identity in the
    trust domain satisfies RequireAndVerifyClientCert, and borrowing the existing
    one avoids standing up a second SPIRE registration just to hold a certificate.
    The point of the test is that the handshake completes at all, not which
    identity completes it.
    """
    ns, name = mtls_strict_agent["namespace"], mtls_strict_agent["name"]
    pod = agent_pod(ns, name)["metadata"]["name"]
    args = ["create", "secret", "generic", SVID_SECRET_NAME, "-n", ns]
    # A private 0700 directory, removed on the way out: the SVID *private key*
    # passes through here, and an SVID being short-lived is not a reason to leave
    # key material on the runner. The context manager also covers the skip/raise
    # paths below, which an explicit unlink at the end would not.
    with tempfile.TemporaryDirectory(prefix=f"{SVID_SECRET_NAME}-") as tmpdir:
        for f in ("svid.pem", "svid_key.pem", "svid_bundle.pem"):
            proc = kubectl_run(
                "exec",
                pod,
                "-n",
                ns,
                "-c",
                "authbridge-proxy",
                "--",
                "cat",
                f"/opt/{f}",
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                _skip_or_fail_svid(f, pod, proc)
            path = pathlib.Path(tmpdir) / f
            path.write_text(proc.stdout)
            args.append(f"--from-file={f}={path}")
        rendered = kubectl(*args, "--dry-run=client", "-o", "yaml")
    kubectl("apply", "-f", "-", stdin=rendered)
    yield SVID_SECRET_NAME
    kubectl("delete", "secret", SVID_SECRET_NAME, "-n", ns, "--wait=false", check=False)


@pytest.fixture(scope="session")
def reverse_proxy_agent(linux_nodes):
    """Control: agent deployed with the default port-stealing mechanism."""
    ns, name = NS_CONTROL, "ti-e2e-control"
    original = _deploy(ns, name, "reverse-proxy")
    yield {"namespace": ns, "name": name}
    _teardown(ns, name, original)


def agent_pod(namespace: str, name: str) -> dict:
    pods = kubectl_json("get", "pods", "-n", namespace, "-l", f"app={name}")
    running = [p for p in pods["items"] if p["status"]["phase"] == "Running"]
    assert running, f"no Running pod for {namespace}/{name}"
    return running[0]


def container(pod: dict, name: str) -> dict:
    for c in pod["spec"]["containers"] + pod["spec"].get("initContainers", []):
        if c["name"] == name:
            return c
    raise AssertionError(
        f"container {name} not found in pod {pod['metadata']['name']}; "
        f"have {[c['name'] for c in pod['spec']['containers']]}"
    )


def env_of(c: dict, key: str):
    for e in c.get("env", []):
        if e["name"] == key:
            return e
    return None


def curl_from_probe(namespace: str, url: str) -> int:
    """Dial url from a throwaway pod in `namespace` and return the HTTP status.

    A separate pod is essential: the whole point is to exercise the pod-to-pod
    path. Dialing from inside the agent pod would traverse loopback, which is
    inside the trust boundary and deliberately not intercepted.
    """
    # busybox wget rather than curl: it ships in the Alpine agent image, which is
    # already cached on the nodes, so the probe needs no registry pull. It writes
    # the status line to stderr, hence the 2>&1.
    out = kubectl(
        "run",
        f"ti-probe-{int(time.time() * 1000) % 100000}",
        "-n",
        namespace,
        "--rm",
        "-i",
        "--restart=Never",
        f"--image={PROBE_IMAGE}",
        "--image-pull-policy=IfNotPresent",
        "--quiet",
        "--command",
        "--",
        "sh",
        "-c",
        f"wget -q -S -T 15 -O /dev/null '{url}' 2>&1 | head -1",
        check=False,
    )
    return http_status(out, url)


def exec_in(
    namespace: str, pod: str, container_name: str, script: str
) -> subprocess.CompletedProcess:
    """Run a shell script in one container of a pod."""
    return kubectl_run(
        "exec", pod, "-n", namespace, "-c", container_name, "--", "sh", "-c", script
    )


def http_status(out: str, url: str) -> int:
    """Parse the HTTP status from busybox `wget -S` output.

    Parsed from the output, not the exit code: busybox wget exits non-zero on 4xx/5xx.
    """
    for token in out.split():
        if token.isdigit() and len(token) == 3 and token[0] in "12345":
            return int(token)
    raise AssertionError(
        f"probe produced no HTTP status for {url}; raw output: {out!r}"
    )
