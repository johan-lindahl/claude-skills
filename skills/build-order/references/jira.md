# Jira

## Detect
- Issue keys like `ABC-123` in branch names, commit messages or PR titles (`git log --oneline -50`).
- `*.atlassian.net` links in README, CLAUDE.md or docs.
- An Atlassian connector in the session (tools named like `mcp__claude_ai_Atlassian__*` or
  `mcp__atlassian__*`). If it only offers `authenticate`, ask the user to connect it first.

## Fetch the scope
- Ask for the scope as JQL or turn their words into JQL: an epic (`parent = ABC-10`, or on older
  company-managed projects `"Epic Link" = ABC-10`), a sprint (`sprint = 42`), a fix version
  (`fixVersion = "1.4"`) or a label.
- Read the connector's tool list and input schemas in this session before calling: tool names differ
  between connector versions (typically a JQL search tool plus a get-issue tool, and some need a
  `cloudId` from an "accessible resources" tool first). Never guess argument names.
- Fields to request: `summary`, `status`, `issuetype`, `parent`, `issuelinks`, `description`, and the
  story-points field.
- **Story points have no fixed field id.** Common ids: `customfield_10016` ("Story point estimate",
  team-managed) and `customfield_10026` / `customfield_10028` ("Story Points", company-managed). Find it
  in one issue's raw fields or the field list, or ask the user. Without it, leave points empty (the plan
  weights each item as 1).

## Dependencies
- `issuelinks[]` entries have `type: {name, inward, outward}` plus either `inwardIssue` or `outwardIssue`.
- Link type **Blocks** (`inward: "is blocked by"`, `outward: "blocks"`):
  an entry with `inwardIssue: X` on issue A means X blocks A, so **A needs X**;
  an entry with `outwardIssue: Y` means A blocks Y (Y needs A; record it on Y).
- Some sites add a **Depends** type ("depends on" / "is depended on by"): same direction logic.
- "Relates", "Duplicate" and "Cloners" are not dependencies.
- Text fallback: "Depends on ABC-12" / "Blocked by ABC-12" in the description.

## States
Use the status **category** first; it is stable across workflows: `new` → new,
`indeterminate` → active, `done` → done. Refine with the status name where it matters
("In Review", "Code Review" → review; "Blocked", "On Hold" → hold; resolution "Won't Do" → removed).
Pass the status name as `state` and put the refinements in `stateMap`, e.g.
`{"In Review":"review","Code Review":"review","Blocked":"hold","Won't Do":"removed"}`.
Jira usually closes issues through its own workflow, but check for issues sitting in review after their PR merged.

## Live source
Prefer the claude.ai Atlassian connector: it also works in a plain browser.

- `server`: the connector's display name (the `<connector>` segment of its tool names also works when
  publishing; the publish result tells you the display name to use in page calls).
- `tool` / `input`: the JQL search tool with a **scope** query, not a key list, so new issues appear:
  `jql: "parent = ABC-1"` (or `"Epic Link" = ABC-1` on older sites, `parent in (...)` for several
  epics), the fields above plus `issuetype` and `parent`, and a generous `maxResults` (plus `cloudId`
  if the tool needs it). No discover call is needed. Return `type` and `parent` from the extract.
- Make one real call and write the extract from what came back, for example:

```js
(result, h) => {
  const data = h.json(result);
  const issues = data.issues || data;
  return issues.map(i => ({
    id: i.key,
    state: i.fields.status.statusCategory.key === "done" ? "Done" : i.fields.status.name,
    title: i.fields.summary,
    points: i.fields["customfield_10016"],
  }));
}
```

- Item ids in the plan are issue keys (`ABC-123`); set `idPrefix` to `""`.
- `itemUrl`: `https://<site>.atlassian.net/browse/{id}`.
- `setupHint`: "Connect Atlassian in claude.ai Settings → Connectors, then Retry."

## Planning from the page
For the "Find and plan new items" button, set `live.detail` to the get-issue tool (fields `description`, `issuelinks`) and write `detailInput` /
`detail` from one real call: `needs` are the items this one is blocked by, `blocks` the items it blocks,
`description` the text Claude reads for "depends on" wording.
