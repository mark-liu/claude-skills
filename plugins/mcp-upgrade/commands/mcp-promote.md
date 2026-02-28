---
name: mcp-promote
description: Bump MCP server version pins in config files.
---

# MCP Promote

**npm packages**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcp-promote.py" --config "${CLAUDE_PLUGIN_ROOT}/config.json" promote <package> <version>
```

**git repos**:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcp-promote.py" --config "${CLAUDE_PLUGIN_ROOT}/config.json" promote-git <name>
```

Updates `claude.json` version pins and any configured tracking files. Restart Claude Code after promoting. Rollback = promote the old version.

See `promotion-pipeline` skill for the full workflow and verification steps.
