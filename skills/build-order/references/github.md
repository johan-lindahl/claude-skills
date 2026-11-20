# GitHub

## Detect
- `git remote -v` shows `github.com/<owner>/<repo>`.
- `gh` is installed and authenticated (`gh auth status`), and/or a GitHub connector or local GitHub MCP
  server is in the session (tools named like `mcp__claude_ai_GitHub__*` or `mcp__github__*`).

## Fetch the scope
- Typical scopes: a milestone, a label, a parent issue with sub-issues, or a Projects (v2) board.
- `gh` is the most reliable way to read structure:
  - `gh issue list -R owner/repo --milestone "M1" --state all --json number,title,state,stateReason,labels,body --limit 500`
  - Sub-issues and issue dependencies come from GraphQL: `gh api graphql -f query='...'`. Check the
    current schema for the field names (`gh api graphql -f query='{__type(name:"Issue"){fields{name}}}'`)
    before relying on fields such as sub-issues or blocked-by/blocking; they are newer and their names
    have changed before.
  - Projects (v2) fields such as Status or an Estimate number: `gh project item-list <n> --owner <owner> --format json`.

## Dependencies
- Native issue dependencies ("Blocked by" / "Blocking") when the repo uses them: A blocked by B means
  A needs B.
- Sub-issues are hierarchy, not dependencies. Use the parent only to define the scope or lanes.
- Text fallback: "Depends on #12", "Blocked by #12", "after #12" in the issue body; task-list items
  (`- [ ] #12`) in a parent body are children, not dependencies.

## States
GitHub issues are only `open` or `closed`. Derive more from `stateReason` and labels:
- closed + `completed` → done; closed + `not_planned` → removed.
- open with a label like "in progress"/"doing" → active; "in review"/"needs review" → review;
  "blocked"/"on hold" → hold; otherwise new.
- If the project uses a Projects (v2) Status field, prefer it ("Todo"/"In Progress"/"Done").
In the extract, build `state` from these (e.g. return the matching label name, or "Done" / "Removed").
PRs with "Closes #12" close the issue on merge, so merged work normally shows as done without manual steps.

## Points
No native field. Use a Projects (v2) number field, a label like `points: 3` / `size: M`, or leave empty.

## Live source
- Prefer a claude.ai GitHub connector (works in a browser); else a local GitHub MCP server as
  `host:<name>` (desktop app only). Read the tool schemas in this session; tool names and result shapes
  differ between servers.
- One call that returns all items **by scope** (so new issues appear; never a list of numbers) is best: an issue search such as
  `repo:owner/repo is:issue milestone:"M1"`, or a list call filtered by milestone/label. Make one real
  call and write the extract from the result, for example:

```js
(result, h) => {
  const data = h.json(result);
  const list = data.items || data.issues || data;
  const label = (i, re) => (i.labels || []).some(l => re.test(typeof l === "string" ? l : l.name));
  return list.map(i => ({
    id: String(i.number),
    state: i.state === "closed" ? (i.state_reason === "not_planned" ? "Removed" : "Done")
         : label(i, /review/i) ? "In review" : label(i, /progress|doing/i) ? "In progress"
         : label(i, /blocked|hold/i) ? "On hold" : "New",
    title: i.title,
  }));
}
```

- `itemUrl`: `https://github.com/<owner>/<repo>/issues/{id}`.
- If no GitHub connection can serve the page, publish without `live` (static snapshot) and offer to
  refresh it on request.

## Planning from the page
For the "Find and plan new items" button, set `live.detail` to the get-issue tool (the body, plus the dependency API's `blocked_by` / `blocking` if the server exposes it) and write `detailInput` /
`detail` from one real call: `needs` are the items this one is blocked by, `blocks` the items it blocks,
`description` the text Claude reads for "depends on" wording.
