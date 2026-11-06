#!/usr/bin/env python3
"""Summarize Argo CD status from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-applications.json"


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
    if not isinstance(value, dict) or not isinstance(value.get("cluster"), str) or not value["cluster"].strip():
        raise ValueError("snapshot must be an object with a non-empty cluster name")
    for key in ("controllers", "applications"):
        if not isinstance(value.get(key), list) or not all(isinstance(item, dict) for item in value[key]):
            raise ValueError(f"snapshot.{key} must be a list of objects")
    return value


def analyze(snapshot: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not snapshot["controllers"]:
        findings.append(Finding("WARNING", "Snapshot contains no controller records"))
    if not snapshot["applications"]:
        findings.append(Finding("WARNING", "Snapshot contains no application records"))

    for controller in snapshot["controllers"]:
        name = controller.get("name")
        desired = controller.get("desired")
        ready = controller.get("ready")
        if not isinstance(name, str) or not name:
            raise ValueError("each controller requires a name")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (desired, ready)):
            raise ValueError(f"controller {name} requires non-negative desired and ready counts")
        if ready > desired:
            raise ValueError(f"controller {name} ready count cannot exceed desired replicas")
        if ready < desired:
            findings.append(Finding("WARNING", f"Controller {name} is ready on {ready}/{desired} replicas"))

    for application in snapshot["applications"]:
        name = application.get("name")
        sync = application.get("sync")
        health = application.get("health")
        if not all(isinstance(item, str) and item for item in (name, sync, health)):
            raise ValueError("each application requires non-empty name, sync, and health fields")
        if sync != "Synced":
            findings.append(Finding("WARNING", f"Application {name} sync status is {sync}"))
        if health != "Healthy":
            findings.append(Finding("CRITICAL" if health == "Degraded" else "WARNING", f"Application {name} health is {health}"))
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
        "cluster": snapshot["cluster"],
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": status,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Cluster: {report['cluster']}\nSource: {report['source']}\nStatus: {status}\nFindings: {len(findings)}")
        for item in findings:
            print(f"[{item.severity}] {item.message}")
        if not findings:
            print("No health findings detected.")
    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())