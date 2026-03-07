---
name: initializer-agent
description: Deterministic workspace scaffolding for multi-step coding pipelines — task tracker JSON, git branch setup, sanity checks.
---

# Initializer Agent Pattern

Every multi-step pipeline starts with an **init phase** that creates deterministic scaffolding before any agent touches code. Prevents agents from improvising directory structure or colliding with each other.

## What It Does

1. **Create working directory** — timestamped, isolated (`/tmp/agent-{project}-{ts}/`)
2. **Initialize git branch** — `git checkout -b agent/{project}` from latest main
3. **Write task tracker** (`tasks.json`) — structured JSON with `passes: false` per task
4. **Write progress file** (`progress.md`) — template for agents to append to
5. **Run sanity checks** — repo builds clean, tests pass, deps available
6. **Output init result** — working dir path, branch name, tracker path

## Task Tracker Format

JSON over Markdown — LLMs prioritize structured data and are less likely to corrupt JSON fields.

```json
{
  "project": "add-retry-logic",
  "created": "2026-02-28T09:00:00Z",
  "tasks": [
    {"id": "t1", "name": "Add RetryConfig struct", "passes": false},
    {"id": "t2", "name": "Implement backoff logic", "passes": false},
    {"id": "t3", "name": "Wire into HTTP client", "passes": false},
    {"id": "t4", "name": "Add unit tests", "passes": false}
  ]
}
```

Coding agents flip `passes` to `true` only after implementation + verification.
The tracker is the single source of truth for what's done vs pending.

## When to Use

- Multi-feature implementation (3+ tasks)
- Long-running sessions that may span context window boundaries
- Multi-agent DAGs where multiple agents touch the same repo
- Any pipeline where the coding agent isn't the one setting up the workspace

Single-issue, single-agent tasks can fold init into the first step (e.g. a `prep`
step that creates the branch and validates the environment).
