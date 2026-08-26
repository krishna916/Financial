# Strategy V2 quality-base breakout validation

This module validates Strategy V2 as a new strategy family. T1 remains retired; this is not a T1 rescue experiment.

The governing design spec is `Swing Trading/docs/superpowers/specs/2026-08-26-strategy-v2-quality-base-breakout-design.md`, and the implementation is for [Issue #13](https://github.com/krishna916/Financial/issues/13). The complete hypothesis requires custom research (`CUSTOM_REQUIRED`) because it combines point-in-time Nifty 500 membership, same-day active-universe RS ranking, a persistent pivot/base state machine, failed-probe updates, base-depth and volatility-contraction state, strict next-session timing, structural-stop simulation, and auditable robustness outputs. A simplified Streak proxy would change the hypothesis.

## Locked methodology

- Signal window: `2023-08-01` through `2026-08-25` inclusive.
- Membership: `../market_breadth/config/nifty500_membership.csv`, evaluated on each signal date with inclusive `Member_From`/`Member_To` intervals. Current membership is never applied retrospectively.
- Price data: one Yahoo Finance `yfinance` download per ticker, `auto_adjust=True`, `actions=False`, daily adjusted Open/High/Low/Close/Volume, from `2022-01-01` through exclusive `2026-08-27`. Missing sessions and missing fields are preserved; OHLCV is never forward-filled.
- ATR: standard Wilder ATR14. The first ATR is the arithmetic mean of the first 14 valid true ranges; later values use `((prior_ATR * 13) + current_TR) / 14`.
- RS: same-day active point-in-time Nifty 500 cross-sectional percentiles for 21/63/126-session returns, weighted `30%/40%/30%`; `Composite_RS >= 70`. A date is research-safe only when at least 80% of active members have all three returns.
- Base: a 63-session high seeds one base; base sessions 1–30 are tracked, with qualifying breakouts only on sessions 10–30. Base depth is at most `4 ATR14` using the original seed ATR. Failed probes update the pivot without resetting base age. Initial-five versus final-five pre-breakout true range must contract by at least 20% (`Final <= 0.80 * Initial`).
- Breakout and entry: close above the active pivot, signal-day extension no more than `1 ATR14`, and exactly one entry opportunity at the next market-session open within pivot through pivot plus `1 ATR14`.
- Stop: final-five pre-breakout low minus `0.25 ATR14_signal`; reject if the stop is not below entry or is more than `2.5 ATR14_signal` away.
- Exits: setup-quality uses the next open after a close below SMA20; practical trading uses the same SMA20 exit plus the fixed structural stop, with scheduled SMA20 exit before gap-stop and intraday-stop checks.
- Breadth is diagnostic-only and uses the latest strict prior date (`Breadth_Matched_Date < Entry_Date`). Sector RS, breakout volume, breadth, event-risk governance, targets, breakeven, trailing stops, time stops, and portfolio-capacity constraints are not entry gates in this validation.
- Thresholds and filters are frozen. Outcomes must not be used to tune this hypothesis.

## Rebuild and tests

From the repository root:

```text
python "Swing Trading/research/swing/strategy_v2_quality_base/build_v2_features.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/generate_v2_signals.py"
python "Swing Trading/research/swing/strategy_v2_quality_base/analyze_v2_results.py"
python -m pytest -q "Swing Trading/research/swing/strategy_v2_quality_base/tests"
```

The existing legacy swing tests import their modules as `research.*`; run them from the `Swing Trading` directory:

```text
Set-Location "Swing Trading"
python -m pytest -q research/swing
```

Historical execution deliberately rebuilds daily data in memory and does not commit raw Yahoo downloads or a giant all-symbol feature cache.

## Committed outputs

| Output | Purpose |
| --- | --- |
| `v2_data_validation.csv` | Per-symbol adjusted OHLCV row, missing-field, duplicate-date, and usability audit. |
| `v2_universe_rs_audit.csv` | Per-date active-universe denominator, RS-eligible count, coverage, and research-safety audit. |
| `v2_base_state_audit.csv` | Seed, failed-probe, depth invalidation, too-short, expiry, and breakout state transitions. |
| `v2_signal_candidates.csv` | Every breakout candidate with frozen base, RS, trend, liquidity, contraction, extension, and rejection fields. |
| `v2_entries.csv` | Accepted immediate next-session entries and fixed structural stops. |
| `v2_entry_cancellations.csv` | One primary cancellation reason for each rejected next-session opportunity. |
| `v2_setup_quality_trades.csv` | Completed setup-quality lens outcomes. |
| `v2_practical_trades.csv` | Completed practical lens outcomes with fixed-stop R multiples. |
| `v2_validation_summary.csv` | Headline metrics for both lenses. |
| `v2_validation_gates.csv` | One row per locked gate plus final status. |
| `v2_year_summary.csv` | Calendar-year entry cohorts for temporal robustness. |
| `v2_outlier_robustness.csv` | Top-1, top-3, and top-5 winner-removal results with exact removed IDs/symbols. |
| `v2_leave_one_symbol_out.csv` | Robustness results after omitting each represented symbol. |
| `v2_breadth_summary.csv` | Diagnostic metrics by strict-prior breadth regime. |
| `v2_overlap_diagnostic.csv` | Signal-level overlap and same-day-entry diagnostics. |
| `research_report.md` | Mechanically generated evidence report ending with the locked handoff statement. |
