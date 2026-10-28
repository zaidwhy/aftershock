"""The launch-kit example chip names this week's hero title and country (public/js/ask.js); run under node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def examples(hero, top=None):
    code = f"import {{ examples }} from {json.dumps((ROOT / 'public/js/ask.js').as_uri())};" \
           f"console.log(JSON.stringify(examples({json.dumps(hero)}, {json.dumps(top)})));"
    out = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_kit_chip_uses_hero_title_and_country():
    got = examples({"title": "Some Show", "country": "Brazil"})
    assert got[1] == "What should Some Show pair with in Brazil?"
    assert got[0] == "Where will Fukrey Returns go next?"
    assert examples(None, {"title": "Top Show"})[0] == "Where will Top Show go next?"
    assert len(got) == 2 and not any("song" in q.lower() or " by " in q for q in got)


def test_kit_chip_falls_back_without_hero():
    assert examples(None)[1] == "What should Fukrey Returns pair with in Bangladesh?"
    assert examples({"title": "Only Title"})[1] == "What should Fukrey Returns pair with in Bangladesh?"
