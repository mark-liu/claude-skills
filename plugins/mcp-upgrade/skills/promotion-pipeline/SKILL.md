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

## Smoke Test Details

**Pass criteria**:
- Server starts without crash
- MCP `initialize` handshake succeeds (valid JSON-RPC response)
- `tools/list` returns tools (count > 0)
- No unexpected errors on stderr

**Implementation notes**:
- npx and uv don't forward stdin to child processes -- the test bypasses them:
  - npm servers: installs to tmpdir, resolves bin entry, runs with `node` directly
  - Native binary wrappers (slack Go binary): detects `execFileSync` in wrapper, finds platform binary, runs directly
  - uv servers: resolves `.venv/bin/python` and runs script directly
- Playwright and Notion (mcp-remote SSE) are not testable via this method

**Known limitations**:
- Auth-dependent servers test with existing credentials from claude.json -- if tokens expired, failure is auth not server
- Test exercises protocol layer only, not individual tool functionality
- npm install to tmpdir adds ~5-10s overhead per server

## Post-Upgrade Verification

After session restart, call one tool from the upgraded server to verify end-to-end:
- slack: `slack_list_channels` or `slack_search`
- gdrive: `search` for a known file
- telegram: `get_chats`
- discord: `get_servers`
- codex: `ping`

## Rollback

```bash
# Revert npm to previous version
python3 ~/scripts/mcp-promote.py promote <package> <old-version>

# Revert git repo to previous commit
cd ~/.local/share/<repo> && git reset --hard <old-commit>
```

Then restart Claude Code.

## Package to Server Mapping

| Package | Server(s) | Type |
|---------|-----------|------|
| slack-mcp-server | slack | npm |
| mcp-remote | notion | npm |
| mcp-fantastical | fantastical | npm |
| @playwright/mcp | playwright | npm |
| @piotr-agier/google-drive-mcp | gdrive-work, gdrive-personal | npm |
| codex-mcp-server | codex | npm |
| telegram-mcp | telegram | git (upstream) |
| discord-mcp | discord | git (fork) |

### discord-mcp Fork Policy

discord-mcp is a **maintained fork** -- do NOT blindly `promote-git`. Upstream changed logger from stderr to stdout which breaks MCP protocol (logs corrupt JSON-RPC stream). The fork has the fix. Review upstream changes via `scan-git discord-mcp` and cherry-pick only safe changes.

## Upgrade Cadence

- **Critical CVEs**: same day
- **High CVEs on direct deps**: within a week
- **Feature releases**: batch monthly
- **Transitive dep CVEs (moderate/low)**: next routine cycle
