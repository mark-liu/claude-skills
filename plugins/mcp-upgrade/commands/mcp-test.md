---
name: mcp-test
description: MCP protocol handshake smoke test — verifies server starts, initializes, and lists tools.
---

# MCP Test

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mcp-promote.py" --config "${CLAUDE_PLUGIN_ROOT}/config.json" test <server> [--version VER]
```

Starts the server, sends `initialize` + `tools/list`. Reports PASS/FAIL with tool count.

Bypasses npx/uv stdin forwarding issues by resolving entrypoints directly (node scripts, native binaries, venv python).

**Limitations**: tests protocol layer only (not tool functionality); auth-dependent servers need valid credentials; SSE-based servers not testable.
