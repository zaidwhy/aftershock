"""The AI names Qloo rejected are listed struck through with the reason as text (public/js/rejected.js); run under node
with a minimal DOM stand-in."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

STUB = """
class Node_ { constructor(t){this.tag=t;this.kids=[];this.nodeType=1;}
  setAttribute(){} addEventListener(){} set className(v){this.cls=v}
  append(...k){this.kids.push(...k);} }
globalThis.document = { createElement: (t) => new Node_(t), createTextNode: (t) => ({ nodeType: 3, text: String(t) }) };
const html = (n) => n.nodeType === 3 ? n.text : `<${n.tag}>${n.kids.map(html).join("")}</${n.tag}>`;
"""


def render(rejected):
    code = STUB + f"import {{ rejectedList }} from {json.dumps((ROOT / 'public/js/rejected.js').as_uri())};" \
                  f"const r = rejectedList({json.dumps(rejected)}); console.log(JSON.stringify(r ? html(r) : null));"
    out = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_only_not_placed_names_are_struck_through_and_unknown_ones_are_listed_apart():
    out = render([{"domain": "artist", "name": "Alpha", "verdict": "not_placed"},
                  {"domain": "brand", "name": "Beta", "verdict": "not_in_qloo"}])
    assert "<s>Alpha</s>" in out and "<s>Beta</s>" not in out
    assert "not in Qloo's picks for these viewers here" in out
    assert "No Qloo data yet, so check these yourself: </span>Beta." in out


def test_unknown_names_alone_have_no_strikethrough_or_reason():
    out = render([{"domain": "artist", "name": "Tahsan Khan", "verdict": "not_in_qloo"}])
    assert "<s>" not in out and "Not used" not in out and "Tahsan Khan" in out


def test_long_lists_stop_at_eight_with_a_count():
    out = render([{"domain": "artist", "name": f"N{i}", "verdict": "not_placed"} for i in range(11)])
    assert out.count("<s>") == 8 and "and 3 more" in out


def test_nothing_when_there_are_no_rejected_names():
    assert render([]) is None and render(None) is None


def run_js(body):
    out = subprocess.run(["node", "--input-type=module", "-e", STUB + body], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_check_box_verdicts_render_in_words():
    body = ("import { verdictNode } from " + json.dumps((ROOT / "public/js/check.js").as_uri()) + ";"
            "const o = (v, n) => html(verdictNode({ verdict: v, name: n }, 'artist', 'Nightwatch', 'Sweden'));"
            "console.log(JSON.stringify([o('confirmed','A'), o('not_placed','B'), o('not_in_qloo','C')]));")
    yes, no, unknown = run_js(body)
    assert "Confirmed by Qloo: </strong><span>A</span>" in yes and "<s>" not in yes
    assert "<s>B</s>" in no and "not in Qloo's picks for these viewers here" in no
    assert "<s>" not in unknown and "No Qloo data yet, so check this yourself: </span><span>C</span>" in unknown


def test_catalog_tag_rule():
    body = ("import { isCatalogTitle } from " + json.dumps((ROOT / "public/js/catalog.js").as_uri()) + ";"
            "console.log(JSON.stringify([isCatalogTitle(2020, 2026), isCatalogTitle(2021, 2026), isCatalogTitle(2012, 2026), isCatalogTitle(null, 2026)]));")
    assert run_js(body) == [True, False, True, False]
