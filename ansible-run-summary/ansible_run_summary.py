#!/usr/bin/env python3
"""Summarize Ansible task counts from a local JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-run.json"
COUNTERS = ("ok", "changed", "failed", "unreachable", "skipped")


def load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(report, dict) or not isinstance(report.get("hosts"), list):
        raise ValueError("report must be an object with a hosts list")
    if not report["hosts"]:
        raise ValueError("report.hosts must contain at least one host")
    return report


def summarize(report: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    totals = {counter: 0 for counter in COUNTERS}
    failed_hosts: list[str] = []
    for index, host in enumerate(report["hosts"], start=1):
        if not isinstance(host, dict):
            raise ValueError(f"hosts[{index - 1}] must be an object")
        label = host.get("label")
        if not isinstance(label, str) or not label:
            raise ValueError(f"hosts[{index - 1}].label must be a non-empty string")
        for counter in COUNTERS:
            value = host.get(counter)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"hosts[{index - 1}].{counter} must be a non-negative integer")
            totals[counter] += value
        if host["failed"] or host["unreachable"]:
            failed_hosts.append(label)
    return totals, failed_hosts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="synthetic or sanitized JSON report")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()
    try:
        source = load_report(args.input)
        totals, failed_hosts = summarize(source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "FAILED" if failed_hosts else "CHANGED" if totals["changed"] else "OK"
    report = {
        "playbook": source.get("playbook", "unspecified"),
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local report",
        "status": status,
        "host_count": len(source["hosts"]),
        "totals": totals,
        "failed_host_count": len(failed_hosts),
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Playbook: {report['playbook']}\nSource: {report['source']}\nStatus: {status}")
        print(f"Hosts: {report['host_count']}\nFailed or unreachable hosts: {report['failed_host_count']}")
        for counter, value in totals.items():
            print(f"{counter}: {value}")
    return 1 if failed_hosts else 0


if __name__ == "__main__":
    raise SystemExit(main())