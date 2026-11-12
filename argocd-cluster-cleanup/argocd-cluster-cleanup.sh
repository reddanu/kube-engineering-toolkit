#!/usr/bin/env bash

# Preview or remove Argo CD Application records for a decommissioned cluster.
# Requires Bash 3.2+, kubectl, and jq. Run with --help for examples and safety notes.

set -euo pipefail

usage() {
  printf '%s\n' \
    'Argo CD Cluster Application Cleanup' \
    '' \
    "Usage: bash ${0##*/} --context CONTEXT (--cluster NAME | --cleanup NAME) [OPTIONS]" \
    '' \
    '  --context CONTEXT    Kubeconfig context hosting Argo CD (required).' \
    '  --namespace NAME     Namespace containing Applications (default: argocd).' \
    '  --cluster NAME       Preview Applications targeting this cluster.' \
    '  --cleanup NAME       Preview, confirm, and remove matching Applications.' \
    '  --server URL         Exact target API server URL, for server-based destinations.' \
    '  --app NAME           Limit to this exact Application name; repeat as needed.' \
    '  --dry-run            Preview only (default; cannot be combined with --cleanup).' \
    '  -h, --help           Show this help.' \
    '' \
    'Examples:' \
    "  bash ${0##*/} --context argo-host --cluster retired-cluster" \
    "  bash ${0##*/} --context argo-host --cleanup retired-cluster --server https://retired-cluster.example.com" \
    "  bash ${0##*/} --context argo-host --cleanup retired-cluster --app my-application" \
    '' \
    'Applications match an exact destination name or the explicitly provided server URL.' \
    'A URL with a matching hostname but no --server is shown as a candidate, not deleted.' \
    'Cleanup removes Application records without cascading to deployed resources.' \
    'ApplicationSets, cluster registrations, Secrets, and other resources are untouched.' \
    'ApplicationSet or Git reconciliation can recreate Applications after deletion.' \
    'Changes to an Application during cleanup cause that deletion to fail safely.'
}

context=""
namespace="argocd"
cluster=""
server=""
cleanup=false
dry_run=false
app_filters=()
app_filter_count=0

while (( $# )); do
  case "$1" in
    --context|--namespace|--cluster|--cleanup|--server|--app)
      option="$1"
      if (( $# < 2 )) || [[ -z "$2" || "$2" == -* ]]; then
        printf '%s requires a value.\n' "$option" >&2
        exit 2
      fi
      value="$2"
      shift 2
      ;;
    --context=*|--namespace=*|--cluster=*|--cleanup=*|--server=*|--app=*)
      option="${1%%=*}"
      value="${1#*=}"
      shift
      if [[ -z "$value" || "$value" == -* ]]; then
        printf '%s requires a value.\n' "$option" >&2
        exit 2
      fi
      ;;
    --dry-run) dry_run=true; shift; continue ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  case "$option" in
    --context) context="$value" ;;
    --namespace) namespace="$value" ;;
    --cluster|--cleanup)
      if [[ -n "$cluster" ]]; then
        printf 'Specify exactly one of --cluster or --cleanup.\n' >&2
        exit 2
      fi
      cluster="$value"
      if [[ "$option" == --cleanup ]]; then cleanup=true; fi
      ;;
    --server) server="$value" ;;
    --app)
      app_filters[$app_filter_count]="$value"
      app_filter_count=$((app_filter_count + 1))
      ;;
  esac
done

if [[ -z "$context" || -z "$cluster" ]]; then
  printf 'Both --context and a target cluster are required.\n' >&2
  usage >&2
  exit 2
fi
if [[ "$cleanup" == true && "$dry_run" == true ]]; then
  printf 'Choose either --dry-run or --cleanup.\n' >&2
  exit 2
fi
if [[ ! "$cluster" =~ ^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$ || ! "$namespace" =~ ^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$ ]]; then
  printf 'Cluster and namespace must be valid lowercase names.\n' >&2
  exit 2
