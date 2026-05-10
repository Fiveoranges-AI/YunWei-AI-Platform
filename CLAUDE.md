# Repo conventions for Claude

## Git workflow

When you commit and push to a feature branch, **normally also open a PR** with
`gh pr create` targeting `main`. The default flow is: `git push -u origin <branch>`
→ `gh pr create` → report the PR URL to the user.

Skip the PR step only when:
- The user explicitly says "just push, don't open a PR"
- The push is to a draft / WIP branch the user has flagged as ongoing
- The branch is already associated with an open PR (use `gh pr view` to check)

PR body should follow the standard format: 1-3 bullet `## Summary` + a
`## Test plan` checklist. Include the Co-Authored-By trailer.
