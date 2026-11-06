#!/usr/bin/env bash
set -euo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
  printf 'kubectl is required but was not found in PATH.\n' >&2
  exit 127
fi

if (( $# > 1 )); then
  printf 'Usage: %s [namespace]\n' "$0" >&2
  exit 2
fi

namespace="${1:-}"
context="$(kubectl config current-context)" || {
  printf 'Could not determine the current kubectl context.\n' >&2
  exit 1
}

printf 'Context: %s\n' "${context}"

if [[ -n "${namespace}" ]]; then
  printf 'Namespace: %s\n\n' "${namespace}"
  kubectl get poddisruptionbudgets --namespace "${namespace}" -o wide
else
  printf 'Scope: all namespaces\n\n'
  kubectl get poddisruptionbudgets --all-namespaces -o wide
fi