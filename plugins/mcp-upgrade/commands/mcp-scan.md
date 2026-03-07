---
name: mcp-scan
description: Security scan an MCP package — npm audit + source pattern analysis.
---

# MCP Scan

**npm packages**:
```bash
python3 ~/scripts/mcp-promote.py scan <package> <version>
```

**git repos**:
```bash
python3 ~/scripts/mcp-promote.py scan-git <name>
```

npm scan installs to tmpdir, runs `npm audit --json`, scans source for suspicious patterns. Returns JSON with vulnerability count, source findings, dependency count, package size.

git scan fetches upstream, diffs against local HEAD, scans added lines. Returns JSON with commit log, line counts, findings, plus full diff.

See `security-scanning` skill for pattern interpretation and triage.
