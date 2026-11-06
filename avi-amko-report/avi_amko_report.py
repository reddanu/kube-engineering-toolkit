#!/usr/bin/env python3
"""Summarize AVI / AMKO status metadata from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-gslb.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("snapshot must be a JSON object")
    for key in ("services", "host_rules"):
        if not isinstance(value.get(key), list) or not all(isinstance(item, dict) for item in value[key]):
            raise ValueError(f"snapshot.{key} must be a list of objects")
    return value


def count_pair(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    healthy = value.get("healthy")
    total = value.get("total", value.get("configured"))
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (healthy, total)):
        raise ValueError(f"{label} requires non-negative healthy and total counts")
    if healthy > total:
        raise ValueError(f"{label}.healthy cannot exceed its total")
    return healthy, total


def analyze(snapshot: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not snapshot["services"]:
        findings.append(Finding("WARNING", "Snapshot contains no GSLB service records"))

    for index, service in enumerate(snapshot["services"], start=1):
        sites_healthy, sites_total = count_pair(service.get("sites"), f"service {index} sites")
        if sites_healthy < sites_total:
            findings.append(Finding("CRITICAL", f"GSLB service {index} has {sites_healthy}/{sites_total} healthy sites"))
        pools = service.get("pools")
        if not isinstance(pools, list):
            raise ValueError(f"service {index} pools must be a list")
        for pool_index, pool in enumerate(pools, start=1):
            healthy, total = count_pair(pool, f"service {index} pool {pool_index}")
            if healthy < total:
                findings.append(Finding("WARNING", f"GSLB service {index} pool {pool_index} has {healthy}/{total} healthy members"))
        traffic_enabled = service.get("traffic_enabled")
        if not isinstance(traffic_enabled, bool):
            raise ValueError(f"service {index} traffic_enabled must be a boolean")
        if not traffic_enabled:
            findings.append(Finding("WARNING", f"GSLB service {index} has traffic disabled"))

    for index, rule in enumerate(snapshot["host_rules"], start=1):
        sync_status = rule.get("sync_status")
        if not isinstance(sync_status, str) or not sync_status:
            raise ValueError(f"host rule {index} requires a sync_status string")
        if sync_status.lower() not in ("synchronized", "synced"):
            findings.append(Finding("WARNING", f"Host rule {index} sync status is {sync_status}"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="synthetic or sanitized JSON snapshot")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()
    try:
        snapshot = load_snapshot(args.input)
        findings = analyze(snapshot)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "CRITICAL" if any(item.severity == "CRITICAL" for item in findings) else "WARNING" if findings else "HEALTHY"
    report = {
        "environment": snapshot.get("environment", "unspecified"),
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": status,
        "service_count": len(snapshot["services"]),
        "host_rule_count": len(snapshot["host_rules"]),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Environment: {report['environment']}\nSource: {report['source']}\nStatus: {status}")
        print(f"Services: {report['service_count']}\nHost rules: {report['host_rule_count']}\nFindings: {len(findings)}")
        for item in findings:
            print(f"[{item.severity}] {item.message}")
        if not findings:
            print("No health findings detected.")
    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())