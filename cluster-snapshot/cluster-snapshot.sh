#!/usr/bin/env bash
set -euo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
  printf 'kubectl is required but was not found in PATH.\n' >&2
  exit 127
fi

context="$(kubectl config current-context)" || {
  printf 'Could not determine the current kubectl context.\n' >&2
  exit 1
}

printf 'Context: %s\n\n' "${context}"
printf 'Nodes:\n'
kubectl get nodes -o wide

printf '\nNamespaces:\n'
kubectl get namespaces

printf '\nPending pods:\n'
kubectl get pods --all-namespaces --field-selector=status.phase=Pending

printf '\nFailed pods:\n'
kubectl get pods --all-namespaces --field-selector=status.phase=Failed