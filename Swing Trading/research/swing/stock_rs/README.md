# Stock Relative-Strength Dataset

This directory builds the fixed 20-stock, point-in-time stock relative-strength
(RS) dataset for the later T1 validation experiment. It is data preparation
only. No T1 trade outcomes, returns, or P&L are loaded or inspected here.

## Validation-source hierarchy

Streak is preferred whenever it can faithfully express a hypothesis. This
custom dataset exists only because the current experiment requires same-day
cross-sectional historical ranking across multiple stocks. It is a
proxy-validation input, not a replacement for Streak where Streak can perform
the exact test.

The completed preflight in `streak_preflight.md` records `CUSTOM_REQUIRED`.
The exact test requires historical same-date ranking of every stock against the
comparison universe for 21-, 63-, and 126-session returns, fixed 30/40/30
combination, and a usable historical feature. Single-stock RSI, ROC, momentum,
moving-average, or relative-performance conditions are not equivalent.

## Locked methodology

- Universe: exactly the 20 symbols in `stock_ticker_config.csv`.
- Yahoo history: daily bars from `2022-01-01` through `2026-08-25` inclusive,
  downloaded one ticker at a time with `auto_adjust=False`.
- Prices: preserve both `Close` and `Adj Close`; calculate all RS returns from
  `Adj Close` only.
- Session returns:
  `Adj_Close(t) / Adj_Close(t-N) - 1` for `N` equal to 21, 63, and 126.
- On dates with all 20 valid stocks, rank each horizon cross-sectionally with
  `rank(method="average", pct=True, ascending=True) * 100`.
- Composite score: `0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126`.
- Composite rank 1 is strongest. Exact composite-score ties sort symbols
  ascending before descending `rank(method="first")`.
- Research-safe rows require `Stock_Count == 20` and
  `Is_Full_Universe == true`.
- Status bands are locked: `PREFERRED >= 80`, `VALID >= 70 and < 80`, and
  `BELOW_VALID < 70`.

No interpolation, forward-filled synthetic sessions, alternate securities,
extra indicators, parameter tuning, result-driven exclusions, or historical
Nifty 500 constituent substitutions are used.

## Reliability limitations

Yahoo/yfinance history can differ from broker, exchange, or Streak histories
because of vendor adjustments, corporate-action treatment, missing sessions,
or calendar differences. Raw row counts, date ranges, missing values, and
duplicate dates are recorded in `output/stock_rs_validation.csv`; suspicious
vendor/calendar gaps must be spot-checked before using any result.

The fixed 20-stock basket is an intentional proxy validation universe, not the
final point-in-time Nifty 500 universe. Any promising RS result must later be
robustness-checked against trusted market data before live deployment. Do not
use this custom pipeline where an equivalent exact Streak test is available.

## Run from repository root

```bash
python -m pytest "Swing Trading/research/swing/stock_rs/tests/test_stock_rs.py" -v
python "Swing Trading/research/swing/stock_rs/build_stock_rs.py"
```

The build fails before writing a research-safe primary output if any configured
stock fails to download, has missing required prices, or violates a raw-data
invariant. A successful build writes:

- `output/stock_rs_daily.csv` — one row per stock and complete ranked date;
- `output/stock_rs_summary.csv` — per-symbol ranked-day and status counts;
- `output/stock_rs_validation.csv` — per-symbol raw download audit.

The next issue may independently join this feature dataset to the fixed T1
trades. That join and any strategy interpretation are intentionally outside
this issue.
