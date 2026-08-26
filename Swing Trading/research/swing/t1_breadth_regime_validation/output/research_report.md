# T1 Breadth Regime Validation

This is the precommitted final rescue test for the immutable 218-trade T1 sample. The Portfolio Advisor's methodology decision was `CUSTOM_REQUIRED`; the implementation is mechanical and does not tune thresholds after observing outcomes.

## Data-integrity gate

- Breadth universe method: `POINT_IN_TIME`.
- Breadth rows were built independently in `market_breadth/`; the breadth builder does not load the T1 input.
- The frozen breadth series contains 218 decision-time matches; research-safe matches: 218.
- Breadth lag maximum: 4 calendar days; median: 1 calendar days; lags over seven days: 0.
- No minimum-duration filter was applied to strong episodes.

## New breadth-regime result

| Comparison | Group | Trades | Win_Rate | Mean_Return | Return_Profit_Factor | Total_PnL |
| --- | --- | --- | --- | --- | --- | --- |
| THREE_REGIMES | STRONG_MOMENTUM | 88 | 0.3864 | 0.5469 | 1.2974 | 11570.9500 |
| THREE_REGIMES | NORMAL | 101 | 0.3168 | -0.1520 | 0.9310 | -5243.7100 |
| THREE_REGIMES | HOSTILE | 29 | 0.3448 | -1.5427 | 0.3934 | -10958.5600 |

| Comparison | Group | Trades | Win_Rate | Mean_Return | Return_Profit_Factor | Total_PnL |
| --- | --- | --- | --- | --- | --- | --- |
| STRONG_MOMENTUM_vs_NON_STRONG | STRONG_MOMENTUM | 88 | 0.3864 | 0.5469 | 1.2974 | 11570.9500 |
| STRONG_MOMENTUM_vs_NON_STRONG | NON_STRONG | 130 | 0.3231 | -0.4622 | 0.7971 | -16202.2700 |
| HOSTILE_vs_NON_HOSTILE | HOSTILE | 29 | 0.3448 | -1.5427 | 0.3934 | -10958.5600 |
| HOSTILE_vs_NON_HOSTILE | NON_HOSTILE | 189 | 0.3492 | 0.1734 | 1.0853 | 6327.2400 |

## Robustness outputs

- Entry-year comparison: `output/t1_breadth_year_summary.csv`.
- Global positive-P&L outlier removal: `output/t1_breadth_outlier_robustness.csv`.
- Leave-one-symbol-out diagnostic across all 20 fixed symbols: `output/t1_breadth_leave_one_symbol_out.csv`.
- Strong-episode fragmentation and trade distribution: `output/t1_breadth_episode_summary.csv`.

## Existing simple index regime comparison

The earlier `RISK_ON`/`MIXED`/`RISK_OFF` labels were matched strictly before entry from the existing committed Nifty 500 regime file. The table is factual context only; no regime definition was changed to improve the result.

| Comparison | Group | Trades | Win_Rate | Mean_Return | Return_Profit_Factor | Total_PnL |
| --- | --- | --- | --- | --- | --- | --- |
| EXISTING_SIMPLE_INDEX_REGIME | RISK_ON | 150 | 0.3533 | 0.0307 | 1.0149 | 1550.1500 |
| EXISTING_SIMPLE_INDEX_REGIME | MIXED | 39 | 0.3333 | 0.7223 | 1.3777 | 4777.0900 |
| EXISTING_SIMPLE_INDEX_REGIME | RISK_OFF | 29 | 0.3448 | -1.5427 | 0.3934 | -10958.5600 |

## Interpretation boundary

This report supplies the locked evidence only. The Portfolio Advisor retains the keep/retire decision. The precommitted gate calls for positive expectancy, materially stronger separation from `NON_STRONG`, robustness to removing the top 1/3/5 positive-P&L trades, no single-symbol dependence, and evidence across more than one episode where sample size permits.
