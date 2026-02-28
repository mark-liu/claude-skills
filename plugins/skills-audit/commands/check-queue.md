---
name: check-queue
description: Quick review of pending audit findings.
---

# Check Audit Queue

Read `{PLUGIN_DIR}/queue.json`, filter to `status: "pending"`, present as table:

```
| # | Priority | Type | Title | Age |
|---|----------|------|-------|-----|
```

If no queue file exists, suggest running `/skills-audit:audit` first.
