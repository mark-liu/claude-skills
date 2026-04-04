# skills-audit

Self-maintaining skill and memory hygiene -- cross-reference validation, content drift detection, staleness checks, backup integrity, and improvement queue management.

## Install

```bash
claude plugin install skills-audit@mark-liu-skills
```

## Contents

1 agent (`skill-auditor`) + 2 commands (`audit`, `check-queue`) + 3 skills (`cross-reference-validation`, `content-drift-detection`, `staleness-detection`) + 2 scripts.

## What It Does

A 9-step audit process for skill and memory ecosystems:

1. **Inventory** -- enumerate skills and memory files
2. **Cross-References** -- taxonomy-aware link checking (utility/domain/standalone skills)
3. **Content Drift** -- anchor-based hard drift + file watchlist soft drift against source repos
4. **Staleness** -- flag files past configurable thresholds (infra: 14d, reference: 30d)
5. **Hidden Workflows** -- find procedures in memory that should be skills
6. **Orphans** -- broken references (indexed but missing, present but not indexed)
7. **Linkage Strength** -- classify skill relationships (strong/medium/weak/none)
8. **Queue Update** -- track findings in a persistent queue
9. **Report** -- markdown summary

Additional automated checks: security scan (if `security_scan.py` is provided), backup integrity (symlink verification, untracked/uncommitted file detection).

## Setup

1. Copy `config.example.json` to `config.json` and edit paths for your environment
2. For drift detection: seed `drift-state.json` with code-backed skills, then run `python3 scripts/content_drift_check.py --init`
3. Schedule `scripts/audit-check.py --config config.json` via cron, systemd timer, or launchd

## Configuration

Key fields in `config.json`:

| Field | Purpose |
|-------|---------|
| `skills_dir` | Path to skills directory (e.g. `~/.claude/skills`) |
| `memory_index` | Path to the knowledge index file with date tables |
| `staleness_thresholds` | `infra_days` and `reference_days` thresholds |
| `utility_skills` | Skills that should have `## Used By` sections |
| `standalone_skills` | Skills exempt from cross-ref requirements |
| `backup_repo` | Git repo path for backup integrity checks |
| `expected_symlinks` | Array of `{live, target}` pairs for symlink verification |

## Scripts

- `scripts/audit-check.py` -- main checker, run via scheduler or CLI (`--dry-run`, `--no-notify`, `--output-dir`)
- `scripts/content_drift_check.py` -- standalone drift detection (`--init`, `--dry-run`, `--verbose`, `--state-path`, `--queue-path`)

## Queue Format

```json
{
  "id": "uuid",
  "type": "new-skill | cross-ref | stale | workflow | fix | content-drift",
  "priority": "high | medium | low",
  "title": "Short description",
  "detail": "What needs doing and why",
  "skills": ["affected-skill"],
  "added": "2026-02-28",
  "status": "pending | in-progress | done | wontfix"
}
```
