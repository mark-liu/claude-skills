---
name: security-scanning
description: Source code pattern analysis and CVE triage for MCP server upgrades — pattern list, interpretation guide, and triage workflow.
---

# Security Scanning for MCP Servers

Automated source code scanning flags constructs that warrant manual review before upgrading an MCP server.

## Source Scan Patterns

| Pattern | Category | What it detects |
|---------|----------|----------------|
| `eval()` | Dynamic execution | Arbitrary code execution |
| `new Function()` | Dynamic execution | Runtime code generation |
| `vm.run()`, `vm.createContext` | Dynamic execution | Sandboxed code execution |
| `child_process`, `exec()`, `spawn()` | Process spawning | Shell access |
| `fs.write`, `fs.unlink`, `fs.rm` | File mutation | File system writes |
| `Buffer.from(..., 'base64')` | Obfuscation | Base64 decode (possible obfuscation) |
| Hex escape chains (`\x00\x01...`) | Obfuscation | Encoded strings |
| `crypto.createCipher` | Crypto | Encryption operations |
| `net.connect`, `net.Socket` | Network | Raw socket connections |
| `dns.resolve`, `dns.lookup` | Network | DNS lookups |
| `WebSocket()` | Network | Persistent connections |

## Interpretation Guide

These are **flags for review, not automatic blockers**. Context matters:

| Server type | Expected patterns | Suspicious patterns |
|-------------|------------------|-------------------|
| Terminal/shell MCP | `child_process`, `spawn` | `eval`, obfuscation |
| File management MCP | `fs.write`, `fs.unlink` | `child_process`, network |
| API client MCP | `net.connect`, `dns` | `fs.write`, `eval` |
| Calendar/notes MCP | None of the above | Any of the above |

## CVE Triage Workflow

1. **Critical/High on MCP SDK** (`@modelcontextprotocol/sdk`): affects all npm MCP servers. Check if patched in the latest SDK version.
2. **High on direct dependency**: check if the vulnerable code path is actually exercised by your usage.
3. **Moderate/Low on transitive dep**: note it, upgrade if convenient, don't block on it.
4. **False positives**: `npm audit` flags everything in the dependency tree. Many CVEs are in server-side code that doesn't apply to stdio transport (e.g. ALB IP spoofing is irrelevant for a local MCP server).

## Custom Patterns

Add patterns to `config.json` under `extra_scan_patterns`:

```json
{
  "extra_scan_patterns": [
    ["\\bfetch\\s*\\(", "fetch() — HTTP request"],
    ["\\brequire\\s*\\([^)]*\\bpath\\b", "dynamic require with path — code loading"]
  ]
}
```

Each entry is `[regex_pattern, description]`. These supplement the built-in patterns.
