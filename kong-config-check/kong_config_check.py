#!/usr/bin/env python3
"""Check local declarative Kong configuration without printing identifiers."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(__file__).parent / "examples" / "sample-config.json"


@dataclass(frozen=True)
class Finding:
    severity: str
    message: str


def load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read input file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("configuration must be a JSON object")
    for key in ("services", "routes", "plugins"):
        if not isinstance(value.get(key, []), list) or not all(isinstance(item, dict) for item in value.get(key, [])):
            raise ValueError(f"configuration.{key} must be a list of objects")
    value.setdefault("plugins", [])
    return value


def named_entities(items: list[dict[str, Any]], label: str) -> dict[str, int]:
    names: dict[str, int] = {}
    for index, item in enumerate(items, start=1):
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} record {index} requires a name")
        if name in names:
            raise ValueError(f"duplicate {label} name at record {index}")
        names[name] = index
    return names


def analyze(config: dict[str, Any]) -> list[Finding]:
    services = named_entities(config["services"], "service")
    routes = named_entities(config["routes"], "route")
    findings: list[Finding] = []
    seen_routes: dict[tuple[str, str], int] = {}

    for index, route in enumerate(config["routes"], start=1):
        service = route.get("service")
        if not isinstance(service, str) or service not in services:
            findings.append(Finding("ERROR", f"Route record {index} references an unknown service"))
        hosts = route.get("hosts", [])
        paths = route.get("paths", [])
        if not isinstance(hosts, list) or not all(isinstance(item, str) and item for item in hosts):
            raise ValueError(f"route record {index} hosts must be a list of non-empty strings")
        if not isinstance(paths, list) or not all(isinstance(item, str) and item for item in paths):
            raise ValueError(f"route record {index} paths must be a list of non-empty strings")
        if not hosts or not paths:
            findings.append(Finding("WARNING", f"Route record {index} has no host or path matcher"))
        for host in hosts:
            for path in paths:
                key = (host.lower(), path.rstrip("/") or "/")
                if key in seen_routes:
                    findings.append(Finding("WARNING", f"Route records {seen_routes[key]} and {index} have a duplicate host/path matcher"))
                else:
                    seen_routes[key] = index

    for index, plugin in enumerate(config["plugins"], start=1):
        service = plugin.get("service")
        route = plugin.get("route")
        if service is not None and (not isinstance(service, str) or service not in services):
            findings.append(Finding("WARNING", f"Plugin record {index} references an unknown service"))
        if route is not None and (not isinstance(route, str) or route not in routes):
            findings.append(Finding("WARNING", f"Plugin record {index} references an unknown route"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="synthetic or sanitized declarative JSON")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report output format")
    args = parser.parse_args()
    try:
        config = load_config(args.input)
        findings = analyze(config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    status = "CRITICAL" if any(item.severity == "ERROR" for item in findings) else "WARNING" if findings else "HEALTHY"
    report = {
        "source": "synthetic" if args.input.resolve() == DEFAULT_INPUT.resolve() else "local config",
        "service_count": len(config["services"]),
        "route_count": len(config["routes"]),
        "plugin_count": len(config["plugins"]),
        "status": status,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Source: {report['source']}\nStatus: {status}\nServices: {report['service_count']}\nRoutes: {report['route_count']}\nPlugins: {report['plugin_count']}")
        for item in findings:
            print(f"[{item.severity}] {item.message}")
        if not findings:
            print("No configuration findings detected.")
    return 1 if any(item.severity in ("WARNING", "ERROR") for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())