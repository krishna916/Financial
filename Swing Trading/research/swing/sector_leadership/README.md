# Sector Leadership Dataset

This job builds an independent, point-in-time sector-leadership feature dataset for later Swing Strategy V1 validation. It does not consume trade outcomes and does not claim that any leadership bucket is profitable.

> This dataset must not be interpreted as evidence that sector leadership improves trading performance. It is an independent point-in-time feature dataset intended for a separate validation step.

## Fixed inputs

The historical window is daily data from `2022-01-01` through `2026-08-25` inclusive. The pipeline requests the exclusive end date `2026-08-26`, uses `interval="1d"`, `auto_adjust=False`, and uses ordinary daily `Close` values.

The fixed Nifty sector-index universe is configured in `sector_index_config.csv`:

| Sector key | Yahoo identity | Yahoo ticker |
| --- | --- | --- |
| AUTO | NIFTY AUTO | `^CNXAUTO` |
| BANK | NIFTY BANK | `^NSEBANK` |
| FINANCIAL_SERVICES | NIFTY FIN SERVICE | `NIFTY_FIN_SERVICE.NS` |
| FMCG | NIFTY FMCG | `^CNXFMCG` |
| IT | NIFTY IT | `^CNXIT` |
| MEDIA | NIFTY MEDIA | `^CNXMEDIA` |
| METAL | NIFTY METAL | `^CNXMETAL` |
| PHARMA | NIFTY PHARMA | `^CNXPHARMA` |
| REALTY | NIFTY REALTY | `^CNXREALTY` |
| ENERGY | NIFTY ENERGY | `^CNXENERGY` |
| INFRASTRUCTURE | NIFTY INFRA | `^CNXINFRA` |

Every configured ticker is checked for daily history, NSI/NSE index metadata, matching display identity, duplicate dates, missing Close values, and enough history for the 126-session return. Unavailable or invalid sectors are recorded in `output/sector_data_validation.csv` and excluded from ranking. The verified run used to generate the committed artifacts had no unavailable or invalid sectors.

The locked stock-to-sector proxy mapping is in `stock_sector_map.csv`:

| Stock | Sector key |
| --- | --- |
| HDFCBANK, ICICIBANK, SBIN | BANK |
| BAJFINANCE | FINANCIAL_SERVICES |
| TCS, INFY | IT |
| M&M, MARUTI | AUTO |
| LT, BHARTIARTL, ADANIENT, ULTRACEMCO | INFRASTRUCTURE |
| RELIANCE, ONGC, POWERGRID | ENERGY |
| ITC, HINDUNILVR | FMCG |
| SUNPHARMA, APOLLOHOSP | PHARMA |
| TATASTEEL | METAL |

The PHARMA mapping for `APOLLOHOSP` and INFRASTRUCTURE mappings for `BHARTIARTL`, `LT`, `ADANIENT`, and `ULTRACEMCO` are deliberate first-pass proxies. They are limitations to document, not reasons to alter the locked mapping.

## Calculations

For each sector and trading session, the pipeline calculates trading-session returns without manufacturing holiday rows:

```text
Ret21 = Close / Close.shift(21) - 1
Ret63 = Close / Close.shift(63) - 1
Ret126 = Close / Close.shift(126) - 1
```

Rows missing any of these three lookbacks are excluded before cross-sectional ranking. For each date independently, valid sectors are ranked with pandas `rank(method="average", pct=True) * 100` for each return horizon. The locked composite is:

```text
Composite_RS = 0.30 * RS21_Percentile
             + 0.40 * RS63_Percentile
             + 0.30 * RS126_Percentile
```

Composite rank is descending, with strongest sector rank `1`. Exact score ties use deterministic `rank(method="first", ascending=False)`, so exported ranks are unique and reproducible. `Sector_Count` is the number of complete valid sectors on that date. The primary output also includes `Is_Full_Universe`, which is exactly `Sector_Count == 11` for the fixed configured universe.

For `N = Sector_Count`, buckets are applied in this priority order:

```text
LEADING:    rank <= ceil(N / 3)
ACCEPTABLE: rank > ceil(N / 3) and rank <= ceil(N / 2)
LAGGING:    rank > N - ceil(N / 3)
WEAK:       all remaining valid ranks
```

All returns, percentiles, composite scores, ranks, and buckets use only the current date and earlier observations. No future dates, interpolation, synthetic trading sessions, alternate indicators, or tuned thresholds are used.

Sector-index calendars are not identical, so the primary output preserves partial-universe dates rather than silently treating them as full 11-sector observations. Downstream research must use only rows with `Sector_Count == 11` (equivalently, `Is_Full_Universe == True`) for full-universe comparisons. When joining a trade entry date to this feature dataset, use the latest full-universe observation on or before the entry date using strict backward/as-of matching; never use a future observation.

## Run

The repository contains the nested `Swing Trading/` project directory. From the repository root (`Financial/`), enter that directory first:

```powershell
Set-Location "Swing Trading"
python -m pip install -r research/swing/sector_leadership/requirements.txt
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
python research/swing/sector_leadership/build_sector_leadership.py
```

The pipeline validates the primary output, sampled return equations, bucket boundaries, rank ranges, same-day sector counts, and summary reconciliation before writing files.

## Generated files

- `output/sector_leadership_daily.csv` — one row per date and sector with complete 21/63/126-session data and the calculated RS fields.
- `output/sector_leadership_summary.csv` — non-performance counts of ranked days by sector and bucket.
- `output/sector_data_validation.csv` — per-index download status, coverage, missing/duplicate checks, and identity/provider notes.
