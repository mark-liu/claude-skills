---
name: mcp-test
description: MCP protocol handshake smoke test — verifies server starts, initializes, and lists tools.
---

# MCP Test

```bash
python3 ~/scripts/mcp-promote.py test <server> [--version VER]
```

Starts the server, sends `initialize` + `tools/list`. Reports PASS/FAIL with tool count.

Bypasses npx/uv stdin forwarding issues by resolving entrypoints directly (node scripts, native binaries, venv python).

**Limitations**:
- Tests protocol layer only (not tool functionality)
- Auth-dependent servers need valid credentials in claude.json
- SSE-based servers (Playwright, Notion mcp-remote) are not testable
- npm install to tmpdir adds ~5-10s overhead per server
