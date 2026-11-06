#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s --resource-group NAME --cluster NAME [--subscription ID]\n' "$0"
  printf 'List AKS node-pool state without changing the active Azure subscription.\n'
}

resource_group=""
cluster_name=""
subscription=""

while (( $# > 0 )); do
  case "$1" in
    --resource-group|-g)
      (( $# >= 2 )) || { usage >&2; exit 2; }
      resource_group="$2"
      shift 2
      ;;
    --cluster|-n)
      (( $# >= 2 )) || { usage >&2; exit 2; }
      cluster_name="$2"
      shift 2
      ;;
    --subscription|-s)
      (( $# >= 2 )) || { usage >&2; exit 2; }
      subscription="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${resource_group}" || -z "${cluster_name}" ]]; then
  usage >&2
  exit 2
fi

if ! command -v az >/dev/null 2>&1; then
  printf 'Azure CLI (az) is required but was not found in PATH.\n' >&2
  exit 127
fi

az_args=(--resource-group "${resource_group}" --cluster-name "${cluster_name}")
if [[ -n "${subscription}" ]]; then
  az_args+=(--subscription "${subscription}")
fi

az aks nodepool list "${az_args[@]}" \
  --query '[].{Name:name,State:provisioningState,Mode:mode,Nodes:count,VMSize:vmSize,OS:osType,KubernetesVersion:orchestratorVersion}' \
  --output table