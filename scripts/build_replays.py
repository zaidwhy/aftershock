"""Write data/public/replays.json: monthly en-Wikipedia views around famous song ripples."""
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "public" / "replays.json"
# Wikimedia asks for a contact in the User-Agent and rejects some bare ones.
UA = {"User-Agent": "aftershock/0.1 (https://github.com/zaidwhy/aftershock; zaidsyed7021@gmail.com)"}
CASES = [
    ("Stranger Things 4", "2022-05-27", "Running Up That Hill", "Kate Bush", "Running_Up_That_Hill", "2021120100", "2022123100"),
    ("Stranger Things 4 vol. 2", "2022-07-01", "Master of Puppets", "Metallica", "Master_of_Puppets_(song)", "2022010100", "2022123100"),
    ("Wednesday", "2022-11-23", "Bloody Mary", "Lady Gaga", "Bloody_Mary_(Lady_Gaga_song)", "2022060100", "2023063000"),
    ("Saltburn", "2023-11-17", "Murder on the Dancefloor", "Sophie Ellis-Bextor", "Murder_on_the_Dancefloor", "2023060100", "2024063000"),
]


def main():
    replays = []
    for show, release, song, artist, article, start, end in CASES:
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article}/monthly/{start}/{end}"
        items = httpx.get(url, headers=UA, timeout=20).json()["items"]
        replays.append({"show": show, "release": release, "song": song, "artist": artist, "article": article,
                        "monthly_views": [[i["timestamp"][:4] + "-" + i["timestamp"][4:6], i["views"]] for i in items]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "Wikimedia Pageviews API, en.wikipedia, user agents", "replays": replays}, indent=1))
    for r in replays:
        views = [v for _, v in r["monthly_views"]]
        print(f"{r['song']}: min {min(views)}, max {max(views)}")


if __name__ == "__main__":
    main()
