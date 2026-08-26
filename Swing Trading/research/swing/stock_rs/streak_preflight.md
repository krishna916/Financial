# Stock RS Streak Preflight

Decision: CUSTOM_REQUIRED

Exact hypothesis: same-day cross-sectional 21/63/126-session stock RS percentile
across the comparison universe, combined with fixed 30/40/30 weights.

## Exact capability test

The Streak path would be exact only if all of these capabilities were available
together:

- evaluate multiple symbols on the same historical date;
- calculate 21-, 63-, and 126-session stock returns;
- convert each return horizon into a same-date cross-sectional percentile/rank
  against the selected universe;
- combine those percentiles with fixed 30/40/30 weights; and
- use or export the resulting historical `Composite_RS` feature.

## Evidence checked

- Streak's official product overview, checked 2026-08-26:
  <https://zerodha.com/z-connect/streak/introducing-streak-v4>. It describes
  scanners that filter a basket of stocks using conditions and backtests that
  run strategies on multiple stocks, but it does not document same-date
  cross-sectional percentile/rank calculation or an exportable historical
  composite feature.
- Streak's current product site and help center, checked 2026-08-26:
  <https://www.streak.tech/> and <https://help.streak.tech/>. No explicit
  documentation was available for the complete capability test above.
- This repository has no authenticated Streak session, connector, or saved
  exact-hypothesis setup with which to execute an additional product test.

## Why Streak is insufficient for this experiment

The available evidence supports per-symbol technical conditions and
multi-symbol backtests, but does not establish historical same-date ranking of
each stock against the fixed 20-stock comparison universe or export of that
ranked feature. A single-stock RSI, ROC, momentum, moving-average, or relative
performance condition is not equivalent to cross-sectional universe percentile
ranking.

Because the exact A-E capability is not explicitly available or verifiable,
the approved custom-data path is allowed. This preflight does not inspect or
join T1 trade outcomes.
