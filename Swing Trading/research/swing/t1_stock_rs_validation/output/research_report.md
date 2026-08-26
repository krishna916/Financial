# T1 Stock Relative-Strength Validation

## Methodology

This is a fixed-sample validation experiment, not optimization. It joins the immutable 218 completed T1 breakout trades to the merged Issue #5 / PR #6 stock-RS dataset. The locked feature uses 21-, 63-, and 126-session returns, 30/40/30 percentile weights, rank 1 as strongest, and the unchanged PREFERRED, VALID, and BELOW_VALID status bands.

## Decision-Time Integrity

T1's Streak daily entry is next-candle-open after an EOD signal, so this validation uses only feature/context observations strictly before Entry_Date. Same-entry-day daily RS/market/sector closes are not decision-time-safe for this experiment.

The stock-RS join had 0 unmatched trades and used backward/as-of observations with no same-day or future matches. Median RS lag was 1.0 calendar days and maximum lag was 4 days. Market and sector interactions use the same strict-before-entry rule and are independent of the earlier same-day sector join.

## Unfiltered T1 Baseline

The unfiltered joined sample contains 218 trades, 76 winners, mean return -0.0549, median return -1.5676, and total P&L -4631.32. Median holding time was 20.0 days.

## RS Status Results

- PREFERRED: 45 trades, mean return -1.8855, total P&L -20730.09.
- VALID: 48 trades, mean return -1.3052, total P&L -14062.37.
- BELOW_VALID: 125 trades, mean return 1.0843, total P&L 30161.14.

## Primary Binary Comparisons

- PREFERRED_TEST: PREFERRED: 45 trades, mean return -1.8855, total P&L -20730.09; NON_PREFERRED: 173 trades, mean return 0.4213, total P&L 16098.77.
- VALID_OR_BETTER_TEST: VALID_OR_BETTER: 93 trades, mean return -1.5860, total P&L -34792.46; BELOW_VALID: 125 trades, mean return 1.0843, total P&L 30161.14.

These are the only two primary binary comparisons. No additional rank cutoff or combined buy rule is inferred here.

## Rank Diagnostics

Diagnostic metrics for every Composite_Rank from 1 through 20 are in `output/t1_stock_rs_rank_summary.csv`. Ranks are retained separately and are not converted into an optimized cutoff.

## Year Stability

- 2023: PREFERRED_TEST PREFERRED mean return -0.4117; PREFERRED_TEST NON_PREFERRED mean return 2.7216; VALID_OR_BETTER_TEST VALID_OR_BETTER mean return 1.1720; VALID_OR_BETTER_TEST BELOW_VALID mean return 2.7658.
- 2024: PREFERRED_TEST PREFERRED mean return -3.2330; PREFERRED_TEST NON_PREFERRED mean return 0.1964; VALID_OR_BETTER_TEST VALID_OR_BETTER mean return -1.5700; VALID_OR_BETTER_TEST BELOW_VALID mean return 0.2516.
- 2025: PREFERRED_TEST PREFERRED mean return -1.3345; PREFERRED_TEST NON_PREFERRED mean return -0.5863; VALID_OR_BETTER_TEST VALID_OR_BETTER mean return -1.9134; VALID_OR_BETTER_TEST BELOW_VALID mean return 0.8047.
- 2026: PREFERRED_TEST PREFERRED mean return -1.1625; PREFERRED_TEST NON_PREFERRED mean return -1.2061; VALID_OR_BETTER_TEST VALID_OR_BETTER mean return -2.3687; VALID_OR_BETTER_TEST BELOW_VALID mean return 1.6150.

## Outlier Robustness

The largest positive-P&L trades were removed globally only for the declared sensitivity scenarios; losing trades were not removed.

- ALL_TRADES: excluded none; PREFERRED_TEST direction negative (ALL_TRADES was negative); VALID_OR_BETTER_TEST direction negative (ALL_TRADES was negative).
- EXCLUDE_TOP_1_POSITIVE_PNL: excluded M&M|2024-04-03|10276.20; PREFERRED_TEST direction negative (ALL_TRADES was negative); VALID_OR_BETTER_TEST direction negative (ALL_TRADES was negative).
- EXCLUDE_TOP_3_POSITIVE_PNL: excluded M&M|2024-04-03|10276.20;SUNPHARMA|2023-11-07|8237.25;ONGC|2024-01-04|5711.20; PREFERRED_TEST direction negative (ALL_TRADES was negative); VALID_OR_BETTER_TEST direction negative (ALL_TRADES was negative).
- EXCLUDE_TOP_5_POSITIVE_PNL: excluded M&M|2024-04-03|10276.20;SUNPHARMA|2023-11-07|8237.25;ONGC|2024-01-04|5711.20;SUNPHARMA|2024-07-04|5408.00;ADANIENT|2023-11-28|4621.00; PREFERRED_TEST direction negative (ALL_TRADES was negative); VALID_OR_BETTER_TEST direction negative (ALL_TRADES was negative).

## Stock-Identity Robustness

Symbol-by-status metrics are in `output/t1_stock_rs_symbol_summary.csv`; cells with fewer than five trades are flagged. Leave-one-symbol-out differences are summarized below, with all fixed-basket symbols retained:

- PREFERRED_TEST: group mean-return difference range across 20 exclusions was -2.5918 to -1.8542.
- VALID_OR_BETTER_TEST: group mean-return difference range across 20 exclusions was -3.0113 to -2.1372.

## Market-Regime Interaction

The secondary market-regime matrix is in `output/t1_stock_rs_market_matrix.csv`. It contains a full Market_Regime x RS_Status status matrix and both locked binary comparisons within each regime. These diagnostics do not redefine the primary stock-RS analysis.

## Sector-Leadership Interaction

The secondary sector matrix is in `output/t1_stock_rs_sector_matrix.csv`. It contains a full Leadership_Bucket x RS_Status status matrix and both locked binary comparisons within each sector bucket. Sector rows use the existing definitions and full-universe observations only.

## Data / Method Limitations

- The T1 sample is a fixed 218-trade, 20-symbol sample and is not regenerated here.
- Stock RS is an observational feature joined as-of by calendar date; a calendar lag over seven days is reported for audit rather than silently filled.
- Small cells and stock identity can make subgroup metrics unstable.
- Interaction tables are secondary diagnostics and do not establish causality or authorize new filters.

## Evidence Summary

The generated CSVs and validation report provide the predeclared factual comparisons, timing checks, and robustness evidence for the Portfolio Advisor's separate decision gate. This report does not adopt a threshold, change T1 rules, or make the final strategy decision.
