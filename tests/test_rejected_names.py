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


def test_names_are_struck_through_with_a_reason_in_words():
    out = render([{"domain": "artist", "name": "Alpha", "verdict": "not_placed"},
                  {"domain": "brand", "name": "Beta", "verdict": "not_in_qloo"}])
    assert "<s>Alpha</s>" in out and "<s>Beta</s>" in out
    assert "Qloo does not link it to these viewers here" in out and "Qloo does not know it" in out


def test_long_lists_stop_at_eight_with_a_count():
    out = render([{"domain": "artist", "name": f"N{i}", "verdict": "not_placed"} for i in range(11)])
    assert out.count("<s>") == 8 and "and 3 more" in out


def test_nothing_when_there_are_no_rejected_names():
    assert render([]) is None and render(None) is None
