# T1 Sector Leadership Validation

This analysis validates the fixed 218-trade T1 sample against the existing Issue #1/PR #2 point-in-time sector-leadership output. It is a validation experiment, not an optimization or a strategy decision.

## Run from repository root

```bash
python -m pytest "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py" -v
python "Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py"
```

The fixed input source is `input/t1_trades.csv.gz.b64`. The analysis requires the deterministic decoded `input/t1_trades.csv`; the payload is decoded from base64/gzip and checked against SHA-256 `6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4` before analysis. The normalized input is locked at 218 completed trades across the 20-stock basket.

Only sector rows with `Sector_Count == 11` (and a consistent `Is_Full_Universe` flag when present) are eligible. Each trade is matched backward/as-of to the latest eligible row satisfying `Sector_Date <= Entry_Date`; the matched date and calendar lag are exported for audit. The stock-to-sector mapping is the precommitted Issue #1 mapping and is checked exactly.

The existing NIFTY 500 regime dataset is also joined backward/as-of when present. No future data, regenerated trade set, additional indicators, or result-driven filters are introduced.
