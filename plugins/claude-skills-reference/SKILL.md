---
name: claude-skills-reference
description: Claude Skills format reference — SKILL.md structure, YAML frontmatter, progressive disclosure, patterns, and distribution. Use when building, reviewing, or troubleshooting Claude Code skills.
---

# Claude Skills — Reference

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

Three levels, from manual to automated:

### Manual Checks
- **Triggering**: does it load on relevant queries, not on unrelated ones?
- **Functional**: correct outputs, successful API calls, error handling works
- **Performance**: compare with vs without skill (tool calls, tokens, corrections)

### Eval Framework (via skill-creator)

Store test cases in `evals/evals.json` alongside the skill:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "assertions": [],
      "files": []
    }
  ]
}
```

Run evals by spawning parallel subagents — one with-skill, one baseline (no skill or previous version). Each agent gets a clean context to prevent bleed. Results go in `<skill-name>-workspace/iteration-N/eval-ID/`.

### Benchmarking

After evals run, track per-iteration:
- **Pass rate** across assertions
- **Execution time** and **token consumption**
- **A/B comparison** — blind evaluator agent scores skill-v1 vs skill-v2 output

### Description Optimizer

Analyzes the skill's `description` field against sample prompts and suggests edits to improve trigger accuracy (reduce false positives and false negatives). Anthropic reported improved triggering on 5/6 public skills after applying this. Use when a skill undertriggers or overtriggers — run the optimizer before manually tweaking description text.

## Distribution
- **Claude.ai**: Settings > Capabilities > Skills (upload zip)
- **Claude Code**: place in skills directory
- **API**: `/v1/skills` endpoint, `container.skills` parameter in Messages API
- **Org-wide**: admins deploy workspace-wide (shipped Dec 2025)
- **Open standard**: portable across platforms (like MCP)

## Memory Integration

Skills handle **procedure** — how to do something. Topic files handle **knowledge** — what's been learned across sessions. The two layers reinforce each other.

### Topic Files

A skill can have an associated topic file in a persistent memory directory. The topic file stores facts, lessons, state, and context that the skill needs but shouldn't embed (because it changes over time).

```
skill: deploy-pipeline     → topic file: deploy-history.md
skill: api-integration     → topic file: api-inventory.md
skill: monitoring-alerts   → topic file: alert-patterns.md
```

Not every skill needs one. Pure procedure skills (style guides, upgrade runbooks) work fine standalone. Add a topic file when the skill accumulates knowledge across sessions — server inventories, learned lessons, project state, contact details.

### Memory Index

Maintain an index table in your main memory file mapping topic files to their skills:

```markdown
| Topic File | Skill | Key Contents | Updated |
|------------|-------|-------------|---------|
| deploy-history.md | deploy-pipeline | Deployment log, rollback procedures | 2026-02-28 |
| api-inventory.md | api-integration | Endpoint registry, auth methods, rate limits | 2026-02-28 |
```

Also list skill-only entries (no topic file) so you know the full inventory. The index is your routing table — scan it before searching blindly.

### Backlinks

Cross-references should be bilateral:
- **Topic file → skill**: mention which skill provides the procedure
- **Memory index → both**: map the relationship so either can be found from the index
- **Skill → topic file**: reference the topic file when the skill needs persistent knowledge

| Linkage | Direction | Purpose |
|---------|-----------|---------|
| Strong (bilateral) | Skill ↔ Topic file, both in index | Full coverage — audit tools can verify |
| Medium (unilateral) | One direction only | Works but fragile — add the backlink |
| Weak (implicit) | Related but no explicit reference | Fine for loosely related skills |

### Promotion Pipeline

Knowledge flows upward through tiers:
1. **Daily logs** — raw session notes, errors, decisions (append-only)
2. **Topic files** — curated facts promoted from daily logs
3. **Memory index** — hot summary of all topic files (always loaded)

Only promote when a fact has proven durable across multiple sessions. The daily log is cheap — write everything. The memory index is expensive (always in context) — keep it tight.

## skill-creator

Anthropic's official tool for creating and iterating on skills. Updated March 2026 with eval framework and description optimizer.

### Availability
- **Claude.ai**: built-in
- **Claude Code**: install as plugin — `github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator`
- **Standalone repo**: `github.com/anthropics/skills/tree/main/skills/skill-creator`

### Core Workflow
1. Capture intent — what the skill does, when it triggers, expected output
2. Write SKILL.md draft
3. Create test prompts → run with-skill + baseline agents in parallel
4. Evaluate results (qualitative review + quantitative assertions)
5. Iterate: rewrite skill → re-run evals → compare versions
6. Optimize description for trigger accuracy

### Key Features (March 2026)
- **Eval framework** — `evals/evals.json` with prompts, expected outputs, and assertions
- **Multi-agent parallel testing** — each eval runs in isolated agent context, no bleed
- **A/B comparison** — blind evaluator scores skill-v1 vs v2 or skill vs no-skill
- **Benchmark mode** — tracks pass rate, execution time, token cost across iterations
- **Description optimizer** — analyzes trigger phrases against sample prompts, suggests edits to reduce false positives/negatives. Improved triggering on 5/6 public skills in Anthropic's testing

### When to Use
- Building a new skill from scratch
- Diagnosing trigger misfires (undertriggering or overtriggering)
- Comparing before/after when editing an existing skill
- Invoke: "Help me build a skill using skill-creator"

Source: [Improving skill-creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) (Lance Martin, March 2026)

## Quality Standards (established 2026-03-04)

Every skill should meet these standards. Use as a checklist when building or reviewing skills.

### Required Sections
1. **YAML frontmatter** — `name` + `description` with trigger phrases and negative triggers
2. **Cross-References** — bilateral links to related skills and topic files (at bottom of file)

### Recommended Sections (for workflow/operational skills)
3. **Error Handling** — table with Failure / Symptom / Recovery columns
4. **Verification** — post-action validation steps; HARD-GATE for safety-critical operations
5. **Safety** — explicit rails for destructive/remote/financial operations

### Progressive Disclosure
- SKILL.md body must stay under 5,000 words
- Move detailed reference material to `references/` subdirectory (e.g. `book-notes` uses 5 domain files)
- Move executable code to `scripts/` subdirectory
- First skill using `references/`: `book-notes` (753-line monolith → 138-line index + 5 reference files)

### Common Defects (from 2026-03-04 audit of 49 skills)
- Non-standard YAML keys (e.g. `trigger:` instead of trigger phrases in `description:`)
- Missing cross-references (unilateral links, no backlinks)
- No error handling for common failure modes
- No verification steps — claims success without evidence
- Wall-of-text structure instead of decision trees / tables
- Flat files exceeding 5,000 words without `references/` extraction

## Cross-References
- Companion to any skill-building workflow
- Works with audit/quality tools that verify skill structure