fi
if [[ -n "$server" && ! "$server" =~ ^https?://[^[:space:]]+$ ]]; then
  printf 'Server must be an exact http or https URL.\n' >&2
  exit 2
fi
for command_name in kubectl jq; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '%s is required.\n' "$command_name" >&2
    exit 127
  fi
done

if ! contexts="$(kubectl config get-contexts -o name)" || ! printf '%s\n' "$contexts" | grep -Fx -- "$context" >/dev/null; then
  printf 'Kubeconfig context not found: %s\n' "$context" >&2
  exit 1
fi

if ! records="$(kubectl --context "$context" --namespace "$namespace" --request-timeout=30s get applications.argoproj.io -o json | jq -ce --arg cluster "$cluster" --arg server "$server" '
  if (.items | type) != "array" then error("invalid Application list") else
    [.items[] |
      {name: .metadata.name, uid: .metadata.uid, resourceVersion: .metadata.resourceVersion,
       destinationName: (.spec.destination.name // ""), server: (.spec.destination.server // ""),
       owner: ([.metadata.ownerReferences[]? | select(.kind == "ApplicationSet") | .name] | join(", ")),
       sync: (.status.sync.status // "Unknown")} |
      if (.name | type) != "string" or (.uid | type) != "string" or (.resourceVersion | type) != "string" then
        error("invalid Application metadata")
      else . end |
      . + {match: (if .destinationName == $cluster then "exact name"
        elif .destinationName == "" and $server != "" and .server == $server then "exact server"
        elif .destinationName == "" and (.server | test("^https?://")) and
          ((.server | sub("^https?://"; "") | split("/")[0] | split(":")[0]) as $host |
           $host == $cluster or ($host | startswith($cluster + "."))) then "candidate"
        else "none" end)} |
      select(.match != "none")]
  end')"; then
  printf 'Unable to discover Applications; nothing was changed.\n' >&2
  exit 1
fi

selected=()
selected_count=0
candidate_count=0
printf 'Argo CD context: %s | Namespace: %s | Target cluster: %s\n' "$context" "$namespace" "$cluster"
while IFS= read -r record; do
  [[ -z "$record" ]] && continue
  app_name="$(printf '%s' "$record" | jq -r '.name')"
  include=true
  if (( app_filter_count > 0 )); then
    include=false
    for filter in "${app_filters[@]}"; do
      if [[ "$app_name" == "$filter" ]]; then include=true; break; fi
    done
  fi
  [[ "$include" == true ]] || continue
  match="$(printf '%s' "$record" | jq -r '.match')"
  destination="$(printf '%s' "$record" | jq -r 'if .destinationName != "" then .destinationName else .server end')"
  owner="$(printf '%s' "$record" | jq -r 'if .owner == "" then "none" else .owner end')"
  sync_status="$(printf '%s' "$record" | jq -r '.sync')"
  if [[ "$match" == candidate ]]; then
    printf '  CANDIDATE (not selected): %s | Destination: %s | ApplicationSet: %s | Sync: %s\n' "$app_name" "$destination" "$owner" "$sync_status"
    candidate_count=$((candidate_count + 1))
  else
    printf '  MATCH: %s | Destination: %s | ApplicationSet: %s | Sync: %s\n' "$app_name" "$destination" "$owner" "$sync_status"
    selected[$selected_count]="$record"
    selected_count=$((selected_count + 1))
  fi
done < <(printf '%s' "$records" | jq -c '.[]')

printf 'Selected Applications: %s | Server candidates not selected: %s\n' "$selected_count" "$candidate_count"
if (( candidate_count > 0 )); then
  printf 'To include a candidate, verify its server URL and pass it with --server.\n'
fi
printf 'ApplicationSets are not modified; Git or ApplicationSet reconciliation may recreate Applications.\n'

if [[ "$cleanup" != true ]]; then
  printf 'Dry run: nothing was changed.\n'
  exit 0
fi
if (( selected_count == 0 )); then
  printf 'No Applications selected for cleanup.\n'
  exit 0
fi
printf 'Delete these %s Application records without deleting their workloads? [y/N]: ' "$selected_count"
if ! IFS= read -r confirmation || [[ "$confirmation" != y && "$confirmation" != Y ]]; then
  printf 'Not confirmed; nothing was changed.\n' >&2
  exit 1
fi

failures=0
for (( index=0; index<selected_count; index++ )); do
  record="${selected[$index]}"
  app_name="$(printf '%s' "$record" | jq -r '.name')"
  expected_uid="$(printf '%s' "$record" | jq -r '.uid')"
  expected_name="$(printf '%s' "$record" | jq -r '.destinationName')"
  expected_server="$(printf '%s' "$record" | jq -r '.server')"
  for (( attempt=1; attempt<=3; attempt++ )); do
    if ! current="$(kubectl --context "$context" --namespace "$namespace" --request-timeout=30s get applications.argoproj.io "$app_name" -o json | jq -ce --arg uid "$expected_uid" --arg name "$expected_name" --arg server "$expected_server" '
    if .metadata.uid != $uid or (.spec.destination.name // "") != $name or (.spec.destination.server // "") != $server then
      error("Application identity or destination changed")
    else {uid: .metadata.uid, resourceVersion: .metadata.resourceVersion, finalizers: (.metadata.finalizers // [])} end')"; then
      printf 'Skipped %s: unable to verify its current identity and destination.\n' "$app_name" >&2
      failures=$((failures + 1))
      break
    fi
    patch="$(printf '%s' "$current" | jq -c '
    [{op:"test",path:"/metadata/uid",value:.uid}, {op:"test",path:"/metadata/resourceVersion",value:.resourceVersion}] +
    ([.finalizers | to_entries[] | select(.value == "resources-finalizer.argocd.argoproj.io" or .value == "resources-finalizer.argocd.argoproj.io/background") | .key] | reverse | map({op:"remove",path:("/metadata/finalizers/" + tostring)}))')"
    patch_count="$(printf '%s' "$patch" | jq 'length')"
    resource_version="$(printf '%s' "$current" | jq -r '.resourceVersion')"
    if (( patch_count > 2 )); then
      if ! resource_version="$(kubectl --context "$context" --namespace "$namespace" --request-timeout=30s patch applications.argoproj.io "$app_name" --type=json --patch "$patch" -o json | jq -er '.metadata.resourceVersion')"; then
        printf 'Skipped %s: could not safely remove Argo CD deletion finalizers.\n' "$app_name" >&2
        failures=$((failures + 1))
        break
      fi
    fi
    delete_options="$(jq -nc --arg uid "$expected_uid" --arg version "$resource_version" '{apiVersion:"v1",kind:"DeleteOptions",preconditions:{uid:$uid,resourceVersion:$version},propagationPolicy:"Orphan"}')"
    if delete_result="$(printf '%s' "$delete_options" | kubectl --context "$context" --request-timeout=30s delete --raw "/apis/argoproj.io/v1alpha1/namespaces/$namespace/applications/$app_name" -f - 2>&1)"; then
      printf 'Deletion requested: %s\n' "$app_name"
      break
    elif [[ "$delete_result" == *'Error from server (Conflict)'* ]] && (( attempt < 3 )); then
      printf 'Conflict deleting %s; rechecking before retry %s of 3.\n' "$app_name" "$((attempt + 1))" >&2
    else
      printf '%s\nFailed to delete %s; it may have changed.\n' "$delete_result" "$app_name" >&2
      failures=$((failures + 1))
      break
    fi
  done
done

printf 'Cleanup requests completed with %s failure(s). Re-run the preview to check for remaining or recreated Applications.\n' "$failures"
if (( failures > 0 )); then exit 1; fi