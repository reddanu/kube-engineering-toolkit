# PowerShell AKS Inventory

Read a local AKS inventory JSON snapshot with PowerShell. This report does not call Azure, require Az modules, or change the active subscription.

```powershell
./aks_inventory_report.ps1
./aks_inventory_report.ps1 -InputPath ./examples/aks-inventory.json -Format json
```

The included cluster and node-pool values are synthetic. PowerShell 5.1 or newer is required. Exit code `2` indicates a missing or invalid input file.