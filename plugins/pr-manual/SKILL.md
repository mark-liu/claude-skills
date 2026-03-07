---
name: pr-manual
description: Pre-submission review checklist for manually crafted upstream PRs. Runs placement analysis, edge case audit, TDD gap check, related issue search, scope validation, and maintainer perspective scoring.
triggers:
  - /pr-manual
  - manual PR review
  - PR readiness check
user_invocable: true
---

# Manual PR Review

Run this before submitting any manually crafted upstream PR. It catches issues that automated pipelines miss because they don't have the context a human reviewer brings.

## Working Notes

Throughout the investigation and implementation, maintain a running notes section in conversation. Record:

- **Root cause discoveries** — what we learned about the actual bug vs initial assumptions
- **Dead ends** — approaches considered and why they were rejected
- **Codebase patterns** — conventions, related code, prior art found during research
- **Cross-cutting concerns** — other providers/callers/users affected by the same issue

These notes feed directly into the PR body. A good PR description tells the story of the investigation, not just the fix.

## Review Steps

Run these checks in order after the implementation is complete and tests pass.

### 1. Related Issues & PRs

Before finalising, search for existing work on the same problem:

- `gh search issues` and `gh search prs` for keywords from the bug report
- Check if the issue has linked PRs or cross-references to other issues
- Search commit history for prior fixes in the same code area (`git log --all -- <file>`)
- Check if the fix exists on a different branch or was reverted
- Look for similar bugs in other providers/modules (same pattern, different location)
- If related work exists, decide: reference it in the PR, coordinate, or defer

### 2. Placement Analysis

Read the neighbouring functions and types around every modified location. Ask:

- Is this the most natural file/package for this change?
- Does the change follow the existing abstraction boundaries?
- Would a maintainer expect to find this code here?
- Are there similar patterns elsewhere in the codebase that handle the same concern differently? (e.g. AWS Route53 uses `MatchParent` fallback but PDNS doesn't — flag this)
- If adding a new exported method/type, does it belong on this type or should it be a standalone function?

### 3. Edge Case Audit

For every branch/condition in the changed code, enumerate the input combinations and check coverage:

- List all combinations of nil/empty/set for each parameter
- Check boundary conditions (empty slices, nil pointers, zero values)
- Check interaction with features that share the same code path
- For each uncovered case, decide: add a test, or document why it's safe to skip
- Present findings as a table: Case | Expected | Tested?

### 4. TDD Gap Analysis

After tests pass, audit what's NOT tested:

- Are there integration paths that only use stubs/mocks? Does the real code path get exercised?
- Is there an end-to-end scenario that proves the bug is fixed (not just unit-level)?
- Are error paths tested (timeouts, malformed input, permission errors)?
- For regression tests: does the test fail on the old code and pass on the new code?
- List missing tests with priority: must-have vs nice-to-have
- TDD gaps are internal review notes — do NOT include them in the PR body

### 5. Maintainer Perspective

Score the PR on these dimensions (1-10 each):

| Dimension | What to check |
|-----------|--------------|
| **Scope discipline** | Does the diff ONLY fix the reported issue? No drive-by refactors, no unnecessary renames, no bonus features |
| **Convention compliance** | Matches repo's test framework, assertion style, import groups, naming, CONTRIBUTING.md rules |
| **Commit hygiene** | Clean history, descriptive messages, DCO/CLA compliance if required |
| **Documentation** | PR description links to issue, explains root cause, describes fix approach, notes what was considered and rejected |
| **Risk assessment** | Are there performance implications? Could this break other providers/users? Is the blast radius documented? |

Flag anything that would trigger a "please fix" comment from a maintainer.

**Include maintainer-facing notes in the PR body:**
- Performance implications
- Cross-cutting concerns (other providers with the same bug)
- If there's a higher-level fix that would supersede this PR, say so: "Happy to close if this is addressed at the DomainFilter level instead"
- Alternative approaches considered and why they were rejected

### 6. Scope Validation

Re-read the original issue one final time. Then review the diff and ask:

- Does the fix actually address the reported symptom?
- Has the investigation led us to fix a different (possibly related) problem instead?
- Would the original reporter's exact config now work correctly?
- Are there parts of the issue we're NOT fixing? If so, document them explicitly
- Did we introduce any behavioural changes beyond the bug fix?

If the fix has drifted from the original issue, either realign or document the divergence in the PR body.

## Output Format

Present findings inline as you go through each step. At the end, give a single verdict:

- **Ship it** — no blocking issues found
- **Fix first** — list the blocking items
- **Reconsider approach** — fundamental design concern

After drafting the PR body, only surface issues that need the user's attention. Don't present an internal convention compliance checklist — if everything passes, just present the draft and ask if it's ready.

## Cross-References

- Works alongside PR style guides and upstream review workflows
- Complements automated CI/linting — this skill catches semantic issues that tools miss
