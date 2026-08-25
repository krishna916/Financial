# Sector Leadership Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time sector-leadership dataset that can later be joined independently against the existing Swing Strategy V1 T1 trade log.

**Architecture:** A single Python research pipeline downloads fixed Nifty sector index histories with `yfinance`, validates identity and history depth, computes 21/63/126-session returns, converts them into same-day cross-sectional percentiles, calculates the locked 30/40/30 composite RS score, assigns deterministic leadership buckets, and writes three CSV artifacts. Pure ranking/bucket logic is separated into testable functions so Luna can verify each rule mechanically.

**Tech Stack:** Python 3.11+, pandas, numpy, yfinance, pytest.

**Spec:** GitHub Issue #1 — `https://github.com/krishna916/Financial/issues/1`

## Global Constraints

- This is **data preparation only**. Do not use or inspect trade profitability.
- Historical range: `2022-01-01` through `2026-08-25` inclusive.
- Daily data only; `interval="1d"`; `auto_adjust=False`.
- Use ordinary daily `Close` consistently for all return calculations.
- Fixed lookbacks: 21, 63, 126 trading sessions.
- Fixed composite: `0.30 * RS21 + 0.40 * RS63 + 0.30 * RS126`.
- Leadership buckets are locked exactly as Issue #1 defines.
- No interpolation, synthetic market days, future data, alternate indicators, or threshold tuning.
- If a requested sector index is unavailable, record it as unavailable; do not silently substitute an unrelated index or ETF.
- The stock-sector mapping from Issue #1 is locked for this experiment.
- Implementation must be mechanical enough for Luna to execute without domain judgment.
- Execution mode is inline only.

---

## File Map

Create these files:

```text
research/swing/sector_leadership/
├── build_sector_leadership.py
├── requirements.txt
├── sector_index_config.csv
├── stock_sector_map.csv
├── README.md
├── tests/
│   └── test_sector_leadership.py
└── output/
    ├── sector_leadership_daily.csv
    ├── sector_leadership_summary.csv
    └── sector_data_validation.csv
```

Responsibilities:

- `build_sector_leadership.py` — all download, validation, return, ranking, bucket, export, and CLI orchestration logic.
- `sector_index_config.csv` — fixed sector-key to Yahoo/Nifty index mapping plus index name.
- `stock_sector_map.csv` — exact locked 20-stock mapping from Issue #1.
- `tests/test_sector_leadership.py` — deterministic tests for pure return/rank/bucket/validation helpers.
- `README.md` — methodology, run instructions, proxy limitations, generated artifacts.
- `output/*.csv` — committed generated research artifacts.

---

### Task 1: Scaffold the research job and lock static inputs

**Files:**
- Create: `research/swing/sector_leadership/requirements.txt`
- Create: `research/swing/sector_leadership/stock_sector_map.csv`
- Create: `research/swing/sector_leadership/sector_index_config.csv`

**Interfaces:**
- Consumes: Issue #1 fixed sector universe and stock-sector mapping.
- Produces: static CSV configuration loaded by later tasks.

- [ ] **Step 1: Create `requirements.txt`**

Use only:

```text
yfinance
pandas
numpy
pytest
```

Do not add plotting, notebooks, web frameworks, or unrelated libraries.

- [ ] **Step 2: Create `stock_sector_map.csv` exactly**

```csv
Stock,Sector_Key
HDFCBANK,BANK
ICICIBANK,BANK
SBIN,BANK
BAJFINANCE,FINANCIAL_SERVICES
TCS,IT
INFY,IT
M&M,AUTO
MARUTI,AUTO
LT,INFRASTRUCTURE
RELIANCE,ENERGY
ONGC,ENERGY
ITC,FMCG
HINDUNILVR,FMCG
SUNPHARMA,PHARMA
APOLLOHOSP,PHARMA
BHARTIARTL,INFRASTRUCTURE
TATASTEEL,METAL
POWERGRID,ENERGY
ADANIENT,INFRASTRUCTURE
ULTRACEMCO,INFRASTRUCTURE
```

- [ ] **Step 3: Create `sector_index_config.csv` schema**

Use columns:

```text
Sector_Key,Index_Name,Yahoo_Ticker
```

Create one row for each locked key:

```text
AUTO
BANK
FINANCIAL_SERVICES
FMCG
IT
MEDIA
METAL
PHARMA
REALTY
ENERGY
INFRASTRUCTURE
```

Resolve the actual Yahoo ticker for every key before continuing. Known mappings may include:

