#!/usr/bin/env bash
# Guard: charts/rossoctl-deps/files/mesh-recover.sh must be a verbatim copy of
# scripts/k8s/mesh-recover.sh (Helm .Files.Get cannot read outside the chart, so the mesh
# self-heal CronJob (rossoctl/rossoctl#1899 Part B) mounts a copy). Re-sync with:
#   cp scripts/k8s/mesh-recover.sh charts/rossoctl-deps/files/mesh-recover.sh
set -euo pipefail
SRC="scripts/k8s/mesh-recover.sh"
DST="charts/rossoctl-deps/files/mesh-recover.sh"
if ! diff -q "$SRC" "$DST" >/dev/null 2>&1; then
  echo "error: $DST is out of sync with $SRC" >&2
  echo "  re-sync: cp $SRC $DST" >&2
  exit 1
fi
echo "mesh-recover.sh chart copy is in sync ✓"
