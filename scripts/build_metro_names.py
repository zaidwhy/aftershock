"""Build data/private/metro_names.json: each launch-kit country's well-known destinations, for aftershock/metro_names.py.

For every country code in any storm's launch kit (data/private/storms.json and the weekly archive) it asks Qloo for
that country's destinations (`filter.type=urn:entity:destination`, `filter.geocode.country_code`), with no signal:
Qloo returns the country's whole destination list either way (the same 5 to 9 rows for any signal), so a signal only
adds a dependency. Rows at or above FLOOR popularity are kept as [name, lat, lon, popularity]. One call per country,
more only for a country whose first page is full and still above the floor (the US); cached on disk by the Qloo client; the output is Qloo-derived, so it lives under the gitignored data/private/.

Run: .venv/Scripts/python scripts/build_metro_names.py [--floor 0.5] [--extra US,CA,MX]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aftershock import storm_archive  # noqa: E402
from aftershock.metro_names import METRO_FILE  # noqa: E402
from aftershock.qloo import Qloo, QlooError  # noqa: E402

PRIVATE = ROOT / "data" / "private"
FLOOR = 0.5  # destinations are relative to the country: Helsingborg (0.51) is in, Bergen (0.29) and the small resorts are out
TAKE = 50  # Qloo's maximum per call; `offset` pages past it, most popular first
MAX_PAGES = 8  # a safety stop per country; the US needs about 3 at the 0.5 floor


def kit_countries(private=PRIVATE):
    """Country codes with a launch-kit row in the current storms file or any archived week."""
    detail_lists = []
    current = private / "storms.json"
    if current.exists():
        detail_lists.append([s["detail"] for s in json.loads(current.read_text(encoding="utf-8"))["storms"]])
    detail_lists.append([d for _, _, d in storm_archive.all_storms(private / "storm_archive")])
    return sorted({row["code"] for details in detail_lists for d in details for row in d.get("launch_kit") or []
                   if row.get("code")})


# The site's country table is the one list of country names the project keeps; read it rather than copy it.
COUNTRY_NAMES = {m.casefold() for m in re.findall(r'\[\d+, "([^"]+)"\]', (ROOT / "public" / "js" / "iso.js").read_text(encoding="utf-8"))}


def destinations(body, code, floor=FLOOR):
    """[[name, lat, lon, popularity], ...] for the entities of one country at or above `floor`, most popular first.
    Qloo also lists time zones as destinations ("Europe/Madrid"); a slash never appears in a city name."""
    rows = []
    for entity in (body.get("results") or {}).get("entities") or []:
        geo = (entity.get("properties") or {}).get("geocode") or {}
        loc, popularity = entity.get("location") or {}, entity.get("popularity")
        if (geo.get("country_code") != code or not entity.get("name") or "/" in entity["name"]
                or loc.get("lat") is None or loc.get("lon") is None or popularity is None or popularity < floor):
            continue
        name = entity["name"]
        # Some countries are listed as one country-wide destination ("Maldives"); a hotspot named after the whole
        # country says nothing, so use the locality Qloo geocodes it to (Male) instead.
        if name.casefold() in COUNTRY_NAMES and geo.get("name"):
            name = geo["name"]
        rows.append([name, round(loc["lat"], 4), round(loc["lon"], 4), round(popularity, 3)])
    return sorted(rows, key=lambda r: -r[3])


def fetch(client, code, floor=FLOOR):
    """All of a country's destination rows at or above `floor`. Pages are most popular first, so paging stops at a short
    page or one that reaches below the floor; returns (rows, pages_fetched, hit_page_cap)."""
    rows = []
    for page in range(MAX_PAGES):
        params = {"filter.type": "urn:entity:destination", "filter.geocode.country_code": code, "take": TAKE}
        if page:
            params["offset"] = page * TAKE
        body = client.get("/v2/insights", params)
        entities = (body.get("results") or {}).get("entities") or []
        rows += destinations(body, code, floor)
        if len(entities) < TAKE or min(e.get("popularity") or 0 for e in entities) < floor:
            return rows, page + 1, False
    return rows, MAX_PAGES, True


def build(client, codes, floor=FLOOR):
    countries, empty, capped = {}, [], []
    for code in codes:
        try:
            rows, _, hit_cap = fetch(client, code, floor)
        except QlooError as err:
            print(f"{code}: {err}")
            empty.append(code)
            continue
        if hit_cap:
            capped.append(code)
        if rows:
            countries[code] = sorted(rows, key=lambda r: -r[3])
        else:
            empty.append(code)
    return {"floor": floor, "countries": countries}, empty, capped


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=FLOOR)
    ap.add_argument("--extra", default="", help="more country codes, comma separated")
    args = ap.parse_args()
    codes = sorted(set(kit_countries()) | {c.strip().upper() for c in args.extra.split(",") if c.strip()})
    client = Qloo(call_budget=len(codes) * MAX_PAGES)
    result, empty, capped = build(client, codes, args.floor)
    METRO_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRO_FILE.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kept = sum(len(v) for v in result["countries"].values())
    print(f"{len(codes)} countries, {client.live_calls} live calls, {kept} destinations at popularity >= {args.floor} "
          f"in {len(result['countries'])} countries; none kept for {empty or 'no country'}; "
          f"stopped at {MAX_PAGES} pages: {capped or 'none'}; wrote {METRO_FILE}")
