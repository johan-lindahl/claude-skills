#!/usr/bin/env python3
"""Turn tracker items + dependencies into a build plan: waves, lanes, critical path.

Input  (items.json): a JSON list of items:
  {
    "id": "58272",              # string or number; used as-is in the page
    "title": "Brand theming foundation",
    "state": "new",             # normalized: done | review | active | hold | new | removed
    "points": 8,                # optional; missing -> 1 for critical-path weighting
    "needs": ["58271"],         # hard dependencies (ids)
    "soft": ["58042"],          # optional "helps but not required"
    "external": ["mobile* fields on main"],   # optional blockers outside the tracker scope
    "lane": "main",             # optional; anything other than "main" renders as a side lane
    "note": "Start it first."   # optional
  }

Output (stdout or --out): {"items": [...with "wave"], "waves": [...], "lanes": [...],
         "critical": [ids...], "warnings": [...]}

Rules
- done items -> wave "done". removed items are dropped.
- Every open item gets level = 0 if none of its hard needs are open, else 1 + max(level of open needs).
  Levels are computed across all lanes, so a cross-lane need pushes the item later.
- Main-lane items are grouped into columns by level ("w1", "w2", ...). Side-lane items keep the level
  for ordering inside their lane.
- Needs that point outside the item set are moved to "external" with a warning (out of scope).
- Critical path = the longest open chain weighted by points (missing points count as 1).
- A dependency cycle aborts with the cycle listed: fix the links, never guess.
"""
import argparse
import json
import sys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("items")
    ap.add_argument("--out")
    args = ap.parse_args()

    raw = json.load(open(args.items))
    warnings = []
    items = {}
    for it in raw:
        if it.get("state") == "removed":
            continue
        it = dict(it)
        it["id"] = str(it["id"])
        it.setdefault("needs", [])
        it.setdefault("soft", [])
        it.setdefault("external", [])
        it.setdefault("lane", "main")
        it["needs"] = [str(n) for n in it["needs"]]
        it["soft"] = [str(n) for n in it["soft"]]
        items[it["id"]] = it

    for it in items.values():
        missing = [n for n in it["needs"] if n not in items]
        if missing:
            warnings.append(f"#{it['id']} needs {', '.join('#' + m for m in missing)} outside the plan; shown as external")
            it["external"] += ["#" + m for m in missing]
            it["needs"] = [n for n in it["needs"] if n in items]
        it["soft"] = [n for n in it["soft"] if n in items]

    def is_open(i):
        return items[i]["state"] != "done"

    level, visiting = {}, []

    def lvl(i):
        if i in level:
            return level[i]
        if i in visiting:
            cyc = visiting[visiting.index(i):] + [i]
            sys.exit("dependency cycle: " + " -> ".join("#" + c for c in cyc))
        visiting.append(i)
        open_needs = [n for n in items[i]["needs"] if is_open(n)]
        level[i] = 0 if not open_needs else 1 + max(lvl(n) for n in open_needs)
        visiting.pop()
        return level[i]

    for i in items:
        if is_open(i):
            lvl(i)

    # critical path: longest weighted chain through open items
    best = {}

    def chain(i):
        if i in best:
            return best[i]
        w = items[i].get("points") or 1
        prev = [chain(n) for n in items[i]["needs"] if is_open(n)]
        top = max(prev, key=lambda c: c[0], default=(0, []))
        best[i] = (top[0] + w, top[1] + [i])
        return best[i]

    open_ids = [i for i in items if is_open(i)]
    critical = max((chain(i) for i in open_ids), key=lambda c: c[0], default=(0, []))[1]

    # Main-lane columns are numbered consecutively: a level can be empty on the main lane when the gap
    # comes from a side-lane need, and "Wave 4, Wave 6" would read as a missing wave.
    main_levels = sorted({level[i] for i in open_ids if items[i]["lane"] == "main"})
    wave_of = {L: n + 1 for n, L in enumerate(main_levels)}
    waves = [{"key": "done", "n": "DONE", "items": [i for i in items if not is_open(i)]}]
    for L in main_levels:
        ids = [i for i in open_ids if items[i]["lane"] == "main" and level[i] == L]
        waves.append({"key": f"w{wave_of[L]}", "n": f"WAVE {wave_of[L]}", "items": ids, "parallel": len(ids)})
    waves = [w for w in waves if w["items"]]

    lanes = []
    for lane in dict.fromkeys(it["lane"] for it in items.values() if it["lane"] != "main"):
        ids = sorted((i for i in items if items[i]["lane"] == lane), key=lambda i: (is_open(i), level.get(i, -1)))
        lanes.append({"key": lane, "items": ids})

    for i, it in items.items():
        it["wave"] = "done" if not is_open(i) else (f"w{wave_of[level[i]]}" if it["lane"] == "main" else it["lane"])
        it["level"] = level.get(i)

    out = {"items": list(items.values()), "waves": waves, "lanes": lanes, "critical": critical, "warnings": warnings}
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if args.out:
        open(args.out, "w").write(text)
    else:
        print(text)
    for w in warnings:
        print("warning:", w, file=sys.stderr)


if __name__ == "__main__":
    main()
