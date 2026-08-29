# E1 Positive Earnings Surprise Drift

This module validates the frozen E1 hypothesis in two stages.

1. `build_e1_source_snapshot.py` acquires official NSE/BSE filing metadata,
   machine-readable EPS, corporate actions, and adjusted Yahoo price inputs.
   It writes immutable CSV snapshots with SHA256 provenance.
2. `run_e1_validation.py` consumes only those frozen inputs. It performs event
   normalization, causal seasonal SUE, shared positive/neutral/negative trade
   construction, analysis, integrity checks, formal gates, and report writing.

Stage B makes no network calls. Missing or hash-mismatched inputs fail closed.
The PIT membership manifest at
`../market_breadth/config/nifty500_membership.csv` is read-only.

From the repository root:

```text
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py"
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

The formal status is the `FINAL_STATUS` value in
`output/e1_validation_gates.csv`.
