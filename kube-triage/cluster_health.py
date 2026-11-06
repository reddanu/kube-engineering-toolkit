#!/usr/bin/env python3
"""Report common Kubernetes health signals from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-cluster.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def read_snapshot(path: Path) -> dict[str, Any]:
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc

    try:
        snapshot = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc

    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    if not isinstance(snapshot.get("cluster"), str) or not snapshot["cluster"].strip():
        raise ValueError("snapshot.cluster must be a non-empty string")

    for collection in ("nodes", "pods", "deployments", "pod_disruption_budgets"):
        if not isinstance(snapshot.get(collection), list):
            raise ValueError(f"snapshot.{collection} must be a list")
        if not all(isinstance(item, dict) for item in snapshot[collection]):
            raise ValueError(f"every entry in snapshot.{collection} must be an object")

    return snapshot


def required_text(item: dict[str, Any], field: str, collection: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"each {collection} entry requires a non-empty {field}")
    return value


def required_count(item: dict[str, Any], field: str, collection: str) -> int:
    value = item.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"each {collection} entry requires a non-negative integer {field}")
    return value


def analyze(snapshot: dict[str, Any], restart_threshold: int) -> list[Finding]:
    findings: list[Finding] = []
    if not snapshot["nodes"]:
        findings.append(Finding("WARNING", "Snapshot contains no node records"))

    for node in snapshot["nodes"]:
        name = required_text(node, "name", "nodes")
        if not isinstance(node.get("ready"), bool):
            raise ValueError("each nodes entry requires a boolean ready field")
        if not node["ready"]:
            findings.append(Finding("CRITICAL", f"Node {name} is not Ready"))

    for pod in snapshot["pods"]:
        namespace = required_text(pod, "namespace", "pods")
        name = required_text(pod, "name", "pods")
        phase = required_text(pod, "phase", "pods")
        restarts = required_count(pod, "restarts", "pods")
        location = f"Pod {namespace}/{name}"

        if phase == "Failed":
            findings.append(Finding("CRITICAL", f"{location} is Failed"))
        elif phase == "Pending":
            reason = pod.get("reason")
            detail = f": {reason}" if isinstance(reason, str) and reason else ""
            findings.append(Finding("WARNING", f"{location} is Pending{detail}"))

        if restarts >= restart_threshold:
            findings.append(
                Finding("WARNING", f"{location} has {restarts} restarts (threshold: {restart_threshold})")
            )

    for deployment in snapshot["deployments"]:
        namespace = required_text(deployment, "namespace", "deployments")
        name = required_text(deployment, "name", "deployments")
        desired = required_count(deployment, "desired", "deployments")
        ready = required_count(deployment, "ready", "deployments")
        if ready < desired:
            findings.append(
                Finding("WARNING", f"Deployment {namespace}/{name} has {ready}/{desired} ready replicas")
            )

    for budget in snapshot["pod_disruption_budgets"]:
        namespace = required_text(budget, "namespace", "pod_disruption_budgets")
        name = required_text(budget, "name", "pod_disruption_budgets")
        allowed = required_count(budget, "allowed_disruptions", "pod_disruption_budgets")
        if allowed == 0:
            findings.append(
                Finding("WARNING", f"PodDisruptionBudget {namespace}/{name} allows no disruptions")
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="sanitized JSON snapshot (default: synthetic example)")
    parser.add_argument("--restart-threshold", type=positive_int, default=10, help="restart count that triggers a finding")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()

    try:
        snapshot = read_snapshot(args.input)
        findings = analyze(snapshot, args.restart_threshold)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    overall = "CRITICAL" if any(item.severity == "CRITICAL" for item in findings) else "WARNING" if findings else "HEALTHY"
    report = {
        "cluster": snapshot["cluster"],
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": overall,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Cluster: {report['cluster']}")
        print(f"Source: {report['source']}")
        print(f"Status: {report['status']}")
        print(f"Findings: {report['finding_count']}")
        if findings:
            for item in findings:
                print(f"[{item.severity}] {item.message}")
        else:
            print("No health findings detected.")

    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())