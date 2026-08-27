# Strategy V3 shallow-pullback validation

This module validates the locked Strategy V3 family:

```text
RS leader -> controlled 3-10 session pullback -> first resumption
-> immediate next-session entry -> structural stop + SMA20 exit
```

The implementation is intentionally separate from the retired T1 research and
closed Strategy V2 evidence. It uses point-in-time Nifty 500 membership,
point-in-time cross-sectional RS, adjusted Yahoo OHLCV, a deterministic
leader/pullback state machine, one-shot entry opportunities, two locked exit
lenses, strict-prior breadth diagnostics, and artifact-derived PIT audits.

Run the historical stages from the repository root:

```bash
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/build_v3_features.py"
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/generate_v3_signals.py"
python "Swing Trading/research/swing/strategy_v3_shallow_pullback/analyze_v3_results.py"
```

Run the deterministic tests:

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
```

The generated `output/` directory contains the data, state, signal, entry,
outcome, diagnostic, PIT, gate, and evidence-report artifacts named in the
approved implementation plan. Raw Yahoo downloads and full all-symbol feature
caches are deliberately not written to the repository.

The report records evidence only. It does not tune Strategy V3 or prescribe a
follow-up threshold/filter; Portfolio Advisor retains strategy interpretation.
