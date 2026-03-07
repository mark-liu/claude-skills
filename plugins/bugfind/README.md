# bugfind

Adversarial 3-agent bug analysis for Claude Code — hunter finds bugs aggressively, skeptic challenges them, referee produces the final verdict.

## Install

```bash
claude plugin install bugfind@mark-liu-skills
```

## How It Works

Three phases run in sequence:

1. **Hunter** (3 parallel agents) — split the codebase by domain, maximize bug count with severity scoring (+1/+5/+10)
2. **Skeptic** (1 agent) — reads actual code at each reported location, disproves false positives with asymmetric penalty (-2x for wrongly dismissing a real bug)
3. **Referee** (orchestrator) — combines results into a prioritised table: fix now, fix when touching, disproved

The skill includes full prompt templates for each agent role, scoring systems, output formats, and fix-application workflow.

## Why Not Just Static Analysis?

`pylint` and `shellcheck` catch syntax issues. This process catches semantic bugs — wrong variable reuse, hardcoded values that will break next year, timezone double-conversions, silent state corruption on failure paths. Run static analysis as a pre-filter, then let the AI agents focus on what tools miss.

## License

MIT
