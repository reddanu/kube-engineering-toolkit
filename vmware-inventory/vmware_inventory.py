#!/usr/bin/env python3
"""Summarize VMware inventory status from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-inventory.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        raise ValueError(f"{label} must be a non-negative number")
    return float(value)


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    for key in ("vms", "datastores"):
        if not isinstance(snapshot.get(key), list) or not all(isinstance(item, dict) for item in snapshot[key]):
            raise ValueError(f"snapshot.{key} must be a list of objects")
    return snapshot


def analyze(snapshot: dict[str, Any]) -> tuple[list[Finding], float]:
    findings: list[Finding] = []
    if not snapshot["vms"]:
        findings.append(Finding("WARNING", "Snapshot contains no VM records"))
    if not snapshot["datastores"]:
        findings.append(Finding("WARNING", "Snapshot contains no datastore records"))

    for index, vm in enumerate(snapshot["vms"], start=1):
        power_state = vm.get("power_state")
        tools_state = vm.get("guest_tools")
        age = number(vm.get("snapshot_age_days"), f"VM {index} snapshot_age_days")
        if power_state not in ("poweredOn", "poweredOff"):
            raise ValueError(f"VM {index} has an invalid power_state")
        if power_state == "poweredOff":
            findings.append(Finding("INFO", f"VM record {index} is powered off"))
        if power_state == "poweredOn" and tools_state != "running":
            findings.append(Finding("WARNING", f"Guest tools are not running for VM record {index}"))
        if age >= 14:
            findings.append(Finding("WARNING", f"VM record {index} has a snapshot at least 14 days old"))

    maximum_utilization = 0.0
    for index, datastore in enumerate(snapshot["datastores"], start=1):
        capacity = number(datastore.get("capacity_gib"), f"datastore {index} capacity_gib")
        free = number(datastore.get("free_gib"), f"datastore {index} free_gib")
        if capacity == 0 or free > capacity:
            raise ValueError(f"datastore {index} capacity/free values are inconsistent")
        utilization = (capacity - free) * 100.0 / capacity
        maximum_utilization = max(maximum_utilization, utilization)
        if utilization >= 90:
            findings.append(Finding("CRITICAL", f"Datastore record {index} utilization is {utilization:.1f}%"))
        elif utilization >= 80:
            findings.append(Finding("WARNING", f"Datastore record {index} utilization is {utilization:.1f}%"))
    return findings, maximum_utilization


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="synthetic or sanitized JSON snapshot")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()
    try:
        snapshot = load_snapshot(args.input)
        findings, maximum_utilization = analyze(snapshot)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "CRITICAL" if any(item.severity == "CRITICAL" for item in findings) else "WARNING" if any(item.severity == "WARNING" for item in findings) else "HEALTHY"
    report = {
        "environment": snapshot.get("environment", "unspecified"),
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": status,
        "vm_count": len(snapshot["vms"]),
        "datastore_count": len(snapshot["datastores"]),
        "maximum_datastore_utilization_percent": round(maximum_utilization, 1),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Environment: {report['environment']}\nSource: {report['source']}\nStatus: {status}")
        print(f"VMs: {report['vm_count']}\nDatastores: {report['datastore_count']}\nMaximum utilization: {report['maximum_datastore_utilization_percent']:.1f}%")
        for item in findings:
            print(f"[{item.severity}] {item.message}")
        if not findings:
            print("No health findings detected.")
    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())