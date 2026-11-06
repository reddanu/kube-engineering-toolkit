# Duplicate Node Addresses

Read Kubernetes node addresses from one explicitly selected or current kubeconfig context and report duplicate `InternalIP` or `ExternalIP` assignments. The tool only runs `kubectl config current-context` (when needed) and `kubectl get nodes -o json`; it never reads Secrets or changes cluster resources.

```bash
python3 check_duplicate_node_addresses.py --context demo-context
python3 check_duplicate_node_addresses.py --address-type ExternalIP --format json
```

Exit codes: `0` no actionable findings, `1` duplicate addresses or missing node addresses, `2` invalid arguments, API data, or command failures. Output includes node names and IP addresses; treat it as operational metadata and review it before sharing.