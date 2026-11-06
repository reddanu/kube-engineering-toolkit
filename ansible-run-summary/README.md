# Ansible Run Summary

Summarize task outcome counts from a local JSON report. The bundled fixture is synthetic. This tool does not run Ansible or connect to managed hosts.

```bash
python3 ansible_run_summary.py
python3 ansible_run_summary.py --format json
python3 ansible_run_summary.py --input examples/sample-run.json
```

The input format is intentionally limited to host labels and aggregate `ok`, `changed`, `failed`, `unreachable`, and `skipped` counts. Do not include task output, variables, credentials, or internal hostnames.