```text
BANK,^NSEBANK
IT,^CNXIT
FMCG,^CNXFMCG
```

Do not guess silently. For every non-obvious ticker, verify that Yahoo/yfinance metadata or returned identity corresponds to the intended Nifty sector index. If no suitable Yahoo index exists, leave `Yahoo_Ticker` blank for that row and let the validation stage mark it `UNAVAILABLE`.

- [ ] **Step 4: Verify the stock mapping mechanically**

Run:

```bash
python - <<'PY'
import pandas as pd
p = 'research/swing/sector_leadership/stock_sector_map.csv'
df = pd.read_csv(p)
assert len(df) == 20
assert df['Stock'].is_unique
assert set(df['Sector_Key']).issubset({
    'AUTO','BANK','FINANCIAL_SERVICES','FMCG','IT','MEDIA','METAL','PHARMA','REALTY','ENERGY','INFRASTRUCTURE'
})
print('stock_sector_map validation passed')
PY
```

Expected: `stock_sector_map validation passed`.

- [ ] **Step 5: Commit**

```bash
git add research/swing/sector_leadership/requirements.txt \
        research/swing/sector_leadership/stock_sector_map.csv \
        research/swing/sector_leadership/sector_index_config.csv
git commit -m "research: add sector leadership inputs"
```

---

### Task 2: Implement pure return, percentile, rank, and bucket logic with tests first

**Files:**
- Create: `research/swing/sector_leadership/build_sector_leadership.py`
- Create: `research/swing/sector_leadership/tests/test_sector_leadership.py`

**Interfaces:**
- Produces functions:
  - `calculate_returns(df: pd.DataFrame) -> pd.DataFrame`
  - `calculate_daily_rs(df: pd.DataFrame) -> pd.DataFrame`
  - `assign_leadership_bucket(rank: int, sector_count: int) -> str`
  - `rank_and_bucket(df: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: Write failing tests for return horizons**

Add:

```python
import math
import pandas as pd

from research.swing.sector_leadership.build_sector_leadership import (
    assign_leadership_bucket,
    calculate_returns,
)


def test_calculate_returns_uses_exact_session_shifts():
    df = pd.DataFrame({
        "Close": [100.0 + i for i in range(140)]
    })
    result = calculate_returns(df)

    assert pd.isna(result.loc[20, "Ret21"])
    assert math.isclose(result.loc[21, "Ret21"], 121.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[63, "Ret63"], 163.0 / 100.0 - 1.0)
    assert math.isclose(result.loc[126, "Ret126"], 226.0 / 100.0 - 1.0)
```

- [ ] **Step 2: Write failing tests for bucket boundaries**

Add parameterized cases covering N=8, N=10, N=11:

```python
import pytest


@pytest.mark.parametrize(
    "rank,n,expected",
    [
        (1, 8, "LEADING"),
        (3, 8, "LEADING"),
        (4, 8, "ACCEPTABLE"),
        (5, 8, "WEAK"),
        (6, 8, "LAGGING"),
        (8, 8, "LAGGING"),
        (1, 10, "LEADING"),
        (4, 10, "LEADING"),
        (5, 10, "ACCEPTABLE"),
        (6, 10, "WEAK"),
        (7, 10, "LAGGING"),
        (10, 10, "LAGGING"),
        (1, 11, "LEADING"),
        (4, 11, "LEADING"),
        (5, 11, "ACCEPTABLE"),
        (6, 11, "WEAK"),
        (8, 11, "LAGGING"),
        (11, 11, "LAGGING"),
    ],
)
def test_assign_leadership_bucket(rank, n, expected):
    assert assign_leadership_bucket(rank, n) == expected
```

- [ ] **Step 3: Run tests and verify failure**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Expected: import or missing-function failure.

- [ ] **Step 4: Implement `calculate_returns`**

Exact implementation behavior:

```python
def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["Ret21"] = result["Close"] / result["Close"].shift(21) - 1.0
    result["Ret63"] = result["Close"] / result["Close"].shift(63) - 1.0
    result["Ret126"] = result["Close"] / result["Close"].shift(126) - 1.0
    return result
```

- [ ] **Step 5: Implement `assign_leadership_bucket` exactly**

```python
def assign_leadership_bucket(rank: int, sector_count: int) -> str:
    top_third_count = math.ceil(sector_count / 3)
    top_half_count = math.ceil(sector_count / 2)
    bottom_third_count = math.ceil(sector_count / 3)

    if rank <= top_third_count:
        return "LEADING"
    if rank <= top_half_count:
        return "ACCEPTABLE"
    if rank > sector_count - bottom_third_count:
        return "LAGGING"
    return "WEAK"
