# RR1 Objective Range Sweep Reversion

RR1 is the frozen Candidate-3 objective range-sweep reversion validation. It uses point-in-time Nifty 500 membership, adjusted Yahoo OHLCV, the canonical `^CRSLDX` session calendar, an exact 60-session range, `ER60 <= 0.25`, prior-20-session liquidity of at least ₹10 crore, a strict lower sweep/reclaim, next-session Open entry, a midpoint target, a `0.25 × ATR14` structural stop, a 15-session lifecycle, paired raw/practical lenses, and an upper failed-break mirror.

The methodology, thresholds, holding period, sample gates, and diagnostics are frozen. Diagnostics cannot tune or rescue a result. RR1 is the final planned strategy-family test; after its formal verdict the swing strategy-family program must be reassessed rather than expanded.

## Run commands

```bash
cd "Swing Trading"
python -m pytest -q research/swing/rr1_range_sweep_reversion/tests
python research/swing/rr1_range_sweep_reversion/run_rr1_validation.py
```

The runner rebuilds all artifacts from frozen source inputs in one stage-ordered run. Raw Yahoo downloads and all-symbol feature caches are not committed. A formal `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE` is interpretable; `INVALID_RESEARCH_RUN` exits non-zero and stops profitability interpretation.
