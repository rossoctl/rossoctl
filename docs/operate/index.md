---
title: Install and operate
sidebar_label: Overview
description: Installation targets, observability and diagnosis.
sidebar_position: 1
---

This section is for a platform engineer. If you want a cluster for an evaluation, use
[Quickstart on Kubernetes](../get-started/kubernetes.md). That page is shorter and omits the options.

## Select an installation target

| Target | Page | Status |
| --- | --- | --- |
| Kind, for local development and tests | [Install on Kubernetes](install-kubernetes.md) | Ready |
| OpenShift | [Install on OpenShift](install-openshift.md) | Ready |
| Any cluster, with Helm and OCI charts | [Install with Helm](install-helm.md) | Beta |

Each target needs the same decision about identity. See
[Authentication modes](../security/authentication-modes.md). Select SPIFFE if you install SPIRE.

## Operate the platform

- [Observability](observability.md) covers the traces, the network diagram and the metrics.
- [Troubleshooting](troubleshooting.md) covers the failures that occur most often, and the recovery for
  each one.

## Machine size

Rossoctl has many components. On a Kind cluster with one node, the platform pods alone can request
almost 4 CPUs before an agent starts.

| Profile | Memory | CPUs | What operates |
| --- | --- | --- | --- |
| Recommended | 18 GiB | 6 | The ambient mesh, SPIRE, the console, the backend, and a build from source. |
| Minimum | 16 GiB | 4 | The core platform and the console. You must deploy each agent from an image. |
| Below the minimum | — | 4 or fewer | The installation usually completes. A build from source stays in the `Pending` state. |

The installer examines the machine and gives a **warning** below 18 GiB or 6 CPUs. It does not stop.
These values are therefore recommendations and not limits.

## Subjects that have no page yet

These subjects are necessary for production use and have no page on this site:

- An upgrade from one release to the next release.
- High availability, and how to add capacity.
- More than one team on one cluster: namespace isolation, quotas and token limits.
- Backup and restoration.

Ask in [Slack](https://ibm.biz/rossoctl-slack). If you find a correct method, a pull request for these
documents is welcome.
