# Azure DevOps

## Detect
- `git remote -v` shows `dev.azure.com/<org>/...` or `<org>.visualstudio.com`.
- The repo's `.mcp.json` / CLAUDE.md names `@azure-devops/mcp`, an ADO project id, or `az boards`.
- Tools named `mcp__ado__*` in the session, or a working `az` CLI with the `azure-devops` extension.

## Fetch the scope
- Usually "everything under Epic/Feature #N". Walk the hierarchy: get the parent with relations
  (`System.LinkTypes.Hierarchy-Forward` = child), repeat for each Feature, keep the leaf items
  (User Story, Bug, Task, Product Backlog Item). Or one WIQL tree query:
  `az boards query --org <org> --project <project> --wiql "SELECT [System.Id] FROM WorkItemLinks WHERE [Source].[System.Id] = <epic> AND [System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward' MODE (Recursive)"`.
- Fields per item: `System.Title`, `System.State`, `System.WorkItemType`, `System.Parent`,
  `Microsoft.VSTS.Scheduling.StoryPoints` (Agile) or `Microsoft.VSTS.Scheduling.Effort` (Scrum) or
  `Microsoft.VSTS.Scheduling.Size` (CMMI), `System.Description`, and relations.
- `az rest` against `_apis/wit/workitems?ids=...&$expand=relations&api-version=7.1` returns states,
  fields and links in one call for up to 200 ids.

## Dependencies
- Native links: `System.LinkTypes.Dependency-Reverse` (shown as **Predecessor**) on item A pointing to B
  means A needs B. `Dependency-Forward` (**Successor**) is the same link seen from B.
- `System.LinkTypes.Related` is not a dependency. Ignore it.
- Text fallback: a "Depends on" / "Blocked by" section in `System.Description` listing `#<id>`.
  Treat words like "helpful", "nice to have", "optional" next to an id as a soft need.

## States
Default map (extend it with the project's custom states; check with `get_type` or an item's state list):

```json
{"New":"new","Proposed":"new","To Do":"new","Approved":"new",
 "Active":"active","Committed":"active","In Progress":"active","Doing":"active",
 "Resolved":"review","In Review":"review",
 "On hold":"hold","Blocked":"hold",
 "Closed":"done","Done":"done","Removed":"removed"}
```

**Quirk to tell the user:** in many ADO setups, merging a PR does not move the item to Closed.
`Resolved` usually means "PR open" and stays that way after the merge until someone closes it, so
the page shows merged work as "In review" and the next items as "Waiting". Check open items in the
Resolved state against their PRs (`az repos pr list --source-branch ... --status all`) when building the
plan, and remind the user to close items when their PRs merge.

## Live source
The local `@azure-devops/mcp` server, reached from the page as `host:<name>` (Claude desktop app only).

- `server`: `host:` + the server's name in the desktop config (commonly `host:ado`).
- `get_batch` only takes ids, so the page needs a **discover** call to follow the scope:
  `live.discover = {"tool":"wit_query","input":{"action":"wiql","project":"<id>","top":1000,"wiql":"SELECT [System.Id] FROM WorkItemLinks WHERE [Source].[System.Id] = <epic> AND [System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward' MODE (Recursive)"}}`.
  Pass `top`: the default is 50. The result is `{workItemRelations:[{rel, source:{id}|null, target:{id}}]}`
  (the root comes back with `source: null`; drop it), wrapped in an "UNTRUSTED WIQL QUERY RESULTS" marker.
- `tool`: `wit_work_item`; `input`:
  `{"action":"get_batch","project":"<project id or name>","fields":["System.Title","System.State","Microsoft.VSTS.Scheduling.StoryPoints","System.WorkItemType","System.Parent"]}`;
  `itemsInput` fills in `ids` (numbers, at most 200 per call).
- Response seen in practice (confirm with your own call; versions differ): one text block whose
  first line is an "UNTRUSTED AZURE DEVOPS WORK-ITEMS CONTENT" marker line, then a JSON array of
  `{id, rev, fields:{...}}`, then a closing marker. `helpers.json(result)` extracts the array.
- Example extract (strip the "Area - " title prefix if the project uses one):

```js
({
  discover: (result, h) => h.json(result).workItemRelations.filter(r => r.source).map(r => r.target.id),
  itemsInput: (ids, input) => ({ ...input, ids: ids.map(Number).slice(0, 200) }),
  items: (result, h) => h.json(result)
    .filter(it => !/^(Epic|Feature)$/.test(it.fields["System.WorkItemType"]))
    .map(it => ({
      id: String(it.id),
      state: it.fields["System.State"],
      title: (it.fields["System.Title"] || "").replace(/^[^-]+ - /, "").replace(/^./, c => c.toUpperCase()),
      points: it.fields["Microsoft.VSTS.Scheduling.StoryPoints"],
      type: it.fields["System.WorkItemType"],
      parent: it.fields["System.Parent"],
    })),
})
```

- Planning from the page: `live.detail = {"tool":"wit_work_item","input":{"action":"get","project":"<id>","expand":"Relations"}}`.
  The response is one object `{id, fields:{..., "System.Description"}, relations:[{rel, url, attributes}]}`
  (Bugs keep their text in `Microsoft.VSTS.TCM.ReproSteps`). Extract members:

```js
  detailInput: (id, input) => ({ ...input, id: Number(id) }),
  detail: (result, h) => {
    const it = h.json(result), f = it.fields || {}, rel = it.relations || [];
    const ids = type => rel.filter(r => r.rel === type).map(r => r.url.split("/").pop());
    return { id: String(it.id), description: f["System.Description"] || f["Microsoft.VSTS.TCM.ReproSteps"] || "",
      needs: ids("System.LinkTypes.Dependency-Reverse"), blocks: ids("System.LinkTypes.Dependency-Forward") };
  },
```

- `itemUrl`: `https://dev.azure.com/<org>/<project name, URL-encoded>/_workitems/edit/{id}`.
- `setupHint` for the page: "Live status needs the Claude desktop app with the ado MCP server running.
  Add it in Settings → Developer → Edit Config, restart the app, then Retry."

### Desktop app setup (the user does this)
The server configured for Claude Code (`.mcp.json`) is not visible to the desktop app. The user adds it
under Settings → Developer → Edit Config. Use absolute paths: apps started from the Dock don't get the
shell's PATH, and `-a azcli` needs `az` on the PATH. Find them with `command -v npx az`.

```json
"mcpServers": {
  "ado": {
    "command": "<absolute path to npx>",
    "args": ["-y", "@azure-devops/mcp", "<org>", "-a", "azcli"],
    "env": { "PATH": "<dir of npx>:<dir of az>:/usr/bin:/bin:/usr/sbin:/sbin" }
  }
}
```

After a full restart (⌘Q), Settings → Developer should list `ado` as Running. Editing that file yourself
may be refused by the permission system; give the user the snippet instead.
