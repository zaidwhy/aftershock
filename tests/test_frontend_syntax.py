"""Every front-end module must parse as an ES module. One stray parenthesis in about.js took the whole site down on
29 Oct (app.js imports every view, so a single bad module blanks every page), and no Python test noticed."""
import shutil
import subprocess
from pathlib import Path

import pytest

PUBLIC = Path(__file__).resolve().parents[1] / "public"
MODULES = [PUBLIC / "app.js", *sorted((PUBLIC / "js").glob("*.js"))]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_module_parses(module, tmp_path):
    # node only treats a file as an ES module by its extension, so check a .mjs copy.
    copy = tmp_path / f"{module.stem}.mjs"
    copy.write_text(module.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run(["node", "--check", str(copy)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"{module.name} does not parse:\n{result.stderr[:500]}"
