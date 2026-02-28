---
name: context-discipline
description: Protecting the orchestrator's context window — explicit inputs, token budgets, hard-fail on oversized prompts, truncation over summarization.
---

# Orchestrator Context Discipline

The orchestrator's context window is the scarcest resource. Protect it.

## Explicit Inputs Per Step

Never "load everything from the run dir". Each step declares exactly which artifacts it needs:

```json
{"step": "judge", "inputs": ["analysis.md", "test-results.json"], "max_input_tokens": 6000}
```

Undeclared artifacts are invisible to the step. This prevents context pollution.

## Per-Artifact Token Budgets

Default ~8000 tokens per artifact. Steps with many inputs use lower budgets. Example: judge step with 5 inputs at 6000 each = 30k tokens, leaving room for system prompt + response.

## Log Prompt Sizes

Every LLM step should log `chars` and `~tokens` per artifact. Silent context overflow wastes API budget on truncated or garbage responses.

## Hard-Fail on Oversized Prompts

If rendered prompt exceeds budget (e.g. 200k chars), fail immediately rather than burning an API call.

## Truncation, Not Summarization

Never auto-summarize upstream artifacts — summarization loses detail. Truncate with a clear marker:

```
[TRUNCATED — artifact 'analysis.md' exceeded 8000 token limit]
```

Summaries, if needed, are a separate explicit step — never implicit middleware.

## Cache-Safe Compaction

When the context window fills, compaction is safe if the prefix is preserved (same system prompt, tools, conversation prefix). Append compaction instruction as a new user message — never mutate the system prompt. Same prefix = cache hit.
