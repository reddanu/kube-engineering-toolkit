#!/usr/bin/env python3
"""Find duplicate Kubernetes node IP assignments using read-only API calls."""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
import sys
from collections import defaultdict
from typing import Any


def run_kubectl(arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            ["kubectl", *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"cannot execute kubectl: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or f"command exited with status {result.returncode}"
        raise ValueError(f"kubectl failed: {detail}")
    return result.stdout


def load_nodes(context: str | None) -> tuple[str, list[dict[str, Any]]]:
    if context is None:
        context = run_kubectl(["config", "current-context"]).strip()
    if not context:
        raise ValueError("no kubeconfig context is selected; pass --context")

    output = run_kubectl(["--context", context, "get", "nodes", "-o", "json"])
    try:
        document = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError(f"kubectl returned invalid JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("items"), list):
        raise ValueError("kubectl node response must contain an items list")
    if not all(isinstance(item, dict) for item in document["items"]):
        raise ValueError("kubectl node response contains a non-object item")
    return context, document["items"]


def analyze_nodes(nodes: list[dict[str, Any]], address_type: str) -> dict[str, Any]:
    addresses_by_node: dict[str, set[str]] = {}
    nodes_without_address: list[str] = []

    for index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            raise ValueError(f"node record {index} must be an object")
        metadata = node.get("metadata")
        status = node.get("status")
        if not isinstance(metadata, dict) or not isinstance(status, dict):
            raise ValueError(f"node record {index} requires metadata and status objects")
        name = metadata.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"node record {index} requires a non-empty metadata.name")
        if name in addresses_by_node:
            raise ValueError(f"duplicate node name in API response: {name}")

        address_records = status.get("addresses", [])
        if not isinstance(address_records, list):
            raise ValueError(f"node {name} status.addresses must be a list")
        node_addresses: set[str] = set()
        for address_record in address_records:
            if not isinstance(address_record, dict):
                raise ValueError(f"node {name} has a malformed address record")
            if address_record.get("type") != address_type:
                continue
            address = address_record.get("address")
            if not isinstance(address, str) or not address:
                raise ValueError(f"node {name} has an empty {address_type} address")
            try:
                node_addresses.add(ipaddress.ip_address(address).compressed)
            except ValueError as exc:
                raise ValueError(f"node {name} has an invalid {address_type} IP address") from exc

        if not node_addresses:
            nodes_without_address.append(name)
        addresses_by_node[name] = node_addresses

    owners: dict[str, list[str]] = defaultdict(list)
    for name, addresses in addresses_by_node.items():
        for address in addresses:
            owners[address].append(name)

    duplicates = [
        {"address": address, "nodes": sorted(names)}
        for address, names in sorted(owners.items())
        if len(names) > 1
    ]
    findings: list[dict[str, Any]] = []
    for duplicate in duplicates:
        findings.append({
            "severity": "CRITICAL",
            "message": f"{address_type} {duplicate['address']} is assigned to multiple nodes",
            "address": duplicate["address"],
            "nodes": duplicate["nodes"],
        })
    for name in nodes_without_address:
        findings.append({
            "severity": "WARNING",
            "message": f"Node {name} has no {address_type} address",
        })
    if not nodes:
        findings.append({"severity": "WARNING", "message": "No node records were returned"})

    status = "CRITICAL" if duplicates else "WARNING" if findings else "HEALTHY"
    return {
        "status": status,
        "node_count": len(nodes),
        "address_type": address_type,
        "duplicate_count": len(duplicates),
        "nodes_without_address": nodes_without_address,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", help="kubeconfig context; defaults to the current context")
    parser.add_argument("--address-type", choices=("InternalIP", "ExternalIP"), default="InternalIP")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    try:
        context, nodes = load_nodes(args.context)
        report = analyze_nodes(nodes, args.address_type)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report["context"] = context
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Context: {context}")
        print(f"Status: {report['status']}")
        print(f"Nodes inspected: {report['node_count']}")
        print(f"Address type: {report['address_type']}")
        print(f"Duplicate addresses: {report['duplicate_count']}")
        for finding in report["findings"]:
            print(f"[{finding['severity']}] {finding['message']}")
            if "nodes" in finding:
                print(f"  Nodes: {', '.join(finding['nodes'])}")
        if not report["findings"]:
            print("No duplicate or missing addresses detected.")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())