# Argo CD Health Report

Summarize application sync and health states plus controller readiness from a local JSON snapshot. The included data is synthetic; this tool does not contact an Argo CD API or Kubernetes cluster.

```bash
python3 argocd_health.py
python3 argocd_health.py --format json
python3 argocd_health.py --input examples/sample-applications.json
```

The report flags applications that are not `Synced` or `Healthy`, and controller components whose ready count is below the desired count. Input and output contain names and status metadata only; do not use snapshots containing internal project identifiers or credentials.