# agent-orchestration

Multi-agent coordination patterns for Claude Code — filesystem state, claim/abort, context budgets, initializer agents, research-before-coding pipelines.

## Install

```bash
claude plugin install agent-orchestration@mark-liu-skills
```

## Contents

1 agent (`orchestration-advisor`) + 5 skills: `filesystem-coordination`, `claim-abort-patterns`, `initializer-agent`, `context-discipline`, `research-pipeline`.

Pure knowledge — no scripts, no config. Skills teach Claude the patterns; your dispatcher implements them.
