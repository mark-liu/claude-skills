---
name: skill-format
description: SKILL.md structure, YAML frontmatter, progressive disclosure, and distribution. Use when building, reviewing, or troubleshooting Claude Code skills.
---

# Skill Format Reference

Source: "The Complete Guide to Building Skills for Claude" (Anthropic, Jan 2026)

## What is a Skill

A folder that teaches Claude how to handle specific tasks/workflows. Works across Claude.ai, Claude Code, and API.

### Required Structure
```
skill-name/              # kebab-case only
├── SKILL.md             # required — instructions + YAML frontmatter
├── scripts/             # optional — executable code
├── references/          # optional — docs loaded as needed
└── assets/              # optional — templates, fonts, icons
```

No `README.md` inside the skill folder (goes at repo level for human users).

### YAML Frontmatter (always in system prompt)
```yaml
---
name: skill-name          # required, kebab-case, no spaces/capitals
description: |            # required, <1024 chars, no XML tags
  What it does. Use when user asks to [trigger phrases].
license: MIT              # optional
allowed-tools: "Bash(python:*) WebFetch"  # optional
compatibility: "..."      # optional, 1-500 chars
metadata:                 # optional
  author: Name
  version: 1.0.0
  mcp-server: server-name
---
```

**Forbidden**: XML angle brackets (`< >`), "claude" or "anthropic" in skill name.

## Progressive Disclosure (3 levels)
1. **Frontmatter** — always in system prompt. Just enough for Claude to know *when* to use the skill.
2. **SKILL.md body** — loaded when Claude thinks the skill is relevant.
3. **Linked files** (`references/`, `scripts/`) — loaded only as needed.

## Use Case Categories
1. **Document & Asset Creation** — consistent output (docs, presentations, code, designs)
2. **Workflow Automation** — multi-step processes with validation gates
3. **MCP Enhancement** — workflow guidance on top of MCP tool access (the "recipe" layer)

## Key Patterns
1. **Sequential workflow orchestration** — explicit step ordering, dependencies, validation at each stage
2. **Multi-MCP coordination** — phases spanning multiple services, data passing between MCPs
3. **Iterative refinement** — draft → quality check → fix → re-validate loop
4. **Context-aware tool selection** — decision tree for same outcome via different tools
5. **Domain-specific intelligence** — embedded expertise (compliance rules, style guides)

## Best Practices
- Keep SKILL.md under 5,000 words; move detailed docs to `references/`
- Description must include WHAT + WHEN (trigger conditions)
- Include specific trigger phrases users would actually say
- Add negative triggers if over-triggering ("Do NOT use for...")
- Put critical instructions at the top, use `## Critical` headers
- For critical validations, bundle a script rather than relying on language instructions
- Error handling: include common MCP issues and fixes

## Testing
- **Triggering**: does it load on relevant queries, not on unrelated ones?
- **Functional**: correct outputs, successful API calls, error handling works
- **Performance**: compare with vs without skill (tool calls, tokens, corrections)

## Distribution
- **Claude.ai**: Settings > Capabilities > Skills (upload zip)
- **Claude Code**: place in skills directory
- **API**: `/v1/skills` endpoint, `container.skills` parameter in Messages API
- **Org-wide**: admins deploy workspace-wide (shipped Dec 2025)
- **Open standard**: portable across platforms (like MCP)

## skill-creator
- Built into Claude.ai and available for Claude Code
- Generates skills from natural language descriptions
- Reviews existing skills and suggests improvements
- Invoke: "Help me build a skill using skill-creator"
