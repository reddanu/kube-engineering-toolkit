# Argo CD Cluster Application Cleanup

Preview or remove Argo CD Application records for a decommissioned cluster. The default is read-only.

## Requirements

- Bash 3.2 or newer, `kubectl`, and `jq`
- A kubeconfig context for the Kubernetes cluster hosting Argo CD
- Permission to list Applications in the Argo CD namespace; cleanup also requires get, patch, and delete permissions

## Usage

Preview Applications matching the exact destination name:

```bash
bash argocd-cluster-cleanup/argocd-cluster-cleanup.sh --context argo-host --cluster retired-cluster
```

For Applications using a destination server URL, verify the exact URL and provide it with `--server`. Without it, a matching hostname is shown only as an unselected candidate.

```bash
bash argocd-cluster-cleanup/argocd-cluster-cleanup.sh --context argo-host --cluster retired-cluster --server https://retired-cluster.example.com
```

To remove selected Application records, replace `--cluster` with `--cleanup`, review the refreshed list, and confirm with `y`:

```bash
bash argocd-cluster-cleanup/argocd-cluster-cleanup.sh --context argo-host --cleanup retired-cluster --server https://retired-cluster.example.com
```

Use `--app NAME` to restrict the operation to exact Application names; repeat the flag to select more than one. Use `--namespace NAME` when Argo CD Applications are not in the default `argocd` namespace. Run `--help` for all options.

## Safety

- Cleanup targets Application records only; it does not delete or modify ApplicationSets, cluster registrations, or Kubernetes Secrets.
- Removal is non-cascading: the script removes Argo CD resource-deletion finalizers before deleting an Application, preserving its deployed resources. Other finalizers are retained and may prevent deletion.
- Applications owned by an ApplicationSet or managed from Git may be recreated. Update the generator or source as appropriate and verify the result after cleanup.
- Identity, destination, and resource-version checks protect against concurrent changes. Conflicting deletes are retried up to three times, then reported as failures. A deletion request is not proof that the Application is gone.
- Output contains operational metadata; review it before sharing. Test against a non-production Argo CD instance first.
