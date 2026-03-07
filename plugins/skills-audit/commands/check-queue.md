---
name: check-queue
description: Quick review of pending audit findings from the queue.
---

# Check Audit Queue

Read `{PLUGIN_DIR}/queue.json`, filter to `status: "pending"`, present as table:

```
## Audit Queue (N pending)

| # | Priority | Type | Title | Age |
|---|----------|------|-------|-----|
| 1 | high     | content-drift | Broken anchor in my-skill | 3d |
| 2 | medium   | stale | Update infra-lessons.md (18 days) | 5d |
```

Ask: "Want to tackle any of these, or skip?"

If no queue file exists, suggest running `/skills-audit:audit` first.
