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

## Avoid Compaction (with exceptions)

Never auto-summarise upstream artifacts. Summarisation loses detail that
downstream steps may need.

- Use explicit `inputs` lists to control what each step sees.
- If an artifact is too big, **truncate with a clear marker** at injection time
  (not summarise). The marker tells the model it's working with incomplete data:
  ```
  [TRUNCATED — artifact 'analysis.md' exceeded 8000 token limit]
  ```
- Summaries are a separate, explicit step if needed — never implicit middleware.

## Cache-Safe Compaction (the exception)

When the context window fills during a long session, compaction is safe IF the
prefix is preserved — same system prompt, same tools, same conversation prefix.
Append the compaction instruction as a new user message (never mutate the system
prompt). Same prefix = cache hit on the entire history before the summary.

Source: [x.com/koylanai/status/2027819266972782633](https://x.com/koylanai/status/2027819266972782633)
