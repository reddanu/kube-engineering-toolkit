#!/usr/bin/env python3
"""Count scheduled pods per node from a local Kubernetes snapshot."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON snapshot {path}: {exc}") from exc

    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    if not isinstance(snapshot.get("nodes"), list) or not isinstance(snapshot.get("pods"), list):
        raise ValueError("snapshot must contain 'nodes' and 'pods' arrays")

    node_names = []
    for node in snapshot["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("name"), str) or not node["name"]:
            raise ValueError("each node must have a non-empty string 'name'")
        node_names.append(node["name"])

    for pod in snapshot["pods"]:
        if not isinstance(pod, dict) or not isinstance(pod.get("name"), str):
            raise ValueError("each pod must have a string 'name'")

    if len(set(node_names)) != len(node_names):
        raise ValueError("node names must be unique")
    return snapshot


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    counts = Counter({node["name"]: 0 for node in snapshot["nodes"]})
    unscheduled = 0
    unknown_node_pods = 0

    for pod in snapshot["pods"]:
        node_name = pod.get("nodeName")
        if not node_name:
            unscheduled += 1
        elif node_name not in counts:
            unknown_node_pods += 1
        else:
            counts[node_name] += 1

    return {
        "context": snapshot.get("context", "unspecified"),
        "podsPerNode": [{"node": node, "podCount": count} for node, count in sorted(counts.items())],
        "unscheduledPods": unscheduled,
        "podsOnUnknownNodes": unknown_node_pods,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("examples") / "pods.json",
        help="local JSON snapshot (default: bundled synthetic example)",
    )
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args()

    try:
        report = summarize(load_snapshot(args.input))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Pod count by node ({report['context']})")
        for item in report["podsPerNode"]:
            print(f"{item['node']:<24} {item['podCount']:>4}")
        print(f"Unscheduled pods: {report['unscheduledPods']}")
        print(f"Pods assigned to unknown nodes: {report['podsOnUnknownNodes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())