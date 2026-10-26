"""Day-1 probe: does the hackathon API return what both forecasts need? About 25 live calls.

Run: .venv/Scripts/python scripts/probe.py
Prints shapes and values only, never the key.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aftershock.qloo import Qloo, QlooError, resolve  # noqa: E402

SHOWS = [("Stranger Things", "urn:entity:tv_show"), ("Wednesday", "urn:entity:tv_show"),
         ("Squid Game", "urn:entity:tv_show"), ("Saltburn", "urn:entity:movie")]
ARTISTS = ["Kate Bush", "Metallica", "The Cramps", "Lady Gaga", "Sophie Ellis-Bextor", "Taylor Swift"]
COUNTRIES = ["United States", "India", "Nigeria", "Japan"]


def show(label, value):
    print(f"\n== {label}\n{json.dumps(value, indent=1, default=str)[:1500]}")


def main():
    q = Qloo(call_budget=40)
    ids = {}
    for name, t in SHOWS:
        hit = resolve(q, name, t)
        ids[name] = hit and hit["entity_id"]
        print(f"resolve {name!r} -> {hit and (hit['name'], hit['entity_id'], hit.get('types'))}")
    for name in ARTISTS:
        hit = resolve(q, name, "urn:entity:artist")
        ids[name] = hit and hit["entity_id"]
        print(f"resolve {name!r} -> {hit and (hit['name'], hit['entity_id'])}")

    checks = [
        ("demographics of Stranger Things", dict(filter__type="urn:demographics", signal__interests__entities=ids["Stranger Things"])),
        ("demographics of Kate Bush", dict(filter__type="urn:demographics", signal__interests__entities=ids["Kate Bush"])),
        ("artist fit for Stranger Things audience",
         dict(filter__type="urn:entity:artist", signal__interests__entities=ids["Stranger Things"],
              filter__results__entities=",".join(i for n in ARTISTS if (i := ids[n])), take=10)),
    ]
    show_ids = ",".join(i for n, _ in SHOWS if (i := ids[n]))
    for c in COUNTRIES:
        checks.append((f"tv_show ranks in {c}", dict(filter__type="urn:entity:tv_show", signal__location__query=c,
                                                    filter__results__entities=show_ids, take=10)))
    for label, params in checks:
        try:
            body = q.insights(**params)
            res = body.get("results", {})
            ents = res.get("entities") or res.get("demographics") or res
            if isinstance(ents, list):
                ents = [{k: e.get(k) for k in ("name", "query", "data", "age", "gender") if k in e} or e for e in ents[:10]]
            show(label, ents)
        except QlooError as e:
            print(f"\n== {label}\nERROR {e}")
    print(f"\nlive calls: {q.live_calls}, month remaining header: {q.month_remaining}")


if __name__ == "__main__":
    main()
