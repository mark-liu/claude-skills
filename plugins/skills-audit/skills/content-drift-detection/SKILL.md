---
name: content-drift-detection
description: Detect when skills referencing code-backed sources have drifted — anchor-based hard drift and file watchlist soft drift.
---

# Content Drift Detection

Skills that quote specific values from source code can silently go stale. Two tiers of detection.

## Hard Drift (Anchors)

Skill quotes a value (version number, config value, function name). The audit greps the source file for a regex pattern. If no match, it is a high-confidence alert -- queued and notified.

```json
{
  "file": "src/config.py",
  "pattern": "MODEL_NAME\\s*=\\s*\"gpt-4",
  "description": "Model name is gpt-4"
}
```

## Soft Drift (File Watchlist)

Skill references source files. The audit checks git for changes since last run. If referenced files changed, it is an informational flag -- logged but no notification.

## State File

`{PLUGIN_DIR}/drift-state.json` tracks per-skill configuration:

```json
{
  "skills": {
    "my-skill": {
      "repo": "~/repos/my-project",
      "last_audited_sha": "abc123",
      "anchors": [
        {"file": "src/config.py", "pattern": "VERSION\\s*=", "description": "Version constant"}
      ],
      "watched_files": ["src/main.py", "config/settings.json"]
    }
  },
  "last_run": "2026-03-01T10:00:00"
}
```

## Setup

1. Seed `drift-state.json` with skills that reference code repos
2. Run `python3 scripts/content_drift_check.py --init` to set baseline SHAs and auto-extract watched files from SKILL.md
3. Run `--dry-run --verbose` to verify anchors are matching

## Adding a New Skill

Edit `drift-state.json`, add a skill entry with:
- `repo` — path to the git repository (supports `~` expansion)
- `anchors` — list of `{file, pattern, description}` objects
- `watched_files` (optional) — auto-populated from SKILL.md backtick-quoted paths if omitted

Then run `--init` to set the baseline SHA.

## Script CLI

```
python3 content_drift_check.py [--init] [--dry-run] [--verbose]
python3 content_drift_check.py --state-path PATH --queue-path PATH --skills-dir PATH
```

The script auto-queues hard drift findings with `priority: high` in the audit queue.

## Reporting

```markdown
### Content Drift
- N anchors checked, M broken (hard drift)
- N watched files, M changed since last audit (soft drift)
```
