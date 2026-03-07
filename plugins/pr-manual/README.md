# pr-manual

Pre-submission review checklist for manually crafted upstream PRs. Catches semantic issues that automated CI/linting pipelines miss.

## Install

```bash
claude plugin install pr-manual@mark-liu-skills
```

## Contents

1 skill (`pr-manual`) — a 6-step review checklist:

| Step | Purpose |
|------|---------|
| Related Issues & PRs | Search for existing work, prior fixes, cross-references |
| Placement Analysis | Verify the change lives in the right file/package/abstraction layer |
| Edge Case Audit | Enumerate input combinations, boundary conditions, coverage gaps |
| TDD Gap Analysis | Audit untested paths — integration, error, regression |
| Maintainer Perspective | Score scope discipline, convention compliance, commit hygiene, risk |
| Scope Validation | Re-read the original issue and confirm the fix addresses it |

Pure knowledge — no scripts, no config. Teaches Claude how to review a PR before submission.

## Output

Each review ends with a single verdict:

- **Ship it** — no blocking issues found
- **Fix first** — list of blocking items
- **Reconsider approach** — fundamental design concern
