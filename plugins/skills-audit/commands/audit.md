---
name: audit
description: Run a full 9-step skills and memory audit.
---

# Full Skills Audit

Run all 9 steps: inventory → cross-refs → drift → staleness → hidden workflows → orphans → linkage strength → queue update → report.

1. **Inventory** — enumerate `{SKILLS_DIR}/*/SKILL.md` and `{MEMORY_DIR}/*.md`
2. **Cross-References** — verify links exist, find missing connections (see `cross-reference-validation` skill)
3. **Content Drift** — anchor checks against source repos (see `content-drift-detection` skill)
4. **Staleness** — flag files past configurable thresholds (see `staleness-detection` skill)
5. **Hidden Workflows** — scan memory for step-by-step procedures that should be skills
6. **Orphans** — broken references (indexed but missing, present but not indexed, dead script refs)
7. **Linkage Strength** — classify skill relationships: strong/medium/weak/none
8. **Queue Update** — add new findings to `{PLUGIN_DIR}/queue.json`, skip duplicates
9. **Report** — markdown summary of all findings

Configuration via `config.json` (copy from `config.example.json`).
