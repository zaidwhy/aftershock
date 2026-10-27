from datetime import date, timedelta

from aftershock import wiki
from aftershock.wiki import artist_title_matches, mentions_artist, spike_from_series, title_matches

RELEASE = date(2022, 5, 27)


def _series(baseline: int, after: int, spike_day: int | None = None, spike_views: int = 0) -> dict:
    series = {}
    for offset in range(-60, 36):
        day = RELEASE + timedelta(days=offset)
        series[day] = baseline if offset < 0 else after
    if spike_day is not None:
        series[RELEASE + timedelta(days=spike_day)] = spike_views
    return series


def test_title_accepts_exact_and_disambiguated():
    assert title_matches("Running Up That Hill", "Running Up That Hill")
    assert title_matches("Running Up That Hill (Kate Bush song)", "Running Up That Hill")


def test_title_accepts_song_with_subtitle_and_remix_tail():
    assert title_matches("Running Up That Hill", "Running Up That Hill (A Deal with God)")
    assert title_matches("Separate Ways (Worlds Apart)", "Separate Ways (Worlds Apart) [Bryce Miller/Alloy Tracks Remix]")
    assert title_matches("Dream a Little Dream of Me", "Dream A Little Dream Of Me - Single Version")


def test_title_rejects_unrelated():
    assert not title_matches("Stranger Things (TV series)", "Running Up That Hill")
    assert not title_matches("Hill (surname)", "Running Up That Hill")


def test_title_rejects_non_song_article_with_same_name():
    assert not title_matches("F1 (film)", "F1")
    assert not title_matches("Wicked (album)", "Wicked")
    assert title_matches("Slash (song)", "SLASH")


def test_artist_mention():
    intro = "Running Up That Hill is a song by the English singer-songwriter Kate Bush."
    assert mentions_artist(intro, "Kate Bush")
    assert not mentions_artist(intro, "Metallica")


def test_spike_ratio_on_synthetic_series():
    series = _series(baseline=100, after=1000, spike_day=2, spike_views=5000)
    result = spike_from_series(series, RELEASE, today=RELEASE + timedelta(days=100))
    assert result.status == "ok"
    assert result.baseline_mean == 100
    assert result.after_mean == 1000
    assert result.ratio == (1000 + 1) / (100 + 1)
    assert result.peak == 5000


def test_spike_windows_exclude_release_week_and_far_days():
    series = _series(baseline=10, after=10)
    series[RELEASE + timedelta(days=3)] = 99999  # release week: outside the after window
    series[RELEASE - timedelta(days=5)] = 99999  # days -7..-1: outside the baseline window
    result = spike_from_series(series, RELEASE, today=RELEASE + timedelta(days=100))
    assert result.baseline_mean == 10
    assert result.after_mean == 10
    assert result.peak == 99999


def test_recent_release_is_pending_with_partial_values():
    today = RELEASE + timedelta(days=20)
    series = _series(baseline=50, after=200)
    result = spike_from_series(series, RELEASE, today=today)
    assert result.status == "pending"
    assert result.baseline_mean == 50
    assert result.after_mean == 200  # only days +7..+19 are available
    assert result.ratio == 201 / 51


def test_missing_days_count_as_zero_views():
    series = {RELEASE + timedelta(days=d): 100 for d in range(7, 36, 2)}
    result = spike_from_series(series, RELEASE, today=RELEASE + timedelta(days=100))
    assert result.baseline_mean == 0
    assert result.after_mean == 100 * 15 / 29


def test_artist_title_accepts_exact_and_music_disambiguators():
    assert artist_title_matches("Metallica", "Metallica")
    assert artist_title_matches("Journey (band)", "Journey")
    assert artist_title_matches("The Beach Boys", "The Beach Boys")
    assert artist_title_matches("Kate Bush", "Kate Bush, Peter Gabriel")
    assert artist_title_matches("Sienna Spiro", "SIENNA SPIRO")
    assert artist_title_matches("Pink (singer)", "Pink")


def test_artist_title_rejects_non_music_disambiguators_and_other_names():
    assert not artist_title_matches("Journey (film)", "Journey")
    assert not artist_title_matches("Journey (Journey album)", "Journey")
    assert not artist_title_matches("Journey (song)", "Journey")
    assert not artist_title_matches("Journey Through the Past", "Journey")
    assert not artist_title_matches("Metallica (album)", "Metallica")


def test_api_error_body_is_raised_and_not_cached(tmp_path, monkeypatch):
    class BusyResponse:
        status_code = 200
        text = ""
        def json(self):
            return {"error": {"code": "cirrussearch-too-busy-error"}}
    monkeypatch.setattr(wiki, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(wiki, "_pace", lambda: None)
    monkeypatch.setattr(wiki.httpx, "get", lambda *a, **k: BusyResponse())
    try:
        wiki._cached_get("https://en.wikipedia.org/w/api.php", {"q": "x"})
        raised = False
    except wiki.WikiError:
        raised = True
    assert raised and not list(tmp_path.iterdir())
