#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s --selector LABEL_SELECTOR [--context CONTEXT]\n' "$0"
}

selector=''
context=''

while [[ $# -gt 0 ]]; do
    case "$1" in
        --selector|-l)
            if [[ $# -lt 2 || -z "$2" ]]; then
                printf 'error: --selector requires a non-empty value\n' >&2
                usage >&2
                exit 2
            fi
            selector="$2"
            shift 2
            ;;
        --context)
            if [[ $# -lt 2 || -z "$2" ]]; then
                printf 'error: --context requires a non-empty value\n' >&2
                usage >&2
                exit 2
            fi
            context="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'error: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$selector" ]]; then
    printf 'error: --selector is required\n' >&2
    usage >&2
    exit 2
fi

if [[ -z "$context" ]]; then
    context="$(kubectl config current-context)" || {
        printf 'error: unable to determine the current Kubernetes context\n' >&2
        exit 2
    }
fi
if [[ -z "$context" ]]; then
    printf 'error: no Kubernetes context is selected; pass --context\n' >&2
    exit 2
fi

namespaces="$(kubectl --context "$context" get namespaces --selector "$selector" \
    -o 'custom-columns=NAME:.metadata.name,STATUS:.status.phase' --no-headers)" || {
    printf 'error: namespace query failed for context %s\n' "$context" >&2
    exit 1
}

printf 'Context: %s\nSelector: %s\n' "$context" "$selector"
if [[ -z "${namespaces//[[:space:]]/}" ]]; then
    printf 'No namespaces matched the selector.\n'
else
    printf 'NAME\tSTATUS\n%s\n' "$namespaces"
fi