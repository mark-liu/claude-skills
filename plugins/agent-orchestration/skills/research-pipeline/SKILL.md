---
name: research-pipeline
description: Research-before-coding DAG — parallel research agents, synthesis, PRD generation, phased execution with blockedBy dependencies.
---

# Research-Before-Coding Pipeline

Dispatch research agents first, synthesize findings, create a phased PRD, then execute. Prevents coding agents from guessing at requirements.

## Phases

| Phase | Job type | blockedBy | Output |
|-------|----------|-----------|--------|
| 0. Init | Single agent creates workspace + tracker | none | Working dir, `tasks.json`, clean branch |
| 1. Research | Parallel agents (one per question) | init | `inbox/{id}.json` with findings |
| 2. Synthesize | Single agent reads all research results | all research IDs | Unified context document |
| 3. PRD | Single agent writes phased plan | synthesize ID | `prd.md` with phases |
| 4. Execute | One or more agents per phase | prd ID | Code, tests, artifacts |

## Research Agent Design

Good research agents are **specific and bounded**:
- "Find the API surface for package X" (bounded)
- "List all callers of function Y in repo Z" (bounded)
- "Research best practices for X" (too vague — produces generic output)

Output should be structured (facts, code snippets, API signatures) — not opinions.

## Dispatcher Integration

All jobs go into outbox at once. The `blockedBy` field on each spec controls
execution order — the dispatcher skips jobs whose blockers haven't landed in
inbox yet.

```python
# Example: dispatch a research-before-coding pipeline
import json
from pathlib import Path

OUTBOX = Path("{AGENTS_DIR}") / "outbox"

jobs = [
    {"id": "research-api", "type": "shell", "command": "..."},
    {"id": "research-docs", "type": "shell", "command": "..."},
    {"id": "research-perf", "type": "shell", "command": "..."},
    {
        "id": "synthesise",
        "type": "script",
        "script": "synthesise.py",  # implement per pipeline
        "blockedBy": ["research-api", "research-docs", "research-perf"],
    },
    {
        "id": "write-prd",
        "type": "script",
        "script": "write-prd.py",  # implement per pipeline
        "blockedBy": ["synthesise"],
    },
]
for job in jobs:
    (OUTBOX / f"{job['id']}.json").write_text(json.dumps(job, indent=2))
```

### Output Convention

Downstream jobs read blocker results from inbox:

```python
from pathlib import Path
import json

INBOX = Path("{AGENTS_DIR}") / "inbox"

def load_blocker_results(spec):
    return {
        bid: json.loads((INBOX / f"{bid}.json").read_text())
        for bid in spec.get("blockedBy", [])
        if (INBOX / f"{bid}.json").exists()
    }
```

## When to Use

- Multi-feature implementation with unclear requirements
- Greenfield projects needing API/library research
- Refactoring requiring codebase analysis before planning

Skip for well-defined bug fixes, complete requirements, or small changes (< 3 files).
