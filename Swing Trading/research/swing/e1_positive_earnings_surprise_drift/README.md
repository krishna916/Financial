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

Long Stage A acquisitions may use an explicitly temporary checkpoint directory;
validated per-symbol filing/EPS checkpoints are reused and final frozen CSVs are
still rebuilt deterministically. Current checkpoints use schema/source/parser
version 2 and transient source failures are never reusable. Checkpoints contain
source/provenance fields only and are not Stage B inputs:

```text
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" --work-dir .e1-stage-a-work-v2
```

The previous `.e1-stage-a-work` checkpoint directory uses the retired v1
format and must not be resumed or reused. Start a clean v2 directory after
source or parser changes.

Before a full acquisition, validate the official exchange adapters with the
fixed source-only smoke set (`RELIANCE`, `TCS`, and `INFY`):

```text
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" --smoke --work-dir .e1-stage-a-smoke-v2
```

Smoke mode writes filing, EPS, corporate-action, and source-audit snapshots
plus `smoke_validation.csv`. It does not download prices or calculate SUE,
trades, or returns. The command exits 2 unless every fixed-symbol filing, EPS,
13-quarter basis-chain, BSE-identity, transient-error, and RELIANCE bonus
sentinel gate passes. Do not start full Stage A while smoke is failing.

The formal status is the `FINAL_STATUS` value in
`output/e1_validation_gates.csv`.
