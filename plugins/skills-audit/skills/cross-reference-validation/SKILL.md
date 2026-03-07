---
name: cross-reference-validation
description: Verify cross-references between skills — taxonomy-aware bilateral/unilateral link checking, linkage strength classification.
---

# Cross-Reference Validation

Skills should reference related skills. This skill defines how to check and classify those relationships using a three-tier taxonomy.

## Skill Taxonomy

Skills fall into three categories, each with different cross-reference expectations:

### Utility Skills

Generic capabilities consumed by many domain skills. Examples: `writing-voice`, `pr-style-check`, `bear-notes`, `notion-tickets`.

- Should have a `## Used By` section listing consumers
- `## Cross-References` only for true peers (e.g. writing-voice and pr-style-check)
- Domain skills that consume a utility list it in their `## Cross-References`

### Domain Skills

Workflow-specific skills with cross-references to peers. Everything that isn't utility or standalone.

- Should have `## Cross-References` with bilateral workflow peers
- Should NOT have `## Used By`
- Domain-to-domain links should be bilateral (A references B, B references A)

### Standalone Skills

Self-contained skills with no meaningful cross-references. Examples: `resale-valuator`, `audio-setup`, `keybindings-help`.

- No cross-ref section needed unless genuinely linked
- Do not flag these as missing cross-references

## What to Check

For each skill (`{SKILLS_DIR}/*/SKILL.md`):

1. **Correct section for its type?** — utility has `## Used By`, domain has `## Cross-References`, standalone is exempt
2. **Referenced skills exist?** — each name should map to an actual `SKILL.md`
3. **Domain-to-domain links bilateral?** — if A references B, B should reference A
4. **Utility-to-domain links correct?** — domain lists utility in Cross-References, utility lists domain in Used By
5. **No speculative links?** — remove "may overlap" or uncertain connections

## Linkage Strength

| Strength | Definition | Action |
|----------|-----------|--------|
| **Strong** | Bilateral — A references B and B references A | None needed |
| **Medium** | Unilateral — A references B only | Add the back-link |
| **Weak** | Same domain, no link | Consider adding cross-references |
| **None** | Standalone | Fine for independent skills |

## Detection

Scan each SKILL.md for `## Cross-References` and `## Used By` sections. Extract referenced skill names (lines matching `- **skill-name**`). Build a directed graph. Flag:

- Missing sections (wrong section type for taxonomy category)
- Broken refs (target skill doesn't exist)
- Unilateral links (A references B but not B references A)
- Taxonomy violations (utility skill with Cross-References instead of Used By, etc.)

## Configuration

In `config.json`, define which skills belong to each taxonomy category:

```json
{
  "utility_skills": ["writing-voice", "pr-style-check", "bear-notes", "notion-tickets"],
  "standalone_skills": ["resale-valuator", "audio-setup", "keybindings-help"]
}
```

Skills not listed in either set are treated as domain skills.

## Reporting

```markdown
### Cross-References
- N skills checked, M taxonomy violations, K broken refs, J unilateral links
- [list of specific findings]
```
