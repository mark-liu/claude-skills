---
name: filesystem-coordination
description: Filesystem as shared coordination layer in multi-agent pipelines — atomic writes, directory conventions, incremental writes.
---

# Filesystem as Shared State

Use the filesystem as the coordination layer. One directory per work unit, atomic writes, no external DB dependency.

## Directory Conventions

```
{AGENTS_DIR}/
  runs/{id}/artifacts/    # per-run step outputs
  active/{id}/            # claimed job with pid, spec, logs
  outbox/{id}.json        # pending job specs
  inbox/{id}.json         # completed results
```

## Why Not a Database?

Agents crash, get killed, lose connections. Filesystem state survives all of that. `ls` is your query engine. `cat` is your debugger. Every artifact is inspectable without tooling.

## Atomic Writes

Always `write(tmp) + rename(final)` for artifacts read concurrently. Partial writes cause corrupt reads.

```python
import tempfile
from pathlib import Path

def atomic_write(target: Path, content: str) -> None:
    tmp = tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False, suffix=".tmp")
    try:
        tmp.write(content)
        tmp.flush()
        Path(tmp.name).rename(target)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise
```

## Incremental Writes

Write partial results as work progresses, not batched at end.

- Scripts write output artifacts to their designated artifacts directory as they go.
  If the step crashes mid-way, partial artifacts survive for debugging.
- Long-running jobs expose a progress file (e.g. via env var). Write structured
  JSON progress so the orchestrator can report status on failure:
  ```json
  {"phase": "compiling", "files_processed": 12, "total": 30}
  ```
- Failed jobs include their last progress snapshot in the inbox result,
  giving the next agent (or human) context on where things broke.