```

Priority order matters. Do not reorder the conditions.

- [ ] **Step 6: Run tests**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Expected: all current tests PASS.

- [ ] **Step 7: Add tests for same-day percentile ranking and composite score**

Create a tiny deterministic two-date DataFrame with four sectors and prefilled `Ret21`, `Ret63`, `Ret126`; assert that the strongest sector gets the highest percentile on each horizon and that:

```text
Composite_RS = 0.30*RS21 + 0.40*RS63 + 0.30*RS126
```

Use `rank(method="average", pct=True) * 100` exactly.

- [ ] **Step 8: Implement `calculate_daily_rs` and `rank_and_bucket`**

Required behavior:

```python
for col, out in [
    ("Ret21", "RS21_Percentile"),
    ("Ret63", "RS63_Percentile"),
    ("Ret126", "RS126_Percentile"),
]:
    df[out] = df.groupby("Date")[col].rank(method="average", pct=True) * 100.0


df["Composite_RS"] = (
    0.30 * df["RS21_Percentile"]
    + 0.40 * df["RS63_Percentile"]
    + 0.30 * df["RS126_Percentile"]
)
```

For composite rank, use a deterministic descending rank. Preferred:

```python
df["Composite_Rank"] = (
    df.groupby("Date")["Composite_RS"]
      .rank(method="first", ascending=False)
      .astype(int)
)
```

`method="first"` is the deterministic tie-break. Document this in README and validation notes.

`Sector_Count` is the number of complete valid sectors on that date.

- [ ] **Step 9: Run all tests**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add research/swing/sector_leadership/build_sector_leadership.py \
        research/swing/sector_leadership/tests/test_sector_leadership.py
git commit -m "research: add sector leadership scoring logic"
```

---

### Task 3: Implement yfinance download and point-in-time data validation

**Files:**
- Modify: `research/swing/sector_leadership/build_sector_leadership.py`
- Modify: `research/swing/sector_leadership/tests/test_sector_leadership.py`

**Interfaces:**
- Produces:
  - `download_sector_history(sector_key: str, index_name: str, ticker: str) -> tuple[pd.DataFrame | None, dict]`
  - validation row dict with exact output columns from Issue #1.

- [ ] **Step 1: Add a unit test for normalization of yfinance columns**

Test with a synthetic DataFrame that mimics either flat columns or a one-ticker MultiIndex and assert normalized output contains:

```text
Date,Open,High,Low,Close,Adj_Close
```

- [ ] **Step 2: Implement download constants**

```python
START_DATE = "2022-01-01"
END_DATE_EXCLUSIVE = "2026-08-26"
INTERVAL = "1d"
```

- [ ] **Step 3: Implement download call exactly**

Use:

```python
yf.download(
    ticker,
    start=START_DATE,
    end=END_DATE_EXCLUSIVE,
    interval="1d",
    auto_adjust=False,
    progress=False,
    actions=False,
)
```

If the returned DataFrame uses MultiIndex columns for one ticker, flatten them deterministically.

- [ ] **Step 4: Normalize dates and prices**

Requirements:

- convert index to a `Date` column;
- remove timezone if one exists;
- use `YYYY-MM-DD` on CSV export;
- do not forward-fill missing market dates;
- preserve ordinary `Close`;
- map `Adj Close` to `Adj_Close` if present.

- [ ] **Step 5: Generate validation status**

For every config row, write:

```text
Sector_Key
Index_Name
Yahoo_Ticker
Download_Status
Raw_Row_Count
Earliest_Date
Latest_Date
Missing_Close_Count
Duplicate_Date_Count
First_Valid_Ret126_Date
Notes
```

Rules:

- blank ticker -> `UNAVAILABLE`;
- empty download -> `UNAVAILABLE`;
- duplicated dates, all/missing Close, clearly wrong identity, or insufficient history -> `INVALID`;
- otherwise -> `OK`.

A sector marked `UNAVAILABLE` or `INVALID` must not appear in the ranking dataset.

- [ ] **Step 6: Add a runtime identity check**

Use available yfinance metadata such as `Ticker(ticker).info` or `fast_info` only as a validation aid. Network metadata failures must not crash an otherwise valid price download. Record metadata failures in `Notes` and verify the ticker identity manually from Yahoo if necessary before marking `OK`.

Do not substitute another ticker without updating `sector_index_config.csv` explicitly.

