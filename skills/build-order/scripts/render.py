#!/usr/bin/env python3
"""Render the build-order page from the template.

  render.py --plan plan.json --config config.json --extract extract.js --out build-order.html

- plan.json:   output of plan.py, optionally edited (wave "title"/"m" text, lane "title"/"intro").
- config.json: page and live-source settings (see SKILL.md "Config").
- extract.js:  a JS function expression `(result, helpers) => [{id, state, title?, points?}]` written
               after one real call of the tracker tool. Omit it (or pass --no-live) for a static page.

The JSON is injected into placeholders in assets/template.html; "</" is escaped so data can't close the
<script> block.
"""
import argparse
import datetime
import json
import pathlib

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "template.html"


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--extract")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    # Identifies this publish: a plan applied in the page is saved against it and ignored after a newer publish.
    plan["generatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    config = json.load(open(args.config))
    extract = pathlib.Path(args.extract).read_text().strip() if args.extract else "null"
    if "</script" in extract.lower():
        raise SystemExit("extract.js must not contain </script")

    html = TEMPLATE.read_text()
    title = config.get("title", "Build order")
    for token, value in {
        "__TITLE__": title.replace("<", "&lt;"),
        "/*__CONFIG__*/null": js(config),
        "/*__PLAN__*/null": js(plan),
        "/*__EXTRACT__*/null": extract,
    }.items():
        if token not in html:
            raise SystemExit(f"template is missing {token}")
        html = html.replace(token, value)
    pathlib.Path(args.out).write_text(html)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
