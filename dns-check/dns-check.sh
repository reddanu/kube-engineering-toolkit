#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <hostname> [dns-server]\n' "$0"
  printf 'Resolve A and AAAA records using dig or nslookup.\n'
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if (( $# < 1 || $# > 2 )); then
  usage >&2
  exit 2
fi

hostname="$1"
dns_server="${2:-}"

if ! [[ "${hostname}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  printf 'Hostname may contain only letters, digits, dots, underscores, and hyphens.\n' >&2
  exit 2
fi

if command -v dig >/dev/null 2>&1; then
  result=0
  for record_type in A AAAA; do
    printf '%s records for %s:\n' "${record_type}" "${hostname}"
    if [[ -n "${dns_server}" ]]; then
      dig "@${dns_server}" +time=2 +tries=1 +noall +answer "${hostname}" "${record_type}" || result=1
    else
      dig +time=2 +tries=1 +noall +answer "${hostname}" "${record_type}" || result=1
    fi
  done
  exit "${result}"
fi

if command -v nslookup >/dev/null 2>&1; then
  if [[ -n "${dns_server}" ]]; then
    nslookup "${hostname}" "${dns_server}"
  else
    nslookup "${hostname}"
  fi
  exit
fi

printf 'Install dig or nslookup to run DNS checks.\n' >&2
exit 127