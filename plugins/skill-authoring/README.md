# skill-authoring

How to build, structure, and maintain Claude Code skills. Covers the official SKILL.md format plus operational patterns for persistent knowledge management.

## Skills

**skill-format** — SKILL.md structure, YAML frontmatter, progressive disclosure, testing, and distribution. Based on Anthropic's official skill guide.

**memory-integration** — Persistent knowledge layer for skills that accumulate state across sessions. Topic files, memory indexes, bilateral backlinks, and the promotion pipeline (daily logs → topic files → memory index).

## When to Use

- Building a new skill from scratch
- Reviewing or troubleshooting an existing skill
- Designing a skill system with persistent memory
- Setting up cross-reference auditing between skills and knowledge files

## Install

```bash
claude plugin install skill-authoring@mark-liu-skills
```

Or test locally: `claude --plugin-dir ./plugins/skill-authoring`
