# mcp-upgrade

Three-phase MCP server upgrade pipeline -- security scanning, smoke testing, version promotion with rollback.

## Contents

1 agent (`mcp-upgrade-advisor`) + 4 commands (`mcp-check`, `mcp-scan`, `mcp-test`, `mcp-promote`) + 2 skills (`security-scanning`, `promotion-pipeline`) + 2 reference scripts.

## Workflow

```
check → scan → test → promote → restart → verify
```

| Phase | Command | Description |
|-------|---------|-------------|
| Detect | `mcp-check` | Show available npm/git updates and CVE advisories |
| Scan | `mcp-scan <pkg> <ver>` | Install in tmpdir, npm audit, source pattern analysis |
| Scan (git) | `mcp-scan-git <name>` | Fetch upstream, diff, scan added lines |
| Test | `mcp-test <server>` | MCP protocol handshake + tools/list smoke test |
| Promote | `mcp-promote <pkg> <ver>` | Bump version pins in claude.json, mcp-versions.py, mcp-stack |
| Promote (git) | `mcp-promote-git <name>` | Git pull + update mcp-stack commit hash |
| Verify | Manual | Restart session, call one tool from upgraded server |

## Scripts

- `scripts/mcp-promote.py` -- main pipeline script (scan, test, promote)
- `scripts/mcp-versions.py` -- version checker (npm registry + git ls-remote + npm audit)

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

## discord-mcp Fork Policy

discord-mcp is a maintained fork. Upstream changed logger from stderr to stdout which breaks MCP protocol (logs corrupt JSON-RPC stream). Review upstream changes via `scan-git discord-mcp` and cherry-pick only safe changes -- do NOT blindly `promote-git`.

## Rollback

```bash
# npm: promote the old version
python3 ~/scripts/mcp-promote.py promote <package> <old-version>

# git: reset to old commit
cd ~/.local/share/<repo> && git reset --hard <old-commit>
```

Then restart Claude Code.
