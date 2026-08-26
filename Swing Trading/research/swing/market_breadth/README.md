# Point-in-Time Nifty 500 Breadth

This phase builds the independent market-breadth series used by the T1 rescue test. It does not load trade outcomes or any T1 input.

## Rebuild

From the repository root:

```text
python Swing Trading/research/swing/market_breadth/build_nifty500_breadth.py
python -m pytest -q Swing Trading/research/swing/market_breadth/tests/test_nifty500_breadth.py
```

The builder downloads adjusted daily closes from Yahoo Finance for every distinct listed ticker represented in the reconstructed membership intervals. The download window is 2022-08-01 through 2026-08-25 so the 200-session SMA is complete at the start of the research window. Missing dates are preserved; no prices are forward-filled.

## Membership method

`config/nifty500_membership.csv` is an inclusive interval manifest with `Method=POINT_IN_TIME`. It is reconstructed backward from the official current Nifty 500 constituent file and then walked forward using the official Nifty Indices press-release archive. `config/nifty500_membership_changes.csv` retains the dated INCLUDE, EXCLUDE, INCLUSION_REVOKED, and EXCLUSION_REVOKED evidence rows.

Official sources:

- Current constituents: https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv
- Press-release archive: https://www.niftyindices.com/press-release
- Nifty 500 index page: https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500

Historical issuer aliases are retained in the change log and mapped to the current Yahoo ticker where appropriate (`GET&D` to `GVT&D`, `HBLPOWER` to `HBLENGINE`, and `AKZOINDIA` to `JSWDULUX`). Official dummy constituents remain in the denominator until the documented listed successor date; their pre-listing interval has no fabricated price ticker and is therefore ineligible for that day's price denominator.

The reconstructed state has 500 to 504 members on different dates. The temporary deviations are documented corporate-action/replacement windows in the official releases, including dummy constituents and corrections; they are not silently normalized to 500.

## Outputs

- `output/nifty500_breadth_daily.csv`: daily eligible denominators, percentages, index trend, and locked `STRONG_MOMENTUM`/`NORMAL`/`HOSTILE` labels.
- `output/breadth_data_validation.csv`: research window, row count, coverage minimum, state-size range, and download summary.
- `output/breadth_universe_audit.csv`: per-ticker raw download, missing-value, duplicate-date, and usability audit.

The research-safe rule is `Eligible_Count_200 >= 80% * Universe_Member_Count`. The downstream T1 analyzer checks that rule again and uses only a strict prior-date match.
