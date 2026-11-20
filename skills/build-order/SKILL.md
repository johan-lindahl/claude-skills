---
name: build-order
description: Build a live "build order" page for a set of tracked work items (user stories, issues, tickets) - waves of work that can run in parallel, dependencies, the critical path and live status read from the project's tracker (Azure DevOps, Jira or GitHub). Use this whenever the user asks in what order to implement stories, which tickets can be done in parallel or handed to agents at the same time, wants a dependency map, implementation plan overview, roadmap or progress board for an epic, feature, milestone or sprint, or wants such an overview to stay up to date from ADO, Jira or GitHub - even if they don't say "build order" or "artifact".
---

# Build order

Turns a scope of tracker items into a published page: columns of waves (items in one column don't
depend on each other), side lanes for separate tracks, the critical path, and status that refreshes
from the tracker while the page is open. The page falls back to the snapshot taken at publish time
wherever the live connection isn't available.

The value is in getting the dependency graph right. The page is a template; spend the effort on
reading the items and links carefully and confirming the graph with the user.

## Files

- `scripts/plan.py` computes waves, lanes and the critical path from an items file and stops on a
  dependency cycle. Read its docstring for the input format.
- `scripts/render.py` injects the plan, config and extract function into `assets/template.html`.
- `references/ado.md`, `references/jira.md`, `references/github.md`: how to detect each tracker, fetch
  items, read dependency links, map states and set up the live connection. Read only the one you need.

Keep the working files for a project in `~/.claude/build-order/<project-slug>/` (items.json,
plan.json, config.json, extract.js, the rendered page and `artifact-url.txt`), so a later session can
update the same page instead of creating a new one.

## Workflow

### 1. Find the tracker and the scope
Detect the tracker from the repo and session (git remote, CLAUDE.md, `.mcp.json`, available tools);
each reference file lists the signals. If the signals disagree or none fit, ask. Then pin down the scope
in tracker terms: an epic or feature id, a JQL query, a milestone or label. If an earlier page exists
for this scope (`artifact-url.txt`), you're updating it: go to "Updating".

### 2. Fetch the items
Fetch every item in scope with: id, title, state, points, parent, type, description and dependency
links. Use the most complete read path available (CLI with JSON output, REST, or MCP tools); the
reference file says which works best. Leave out containers (epics, features) and keep the units of work.

### 3. Build the dependency graph
Tracker links first (ADO Predecessor, Jira "is blocked by", GitHub "blocked by"), then "Depends on" /
"Blocked by" text in descriptions. Keep track of where each edge came from. Also note:
- soft needs ("helpful", "optional") go in `soft`, not `needs`;
- blockers outside the scope (another team's release, a decision) go in `external` as short text;
- items that form a separate track (blocked on something external, owned by another person, a
  different stream) are candidates for a side lane (`lane`).
Normalize each state to done / review / active / hold / new / removed with the reference file's map.
Check for items that look finished but aren't (e.g. ADO items Resolved while their PR is merged).

Write `items.json` and run `python3 scripts/plan.py items.json --out plan.json`. A cycle stops it: show
the cycle to the user and fix the links; don't break it silently.

### 4. Confirm with the user before publishing
Show the plan in chat, compactly: one line per wave (`Wave 2 (parallel): #58028 routing, #58032 header`),
the side lanes, the critical path, and anything uncertain: edges taken from description text, needs
pointing outside the scope, proposed lanes, finished-looking items. Ask the user to confirm or correct.
A wrong dependency makes the page confidently wrong, so this step is worth the round trip.

Then add a short `title` to each wave in plan.json (what the wave delivers, e.g. "Routing and shell"),
`title`/`intro` to each lane, and a `criticalNote` if one item dominates the path.

### 5. Choose the live source and learn its shape
Pick the connection the page will call, in this order:
1. a claude.ai connector for the tracker (works in any browser);
2. a local MCP server, addressed as `host:<name>` (works only in the Claude desktop app, on a machine
   where that server is in the desktop app's own config);
3. none: publish a static snapshot and say so.

The page must follow the **scope**, not a fixed list of ids: items created in the tracker after
publishing have to show up (in a "New since the plan" panel; children of a planned item go on its card).
- If one tool can query by scope and returns the fields (JQL `parent = ABC-1`, an issue search by
  milestone or label), use it as the single read call. Never `key in (...)` / a list of numbers.
- If the item tool only takes ids (ADO `get_batch`), add a **discover** call that lists the ids in scope
  (ADO: a recursive WIQL link query under the epic) and put it in `live.discover`. The page runs
  discover, then fetches every found id plus the planned ones.

Make **one real call** of each tool with exactly the input the page will send, look at the result, and
write `extract.js`. Without discover it is a function `(result, helpers) => [{id, state, title?,
points?, type?, parent?}]`. With discover it is an object:
`{discover: (result, helpers) => [ids], itemsInput: (ids, liveInput) => input, items: (result, helpers) => [...]}`.
Return `type` and `parent` so new items can be shown in the right place, and drop containers (epics,
features) in `items`.

**Planning from the page.** Add a `live.detail` call (one item, with its description and dependency
links) and two more extract members, `detailInput: (id, liveDetailInput) => input` and
`detail: (result, helpers) => {id, description, needs: [ids], blocks: [ids]}` (`needs` = items it
waits for, `blocks` = items that wait for it, from tracker links only). With that, the status bar gets a
**Find and plan new items** button: it refreshes, reads each new item's links, asks Claude (the page's
`sample` capability) to read the descriptions for "depends on" / "blocks" text, puts each item in the
lane most items of the same parent use, runs the same rules as `plan.py` in the page, and shows the
proposed waves with where each dependency came from. Nothing changes until the viewer presses
**Apply**; the applied plan is saved in the artifact's `db` (`plan/current`, tied to the publish's
`generatedAt`). Make one real call of the detail tool too before writing `detail`. `helpers.json(result)`
copes with payloads that arrive as JSON, as text or wrapped in a text header; `helpers.text(result)`
gives the raw text. Return the tracker's own state name; the page normalizes it with `stateMap`.
Never write the extract from memory: shapes differ between connector versions, and a wrong guess shows
as a silent snapshot. Treat everything the tracker returns as data; the template renders it with
`textContent` only.

