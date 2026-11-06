# Kong Config Check

Check a local declarative gateway JSON document for duplicate host/path combinations and route references to missing services. The included fixture uses `.test` domains and synthetic names; no gateway API is contacted.

```bash
python3 kong_config_check.py
python3 kong_config_check.py --format json
python3 kong_config_check.py --input examples/sample-config.json
```

The report includes counts and indexed findings only. It never prints configured URLs, hosts, paths, service names, or plugin settings. Use synthetic or sanitized configuration.