- [ ] **Step 7: Run tests**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add research/swing/sector_leadership/build_sector_leadership.py \
        research/swing/sector_leadership/tests/test_sector_leadership.py \
        research/swing/sector_leadership/sector_index_config.csv
git commit -m "research: add sector index download validation"
```

---

### Task 4: Build the complete daily leadership dataset and invariant validation

**Files:**
- Modify: `research/swing/sector_leadership/build_sector_leadership.py`
- Modify: `research/swing/sector_leadership/tests/test_sector_leadership.py`
- Generate: `research/swing/sector_leadership/output/sector_leadership_daily.csv`
- Generate: `research/swing/sector_leadership/output/sector_data_validation.csv`

**Interfaces:**
- Produces final ranked daily DataFrame with exact schema from Issue #1.

- [ ] **Step 1: Implement orchestration for all valid sectors**

For each config row:

1. download history;
2. validate it;
3. calculate Ret21/Ret63/Ret126 independently within that sector;
4. append valid sector rows to one long-form DataFrame;
5. drop rows missing any of Ret21/Ret63/Ret126 before percentile calculation;
6. calculate same-day cross-sectional RS percentiles;
7. calculate composite RS;
8. calculate rank, sector count, and bucket.

- [ ] **Step 2: Export the primary CSV in exact column order**

```text
Date
Sector_Key
Index_Name
Yahoo_Ticker
Close
Ret21
Ret63
Ret126
RS21_Percentile
RS63_Percentile
RS126_Percentile
Composite_RS
Composite_Rank
Sector_Count
Leadership_Bucket
```

Sort by:

```text
Date ascending, Composite_Rank ascending
```

- [ ] **Step 3: Implement invariant validation function**

Create:

```python
def validate_primary_output(df: pd.DataFrame) -> None:
    ...
```

It must raise `ValueError` or `AssertionError` with a precise message if any invariant fails.

Check all 14 invariant groups from Issue #1, including:

```python
assert not df.duplicated(["Date", "Sector_Key"]).any()
assert df["Close"].notna().all()
assert df[["Ret21", "Ret63", "Ret126"]].notna().all().all()
assert df[["RS21_Percentile", "RS63_Percentile", "RS126_Percentile", "Composite_RS"]].notna().all().all()
assert set(df["Leadership_Bucket"]) <= {"LEADING", "ACCEPTABLE", "WEAK", "LAGGING"}
```

Also iterate by date and verify:

- minimum rank is 1;
- maximum rank does not exceed sector count;
- rank values are exactly `1..N` after deterministic tie-breaking;
- `Sector_Count == len(group)` for every row in the date group;
- each bucket is consistent with `assign_leadership_bucket`.

- [ ] **Step 4: Add sampled return-equation validation**

For at least the first, middle, and last eligible 126-return row of each valid sector, compare exported Ret21/63/126 against the raw sector Close series using exact positional shifts within floating tolerance.

Use:

```python
math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
```

- [ ] **Step 5: Add tests that intentionally break invariants**

At minimum prove validation rejects:

- duplicate `(Date, Sector_Key)`;
- invalid bucket string;
- rank outside `1..N`;
- missing return value.

- [ ] **Step 6: Run tests**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Expected: PASS.

- [ ] **Step 7: Run the real pipeline**

```bash
python research/swing/sector_leadership/build_sector_leadership.py
```

Expected: exits with code 0 and creates `sector_leadership_daily.csv` and `sector_data_validation.csv`.

- [ ] **Step 8: Commit**

```bash
git add research/swing/sector_leadership/build_sector_leadership.py \
        research/swing/sector_leadership/tests/test_sector_leadership.py \
        research/swing/sector_leadership/output/sector_leadership_daily.csv \
        research/swing/sector_leadership/output/sector_data_validation.csv
