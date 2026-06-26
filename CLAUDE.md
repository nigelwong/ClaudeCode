# tradesignals — project conventions

## Architecture

```
data layer (Alpaca + SEC EDGAR) -> signal engine -> backtest engine -> reports/CLI
```

- `src/tradesignals/data/` — fetches and caches market bars (Alpaca) and
  SEC filings (EDGAR 13F + Form 4) into SQLite.
- `src/tradesignals/signals/` — pluggable `Strategy` implementations that
  turn data into a ranked daily long/short list.
- `src/tradesignals/backtest/` — deterministic simulation of a strategy
  over historical data, plus parameter sweeps with train/test validation.
- `src/tradesignals/reports/` — renders signals/backtest results to
  Markdown + JSON.
- `src/tradesignals/cli/` — `typer` entrypoints tying it together.

## Invariants (do not violate these)

1. **No lookahead bias.** A strategy's `score()` must only ever be given
   data with date/`filed_date` `<= as_of_date`. For SEC data specifically,
   gate on `filed_date` (when a filing became public), never
   `report_period`/`transaction_date` (the fact date) — a 13F's
   report_period can predate its filed_date by up to ~45 days, so using
   the fact date leaks information the market didn't have yet.
2. **Daily run path is LLM-free.** `tradesignals run-daily` and everything
   it calls must be deterministic plain code — no Claude/LLM API calls.
   This keeps the daily GitHub Actions run cheap, fast, and safe to run
   unattended every weekday.
3. **The daily run never depends on a persisted DB.** It fetches a fresh
   trailing window each time. Only `backfill-data`/`backtest`/`sweep`
   (on-demand, local/manual) rely on the SQLite cache accumulating over
   multiple runs on the same machine.
4. **Overfitting avoidance is the default, not opt-in.** `tradesignals
   sweep` always reports in-sample vs. out-of-sample (or walk-forward)
   results; don't add a sweep path that skips this.

## Adding a new strategy

Implement the `Strategy` interface in `signals/base.py` and register it in
`signals/registry.py`. This is the extension point a future LLM "Model
Creator" agent (Phase 2, not yet built) will write into — keep the
interface stable.

## Known, deliberate Phase 1 limitations

- **Survivorship bias**: `watchlist.yaml` is today's tickers, not a
  point-in-time historical constituent list.
- **CUSIP→ticker mapping**: there's no free official CUSIP↔ticker mapping
  at market scale, so `data/cusip_map.yaml` is a small, manually
  maintained table scoped to the watchlist only.
- **13F filer coverage**: only a small curated list of well-known
  institutional filers is tracked, not the entire market.

These are scope decisions for Phase 1, not bugs — don't "fix" them without
discussing the tradeoff first (e.g. point-in-time constituents and
broader 13F coverage are real Phase 3 candidates, not quick patches).

## Roadmap (do not build ahead of the current phase without discussion)

- **Phase 1 (current)**: deterministic data/signal/backtest pipeline +
  daily GitHub Actions automation. No LLM calls anywhere in this phase.
- **Phase 2**: weekly-cadence LLM agents (Model Researcher, Model Creator,
  Model Manager) that propose new strategies into `signals/registry.py`.
  Still no LLM calls in the daily path.
- **Phase 3**: paid data feeds if justified, formal multi-source
  Information Source module, Information & Model Executor (paper trade
  plans), possible Postgres migration.
- **Phase 4**: real delivery channel (email/Slack/dashboard), possible
  always-on service, optional Alpaca paper/live execution integration.

## Running locally

```bash
pip install -e ".[dev]"
pytest
tradesignals backfill-data --start 2020-01-01
tradesignals backtest --strategy ma_crossover --start 2020-01-01 --end 2023-12-31
```

## Testing conventions

- Pure functions (`backtest/metrics.py`, indicator math) get exact-value
  unit tests against hand-computed fixtures.
- Anything touching SEC/Alpaca data uses fixture files under
  `tests/fixtures/`, never live network calls in CI.
- `tests/test_no_lookahead.py` is the most important test in the repo —
  any change to the data or backtest layers should keep it green.
