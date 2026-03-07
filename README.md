# claude-skills

Operational plugins for Claude Code — multi-agent orchestration, skill maintenance, MCP server lifecycle, and skill authoring.

## Install

```bash
claude plugin marketplace add mark-liu/claude-skills

claude plugin install agent-orchestration@mark-liu-skills
claude plugin install skills-audit@mark-liu-skills
claude plugin install mcp-upgrade@mark-liu-skills
claude plugin install skill-authoring@mark-liu-skills
claude plugin install claude-skills-reference@mark-liu-skills
```

Or test locally: `claude --plugin-dir ./plugins/skill-authoring`

## Plugins

### Operations & Infrastructure

**agent-orchestration** — filesystem state, claim/abort, context budgets, initializer agents, research-before-coding pipelines. Pure knowledge, no scripts. 5 skills + 1 agent.

**skills-audit** — cross-reference validation, content drift detection, staleness checks, improvement queue. 3 skills + 2 commands + 1 agent + 2 scripts.

**mcp-upgrade** — security scanning, smoke testing, version promotion with rollback. 2 skills + 4 commands + 1 agent + 2 scripts.

**skill-authoring** — SKILL.md format reference and memory integration patterns. Topic files, bilateral backlinks, memory indexes, and the promotion pipeline. 2 skills.

### Reference

**claude-skills-reference** — comprehensive guide to building Claude Code skills: SKILL.md format, YAML frontmatter, progressive disclosure, testing framework, quality standards. Pure knowledge.

## Requirements

- Claude Code with plugin support
- Python 3.11+ (for skills-audit and mcp-upgrade scripts)
- Node.js / npm (for mcp-upgrade scanning and testing)

## License

MIT
