---
name: promotion-pipeline
description: Full MCP server upgrade pipeline — five phases from detection through verification, with rollback.
---

# MCP Promotion Pipeline

```
detect → scan → test → promote → verify
```

| Phase | Command | What happens |
|-------|---------|-------------|
| 1. Detect | `mcp-check` | Compare local versions against upstream |
| 2. Scan | `mcp-scan` | CVE check + source pattern analysis |
| 3. Test | `mcp-test` | MCP protocol handshake smoke test |
| 4. Promote | `mcp-promote` | Bump version pins in config files |
| 5. Verify | Manual | Restart session, call one tool |

## Security Analysis

**Automated**: install in tmpdir, `npm audit`, source scan.

**Manual review**: changelog, interpret findings (expected patterns vs suspicious), dependency delta, CVE impact assessment, go/no-go with documented reasoning.

## Rollback

Promote the previous version, then restart Claude Code.

## Upgrade Cadence

- **Critical CVEs**: same day
- **High CVEs on direct deps**: within a week
- **Feature releases**: batch monthly
- **Transitive dep CVEs (moderate/low)**: next routine cycle
