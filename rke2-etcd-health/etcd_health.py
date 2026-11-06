#!/usr/bin/env python3
"""Analyze etcd quorum and performance signals from a local JSON snapshot."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-etcd.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def integer(data: dict[str, Any], key: str, parent: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{parent}.{key} must be a non-negative integer")
    return value


def non_negative_number(data: dict[str, Any], key: str, parent: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{parent}.{key} must be a non-negative number")
    try:
        numeric_value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{parent}.{key} is outside the supported numeric range") from exc
    if not math.isfinite(numeric_value):
        raise ValueError(f"{parent}.{key} must be finite")
    return numeric_value


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("cluster"), str):
        raise ValueError("snapshot must be an object with a cluster name")
    for key in ("members", "database"):
        if not isinstance(snapshot.get(key), dict):
            raise ValueError(f"snapshot.{key} must be an object")
    integer(snapshot["members"], "expected", "members")
    integer(snapshot["members"], "healthy", "members")
    integer(snapshot["database"], "used_mib", "database")
    integer(snapshot["database"], "quota_mib", "database")
    non_negative_number(snapshot, "wal_fsync_p99_ms", "snapshot")
    integer(snapshot, "raft_proposals_pending", "snapshot")
    return snapshot


def analyze(snapshot: dict[str, Any]) -> list[Finding]:
    members = snapshot["members"]
    database = snapshot["database"]
    expected = members["expected"]
    healthy = members["healthy"]
    used = database["used_mib"]
    quota = database["quota_mib"]
    fsync_ms = non_negative_number(snapshot, "wal_fsync_p99_ms", "snapshot")
    proposals = snapshot["raft_proposals_pending"]
    findings: list[Finding] = []

    if expected == 0:
        raise ValueError("members.expected must be greater than zero")
    if healthy > expected:
        raise ValueError("members.healthy cannot exceed members.expected")
    if healthy <= expected // 2:
        findings.append(Finding("CRITICAL", f"etcd quorum at risk: {healthy}/{expected} members healthy"))
    elif healthy < expected:
        findings.append(Finding("WARNING", f"etcd member availability degraded: {healthy}/{expected} healthy"))
    if quota == 0:
        raise ValueError("database.quota_mib must be greater than zero")

    utilization = used * 100.0 / quota
    if utilization >= 90:
        findings.append(Finding("CRITICAL", f"database utilization is {utilization:.1f}%"))
    elif utilization >= 75:
        findings.append(Finding("WARNING", f"database utilization is {utilization:.1f}%"))
    if fsync_ms >= 200:
        findings.append(Finding("CRITICAL", f"WAL fsync p99 is {fsync_ms:g} ms"))
    elif fsync_ms >= 50:
        findings.append(Finding("WARNING", f"WAL fsync p99 is {fsync_ms:g} ms"))
    if proposals:
        severity = "CRITICAL" if proposals >= 100 else "WARNING"
        findings.append(Finding(severity, f"pending Raft proposals: {proposals}"))
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
    database = snapshot["database"]
    report = {
        "cluster": snapshot["cluster"],
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local snapshot",
        "status": status,
        "database_utilization_percent": round(database["used_mib"] * 100 / database["quota_mib"], 1),
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Cluster: {report['cluster']}\nSource: {report['source']}\nStatus: {status}")
        print(f"etcd members: {snapshot['members']['healthy']}/{snapshot['members']['expected']} healthy")
        print(f"Database utilization: {report['database_utilization_percent']:.1f}%")
        print(f"Findings: {len(findings)}")
        for item in findings:
            print(f"[{item.severity}] {item.message}")
        if not findings:
            print("No health findings detected.")
    return 1 if any(item.severity in ("WARNING", "CRITICAL") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())