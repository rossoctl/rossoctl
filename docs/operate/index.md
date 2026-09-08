---
title: Deploy and operate
sidebar_label: Overview
description: Install targets, observability, and troubleshooting.
sidebar_position: 1
---

For platform engineers. If you just want a cluster to try things on, use
[Quickstart: Kubernetes](../get-started/kubernetes.md) — it is shorter and skips the options.

## Install

| Target | Page | Status |
| --- | --- | --- |
| Kind — local development, CI | [Install on Kubernetes](install-kubernetes.md) | Ready |
| OpenShift | [Install on OpenShift](install-openshift.md) | Ready |
| Any cluster, via Helm and OCI charts | [Install with Helm](install-helm.md) | Beta |

Every install variant needs the same decision about identity — see
[Authentication modes](../security/authentication-modes.md). Pick SPIFFE if you are installing SPIRE.

## Run

- [Observability](observability.md) — traces, network topology, and per-agent metrics.
- [Troubleshooting](troubleshooting.md) — the failures people actually hit, and how to recover.

## Sizing

Rossoctl is a lot of moving parts. On a single-node Kind cluster the platform pods alone can request
close to 4 CPUs before any agent runs.

| Profile | RAM | CPUs | What fits |
| --- | --- | --- | --- |
| Recommended | 18 GiB | 6 | Istio ambient, SPIRE, console, backend, and building agents from source. |
| Minimum | 16 GiB | 4 | Core and console. Deploy agents from prebuilt images only. |
| Below that | — | ≤4 | Often installs. Source builds stay `Pending` on `Insufficient cpu`. |

The installer runs a pre-flight check and **warns** below 18 GiB or 6 CPUs. It does not fail, so these
are recommendations rather than enforced limits.

## Not yet documented

These matter in production and have no page here yet:

- Upgrades between releases.
- Scaling and high availability.
- Multi-tenancy — namespace isolation, quotas, and token budgets across teams.
- Backup and restore.

For now, ask in [Slack](https://ibm.biz/rossoctl-slack). If you work out a good answer, a pull request
against these docs is welcome.
