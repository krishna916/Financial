# T1 Sector Leadership Validation

## Input Integrity

The fixed normalized input contains **218 trades**, **20 symbols**, and **76 winners**. Total P&L is `-4631.32`. The committed payload is decoded deterministically before analysis and validated against its locked SHA-256 in the repository workflow.

The sector join matched every trade to the latest full-universe (`Sector_Count == 11`) observation on or before entry. Median sector-date lag was **0.0 calendar days** and maximum lag was **18 days**.

## Four-Bucket Results

| Bucket | Trades | Win rate | Mean return | Median return | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| LEADING | 108 | 0.3704 | 0.2123 | -1.2011 | 3328.25 |
| ACCEPTABLE | 55 | 0.2727 | -1.1443 | -2.7018 | -15620.22 |
| WEAK | 19 | 0.4211 | 0.8142 | -1.4048 | 3927.65 |
| LAGGING | 36 | 0.3611 | 0.3494 | -2.1051 | 3733.00 |

## Locked Binary Comparisons

| Comparison | Group | Trades | Win rate | Mean return | Return PF | Total P&L |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| LEADING_vs_NON_LEADING | LEADING | 108 | 0.3704 | 0.2123 | 1.1082 | 3328.25 |
| LEADING_vs_NON_LEADING | NON_LEADING | 110 | 0.3273 | -0.3172 | 0.8583 | -7959.57 |
| TOP_HALF_vs_LOWER_HALF | TOP_HALF | 163 | 0.3374 | -0.2455 | 0.8882 | -12291.97 |
| TOP_HALF_vs_LOWER_HALF | LOWER_HALF | 55 | 0.3818 | 0.5100 | 1.2804 | 7660.65 |
| LAGGING_vs_NON_LAGGING | LAGGING | 36 | 0.3611 | 0.3494 | 1.1766 | 3733.00 |
| LAGGING_vs_NON_LAGGING | NON_LAGGING | 182 | 0.3462 | -0.1348 | 0.9365 | -8364.32 |

## Rank Diagnostics

Rank-level metrics are exported in `output/t1_sector_rank_summary.csv` for Composite_Rank 1 through 11. These diagnostics do not select a new cutoff.

## Within-Sector Controls

Detailed and TOP_HALF versus LOWER_HALF results by sector are exported in `output/t1_sector_within_sector_summary.csv`. The fixed 20-stock sample is sector-imbalanced, and rows with fewer than five observations are marked `Small_Sample`.

## Time Stability

Entry-year output is available in `output/t1_sector_year_summary.csv` for 2023-2026. Calendar years are diagnostic periods, not optimized market regimes.

## Outlier Robustness

Outlier variants excluding the largest one, three, and five positive-P&L trades are exported in `output/t1_sector_outlier_robustness.csv`. Excluded trades are recorded in an audit field; no losing trades were removed.

## Market-Regime Interaction

The existing NIFTY 500 daily regime dataset was available, so the backward/as-of market-regime join was completed. The complete regime × leadership matrix and the predeclared RISK_ON/MIXED + sector TOP_HALF comparison are in `output/t1_market_sector_matrix.csv`.

| Type | Market regime | Sector bucket | Group | Trades | Win rate | Mean return |
| --- | --- | --- | --- | ---: | ---: | ---: |
| REGIME_X_BUCKET | RISK_ON | LEADING |  | 72 | 0.3611 | 0.5024 |
| REGIME_X_BUCKET | RISK_ON | ACCEPTABLE |  | 43 | 0.2326 | -2.1824 |
| REGIME_X_BUCKET | RISK_ON | WEAK |  | 11 | 0.4545 | 1.1117 |
| REGIME_X_BUCKET | RISK_ON | LAGGING |  | 28 | 0.4643 | 1.4498 |
| REGIME_X_BUCKET | MIXED | LEADING |  | 20 | 0.4000 | 0.5206 |
| REGIME_X_BUCKET | MIXED | ACCEPTABLE |  | 8 | 0.3750 | 3.4241 |
| REGIME_X_BUCKET | MIXED | WEAK |  | 7 | 0.4286 | 0.9591 |
| REGIME_X_BUCKET | MIXED | LAGGING |  | 7 | 0.0000 | -3.5775 |
| REGIME_X_BUCKET | RISK_OFF | LEADING |  | 16 | 0.3750 | -1.4785 |
| REGIME_X_BUCKET | RISK_OFF | ACCEPTABLE |  | 4 | 0.5000 | 0.8776 |
| REGIME_X_BUCKET | RISK_OFF | WEAK |  | 1 | 0.0000 | -3.4729 |
| REGIME_X_BUCKET | RISK_OFF | LAGGING |  | 1 | 0.0000 | -2.9727 |
| RISK_ON_OR_MIXED_TOP_HALF_VS_ALL_OTHER |  |  | RISK_ON_OR_MIXED_TOP_HALF | 143 | 0.3287 | -0.1389 |
| RISK_ON_OR_MIXED_TOP_HALF_VS_ALL_OTHER |  |  | ALL_OTHER_VALID | 75 | 0.3867 | 0.1054 |

## Limitations

- This is a fixed 20-stock sample and sector identity is confounded with leadership frequency.
- Small cells and outlier dependence can make subgroup metrics unstable.
- No transaction-cost adjustment was added unless it was already present in the fixed T1 input.
- The analysis preserves the locked RS windows, weights, ranking, bucket boundaries, mapping, and T1 entry/exit rules.
- This factual report does not authorize changing V1 rules or make the Portfolio Advisor's final strategy decision.
