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
  "tasks": [
    {"id": "t1", "name": "Add RetryConfig struct", "passes": false},
    {"id": "t2", "name": "Implement backoff logic", "passes": false},
    {"id": "t3", "name": "Add unit tests", "passes": false}
  ]
}
```

Agents flip `passes` to `true` only after implementation + verification.

## When to Use

- Multi-feature implementation (3+ tasks)
- Multi-agent DAGs where multiple agents touch the same repo
- Long-running sessions spanning context window boundaries

Skip for single-issue bug fixes or tasks where the user manages the workspace.
