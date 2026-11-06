# AVI / AMKO Health Report

Summarize GSLB site and pool health plus host-rule synchronization from a local JSON snapshot. The included data is synthetic; this tool does not contact AVI, AMKO, Kubernetes, or any network endpoint.

```bash
python3 avi_amko_report.py
python3 avi_amko_report.py --format json
python3 avi_amko_report.py --input examples/sample-gslb.json
```

Use sanitized status metadata only. The report intentionally omits configured URLs, VIPs, and other endpoint values.