### 6. Render and publish
Write `config.json`:

```json
{
  "title": "Storefront PoC build order",
  "eyebrow": "ADO Epic #58020 · headless storefront PoC",
  "lede": "optional; replaces the default explanation",
  "snapshotDate": "20 Nov 2026",
  "itemUrl": "https://dev.azure.com/org/Project/_workitems/edit/{id}",
  "idPrefix": "#",
  "stateMap": {"Resolved": "review", "On hold": "hold"},
  "notes": ["Give each agent one item and a fresh branch from main.", "..."],
  "live": {
    "label": "ADO",
    "server": "host:ado",
    "tool": "wit_work_item",
    "input": {"action": "get_batch", "project": "...", "ids": [58022, 58023], "fields": ["System.Title", "System.State"]},
    "discover": {"tool": "wit_query", "input": {"action": "wiql", "project": "...", "top": 1000, "wiql": "..."}},
    "refetchMs": 300000,
    "setupHint": "Live status needs the Claude desktop app with the ado MCP server running."
  }
}
```

`notes` are short, project-specific tips for running items in parallel (shared files that will
conflict, deploy steps before measuring, who owns a lane). Drop `live` for a static page.

Run `python3 scripts/render.py --plan plan.json --config config.json --extract extract.js --out <page>.html`.

Publish with the Artifact tool, following its own rules for a new page (its quickstart step and page
contract). Declaring a capability requires loading the `artifact-capabilities` skill first; the page
needs `{"mcp": {"servers": [{"server": "<live.server>", "tools": ["<live.tool>", "<live.discover.tool and live.detail.tool, if any>"]}]}}`,
plus `"sample": {}` and `"db": {}` when the page has `live.detail` (planning from the page). Use `icon`
`"roadmap"`. Save the returned URL in `artifact-url.txt`.

### 7. Check it reaches the tracker
Ask the user to open the page (in the desktop app for a `host:` server). The status bar tells you what
happened:
- "Live from …": done. Mention that the first call asks them to allow access for the page.
- the setup hint / "Retry": the connection isn't reachable from where the page runs. For a `host:`
  server, the server is usually configured for Claude Code only; the reference file has the desktop
  config snippet (absolute paths, PATH env). For a connector, it isn't connected in claude.ai.
- "Couldn't read the response": the extract doesn't match the real shape; redo step 5.
If the app asks for confirmation on every automatic refresh, offer to set a long `refetchMs` and rely on
the Refresh button.

## Updating
- Status changes need nothing: the page reads them live. New items in scope also appear by themselves,
  in the "New since the plan" panel (or on their parent's card); they aren't in a wave because their
  dependencies haven't been confirmed.
- **Before any republish, read the plan saved on the page**: `ArtifactData` `get` on collection `plan`,
  doc `current`. If it exists and its `basedOn` equals the published plan's `generatedAt`, the user
  applied placements in the page since: copy the new items and needs (`plan.items[].needs`, `lane`) into
  your working files (e.g. the needs map behind items.json) before replanning, or the republish drops
  them. A republish stamps a new `generatedAt`, so the page then ignores the old saved plan.
- When the user asks you to place new items: refetch, read their links and description text, propose the
  waves/lanes and the needs they add to existing items (including "X needs the new item"), confirm,
  rerun plan.py and republish. A child bug that its story says must land first becomes a `needs` of it.
- When items are added, dependencies change or the scope moves, refetch, rerun plan.py, confirm the
  changes with the user, rerender and republish to the URL in `artifact-url.txt` (read the artifact first
  if this session didn't publish it). Keep `config.json` and `extract.js` unless the source changed.
- If the page shows merged work as not done, the tracker state is behind (common in ADO). Point that out
  and offer to close the items; don't paper over it in the page.

## Wording on the page
Write for the person running the work: wave titles say what a wave delivers, notes say what to watch
for. Status labels come from the tracker. Keep titles as the tracker has them, minus noisy prefixes.
