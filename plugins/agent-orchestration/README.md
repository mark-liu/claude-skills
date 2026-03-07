# agent-orchestration

Multi-agent coordination patterns for Claude Code — filesystem state, claim/abort, context budgets, initializer agents, research-before-coding pipelines.

## Install

```bash
claude plugin install agent-orchestration@mark-liu-skills
```

## Contents

1 agent (`orchestration-advisor`) + 5 skills:

| Skill | Purpose |
|-------|---------|
| `filesystem-coordination` | Filesystem as shared state, atomic writes, directory conventions, incremental writes |
| `claim-abort-patterns` | PID claims, heartbeat, abort markers, retry via outbox re-entry |
| `initializer-agent` | Deterministic workspace scaffolding, JSON task tracker, git branch setup |
| `context-discipline` | Explicit inputs, token budgets, hard-fail on oversized prompts, compaction advice |
| `research-pipeline` | Research-before-coding DAG with blockedBy dependencies, dispatcher integration |

Pure knowledge — no scripts, no config. Skills teach Claude the patterns; your dispatcher implements them.

## Lessons Learned

Hard-won lessons from running multi-agent pipelines in production.

| Lesson |
|--------|
| Filesystem state survives crashes; databases add failure modes |
| Log prompt sizes — silent context overflow wastes API budget |
| Explicit inputs prevent context pollution between steps |
| Heartbeats prevent false-positive reaping of slow-but-alive jobs |
| Never auto-summarise — truncate with markers instead |
| Partial artifacts on failure beat total data loss |
| PID-based claims are simple and race-free on single-host systems |
| `.abort` marker is simpler than signal-based cancellation |
