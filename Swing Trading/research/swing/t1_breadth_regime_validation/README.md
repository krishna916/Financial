# T1 Breadth Regime Validation

This is the precommitted final rescue test for the immutable T1 20-day breakout sample. It compares the fixed trades across the locked Nifty 500 breadth regimes; it is not strategy optimization.

## Run

From the repository root, build and freeze the independent breadth phase first, then run:

```text
python -m pytest -q Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py
python Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py
python -m pytest -q Swing Trading/research/swing/t1_breadth_regime_validation/tests/test_t1_breadth_regime.py
python Swing Trading/research/swing/t1_breadth_regime_validation/analyze_t1_breadth_regime.py
```

The fixed input is `../t1_sector_validation/input/t1_trades.csv`: 218 completed trades, 20 symbols, 76 winners, and total P&L of -4631.32. The analyzer verifies the locked SHA-256 and aggregates before performing any regime comparison.

## Locked rules

The breadth regime uses the existing Nifty 500 `Close > SMA200` index condition and adjusted-close cross-section:

- `STRONG_MOMENTUM`: index above SMA200 and both breadth percentages at least 60%.
- `NORMAL`: index above SMA200 but not strong.
- `HOSTILE`: index close at or below SMA200.

SMA windows are full 50/200 trading-session windows. A trade is matched only to the latest breadth observation with `Breadth_Matched_Date < Entry_Date`; same-entry-day and future matches are rejected. The 80% 200-session coverage rule is checked before the trade data is joined.

The analyzer exports the three-regime result, the two locked binary comparisons, entry-year diagnostics for 2023–2026, global positive-P&L outlier removal, leave-one-symbol-out diagnostics, and strong-episode fragmentation. It also reports the existing simple `RISK_ON`/`MIXED`/`RISK_OFF` result as factual context.

The keep/retire decision remains with the Portfolio Advisor. No thresholds, SMA windows, years, episode durations, losing trades, stocks, or additional indicators are tuned after observing outcomes.
