---
name: claim-abort-patterns
description: PID-based job claiming, heartbeat files, external abort markers, and retry via outbox re-entry.
---

# Claim/Abort Patterns

For multi-agent dispatchers or any coordinator managing parallel workers.

## Claiming a Job

```
{AGENTS_DIR}/active/{id}/
  spec.json     # original job spec
  pid           # process ID of worker
  .heartbeat    # touched periodically by long jobs
```

The PID file is the primary claim. On each dispatch cycle, the reaper checks:

1. **Process dead?** — `os.kill(pid, 0)` fails → reap, write failed result.
2. **Stale?** — claim age > 2x timeout AND no fresh heartbeat (mtime < 60s) → SIGTERM, reap.
3. **Abort requested?** — `.abort` file exists → SIGTERM, write "aborted" result.

## Heartbeat

For jobs that legitimately exceed their timeout, touch the heartbeat file periodically:

```bash
touch "$AGENT_HEARTBEAT_FILE"  # env var set by dispatcher
```

## External Abort

```bash
touch {AGENTS_DIR}/active/{id}/.abort
```

Next reap cycle SIGTERMs the worker and writes an "aborted" result to inbox.

## Retry

Failed/aborted jobs retry via outbox re-entry. Dispatcher decrements `retry` count and creates `{id}-retry{N}`.

## Key Lessons

- PID-based claims are simple and race-free on single-host systems
- `.abort` marker avoids PID reuse races (simpler than signal-based cancellation)
- Heartbeats prevent false-positive reaping of slow-but-alive jobs
- Always write a result (even "failed") so downstream consumers aren't left waiting
