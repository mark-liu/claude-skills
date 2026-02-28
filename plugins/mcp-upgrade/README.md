# mcp-upgrade

Three-phase MCP server upgrade pipeline — security scanning, smoke testing, version promotion with rollback.

## Install

```bash
claude plugin install mcp-upgrade@mark-liu-skills
```

## Contents

1 agent (`mcp-upgrade-advisor`) + 4 commands (`mcp-check`, `mcp-scan`, `mcp-test`, `mcp-promote`) + 2 skills (`security-scanning`, `promotion-pipeline`) + 2 reference scripts.

## Setup

1. Copy `config.example.json` to `config.json`
2. Add your MCP servers (npm packages, git repos, server name mappings)
3. Run `python3 scripts/mcp-versions.py --config config.json` to verify

## Workflow

```
check → scan → test → promote → restart → verify
```
