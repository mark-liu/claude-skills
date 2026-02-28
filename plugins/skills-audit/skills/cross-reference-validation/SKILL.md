---
name: cross-reference-validation
description: Verify cross-references between skills — bilateral/unilateral link checking, linkage strength classification.
---

# Cross-Reference Validation

Skills should reference related skills. Check and classify those relationships.

## What to Check

For each skill (`{SKILLS_DIR}/*/SKILL.md`):

1. **Has a Cross-References section?** — look for `## Cross-References`
2. **Referenced skills exist?** — each name should map to an actual `SKILL.md`
3. **Domain neighbors linked?** — related skills should cross-reference each other

## Linkage Strength

| Strength | Definition | Action |
|----------|-----------|--------|
| **Strong** | Bilateral — A→B and B→A | None needed |
| **Medium** | Unilateral — A→B only | Add the back-link |
| **Weak** | Same domain, no link | Consider adding cross-references |
| **None** | Standalone | Fine for independent skills |

## Detection

Scan each SKILL.md for a `## Cross-References` section. Extract referenced skill names (lines matching `- **skill-name**`). Build a directed graph. Flag: missing sections, broken refs (target doesn't exist), unilateral links (A→B but not B→A).

## Reporting

```markdown
### Cross-References
- N skills checked, M missing section, K broken refs, J unilateral links
```
