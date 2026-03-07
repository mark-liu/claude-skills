---
name: mcp-promote
description: Bump MCP server version pins in config files.
---

# MCP Promote

**npm packages**:
```bash
python3 ~/scripts/mcp-promote.py promote <package> <version>
```

**git repos**:
```bash
python3 ~/scripts/mcp-promote.py promote-git <name>
```

Updates version pins in three files:
- `~/.claude.json` -- pinned version in server args
- `~/scripts/mcp-versions.py` -- NPM_PACKAGES dict
- `~/.claude/skills/mcp-stack/SKILL.md` -- version inventory table

Restart Claude Code after promoting.

**Rollback**: promote the previous version, or `git reset --hard <old-commit>` for git repos. Then restart.

See `promotion-pipeline` skill for the full workflow and verification steps.
