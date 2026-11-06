# Pods Per Node

An offline adaptation of the pod-per-node discovery utility in `toolkit`. Count pods from a local Kubernetes JSON snapshot without loading kubeconfig, installing the Kubernetes client, or contacting a cluster.

```bash
python3 pods_per_node.py
python3 pods_per_node.py --input examples/pods.json --format json
```

The bundled snapshot is synthetic. The report includes nodes with zero scheduled pods, unscheduled pods, and pods referencing nodes absent from the snapshot. Exit code `2` indicates invalid input; valid snapshots exit `0`.