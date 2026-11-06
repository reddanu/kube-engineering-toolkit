# Ansible GSLB Rule Report

An offline Ansible adaptation of a GSLB monitoring workflow from `toolkit`. It filters a local synthetic snapshot and prints rejected host rules. It does not connect to Kubernetes, send notifications, or modify files or infrastructure.

```bash
ansible-playbook ansible-gslb-report/gslb_rule_report.yml
```

Requires `ansible-core`. The example uses only `.test` hostnames and synthetic statuses. The playbook runs locally and can be reviewed or parsed without cluster credentials.