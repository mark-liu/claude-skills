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

These are **flags for review, not automatic blockers** -- many are legitimate in MCP server code.

## Interpretation Guide

Context matters when reviewing findings:

| Server type | Expected patterns | Suspicious patterns |
|-------------|------------------|-------------------|
| Terminal/shell MCP | `child_process`, `spawn` | `eval`, obfuscation |
| File management MCP | `fs.write`, `fs.unlink` | `child_process`, network |
| API client MCP | `net.connect`, `dns` | `fs.write`, `eval` |
| Calendar/notes MCP | None of the above | Any of the above |

## CVE Triage Workflow

Morning routine advisories come from `npm audit` against npx cache dirs. Triage:

1. **Critical/High on `@modelcontextprotocol/sdk`**: affects all npm MCP servers -- check if patched in latest SDK version
2. **High on direct dependency**: check if the vulnerable code path is exercised by our usage
3. **Moderate/Low on transitive dep**: note it, upgrade if convenient, don't block on it
4. **False positives**: `npm audit` flags everything in the dep tree -- many CVEs are in server-side code that doesn't apply to our MCP usage (e.g., Hono ALB IP spoofing is irrelevant for stdio transport)

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
