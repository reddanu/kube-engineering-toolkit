# Offline Cluster Health

Summarize workload, pod, and node findings from a local TSV snapshot. This offline report does not invoke `kubectl` or contact a cluster.

```bash
bash cluster-health-summary.sh
bash cluster-health-summary.sh ./examples/cluster-health.tsv
bash cluster-health-summary.sh --help
```

Each row contains six tab-separated fields: `kind`, `namespace`, `name`, `current`, `desired`, and `status`. Deployment rows use the replica fields; pod and node rows use `status`. The included snapshot is synthetic. Exit code `1` means the input contains findings, `2` means invalid input or arguments, and `0` means no findings.