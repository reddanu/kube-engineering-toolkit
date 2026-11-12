#!/usr/bin/env bash

# Discover and uninstall configured Helm releases across kubeconfig contexts.
#
# Requirements: Bash, kubectl, Helm, jq, kubeconfig access to all the clusters,
# and permission to list and uninstall releases in the target namespaces.
#
# Before running, set the values below:
#   RELEASE_NAME=("my-release" "another-release") # Helm release names
#   NAMESPACE=("namespace-1" "namespace-2")
#   CONTEXTS=("context-1" "context-2" "context-3")
#
# List available contexts with: kubectl config get-contexts -o name
# Verify the contexts point to the intended clusters; different context names
# can still refer to the same cluster. Do not commit environment-specific values.
#
# From the kube-deploy-cleanup repository root:
#   bash kube-deploy-cleanup/uninstall-helm-releases.sh --dry-run
#   bash kube-deploy-cleanup/uninstall-helm-releases.sh --apply
#
# The first command contacts the clusters and shows discovered release metadata,
# marking configured matches and skipped releases; it does not uninstall anything.
# Helm may read release records stored as Secrets.
# The second command repeats discovery and asks for y before uninstalling.
# Each configured namespace is checked in each context; only exact release-name
# matches are targeted. Historical uninstalled and superseded releases are skipped.
# Optional: --env prd|np adds a label only; it does not select or
# validate the contexts. Use --help for the command syntax.
#
# Helm uninstall affects the entire release, not just its deployments. Review
# the release and coordinate with its owners before running; retained resources
# may remain, and GitOps may recreate the release. The script waits up to five
# minutes per context, continues after failures, and exits nonzero if any fail.


set -euo pipefail

RELEASE_NAME=(
  "why-we-need-to-delete-api" 
)

NAMESPACE=(
  "dev-k8s-test" 
  "int-k8s-test" 
  "trn-k8s-test" 
  "prd-k8s-test"
)

CONTEXTS=(
  "a-k8s-test" 
  "b-k8s-test" 
  "c-k8s-test"
)

usage() {
  printf '%s\n' \
    'Helm Release Cleanup' \
    '====================' \
    'Discover configured Helm releases across the clusters.' \
    '' \
    "Usage: bash ${0##*/} [OPTIONS]" \
    '' \
    'Configuration:' \
    '  Edit RELEASE_NAME, NAMESPACE, and CONTEXTS at the top of the script.' \
    '  Every namespace is checked in each context; release names match exactly.' \
    '  CONTEXTS must contain the distinct kubeconfig context names.' \
    '  List available contexts: kubectl config get-contexts -o name' \
    '' \
    'Options:' \
    '  --dry-run               Show discovery progress and targets; do not uninstall (default).' \
    '  --apply                 Uninstall after confirming with y.' \
    '  --env prd|np   Add a label; this does not select or verify contexts.' \
    '  -h, --help              Show this help.' \
    '' \
    'Examples:' \
    "  bash ${0##*/} --dry-run Discover and show matching releases." \
    "  bash ${0##*/} --apply   Rediscover, confirm, and uninstall matches." \
    '' \
    'Safety:' \
    '  Helm uninstalls the entire release, not just its deployments.' \
    '  Discovery contacts clusters and Helm may read release records stored as Secrets.' \
    '  Discovery failure in any namespace stops the run before uninstalling.' \
    '  Historical uninstalled and superseded releases are not targeted.' \
    '  GitOps may recreate the release; retained resources may remain.' \
    '  Failures are reported after all the contexts have been attempted.'
}

apply=false
dry_run=false
environment=""
while (( $# > 0 )); do
  case "$1" in
    --apply)
      apply=true
      shift
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --env)
      if (( $# < 2 )); then
        usage >&2
        exit 2
      fi
      case "$2" in
        prd|np ) environment="$2" ;;
        *) printf 'Invalid environment: %s\n' "$2" >&2; exit 2 ;;
      esac
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

if [[ "$apply" == true && "$dry_run" == true ]]; then
  printf 'Choose either --dry-run or --apply, not both.\n' >&2
  exit 2
fi

