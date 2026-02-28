---
name: mcp-check
description: Show available updates for all configured MCP servers.
---

# MCP Check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcp-versions.py" --config "${CLAUDE_PLUGIN_ROOT}/config.json"
```

Outputs JSON with `npm_updates`, `git_updates`, `advisories`, and a `summary` line. See `security-scanning` skill for CVE triage guidance.
