---
name: bugfind
description: Adversarial 3-agent bug analysis across the local codebase — hunter, skeptic, referee.
triggers:
  - bugfind
  - bug scan
  - find bugs
  - code audit
  - adversarial review
---

# Bugfind

Adversarial 3-agent bug analysis of committed code. Uses the Hunter/Skeptic/Referee
pattern to find real bugs while filtering false positives.

## When to Run

- After significant code changes (new scripts, refactors)
- Periodic hygiene (monthly)
- Before promoting patterns to production
- On user request: `/bugfind`, "find bugs", "code audit"

## Architecture

```
Phase 1: HUNTER (3 parallel agents)
  Codebase split into 3 groups by domain → each agent reads all files in its group
  Maximises bug count with severity scoring (+1/+5/+10)
  Output: raw findings list with file:line, description, impact, points

Phase 2: SKEPTIC (1 agent)
  Receives all Critical (+10) and Medium (+5) findings
  Reads actual code at each location to verify or disprove
  Asymmetric penalty: -2x for wrongly dismissing a real bug
  Output: ACCEPT/DISPROVE verdict for each finding

Phase 3: REFEREE (orchestrator)
  Combines Hunter + Skeptic results
  Produces final prioritised table
  Groups into: fix now, fix when touching, not real
```

## Scope

Configurable. Set your target directories in the Scope section below.

The codebase is split into three domain groups for parallel hunting:

| Group | Domain | Example Files |
|-------|--------|---------------|
| A | API & networking | HTTP clients, webhook handlers, API wrappers, auth modules |
| B | Data processing & pipelines | ETL scripts, parsers, queue consumers, scheduled jobs |
| C | Infrastructure & tooling | Deploy scripts, config generators, monitoring, CLI tools |

## Running

### Full Scan

Invoke with `/bugfind` or "run a bugfind scan". The skill will:

1. Inventory all target files in scope (`wc -l` for sizing)
2. Launch 3 Hunter agents in parallel (one per group)
3. Collect findings, launch 1 Skeptic agent on Critical + Medium
4. Present Referee verdict as a prioritised table
5. Ask which fixes to apply

### Scoped Scan

Narrow scope with arguments:
- `/bugfind auth_handler.py` — single file
- `/bugfind scripts/api-*` — glob pattern
- `/bugfind --group A` — only one domain group

### Fix Mode

After presenting findings, ask:
- "fix all" → apply all accepted fixes
- "fix 1,3,7" → apply specific fixes by number
- "skip" → no fixes, just the report

## Hunter Agent Prompt Template

```
You are a bug-finding agent. Analyze the provided files thoroughly
and identify ALL potential bugs, issues, and anomalies.

**Scoring System:**
- +1 point: Low impact (minor issues, edge cases, cosmetic)
- +5 points: Medium impact (functional issues, data inconsistencies,
  race conditions, silent failures)
- +10 points: Critical impact (security vulnerabilities, data loss
  risks, crashes, credential exposure)

**Your mission:** Maximize your score. Be thorough and aggressive.
Report anything that *could* be a bug. False positives are acceptable
— missing real bugs is not.

Focus areas:
- Error handling gaps (uncaught exceptions, bare except, swallowed errors)
- Race conditions in file I/O, PID files, subprocess calls
- Security issues (credential exposure, command injection, path traversal)
- Logic bugs (off-by-one, wrong variable, stale state)
- Silent failures (errors caught but not logged/reported)
- Resource leaks (unclosed files, connections, processes)
- Hardcoded values that will break (years, paths, tickers)
- Missing input validation at system boundaries

**Output format:**
For each bug:
1. File:line_number
2. Description
3. Impact level (Low/Medium/Critical)
4. Points awarded

End with total score.
```

## Skeptic Agent Prompt Template

```
You are an adversarial bug reviewer. Challenge every Critical and
Medium bug by READING THE ACTUAL CODE at the reported location.

**Scoring:**
- Disprove a bug: +[original score]
- Wrongly dismiss a real bug: -2x [original score]

For each bug:
1. Read the file at the reported line
2. Analyze whether the bug is real
3. Decision: DISPROVE / ACCEPT
4. Confidence level (%)

Common disprove reasons:
- Input is trusted/local (no injection surface)
- Python version handles it (e.g., ET.fromstring safe in 3.7+)
- Error propagates correctly to caller
- Single-user macOS (no multi-user attack surface)
- Intentional design choice (e.g., --no-verify for auto-commit)
- Framework guarantees safety (e.g., CDP always has default context)
```

## Referee Rules

The orchestrator (main context) acts as Referee:

1. **Accept** findings where both Hunter and Skeptic agree it's real
2. **Accept** findings the Skeptic couldn't disprove (low confidence)
3. **Override Skeptic** if the disprove reasoning is weak
4. **Downgrade** findings where severity was overstated
5. **Group** into: Critical (fix now), Medium (fix when touching), Disproved

## Output Format

Final table presented to user:

```markdown
### CRITICAL (fix soon)
| # | File | Line | Bug | Fix |
|---|------|------|-----|-----|

### MEDIUM (fix when touching)
| # | File | Line | Bug | Fix |
|---|------|------|-----|-----|

### DISPROVED
| # | Claim | Reason |
|---|-------|--------|

### Quick Wins (one-liners)
1. file:line — change X to Y
```

## AI-in-the-Loop Design

This skill requires AI judgement at every phase — it cannot be automated
via launchd or cron. The Hunter, Skeptic, and Referee all need LLM reasoning.

**Recommended cadence:** Monthly, or after major code changes. User triggers
manually via `/bugfind` in a Claude Code session.

**Why not automate:**
- Hunter agents need to understand code semantics, not just patterns
- Skeptic needs to reason about whether input sources are trusted
- Referee needs to weigh context (single-user macOS, local scripts, etc.)
- Fix application needs human approval for each change
- Static analysis tools (pylint, shellcheck) catch syntax issues but miss
  the semantic bugs this process finds (wrong ticker, hardcoded year,
  timezone double-conversion, state-save-on-failure)

**Hybrid approach:** Run `shellcheck` and `pylint` as a pre-filter, then
feed their output to the Hunter agents as additional context. This catches
the easy stuff mechanically and lets the AI focus on semantic bugs.

## History

| Date | Files | LOC | Bugs Found | Accepted | Fixed |
|------|-------|-----|-----------|----------|-------|

## Notes

Works well alongside multi-agent orchestration patterns and code audit skills.
