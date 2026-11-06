# Offline Cluster Triage

Analyze a sanitized Kubernetes snapshot as JSON and report common health signals. The included example contains synthetic data. This tool is offline: it does not call `kubectl`, Azure, or any cluster API.

```bash
python3 cluster_health.py
python3 cluster_health.py --format json
python3 cluster_health.py --input examples/sample-cluster.json --restart-threshold 5
```

The report checks node readiness, pending or failed pods, high container restart counts, deployments below their desired replica count, and PodDisruptionBudgets with no allowed disruptions.

## Input format

Provide a sanitized JSON file with `cluster`, `nodes`, `pods`, `deployments`, and `pod_disruption_budgets` fields. The analyzer reads only those fields and does not print unrecognized input fields. Never include credentials, Secret object data, internal hostnames, or real production identifiers in example snapshots.

## Exit behavior

Exit code `0` means the input was analyzed successfully. Health findings are reported in the output and do not cause an error exit. Invalid or unreadable input exits nonzero.