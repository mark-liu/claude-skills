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

All jobs go into outbox at once. `blockedBy` controls execution order — dispatcher skips jobs whose blockers haven't landed in inbox.

Downstream jobs read blocker results from `inbox/{blocker_id}.json`.

## When to Use

- Multi-feature implementation with unclear requirements
- Greenfield projects needing API/library research
- Refactoring requiring codebase analysis before planning

Skip for well-defined bug fixes, complete requirements, or small changes (< 3 files).
