# Ansible GSLB Rule Report

Filter a local synthetic snapshot and print rejected GSLB host rules. This Ansible playbook does not connect to Kubernetes, send notifications, or modify files or infrastructure.

```bash
ansible-playbook ansible-gslb-report/gslb_rule_report.yml
```

Requires `ansible-core`. The example uses only `.test` hostnames and synthetic statuses. The playbook runs locally and can be reviewed or parsed without cluster credentials.