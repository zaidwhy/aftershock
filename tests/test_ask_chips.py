"""The launch-kit example chip names this week's hero title and country (public/js/ask.js); run under node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def examples(hero):
    code = f"import {{ examples }} from {json.dumps((ROOT / 'public/js/ask.js').as_uri())};" \
           f"console.log(JSON.stringify(examples({json.dumps(hero)})));"
    out = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_kit_chip_uses_hero_title_and_country():
    got = examples({"title": "Some Show", "country": "Brazil"})
    assert got[1] == "What should Some Show pair with in Brazil?"
    assert "Where will Squid Game go next?" in got and len(got) == 4


def test_kit_chip_falls_back_without_hero():
    assert examples(None)[1] == "What should Fukrey Returns pair with in Bangladesh?"
    assert examples({"title": "Only Title"})[1] == "What should Fukrey Returns pair with in Bangladesh?"
