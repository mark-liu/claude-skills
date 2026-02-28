# skills-audit

Self-maintaining skill and memory hygiene — cross-reference validation, content drift detection, staleness checks, improvement queue management.

## Install

```bash
claude plugin install skills-audit@mark-liu-skills
```

## Contents

1 agent (`skill-auditor`) + 2 commands (`audit`, `check-queue`) + 3 skills (`cross-reference-validation`, `content-drift-detection`, `staleness-detection`) + 2 reference scripts.

## Setup

1. Copy `config.example.json` to `config.json`, edit paths
2. For drift detection: seed `drift-state.json` with code-backed skills
3. Schedule `scripts/audit-check.py --config config.json` via launchd/cron/systemd
