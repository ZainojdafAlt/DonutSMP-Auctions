#!/usr/bin/env python3
"""Update worth.yml prices to the average DonutSMP auction price per item.

Usage:
    pip install requests
    python update_worth.py YOUR_API_KEY worth.yml
    (get the key by typing /api on DonutSMP)

Writes worth_updated.yml next to the input. Comments/formatting are kept.
Items with no auction listings keep their old price.
Add --debug to print the first raw API response (useful if fields differ).
"""
import re
import sys
import time

import requests

BASE = "https://api.donutsmp.net/v1/auction/list/{page}"
PAGES_PER_ITEM = 2          # ~90 listings per item; raise for better averages
DELAY = 0.26                # keeps us under 250 requests/minute
LINE = re.compile(r"^(    )([A-Z0-9_]+): (-?[\d.]+)\s*$")


def item_id(entry):
    it = entry.get("item", entry)
    if isinstance(it, dict):
        it = it.get("id") or it.get("name") or ""
    return str(it).lower().replace("minecraft:", "")


def item_count(entry):
    it = entry.get("item")
    if isinstance(it, dict) and it.get("count"):
        return it["count"]
    return entry.get("count") or entry.get("amount") or 1


def fetch(session, key, material, debug=False):
    unit_prices = []
    for page in range(1, PAGES_PER_ITEM + 1):
        r = session.post(
            BASE.format(page=page),
            json={"search": material.lower().replace("_", " "), "sort": "lowest_price"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
        if r.status_code == 429:
            time.sleep(5)
            continue
        r.raise_for_status()
        data = r.json()
        if debug:
            print(str(data)[:1500])
            debug = False
        entries = data.get("result", data) if isinstance(data, dict) else data
        if not entries:
            break
        for e in entries:
            if item_id(e) == material.lower() and e.get("price"):
                unit_prices.append(e["price"] / max(item_count(e), 1))
        time.sleep(DELAY)
    return unit_prices


def main():
    args = [a for a in sys.argv[1:] if a != "--debug"]
    debug = "--debug" in sys.argv
    if len(args) != 2:
        sys.exit(__doc__)
    key, path = args
    lines = open(path, encoding="utf-8").read().split("\n")
    session = requests.Session()
    in_type, out, changed, skipped = False, [], 0, 0
    for ln in lines:
        if ln.startswith("TYPE:"):
            in_type = True
        elif ln and not ln.startswith(" ") and not ln.startswith("#"):
            in_type = False
        m = LINE.match(ln) if in_type else None
        if m:
            name, old = m.group(2), m.group(3)
            try:
                prices = fetch(session, key, name, debug)
            except requests.RequestException as e:
                print(f"{name}: error {e}")
                prices = []
            debug = False
            if prices:
                avg = round(sum(prices) / len(prices), 2)
                ln = f"{m.group(1)}{name}: {avg}"
                changed += 1
                print(f"{name}: {old} -> {avg} ({len(prices)} listings)")
            else:
                skipped += 1
                print(f"{name}: no listings, kept {old}")
        out.append(ln)
    new_path = path.rsplit(".", 1)[0] + "_updated.yml"
    open(new_path, "w", encoding="utf-8").write("\n".join(out))
    print(f"\nDone. Updated {changed}, kept {skipped}. Saved to {new_path}")


if __name__ == "__main__":
    main()
