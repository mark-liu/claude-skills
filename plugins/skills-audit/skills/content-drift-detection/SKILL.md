---
name: content-drift-detection
description: Detect when skills referencing code-backed sources have drifted — anchor-based hard drift and file watchlist soft drift.
---

# Content Drift Detection

Skills that quote specific values from source code can silently go stale. Two tiers of detection.

## Hard Drift (Anchors)

Skill quotes a value → audit greps source file for a regex → no match = high-confidence alert.

```json
{"file": "src/config.py", "pattern": "MODEL_NAME\\s*=\\s*\"gpt-4", "description": "Model name is gpt-4"}
```

## Soft Drift (File Watchlist)

Skill references source files → audit checks git for changes since last run → informational flag.

## State File

`{PLUGIN_DIR}/drift-state.json` tracks per-skill: `repo`, `last_audited_sha`, `anchors[]`, `watched_files[]`.

## Setup

1. Seed `drift-state.json` with skills that reference code repos
2. Run `python3 scripts/content-drift-check.py --init` to set baseline SHAs
3. Run `--dry-run --verbose` to verify

To add a new skill: edit `drift-state.json`, add entry with `repo`, `anchors`, optionally `watched_files` (auto-populated from SKILL.md if omitted). Run `--init`.

Script accepts `--state-path`, `--queue-path`, `--skills-dir` CLI args.
