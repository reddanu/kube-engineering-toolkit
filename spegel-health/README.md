# Spegel Health Analyzer

Analyze a local snapshot of peer-to-peer image mirror signals. The bundled snapshot is synthetic; this tool does not call `kubectl`, scrape metrics, read logs, or create workloads.

```bash
python3 spegel_health.py
python3 spegel_health.py --format json
python3 spegel_health.py --input examples/sample-spegel.json --minimum-hit-rate 75
```

The analyzer checks DaemonSet coverage, peer-hit rate, last successful mirror activity, mirror error counts, and image-pull failures.

## Snapshot fields

The input JSON contains a cluster label, schedulable node count, DaemonSet desired/ready counts, peer hits/misses, age of the last successful mirror request, error counts, and image-pull failures. Use synthetic or sanitized data only. Do not include internal hostnames, credentials, or Kubernetes Secret contents.