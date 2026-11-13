# Running AFTERSHOCK locally and from an agent

You need Python 3.12 and, for anything that calls Qloo, a Qloo API key (hackathon keys come from Qloo's form linked on the hackathon page). Nothing Qloo-derived is committed, so a fresh clone has no forecasts or site data until the weekly job has run once.

```bash
python -m venv .venv
# Windows: .venv\Scripts\python   macOS/Linux: .venv/bin/python   (written as "python" below)
python -m pip install -r requirements-dev.txt
python -m pytest -q                        # no key, no network: fixtures and fakes; tests needing local data skip
cp .env.example .env                       # Windows PowerShell: Copy-Item .env.example .env; then set QLOO_API_KEY
python scripts/run_forecasts.py            # downloads Netflix's TSV, forecasts, locks new forecasts, builds kits, hotspots and the title index
python scripts/export_static.py            # writes the read-only site data to public/data/
python -m uvicorn aftershock.api:app --port 8000   # site and API on http://127.0.0.1:8000
```

A first `run_forecasts.py` takes 15 to 30 minutes: about 700 Qloo calls (paced at 4 per second) and up to about 150 OpenStreetMap lookups (1 per second); later runs reuse the disk cache in `.cache/`. `scripts/backtest_spillover.py` needs no key but reads the Netflix file that `run_forecasts.py` downloads to `data/raw/`. The research scripts (`test_ripple*.py`, `test_spillover_qloo.py`, `experiment_kits.py`) also need the key, and `experiment_kits.py` a `GEMINI_API_KEY`.

From an agent: `aftershock/mcp_server.py` is an MCP server (stdio) with ten tools, `list_storms`, `spillover_forecast`, `launch_kit`, `launch_brief`, `artist_opportunities`, `ripple_score`, `sync_scout`, `release_plan`, `netflix_history` and `ask` (the same plain-question router as the site). It reads the weekly run's output, so run `run_forecasts.py` first. In Claude Desktop's config:

```json
{ "mcpServers": { "aftershock": { "command": "<repo>/.venv/bin/python", "args": ["-m", "aftershock.mcp_server"], "cwd": "<repo>" } } }
```

The Qloo key stays in that process's environment. `tests/test_mcp_stdio.py` checks the server with a real MCP client.

Automation and deployment are in [DEPLOYMENT.md](DEPLOYMENT.md).

Accessibility, checked on the live site on 28 Oct 2026: axe-core 4.9.1 reports 0 violations of any severity on all eight pages in light and dark mode, including the home page with an Ask answer and a map country open; every control is reachable by keyboard in reading order with a visible focus ring; answers appear in polite live regions so screen readers announce them; the map has keyboard buttons and a text list of its top countries; `prefers-reduced-motion` stops the animations.

API contract: [API.md](API.md).