if (( ${#RELEASE_NAME[@]} == 0 || ${#NAMESPACE[@]} == 0 || ${#CONTEXTS[@]} != 3 )); then
  printf 'Set at least one release, one namespace, and exactly the contexts in the script.\n' >&2
  exit 2
fi

validate_entries() {
  local label="$1"
  shift
  local entries=("$@")
  local index previous value
  for (( index=0; index<${#entries[@]}; index++ )); do
    value="${entries[$index]}"
    if [[ -z "$value" || "$value" == -* || "$value" == *[[:space:]]* ]]; then
      printf '%s entries must be non-empty, not start with a dash, and contain no whitespace.\n' "$label" >&2
      exit 2
    fi
    for (( previous=0; previous<index; previous++ )); do
      if [[ "$value" == "${entries[$previous]}" ]]; then
        printf 'Duplicate %s entry: %s\n' "$label" "$value" >&2
        exit 2
      fi
    done
  done
}

validate_entries 'release name' "${RELEASE_NAME[@]}"
validate_entries 'namespace' "${NAMESPACE[@]}"
validate_entries 'context' "${CONTEXTS[@]}"

for command_name in kubectl helm jq; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '%s is required.\n' "$command_name" >&2
    exit 127
  fi
done
helm_list_help="$(helm list --help)" || {
  printf 'Cannot determine supported Helm list flags.\n' >&2
  exit 1
}
all_flag=""
if printf '%s\n' "$helm_list_help" | grep -E '(^|[[:space:],])--all([[:space:]]|$)' >/dev/null; then
  all_flag="--all"
fi
available_contexts="$(kubectl config get-contexts -o name)" || {
  printf 'Cannot list kubeconfig contexts.\n' >&2
  exit 1
}
for context in "${CONTEXTS[@]}"; do
  if ! printf '%s\n' "$available_contexts" | grep -F -x -- "$context" >/dev/null; then
    printf 'Kubeconfig context not found: %s\n' "$context" >&2
    exit 1
  fi
done

if [[ -n "$environment" ]]; then
  printf 'Environment label (not verified): %s\n' "$environment"
fi

target_contexts=()
target_namespaces=()
target_releases=()
target_charts=()
target_statuses=()
target_count=0
page_size=256

for context in "${CONTEXTS[@]}"; do
  for namespace in "${NAMESPACE[@]}"; do
    offset=0
    while :; do
      if [[ "$apply" != true ]]; then
        printf '\nChecking context: %s | namespace: %s | offset: %s\n' "$context" "$namespace" "$offset"
      fi
      if ! page="$(helm list --kube-context "$context" --namespace "$namespace" ${all_flag:+"$all_flag"} --max "$page_size" --offset "$offset" --output json)"; then
        printf 'Cannot list releases in context %s, namespace %s; no releases were uninstalled.\n' "$context" "$namespace" >&2
        exit 1
      fi
      if ! page_count="$(printf '%s' "$page" | jq -er 'if type == "array" and all(.[]; type == "object" and (.name | type) == "string" and (.chart | type) == "string" and (.status | type) == "string") then length else error("invalid Helm list response") end')"; then
        printf 'Invalid Helm response in context %s, namespace %s; no releases were uninstalled.\n' "$context" "$namespace" >&2
        exit 1
      fi
      if [[ "$apply" != true ]]; then
        printf '  Helm returned %s release(s).\n' "$page_count"
      fi
      matches="$(printf '%s' "$page" | jq -r '.[] | [.name, .chart, .status] | @tsv')"
      while IFS=$'\t' read -r release chart release_status; do
        [[ -z "$release" ]] && continue
        if [[ "$release_status" == uninstalled || "$release_status" == superseded ]]; then
          if [[ "$apply" != true ]]; then
            printf '  SKIP | Release: %s | Chart: %s | Status: %s (historical)\n' "$release" "$chart" "$release_status"
          fi
          continue
        fi
        matched=false
        for configured_release in "${RELEASE_NAME[@]}"; do
          if [[ "$release" == "$configured_release" ]]; then
            target_contexts[$target_count]="$context"
            target_namespaces[$target_count]="$namespace"
            target_releases[$target_count]="$release"
            target_charts[$target_count]="$chart"
            target_statuses[$target_count]="$release_status"
            target_count=$((target_count + 1))
            matched=true
            break
          fi
        done
        if [[ "$apply" != true ]]; then
          if [[ "$matched" == true ]]; then
            printf '  MATCH | Release: %s | Chart: %s | Status: %s\n' "$release" "$chart" "$release_status"
          else
            printf '  SKIP | Release: %s | Chart: %s | Status: %s (not configured)\n' "$release" "$chart" "$release_status"
          fi
        fi
      done <<< "$matches"
      if (( page_count < page_size )); then
        break
      fi
      offset=$((offset + page_count))
    done
  done
done

printf 'Matching Helm releases:\n'
for context in "${CONTEXTS[@]}"; do
  printf '\nCluster context: %s\n' "$context"
  context_count=0
  for (( index=0; index<target_count; index++ )); do
    if [[ "${target_contexts[$index]}" == "$context" ]]; then
      printf '  Namespace: %s | Release: %s | Chart: %s | Status: %s\n' \
        "${target_namespaces[$index]}" "${target_releases[$index]}" "${target_charts[$index]}" "${target_statuses[$index]}"
      context_count=$((context_count + 1))
    fi
  done
  if (( context_count == 0 )); then
    printf '  No matching releases found.\n'
  fi
done
printf '\nTotal matching releases: %s\n' "$target_count"

if [[ "$apply" != true ]]; then
  printf 'Dry run only; no releases were uninstalled. Use --apply to rediscover and proceed.\n'
  exit 0
fi

if (( target_count == 0 )); then
  printf 'No matching releases to uninstall.\n'
  exit 0
fi

printf 'This uninstalls each listed Helm release and its managed resources.\n'
printf 'Continue? [y/N]: '
if ! IFS= read -r confirmation || [[ "$confirmation" != y && "$confirmation" != Y ]]; then
  printf 'Not confirmed; no releases were uninstalled.\n' >&2
  exit 1
fi

failures=0
for (( index=0; index<target_count; index++ )); do
  context="${target_contexts[$index]}"
  namespace="${target_namespaces[$index]}"
  release="${target_releases[$index]}"
  printf '\nUninstalling %s from %s in %s...\n' "$release" "$context" "$namespace"
  if helm uninstall "$release" --kube-context "$context" --namespace "$namespace" --wait --timeout 5m; then
    printf 'Succeeded: %s / %s / %s\n' "$context" "$namespace" "$release"
  else
    printf 'Failed: %s / %s / %s\n' "$context" "$namespace" "$release" >&2
    failures=$((failures + 1))
  fi
done

if (( failures > 0 )); then
  printf '\nUninstall failed for %s release(s); review the results above.\n' "$failures" >&2
  exit 1
fi
printf '\nUninstall succeeded for all %s matching release(s).\n' "$target_count"