# Claude Code Conventions & Patterns

Distilled from ~3 months of daily Claude Code usage — 70+ skills, 12
autonomous agents, and hundreds of sessions. These are the patterns that
survived contact with reality.

Companion article: [Treating Claude Code Like Infrastructure](https://idlepig.substack.com)

## 1. Memory Architecture

Three-layer system. Each layer has different update cadence and cost.

```
Daily Logs (append-only, raw)
    ↓ promotion (hourly scan)
Topic Files (curated facts, per-domain)
    ↓ tiering (6-hourly)
Memory Index (hot summary, always in context)
```

### Principles

- **Daily logs are cheap** — write everything. Errors, decisions, links,
  corrections. They're the audit trail and the promotion source.
- **Topic files are curated** — only promote when a fact has proven durable
  across multiple sessions. One file per domain (not per session).
- **The index is expensive** — always loaded into context. Keep it tight.
  Two tiers: hot (always loaded) and cold (read on demand).
- **Retrieval over re-reading** — search memory files and cite source.
  If a fact is stored, find it rather than re-deriving.
- **Self-correction pipeline** — after ANY user correction, fix the issue,
  then record the lesson in the relevant topic file.

## 2. Safety & Verification Discipline

### HARD-GATE

Before claiming any task is complete, you MUST have either:
1. Run a verification command and shown the output, OR
2. Explicitly stated "I cannot verify this because [reason]"

"It should work" is not verification.

### Anti-Rationalization Table

Load this into every session. If you catch yourself thinking any of these, STOP:

| Excuse | Reality |
|--------|---------|
| "Too simple to need verification" | Simple things break. Verify takes 10 seconds. |
| "I already checked mentally" | Mental checks miss things. Run the actual command. |
| "The user seems in a hurry" | A wrong answer wastes more time than verification. |
| "This is just a minor change" | Minor changes cause major outages. Verify anyway. |
| "I'll verify at the end" | Errors compound. Verify each step. |
| "The approach is obviously correct" | Obvious is the enemy of correct. Show evidence. |

### 3-Fix Rule

If 3+ attempted fixes for the same issue have failed, **STOP fixing and
question the approach**. The architecture, assumptions, or diagnosis is
likely wrong. Step back and re-investigate. Present findings instead of
trying a 4th fix.

### Filesystem Checkpoints

PreToolUse hook snapshots files before destructive bash commands (rm,
rsync --delete, git reset --hard). Git stash + tar to timestamped
directory. Rollback script restores from any checkpoint.

### Remote Infrastructure Safety

Default to **read-only** for any system outside the local machine.
Mutating operations require showing the exact command and waiting for
explicit approval. Each destructive action gets its own confirmation.

## 3. Skill Design

### Skill Categories (9 types)

From Anthropic's internal audit ([Thariq, Mar 2026](https://x.com/trq212/status/2033949937936085378)):

| # | Category | Purpose |
|---|----------|---------|
| 1 | Library & API Reference | How to use a library/CLI correctly |
| 2 | Product Verification | Test/verify output is correct |
| 3 | Data Fetching & Analysis | Connect to data/monitoring stacks |
| 4 | Business Process & Team | Automate repetitive workflows |
| 5 | Code Scaffolding | Generate framework boilerplate |
| 6 | Code Quality & Review | Enforce code quality standards |
| 7 | CI/CD & Deployment | Fetch, push, deploy code |
| 8 | Runbooks | Symptom -> investigation -> report |
| 9 | Infrastructure Operations | Maintenance with destructive guardrails |

### Progressive Disclosure

Three tiers — don't dump everything into context:

1. **Frontmatter** — always loaded. Description = when to trigger.
2. **SKILL.md body** — loaded when relevant. Keep under 5,000 words.
3. **Linked files** (references/, scripts/) — loaded only as needed.

### On-Demand Session Hooks

Skills that register hooks activated only when invoked:

- `/careful` — blocks destructive commands (rm -rf, DROP TABLE, force-push)
  via PreToolUse matcher. Activate when touching prod.
- `/freeze` — blocks Edit/Write outside a specified directory. Activate when
  debugging to prevent accidental "fixes" to unrelated code.

### Gotchas Sections

The highest-signal content in any skill. Build from real failure points.
Update over time as new edge cases are hit:

```markdown
## Gotchas
- **Problem**: description of what goes wrong
  **Fix**: the correct approach
  **Why**: root cause (so the lesson transfers)
```

### Cross-References

Bilateral links between related skills and topic files. Automated audit
checks for broken or missing backlinks.

### Skill Measurement

Log every skill invocation via a PreToolUse hook ([Thariq's pattern](https://gist.github.com/ThariqS/24defad423d701746e23dc19aace4de5)):

```bash
# settings.json
{ "hooks": { "PreToolUse": [{ "matcher": "Skill", "hooks": [{
  "type": "command", "command": "~/.claude/hooks/log-skill.sh"
}]}]}}

# log-skill.sh
payload=$(cat)
skill=$(jq -r '.tool_input.skill' <<< "$payload")
echo "$(date -u +%s) $USER $skill" >> ~/.claude/skill-usage.log
```

## 4. Hook Ecosystem

Hooks are the nervous system. Each one is a shell script triggered by
Claude Code events.

| Hook | Event | Purpose |
|------|-------|---------|
| FS checkpoint | PreToolUse:Bash | Snapshots before destructive commands |
| Audit log | PostToolUse | Every tool call -> JSONL |
| Agent check-in | PostToolUse | Nudges Claude when background agents finish |
| Daily log | PostToolUse:Edit\|Write | Appends to daily log when topic files edited |
| Merged branch guard | PreToolUse:Bash | Blocks push/commit on merged branches |
| Tool miss detector | PostToolUse:Bash | Detects "command not found", suggests fixes |
| Autocommit | PostToolUse:Edit\|Write | Git add/commit/push memory repo |

### Design Principles

- Fast (<1s) — Claude waits for PreToolUse hooks
- Silent on success — only output on actionable events
- Idempotent — same input, same output
- Session-scoped dedup via `/tmp/` files to prevent alert fatigue

## 5. Agent Architecture

### Mailbox Pattern

```
Claude writes spec -> outbox/{id}.json
                          |
            launchd dispatcher (every 60s)
                          |
                    active/{id}/
                          |
                 inbox/{id}.json <- Claude reads on check-in
```

### Filesystem as Shared State

Use the filesystem as the coordination layer. One directory per work unit.
Atomic writes (write to tmp then rename). No external DB dependency.

**Why not a database?** Agents crash, get killed, lose connections.
Filesystem state survives all of that. `ls` is your query engine.

### Claim/Abort

- PID file as primary claim
- Heartbeat file for long-running jobs
- `.abort` marker for external cancellation
- Failed jobs include last progress snapshot

### Context Discipline

The orchestrator's context window is the scarcest resource:
- Explicit inputs per step — never "load everything"
- Per-artifact token budgets (default 8000 tokens per input)
- Hard-fail on oversized prompts (>200k chars)
- Log prompt sizes for every LLM step

Credit: Seth Lazar's multi-agent orchestration patterns.

## 6. Infrastructure Phase Convention

All infrastructure skills follow a 3-phase model:

| Phase | Scope | Mutation | Human Gate |
|-------|-------|----------|------------|
| Phase 1 | Intelligence & assessment | None | None |
| Phase 2 | Testnet / non-prod | Non-prod only | Operator awareness |
| Phase 3 | Production | Prod, staggered | Every step |

## 7. Prompt Caching Principles

From [Thariq, "Prompt Caching Is Everything"](https://x.com/trq212/status/2024574133011673516):

Prompt caching is a **prefix match** — any change in the prefix invalidates
everything after it.

### Ordering (static first, dynamic last)

```
1. Static system prompt & tools    (globally cached)
2. Project context (CLAUDE.md)     (cached within a project)
3. Session context                 (cached within a session)
4. Conversation messages           (per-turn)
```

### Rules

- Never change models mid-session — use subagents instead
- Never add/remove tools mid-session — use `defer_loading` stubs
- Use system messages for updates — don't mutate the system prompt
- Model state transitions as tools (e.g. EnterPlanMode/ExitPlanMode)
- Cache-safe compaction — fork with identical prefix
- Monitor cache hit rate like uptime

## 8. Output Discipline

- **No AI meta-references** — never mention tool limitations or AI constraints
  in external-facing artifacts. Output should read like a human wrote it.
- **Human-scale delays** — add 30-60s between sequential external posts
  so timestamps look natural.
- **Writing voice skill** — load platform-specific formatting rules before
  composing messages on behalf of the user.

## 9. Feedback Loop

1. User corrects something
2. Fix the immediate issue
3. Record the lesson in the relevant topic file
4. If pattern-level, add to the skill's Gotchas section
5. If safety-critical, add to HARD-GATE or anti-rationalization table

### Pre-flight Constraints

For non-trivial tasks, state which 2-3 constraints apply before writing
code. One sentence — not a plan, just acknowledgement that the rules
are loaded.

---

## Credits

- **Thariq Shihipar** (@trq212, Anthropic) — skill taxonomy, prompt caching, progressive disclosure, skill measurement hooks
- **Seth Lazar** — multi-agent context discipline, orchestration patterns
- **Erlang/OTP** — supervision trees, mailbox pattern, crash-and-restart philosophy
- **Aviation checklists** — HARD-GATE verification, anti-rationalization discipline
- **Infrastructure engineering** — phase gates, canary deployments, circuit breakers

## License

MIT — steal whatever is useful.
