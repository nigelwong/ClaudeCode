# tradesignals

Daily US-equity swing-trading signals, informed by technical indicators plus
"smart money" positioning (13F institutional accumulation + Form 4 insider
buying), with a deterministic backtesting engine that supports parameter
sweeps.

This is **Phase 1** of a larger roadmap (see `CLAUDE.md`). Phase 1 has no
LLM calls in its daily run path — it's a plain, deterministic pipeline,
deliberately, to keep it cheap, fast, and safe to run every day.

## Quickstart

```bash
pip install -e ".[dev]"
cp .env.example .env   # fill in ALPACA_API_KEY, ALPACA_SECRET_KEY, SEC_EDGAR_USER_AGENT

# One-off historical backfill (for backtesting only)
tradesignals backfill-data --start 2020-01-01

# Run a backtest
tradesignals backtest --strategy ma_crossover --start 2020-01-01 --end 2023-12-31

# Sweep a strategy's parameters (always reports in-sample vs out-of-sample)
tradesignals sweep --strategy momentum --param rsi_period=10,14,21 --param oversold=20,25,30

# Generate today's signal report
tradesignals run-daily
```

## Daily automation

`.github/workflows/daily-pipeline.yml` runs `tradesignals run-daily` after
US market close on weekdays and commits the report into `reports/`. It
needs `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `SEC_EDGAR_USER_AGENT` set
as repo secrets.

The daily run never depends on a persisted database — it fetches a fresh
trailing window each time. The local SQLite cache (`data/tradesignals.db`,
gitignored) is for on-demand historical backtesting only.

## Known Phase 1 limitations

See `watchlist.yaml` (survivorship bias) and `CLAUDE.md` (point-in-time
data, CUSIP mapping) for limitations that are deliberate scope decisions,
not oversights.
