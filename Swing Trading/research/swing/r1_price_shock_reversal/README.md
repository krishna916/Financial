# R1 Short-Term Price-Shock Reversal

This module evaluates the frozen R1 hypothesis: a liquid point-in-time Nifty 500 stock with a large low-volume one-day decline is bought at the immediate next-session open and evaluated over five complete holding sessions. The high-volume shock cohort is a falsification control. Structural-stop practical outcomes, fixed friction scenarios, temporal and outlier robustness, bootstrap intervals, overlap diagnostics, and an artifact-derived integrity audit are evidence only.

Primary rules are fixed at Shock_Score <= -2.0, low Volume_Ratio <= 1.0, high-volume control Volume_Ratio >= 1.5, prior-20-session liquidity >= ₹10 crore, a 0.25 ATR14 structural stop, T+1 Open entry, T+6 Open exit, and 0.40% / 0.60% / 0.80% round-trip friction. No momentum, trend, relative-strength, sector, breadth, regime, confirmation, gap, or news filter is part of primary eligibility.

The generated `research_report.md` and CSV files are historical evidence. A weak or failed formal status is preserved as a valid result.

## Run commands

```bash
python "Swing Trading/research/swing/r1_price_shock_reversal/build_r1_features.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/generate_r1_signals.py"
python "Swing Trading/research/swing/r1_price_shock_reversal/analyze_r1_results.py"
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
```