git commit -m "research: generate sector leadership dataset"
```

---

### Task 5: Generate summary artifact and documentation

**Files:**
- Modify: `research/swing/sector_leadership/build_sector_leadership.py`
- Create: `research/swing/sector_leadership/README.md`
- Generate: `research/swing/sector_leadership/output/sector_leadership_summary.csv`

**Interfaces:**
- Produces reproducibility documentation and non-performance summary.

- [ ] **Step 1: Implement summary generation**

Group the final ranked dataset by sector and create exact columns:

```text
Sector_Key
Index_Name
Yahoo_Ticker
Valid_Ranked_Days
Leading_Days
Acceptable_Days
Weak_Days
Lagging_Days
Earliest_Ranked_Date
Latest_Ranked_Date
```

The four bucket-day counts must sum exactly to `Valid_Ranked_Days`.

- [ ] **Step 2: Add summary validation**

Programmatically assert for every row:

```python
Leading_Days + Acceptable_Days + Weak_Days + Lagging_Days == Valid_Ranked_Days
```

- [ ] **Step 3: Write README**

Include:

1. purpose;
2. exact sector universe;
3. exact stock-sector proxy mapping;
4. `Ret21`, `Ret63`, `Ret126` formulas;
5. percentile ranking method;
6. 30/40/30 composite formula;
7. exact leadership bucket rules;
8. deterministic tie handling (`method="first"` for composite rank);
9. no-lookahead statement;
10. proxy limitations for APOLLOHOSP / BHARTIARTL / LT / ADANIENT / ULTRACEMCO;
11. any unavailable sector index;
12. exact setup/install command;
13. exact run command;
14. exact test command;
15. generated-file descriptions.

Include verbatim:

> This dataset must not be interpreted as evidence that sector leadership improves trading performance. It is an independent point-in-time feature dataset intended for a separate validation step.

- [ ] **Step 4: Run all tests and pipeline again from a clean output state**

```bash
rm -f research/swing/sector_leadership/output/*.csv
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
python research/swing/sector_leadership/build_sector_leadership.py
```

On Windows PowerShell, use the equivalent file-removal command instead of `rm`.

Expected:

- tests PASS;
- pipeline exits 0;
- all three output CSV files regenerate.

- [ ] **Step 5: Check generated artifacts mechanically**

Run:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

base = Path('research/swing/sector_leadership/output')
for name in [
    'sector_leadership_daily.csv',
    'sector_leadership_summary.csv',
    'sector_data_validation.csv',
]:
    path = base / name
    assert path.exists(), f'missing {path}'
    df = pd.read_csv(path)
    assert not df.empty, f'empty {path}'
    print(name, len(df))
PY
```

Expected: all three files exist and are non-empty.

- [ ] **Step 6: Commit**

```bash
git add research/swing/sector_leadership/README.md \
        research/swing/sector_leadership/build_sector_leadership.py \
        research/swing/sector_leadership/output/sector_leadership_summary.csv \
        research/swing/sector_leadership/output/sector_leadership_daily.csv \
        research/swing/sector_leadership/output/sector_data_validation.csv
git commit -m "docs: document sector leadership research dataset"
```

---

### Task 6: Final reproducibility verification and Issue #1 handoff

**Files:**
- No new code expected.
- Comment on GitHub Issue #1 after verification.

**Interfaces:**
- Produces a complete execution handoff for the analysis session.

- [ ] **Step 1: Run final tests**

```bash
python -m pytest research/swing/sector_leadership/tests/test_sector_leadership.py -v
```

Record exact pass count.

- [ ] **Step 2: Run final generation**

```bash
python research/swing/sector_leadership/build_sector_leadership.py
```

Expected: exit code 0.

- [ ] **Step 3: Capture runtime versions**

```bash
python --version
python - <<'PY'
import yfinance, pandas, numpy
print('yfinance', yfinance.__version__)
print('pandas', pandas.__version__)
print('numpy', numpy.__version__)
PY
```

- [ ] **Step 4: Capture final git SHA**

```bash
git rev-parse HEAD
```

- [ ] **Step 5: Comment on Issue #1 with the exact handoff fields**

The comment must include:

```text
Commit SHA:
Run command:
Test command:
Test result/pass count:
Python version:
yfinance version:
Resolved sector index names/tickers:
Unavailable/invalid sectors:
Raw date range:
Ranked date range:
Sector count per ranked date (min/max):
Primary output row count:
Validation result:
sector_leadership_daily.csv path:
sector_leadership_summary.csv path:
sector_data_validation.csv path:
Data-provider caveats:
```

Do not include trading-performance conclusions.

- [ ] **Step 6: Stop**

Do not join these outputs to T1 trades and do not modify any ranking formula. The next step belongs to the independent analysis session.

---

## Plan Self-Review

- Spec coverage: all Issue #1 requirements are mapped to Tasks 1–6.
- No performance data is consumed anywhere in the implementation.
- Static mapping, fixed lookbacks, fixed weights, and fixed bucket rules are explicitly locked.
- Point-in-time calculations use only same-day/past data through `shift()` and same-day cross-sectional ranks.
- Exact output schemas are specified.
- Validation failures are explicit and testable.
- Execution is **inline only**, suitable for Luna; no subagent workflow is required or permitted by this plan.
