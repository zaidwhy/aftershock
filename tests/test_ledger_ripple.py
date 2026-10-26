import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aftershock import ledger  # noqa: E402
from aftershock.ripple import AGE_BANDS, age_gap  # noqa: E402

NOW = datetime(2026, 10, 30, 10, 0, tzinfo=timezone.utc)


def test_ledger_chain_detects_edit(tmp_path):
    path = tmp_path / "f.jsonl"
    ledger.append([{"kind": "spillover", "subject": "A", "target": "KR", "probability": 0.2},
                   {"kind": "spillover", "subject": "A", "target": "JP", "probability": 0.1}], path, NOW)
    ledger.append([{"kind": "ripple", "subject": "B", "target": "song", "score": 0.5}], path, NOW)
    assert ledger.verify(path) is None
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["probability"] = 0.9
    lines[1] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ledger.verify(path) == 1


def test_age_gap_young_show_old_artist_is_large():
    show = dict(zip(AGE_BANDS, [0.7, 0.4, 0.1, -0.6, -0.3, -0.5]))
    old_artist = dict(zip(AGE_BANDS, [-0.6, -0.4, 0.0, 0.3, 0.5, 0.6]))
    young_artist = dict(zip(AGE_BANDS, [0.7, 0.5, 0.1, -0.5, -0.4, -0.5]))
    assert age_gap(show, old_artist) > 0.7
    assert age_gap(show, young_artist) < 0.3
    assert 0.0 <= age_gap(show, old_artist) <= 1.0


def test_percentiles_rank_within_show_and_keep_missing():
    from aftershock.ripple import percentiles
    assert percentiles([3.0, 1.0, 2.0]) == [1.0, 0.0, 0.5]
    assert percentiles([1.0, None, 1.0]) == [0.5, None, 0.5]
    assert percentiles([None, 2.0]) == [None, 0.5]
