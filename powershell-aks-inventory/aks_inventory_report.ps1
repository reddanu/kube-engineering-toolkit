[CmdletBinding()]
param(
    [string]$InputPath = (Join-Path $PSScriptRoot 'examples/aks-inventory.json'),
    [ValidateSet('table', 'json')]
    [string]$Format = 'table'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
    Write-Error "Snapshot not found: $InputPath"
    exit 2
}

try {
    $snapshot = Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
}
catch {
    Write-Error "Cannot parse JSON snapshot: $($_.Exception.Message)"
    exit 2
}

if ($null -eq $snapshot.clusters) {
    Write-Error "Snapshot must contain a 'clusters' array."
    exit 2
}

$rows = @(
    foreach ($cluster in @($snapshot.clusters)) {
        if ($null -eq $cluster.nodePools -or @($cluster.nodePools).Count -eq 0) {
            [pscustomobject]@{
                Cluster = $cluster.name
                Location = $cluster.location
                KubernetesVersion = $cluster.kubernetesVersion
                ClusterState = $cluster.provisioningState
                Pool = '(none)'
                Mode = '-'
                Count = 0
                VmSize = '-'
                PoolState = '-'
            }
            continue
        }

        foreach ($pool in @($cluster.nodePools)) {
            [pscustomobject]@{
                Cluster = $cluster.name
                Location = $cluster.location
                KubernetesVersion = $cluster.kubernetesVersion
                ClusterState = $cluster.provisioningState
                Pool = $pool.name
                Mode = $pool.mode
                Count = $pool.count
                VmSize = $pool.vmSize
                PoolState = $pool.provisioningState
            }
        }
    }
)

if ($Format -eq 'json') {
    $rows | ConvertTo-Json -Depth 4
}
else {
    $rows | Format-Table -AutoSize
}