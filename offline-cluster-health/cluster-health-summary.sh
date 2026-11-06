#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s [snapshot.tsv]\n' "${0##*/}"
    printf 'Summarize a local tab-separated cluster snapshot; no cluster connection is made.\n'
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

input_file="${1:-$(dirname "$0")/examples/cluster-health.tsv}"
if [[ ! -r "$input_file" ]]; then
    printf 'Cannot read snapshot: %s\n' "$input_file" >&2
    exit 2
fi

degraded_deployments=0
unhealthy_pods=0
unhealthy_nodes=0

printf 'Cluster snapshot report: %s\n' "${input_file##*/}"
while IFS=$'\t' read -r kind namespace name current desired status || [[ -n "${kind:-}" ]]; do
    [[ -z "$kind" || "$kind" == \#* ]] && continue

    case "$kind" in
        deployment)
            if [[ ! "$current" =~ ^[0-9]+$ || ! "$desired" =~ ^[0-9]+$ ]]; then
                printf 'Invalid replica counts for %s/%s\n' "$namespace" "$name" >&2
                exit 2
            fi
            if (( current < desired )); then
                printf 'Degraded deployment: %s/%s (%s/%s ready)\n' "$namespace" "$name" "$current" "$desired"
                degraded_deployments=$((degraded_deployments + 1))
            fi
            ;;
        pod)
            case "$status" in
                Pending|Failed|CrashLoopBackOff|Unknown)
                    printf 'Unhealthy pod: %s/%s (%s)\n' "$namespace" "$name" "$status"
                    unhealthy_pods=$((unhealthy_pods + 1))
                    ;;
            esac
            ;;
        node)
            case "$status" in
                NotReady|MemoryPressure|DiskPressure|PIDPressure)
                    printf 'Node issue: %s (%s)\n' "$name" "$status"
                    unhealthy_nodes=$((unhealthy_nodes + 1))
                    ;;
            esac
            ;;
        *)
            printf 'Unknown record type: %s\n' "$kind" >&2
            exit 2
            ;;
    esac
done < "$input_file"

finding_count=$((degraded_deployments + unhealthy_pods + unhealthy_nodes))
printf '\nSummary: %s degraded deployment(s), %s unhealthy pod(s), %s node issue(s)\n' \
    "$degraded_deployments" "$unhealthy_pods" "$unhealthy_nodes"

if (( finding_count > 0 )); then
    exit 1
fi