#!/usr/bin/env python3
"""Analyze peer-to-peer image mirror health from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-spegel.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def read_snapshot(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc

    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    if not isinstance(snapshot.get("cluster"), str) or not snapshot["cluster"].strip():
        raise ValueError("snapshot.cluster must be a non-empty string")

    expected = {
        "schedulable_nodes": int,
        "daemonset": dict,
        "mirror": dict,
        "errors": dict,
        "image_pull_failures": int,
    }
    for field, expected_type in expected.items():
        value = snapshot.get(field)
        if isinstance(value, bool) or not isinstance(value, expected_type):
            raise ValueError(f"snapshot.{field} has an invalid or missing value")
    return snapshot


def count_value(data: dict[str, Any], field: str, parent: str) -> int:
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{parent}.{field} must be a non-negative integer")
    return value


def analyze(snapshot: dict[str, Any], minimum_hit_rate: float) -> tuple[list[Finding], float]:
    daemonset = snapshot["daemonset"]
    mirror = snapshot["mirror"]
    errors = snapshot["errors"]

    desired = count_value(daemonset, "desired", "daemonset")
    ready = count_value(daemonset, "ready", "daemonset")
    schedulable = count_value(snapshot, "schedulable_nodes", "snapshot")
    peer_hits = count_value(mirror, "peer_hits", "mirror")
    origin_misses = count_value(mirror, "origin_misses", "mirror")
    last_success = count_value(mirror, "seconds_since_last_success", "mirror")
    unknown_blob = count_value(errors, "unknown_blob", "errors")
    unknown_manifest = count_value(errors, "unknown_manifest", "errors")
    pull_failures = count_value(snapshot, "image_pull_failures", "snapshot")

    total_requests = peer_hits + origin_misses
    hit_rate = peer_hits * 100.0 / total_requests if total_requests else 0.0
    findings: list[Finding] = []

    if schedulable == 0:
        findings.append(Finding("WARNING", "No schedulable nodes were reported"))
    if ready < desired:
        findings.append(Finding("CRITICAL", f"Mirror DaemonSet is ready on {ready}/{desired} desired nodes"))
    if ready > desired:
        raise ValueError("daemonset.ready cannot exceed daemonset.desired")
    if desired < schedulable:
        findings.append(Finding("INFO", f"Mirror DaemonSet targets {desired}/{schedulable} schedulable nodes; confirm placement policy"))
    if hit_rate < minimum_hit_rate:
        findings.append(Finding("WARNING", f"Peer-hit rate is {hit_rate:.1f}% (minimum: {minimum_hit_rate:.1f}%)"))
    if total_requests == 0:
        findings.append(Finding("WARNING", "No mirror requests were recorded in the snapshot"))
    if last_success > 300:
        findings.append(Finding("WARNING", f"Last successful mirror request was {last_success} seconds ago"))
    if unknown_blob:
        findings.append(Finding("WARNING", f"Unknown-blob errors: {unknown_blob}"))
    if unknown_manifest:
        findings.append(Finding("WARNING", f"Unknown-manifest errors: {unknown_manifest}"))
    if pull_failures:
        findings.append(Finding("WARNING", f"Image-pull failures: {pull_failures}"))

    return findings, hit_rate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="synthetic or sanitized JSON snapshot")
    parser.add_argument("--minimum-hit-rate", type=float, default=60.0, help="minimum expected peer-hit rate percentage")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()
    if not 0 <= args.minimum_hit_rate <= 100:
        parser.error("--minimum-hit-rate must be between 0 and 100")

    try:
        snapshot = read_snapshot(args.input)
        findings, hit_rate = analyze(snapshot, args.minimum_hit_rate)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "CRITICAL" if any(item.severity == "CRITICAL" for item in findings) else "WARNING" if any(item.severity == "WARNING" for item in findings) else "HEALTHY"
    report = {
        "cluster": snapshot["cluster"],
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": status,
        "peer_hit_rate_percent": round(hit_rate, 1),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Cluster: {report['cluster']}")
        print(f"Source: {report['source']}")
        print(f"Status: {report['status']}")
        print(f"Peer-hit rate: {report['peer_hit_rate_percent']:.1f}%")
        print(f"Findings: {report['finding_count']}")
        for finding in findings:
            print(f"[{finding.severity}] {finding.message}")
        if not findings:
            print("No health findings detected.")

    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())