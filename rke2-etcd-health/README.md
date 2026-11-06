# RKE2 etcd Health Analyzer

Review etcd quorum and performance signals from a local JSON snapshot. The included example is synthetic; this tool does not connect to etcd, SSH, Kubernetes, or a Rancher server.

```bash
python3 etcd_health.py
python3 etcd_health.py --format json
python3 etcd_health.py --input examples/sample-etcd.json
```

The analyzer checks healthy member count, database utilization, WAL fsync latency, and pending Raft proposals. Thresholds are illustrative defaults, not universal service-level objectives. Replace example values only with sanitized data.