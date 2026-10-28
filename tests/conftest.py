import pytest

from aftershock import metro_names


@pytest.fixture(autouse=True)
def no_metro_file(tmp_path_factory, monkeypatch):
    """The real data/private/metro_names.json (Qloo-derived, built locally) must not rename the places that other
    tests use as fixtures; the tests of the relabel itself point METRO_FILE at a file they write."""
    monkeypatch.setattr(metro_names, "METRO_FILE", tmp_path_factory.mktemp("metro") / "none.json")
