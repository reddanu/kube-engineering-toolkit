# Kubernetes Engineering Toolkit

A personal collection of small, read-only tools for inspecting Kubernetes clusters and troubleshooting common workload issues.

These are clean-room, general-purpose utilities. They contain no employer-owned source, internal endpoints, credentials, or environment configuration. They do not read Kubernetes `Secret` objects or modify cluster resources. Command output can still contain environment-specific names and metadata; review it before sharing.

## Requirements

- Bash 3.2 or newer
- Python 3.9 or newer for offline JSON analyzers
- `kubectl` configured for the cluster you intend to inspect
- Read permissions for the resources queried by each script
- Azure CLI (`az`) for the AKS node-pool report

## Tools

### Cluster snapshot

Show the active context, nodes, namespaces, and pending or failed pods:

```bash
bash cluster-snapshot/cluster-snapshot.sh
```

### Duplicate node addresses

Inspect node `InternalIP` or `ExternalIP` assignments in an explicitly named context, or use the current context:

```bash
python3 duplicate-node-addresses/check_duplicate_node_addresses.py --context <context-name>
python3 duplicate-node-addresses/check_duplicate_node_addresses.py --address-type ExternalIP --format json
```

The report includes node names and addresses, which are operational metadata. Review it before sharing.

### Namespace label selector

List namespaces matching a required label selector without hard-coded organization labels:

```bash
bash label-selector-report/label-selector-report.sh --selector 'team=demo'
bash label-selector-report/label-selector-report.sh --selector 'team=demo' --context <context-name>
```

### Pod triage

List pods and warning events across namespaces, or narrow the output to one namespace:

```bash
bash pod-triage/pod-triage.sh
bash pod-triage/pod-triage.sh <namespace>
```

### Pod disruption budgets

Review disruption budgets and allowed disruptions across the cluster, or for one namespace:

```bash
bash pdb-report/pdb-report.sh
bash pdb-report/pdb-report.sh <namespace>
```

### DNS lookup

Check A and AAAA records through the system resolver or a specified DNS server:

```bash
bash dns-check/dns-check.sh example.org
bash dns-check/dns-check.sh example.org 1.1.1.1
```

The DNS utility uses `dig` when available and falls back to `nslookup`.

### AKS node pools

List node-pool provisioning state and configuration for one explicitly selected cluster:

```bash
bash aks-nodepool-report/aks-nodepool-report.sh --resource-group <resource-group> --cluster <cluster-name>
bash aks-nodepool-report/aks-nodepool-report.sh --resource-group <resource-group> --cluster <cluster-name> --subscription <subscription-id>
```

The report passes the subscription directly to Azure CLI and does not change the active Azure subscription.

### Offline cluster triage

Analyze a local JSON snapshot. The default example is synthetic; this tool does not connect to Kubernetes:

```bash
python3 kube-triage/cluster_health.py
python3 kube-triage/cluster_health.py --format json
```

### Spegel health

Evaluate mirror health from a local synthetic or sanitized JSON snapshot:

```bash
python3 spegel-health/spegel_health.py
python3 spegel-health/spegel_health.py --format json
```

### Argo CD health

Summarize application sync/health and controller readiness from a local snapshot:

```bash
python3 argocd-health/argocd_health.py
python3 argocd-health/argocd_health.py --format json
```

### RKE2 etcd health

Review quorum, database utilization, fsync latency, and pending proposals from synthetic or sanitized metrics:

```bash
python3 rke2-etcd-health/etcd_health.py
python3 rke2-etcd-health/etcd_health.py --format json
```

### AVI / AMKO report

Review synthetic GSLB site, pool, and host-rule health without contacting a controller:

```bash
python3 avi-amko-report/avi_amko_report.py
python3 avi-amko-report/avi_amko_report.py --format json
```

### VMware inventory

Summarize VM power, guest-tools, snapshot-age, and datastore utilization signals from a local snapshot:

```bash
python3 vmware-inventory/vmware_inventory.py
python3 vmware-inventory/vmware_inventory.py --format json
```

### Ansible run summary

Summarize task result counts from a local sanitized JSON report:

```bash
python3 ansible-run-summary/ansible_run_summary.py
python3 ansible-run-summary/ansible_run_summary.py --format json
```

### Kong config check

Check synthetic declarative gateway configuration for duplicate routes and unresolved service references:

```bash
python3 kong-config-check/kong_config_check.py
python3 kong-config-check/kong_config_check.py --format json
```

The Kubernetes scripts only issue `kubectl get` and local kubeconfig context commands. The AKS report only lists node pools. All analyzers read local JSON only. None of the tools modify infrastructure or save output to files.

## Report contract

Offline health analyzers use `HEALTHY`, `WARNING`, or `CRITICAL` in JSON. Their process exits with `0` when no actionable findings exist (`INFO` findings are allowed), `1` when findings need attention, and `2` for invalid arguments or input. A report describes only the supplied snapshot; it is not proof of current live-system health. The Ansible summary exits `1` for failed or unreachable hosts.

## Porting scope

These are clean-room, read-only adaptations of general reporting and troubleshooting patterns from the personal profile repository and the AKS, Kubernetes, Spegel, Rancher/RKE2, AVI/AMKO, VMware, Ansible, and Argo CD areas. Fixed organization labels were replaced with caller-supplied selectors. The Kong configuration check is an original offline utility. No internal URLs, credentials, or production data were copied. Credential and remote-access workflows, cleanup, migration, restart, scaling, and other mutation tools were excluded.

## Safety

- Confirm `kubectl config current-context` before running a tool.
- Treat output as potentially sensitive operational metadata; do not commit real cluster output.
- These scripts do not retrieve, print, or decode secret values.
- Review permissions and test against a non-production cluster before adapting the tools.

## Development

Check shell syntax without connecting to a cluster:

```bash
bash -n */*.sh
python3 -m py_compile kube-triage/cluster_health.py
python3 -m py_compile spegel-health/spegel_health.py
python3 -m py_compile argocd-health/argocd_health.py rke2-etcd-health/etcd_health.py
python3 -m py_compile avi-amko-report/avi_amko_report.py
python3 -m py_compile vmware-inventory/vmware_inventory.py
python3 -m py_compile ansible-run-summary/ansible_run_summary.py
python3 -m py_compile kong-config-check/kong_config_check.py
python3 -m py_compile duplicate-node-addresses/check_duplicate_node_addresses.py
```