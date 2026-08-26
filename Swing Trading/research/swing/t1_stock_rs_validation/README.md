# T1 Stock Relative-Strength Validation

This directory contains the precommitted Issue #7 validation experiment for the immutable 218-trade T1 breakout sample. It tests the already-defined individual-stock relative-strength feature as a selection diagnostic; it is validation, not optimization, and the Portfolio Advisor owns the final strategy decision.

## Canonical inputs

- `../t1_sector_validation/input/t1_trades.csv`
- `../stock_rs/output/stock_rs_daily.csv`
- `../sector_leadership/output/sector_leadership_daily.csv`
- `../sector_leadership/stock_sector_map.csv`
- `../../nifty500_regime_daily.csv`

The stock-RS input is the merged Issue #5 / PR #6 output. No T1 trades or RS rows are regenerated here. Research-safe stock-RS rows require `Stock_Count == 20` and `Is_Full_Universe == true`.

## Timing and locked comparisons

T1's Streak daily entry is next-candle-open after an EOD signal, so this validation uses only feature/context observations strictly before `Entry_Date`. Same-entry-day daily RS/market/sector closes are not decision-time-safe for this experiment.

The only primary comparisons are `PREFERRED` versus `VALID + BELOW_VALID`, and `PREFERRED + VALID` versus `BELOW_VALID`. Composite ranks 1 through 20 are diagnostic only. The analysis does not tune lookbacks, weights, thresholds, rank cutoffs, trade rules, exclusions, or interaction filters.

## Run

From the repository root:

```bash
python -m pytest "Swing Trading/research/swing/t1_stock_rs_validation/tests/test_t1_stock_rs.py" -v
python "Swing Trading/research/swing/t1_stock_rs_validation/analyze_t1_stock_rs.py"
```

## Outputs

- `output/t1_stock_rs_joined_trades.csv`
- `output/t1_stock_rs_status_summary.csv`
- `output/t1_stock_rs_binary_tests.csv`
- `output/t1_stock_rs_rank_summary.csv`
- `output/t1_stock_rs_year_summary.csv`
- `output/t1_stock_rs_outlier_robustness.csv`
- `output/t1_stock_rs_symbol_summary.csv`
- `output/t1_stock_rs_leave_one_symbol_out.csv`
- `output/t1_stock_rs_market_matrix.csv`
- `output/t1_stock_rs_sector_matrix.csv`
- `output/validation_report.csv`
- `output/research_report.md`

The report summarizes evidence only. It does not make the Portfolio Advisor's final strategy decision.
