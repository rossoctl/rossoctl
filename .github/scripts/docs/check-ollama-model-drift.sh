#!/usr/bin/env bash
#
# check-ollama-model-drift.sh
#
# Guards against the demo docs drifting out of sync with the Ollama model name
# that is the source of truth in the rossoctl/examples repo.
#
# Currently scoped to the weather demo ONLY, because it is the sole agent that
# actually publishes an `.env.ollama` in rossoctl/examples. The image, generic,
# file-organizer, and slack demos reference an `.env.ollama` that does not yet
# exist in the examples repo -- see rossoctl/rossoctl#2527. Extend the CHECKS
# array once those files are published.
#
# Exit codes: 0 = in sync, 1 = drift detected, 2 = could not fetch source.

set -euo pipefail

# doc_path <TAB> raw_env_url
CHECKS=(
  "docs/demos/demo-weather-agent.md	https://raw.githubusercontent.com/rossoctl/examples/refs/heads/main/a2a/weather_service/.env.ollama"
)

fetch_with_retry() {
  # $1 = url. Retries to absorb transient network flake.
  local url="$1" attempt
  for attempt in 1 2 3; do
    if curl -fsSL --max-time 20 "$url"; then
      return 0
    fi
    echo "  fetch attempt ${attempt} failed for ${url}" >&2
    sleep $((attempt * 2))
  done
  return 1
}

status=0
for entry in "${CHECKS[@]}"; do
  doc="${entry%%$'\t'*}"
  url="${entry##*$'\t'}"

  echo "Checking ${doc} against ${url}"

  if [[ ! -f "${doc}" ]]; then
    echo "::error file=${doc}::doc not found" >&2
    status=1
    continue
  fi

  env_contents="$(fetch_with_retry "${url}")" || {
    echo "::error::could not fetch ${url} after retries (network flake?)" >&2
    status=2
    continue
  }

  # Extract LLM_MODEL=... (tolerate optional quotes/whitespace).
  model="$(printf '%s\n' "${env_contents}" \
    | grep -iE '^[[:space:]]*LLM_MODEL[[:space:]]*=' \
    | head -1 \
    | sed -E 's/^[^=]*=[[:space:]]*//; s/^["'\'']//; s/["'\'']$//; s/[[:space:]]*$//')"

  if [[ -z "${model}" ]]; then
    echo "::error::no LLM_MODEL found in ${url}" >&2
    status=2
    continue
  fi

  if grep -qF -- "${model}" "${doc}"; then
    echo "  OK: '${model}' present in ${doc}"
  else
    echo "::error file=${doc}::model '${model}' from ${url} not found in ${doc} (docs drifted?)" >&2
    status=1
  fi
done

if [[ "${status}" -eq 0 ]]; then
  echo "All Ollama model references are in sync."
fi
exit "${status}"
