# Namespace Label Selector Report

List namespaces matching a caller-supplied Kubernetes label selector. This generalizes the profile-repository namespace listing without hard-coded organization labels. It uses only `kubectl config current-context` when needed and `kubectl get namespaces`; it does not read Secrets or modify resources.

```bash
bash label-selector-report.sh --selector 'team=demo'
bash label-selector-report.sh --selector 'team=demo' --context demo-context
```

The selector is required, preventing an unfiltered namespace listing. Output includes namespace names and context metadata; review before sharing.