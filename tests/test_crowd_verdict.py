"""The verdict chip comes from the same age bands as the sentence (public/js/crowd.js); run under node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def run(expr):
    code = f"import {{ crowd, gapNote, bandText }} from {json.dumps((ROOT / 'public/js/crowd.js').as_uri())};" \
           f"console.log(JSON.stringify({expr}));"
    out = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_same_partly_and_new_follow_the_bands():
    assert run('crowd(["24_and_younger","25_to_29"], ["25_to_29"])')["label"] == "Same crowd"
    assert run('crowd(["25_to_29"], ["25_to_29","55_and_older"])')["label"] == "Partly new crowd"
    assert run('crowd(["24_and_younger"], ["45_to_54","35_to_44"])')["label"] == "New crowd"
    assert run('crowd(["24_and_younger"], [])') is None


def test_bands_are_listed_in_age_order_and_joined_naturally():
    assert run('bandText(["55_and_older","24_and_younger","35_to_44"])') == "under 25, 35-44 and 55+"
    assert run('bandText(["45_to_54"])') == "45-54"


def test_gap_note_only_when_two_or_more_bands_apart():
    assert run('gapNote("Kate Bush", ["24_and_younger","25_to_29"], ["35_to_44","45_to_54"])') == "Kate Bush's listeners skew older."
    assert run('gapNote("Kate Bush", ["25_to_29","30_to_34"], ["35_to_44"])') is None
    assert run('gapNote("Genesis", ["45_to_54"], ["24_and_younger"])') == "Genesis' listeners skew younger."
