---
name: staleness-detection
description: Flag memory and topic files past configurable thresholds — infrastructure (14 days) and reference (30 days). Includes hidden workflow detection and orphan finding.
---

# Staleness Detection

Memory and topic files go stale. This skill defines how to detect staleness, find hidden workflows that should be skills, and identify orphaned references.

## Staleness Check

For each memory topic file:

1. Parse the "Updated" date from your knowledge index (e.g. MEMORY.md table rows like `| \`topic.md\` | ... | 2026-02-23 |`)
2. Classify the file as infrastructure/ops or reference/knowledge
3. Apply thresholds:
   - **Infrastructure/ops files**: flag if >14 days stale (configurable)
   - **Reference/knowledge files**: flag if >30 days stale (configurable)
4. Exempt files with special cadences (e.g. quarterly reports, books updated on read)

Also parses cold-tier indexes (e.g. `index-cold.md` sibling) so both hot and cold tiers are checked.

### Classification

Infrastructure keywords (default): `infra`, `ops`, `deploy`, `monitor`, `agents`, `projects`, `people`

Files containing these keywords get the shorter threshold. Everything else uses the reference threshold.

### Configuration

In `config.json`:

```json
{
  "staleness_thresholds": {
    "infra_days": 14,
    "reference_days": 30
  },
  "infra_keywords": ["infra", "ops", "deploy", "monitor", "agents", "projects", "people"],
  "exempt_files": ["quarterly-report.md", "books.md"]
}
```

## Hidden Workflow Detection

Scan memory files for workflow patterns that should be skills:

- **Step-by-step procedures** — numbered lists with shell commands
- **Conditional workflows** — "When X happens, do Y" patterns
- **Script references** — scripts mentioned in memory but with no corresponding skill

Compare against existing skills. Flag workflows in memory that could be promoted to skills.

## Orphan Detection

Find broken references across the ecosystem:

| Orphan type | What to check |
|-------------|---------------|
| Indexed but missing | Skill listed in knowledge index but no SKILL.md file exists |
| Present but not indexed | SKILL.md exists but isn't listed in knowledge index |
| Memory not indexed | Topic file exists but isn't in the knowledge index table |
| Dead script refs | Script referenced in a skill but doesn't exist on disk |

## Reporting

```markdown
### Staleness
- N files checked, M stale

| File | Last Updated | Age | Threshold | Type |
|------|-------------|-----|-----------|------|
| infra-lessons.md | 2026-02-10 | 19d | 14d | infra |

### Hidden Workflows
- N workflows found that could be skills
- [list with file and line reference]

### Orphans
- N orphaned references found
- [list with type and details]
```
