# VMware Inventory Report

Summarize VM state and datastore capacity signals from a local JSON snapshot. The bundled fixture is synthetic. The tool does not connect to vCenter, ESXi, or a network endpoint, and it omits IP addresses and datastore names from reports.

```bash
python3 vmware_inventory.py
python3 vmware_inventory.py --format json
python3 vmware_inventory.py --input examples/sample-inventory.json
```

Use sanitized status and capacity fields only. Snapshot age thresholds are illustrative defaults.