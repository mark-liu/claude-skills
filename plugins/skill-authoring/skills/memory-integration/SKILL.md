---
name: memory-integration
description: Persistent knowledge layer for skills — topic files, memory indexes, backlinks, and the promotion pipeline. Use when designing skills that accumulate knowledge across sessions.
---

# Memory Integration

Skills handle **procedure** — how to do something. Topic files handle **knowledge** — what's been learned across sessions. The two layers reinforce each other.

## Topic Files

A skill can have an associated topic file in a persistent memory directory. The topic file stores facts, lessons, state, and context that the skill needs but shouldn't embed (because it changes over time).

```
skill: mcp-upgrade          → topic file: mcp-stack.md
skill: agent-orchestration   → topic file: local-agents.md
skill: twitter-threads       → topic file: twitter-threads.md
```

Not every skill needs one. Pure procedure skills (style guides, upgrade runbooks) work fine standalone. Add a topic file when the skill accumulates knowledge across sessions — server inventories, learned lessons, project state, contact details.

## Memory Index

Maintain an index table in your main memory file mapping topic files to their skills:

```markdown
| Topic File | Skill | Key Contents | Updated |
|------------|-------|-------------|---------|
| mcp-stack.md | mcp-stack | Server inventory, versions, launch commands | 2026-02-28 |
| local-agents.md | local-agent-dispatch | Mailbox pattern, dispatcher config | 2026-02-28 |
```

Also list skill-only entries (no topic file) so you know the full inventory. The index is your routing table — scan it before searching blindly.

## Backlinks

Cross-references should be bilateral:
- **Topic file → skill**: mention which skill provides the procedure
- **Memory index → both**: map the relationship so either can be found from the index
- **Skill → topic file**: reference the topic file when the skill needs persistent knowledge

| Linkage | Direction | Purpose |
|---------|-----------|---------|
| Strong (bilateral) | Skill ↔ Topic file, both in index | Full coverage — audit tools can verify |
| Medium (unilateral) | One direction only | Works but fragile — add the backlink |
| Weak (implicit) | Related but no explicit reference | Fine for loosely related skills |

### Verifying Backlinks

Build a directed graph from all cross-references. Flag:
- **Missing sections**: skill or topic file has no cross-reference section
- **Broken refs**: referenced target doesn't exist
- **Unilateral links**: A→B but not B→A

Automate this check — run it on a schedule (daily or weekly) so drift is caught early.

## Promotion Pipeline

Knowledge flows upward through tiers:

```
Daily logs (raw, append-only)
    ↓ promote when durable
Topic files (curated facts)
    ↓ summarize for index
Memory index (always loaded, scan first)
```

1. **Daily logs** — raw session notes, errors, decisions. Cheap to write — log everything.
2. **Topic files** — curated facts promoted from daily logs when they've proven durable across multiple sessions.
3. **Memory index** — hot summary of all topic files. Always loaded into context, so keep it tight. This is the routing table — if a fact isn't here, it should be findable by scanning the index and reading the right topic file.

### What to Promote

- Stable patterns confirmed across multiple sessions
- Architectural decisions and their rationale
- Learned lessons from failures (especially costly ones)
- Key file paths, inventories, and configuration details

### What NOT to Promote

- Session-specific context (current task, in-progress work)
- Unverified conclusions from reading a single file
- Anything that duplicates existing instructions
- Facts that might change next week

## Skill-Only vs Skill+Topic

| Type | Example | When to Use |
|------|---------|-------------|
| **Skill-only** | Style guides, runbooks, format references | Procedure is stable, no session-to-session state |
| **Skill + topic file** | Infrastructure ops, project tracking, server inventory | Knowledge accumulates and changes over time |

When in doubt, start skill-only. Add a topic file when you find yourself repeatedly looking up the same facts across sessions.
