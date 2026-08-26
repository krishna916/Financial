# T1 Sector Leadership Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task using **inline execution only**. Do not use subagent-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducibly test whether the already-defined point-in-time sector-leadership framework improves selection quality for the fixed 218-trade T1 swing-breakout sample.

**Architecture:** Decode the fixed T1 input payload already committed to the repository, validate it against known aggregate checks, load the merged sector-leadership output from Issue #1 / PR #2, perform a backward/as-of full-universe-only join, calculate predeclared leadership comparisons, sector-identity controls, time/outlier robustness, and export auditable CSV/report artifacts. Keep data transformation and metric functions pure/testable. Do not tune the strategy from the observed outcomes.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, standard-library `base64`, `gzip`, `hashlib`.

**Spec:** GitHub Issue #3 — `https://github.com/krishna916/Financial/issues/3`

## Global Constraints

- This is **validation, not optimization**.
- T1 trade sample is locked at **218 completed trades / 20 symbols**.
- Do not re-run Streak or regenerate T1 from market prices.
- Do not modify T1 entry/exit rules.
- Do not modify sector RS windows, weights, percentile rules, ranking logic, or bucket boundaries.
- Sector join must use **full-universe observations only** (`Sector_Count == 11` or equivalent merged flag).
- Point-in-time join is backward/as-of only: `Sector_Matched_Date <= Entry_Date`.
- Never forward-match to a future sector date.
- Do not drop bad trades, event losses, sectors, or years after seeing results.
- Do not add RSI, ADX, volume, MA-slope, volatility, or other new filters.
- Do not optimize a rank cutoff from the rank-level diagnostic.
- Implementation must be mechanical enough for Luna to execute without domain judgment.
- Execution mode is inline only.

---

## Repository Paths

All research code/data for this task lives under:

```text
Swing Trading/research/swing/t1_sector_validation/
```

Existing dependencies:

```text
Swing Trading/research/swing/sector_leadership/output/sector_leadership_daily.csv
Swing Trading/research/swing/sector_leadership/stock_sector_map.csv
```

Fixed compressed T1 payload already committed:

```text
Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv.gz.b64
```

Expected SHA-256 after decoding to the normalized CSV:

```text
6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4
```

Expected normalized T1 aggregates:

```text
Completed trades: 218
Unique symbols: 20
Total PnL: -4631.32
Mean Return_Pct: approximately -0.0548680341
Winners: 76
```

These are validation checks only, not strategy conclusions.

---

## Target File Map

Create/produce:

```text
Swing Trading/research/swing/t1_sector_validation/
├── analyze_t1_sector_leadership.py
├── README.md
├── input/
│   ├── t1_trades.csv.gz.b64        # already committed; source payload
│   └── t1_trades.csv               # deterministic decoded normalized input
├── tests/
│   └── test_t1_sector_validation.py
└── output/
    ├── t1_sector_joined_trades.csv
    ├── t1_sector_bucket_summary.csv
    ├── t1_sector_binary_tests.csv
    ├── t1_sector_rank_summary.csv
    ├── t1_sector_within_sector_summary.csv
    ├── t1_sector_year_summary.csv
    ├── t1_sector_outlier_robustness.csv
    ├── t1_market_sector_matrix.csv        # only if valid market-regime dependency exists
    ├── validation_report.csv
    └── research_report.md
```

Do not create notebooks or charts for this task.

---

### Task 1: Decode and lock the fixed 218-trade T1 input

**Files:**
- Read: `Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv.gz.b64`
- Create: `Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv`

- [ ] **Step 1: Decode mechanically**

From repository root, use Python rather than OS-specific shell utilities:

```bash
python - <<'PY'
from pathlib import Path
import base64, gzip, hashlib

root = Path('Swing Trading/research/swing/t1_sector_validation/input')
src = root / 't1_trades.csv.gz.b64'
dst = root / 't1_trades.csv'

encoded = src.read_text(encoding='utf-8').strip()
raw = gzip.decompress(base64.b64decode(encoded))
dst.write_bytes(raw)

sha = hashlib.sha256(raw).hexdigest()
print('decoded_sha256=', sha)
assert sha == '6b4c2931f23f0e043816d973eba16b5bf3ca57411642d4528de060ea2febb1e4'
PY
```

Expected: assertion passes and the exact expected SHA is printed.

- [ ] **Step 2: Validate schema and locked aggregates**

Required columns:

```text
Symbol
Entry_Date
Exit_Date
Entry_Price
Exit_Price
Qty
Return_Pct
PnL
Holding_Days
Source_Log
```

Validate:

```text
rows == 218
unique symbols == 20
winners (Return_Pct > 0) == 76
total PnL == -4631.32 within 0.01 tolerance
mean Return_Pct == -0.0548680341 within 1e-8 tolerance
```

Also validate:
- dates parse successfully;
- `Entry_Date <= Exit_Date` for all rows;
- `Qty > 0`;
- no null required fields;
- symbols exactly match the locked 20-stock mapping.

Fail loudly on any mismatch.

- [ ] **Step 3: Commit decoded fixed input**

```bash
git add "Swing Trading/research/swing/t1_sector_validation/input/t1_trades.csv"
git commit -m "research: decode fixed T1 trade sample"
```

---

### Task 2: Scaffold metric and point-in-time join functions with tests first

**Files:**
- Create: `Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py`
- Create: `Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py`

Implement pure functions at minimum:

```python
load_and_validate_trades(...)
load_and_validate_sector_data(...)
prepare_full_universe_sector_data(...)
asof_join_sector_leadership(...)
calculate_trade_metrics(...)
calculate_profit_factor(...)
classify_binary_groups(...)
```

- [ ] **Step 1: Write failing test for full-universe filtering**

Construct sector rows with `Sector_Count` values 11 and 2. Assert that only 11 survives.

- [ ] **Step 2: Write failing no-lookahead as-of test**

Synthetic example:

```text
Sector full-universe dates: 2026-01-02, 2026-01-05
Trade entry:               2026-01-04
```

Expected matched date: `2026-01-02`, never `2026-01-05`.

- [ ] **Step 3: Write failing test for calendar lag**

`Sector_Date_Lag_Days = Entry_Date - Sector_Matched_Date` in calendar days and must be `>= 0`.

- [ ] **Step 4: Write failing metric tests**

Use a tiny fixed sample with known winners/losers to verify:
- trade count;
- winners/losers;
- win rate;
- mean/median return;
- average winner;
- average loser;
- payoff ratio;
- return-based PF = sum positive returns / abs(sum negative returns);
- rupee PF = sum positive PnL / abs(sum negative PnL);
- total PnL;
- median holding days.

Define PF behavior mechanically:
- no losses and positive gains -> `inf`;
- no gains and losses -> `0`;
- no gains and no losses -> `NaN`.

- [ ] **Step 5: Implement minimum code to pass tests**

Run:

```bash
python -m pytest "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py" -v
```

- [ ] **Step 6: Commit**

```bash
git add "Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py" \
        "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py"
git commit -m "research: add T1 sector validation core"
```

---

### Task 3: Load the merged sector dataset and enforce the research-safe universe

- [ ] **Step 1: Load existing merged sector output**

Use:

```text
Swing Trading/research/swing/sector_leadership/output/sector_leadership_daily.csv
```

Required columns at minimum:

```text
Date
Sector_Key
Composite_RS
Composite_Rank
Sector_Count
Leadership_Bucket
```

If merged PR #2 added an explicit full-universe flag, use it in addition to verifying `Sector_Count == 11`.

- [ ] **Step 2: Validate allowed leadership values**

Exactly:

```text
LEADING
ACCEPTABLE
WEAK
LAGGING
```

- [ ] **Step 3: Filter before joining**

The dataframe used for any trade match must contain only full-universe sector dates.

Do **not** use a same-day 2-sector/3-sector observation even if it exists. A trade on such a date must fall back to the latest earlier full-11 observation for that specific sector.

- [ ] **Step 4: Validate stock-sector mapping**

Prefer the existing merged mapping:

```text
Swing Trading/research/swing/sector_leadership/stock_sector_map.csv
```

Assert exactly 20 stocks, unique stock keys, and all T1 symbols mapped exactly once.

---

### Task 4: Perform the audited point-in-time trade join

- [ ] **Step 1: Join sector key to all 218 trades**

No missing mappings allowed.

- [ ] **Step 2: Backward/as-of match per sector**

For each trade, select the latest full-universe row satisfying:

```text
Sector_Key matches
Sector_Date <= Entry_Date
```

- [ ] **Step 3: Add audit columns**

At minimum:

```text
Sector_Key
Sector_Matched_Date
Sector_Date_Lag_Days
Composite_RS
Composite_Rank
Sector_Count
Leadership_Bucket
```

- [ ] **Step 4: Assert join integrity**

All must hold:

```text
joined rows == 218
unmatched rows == 0
all Sector_Count == 11
all Sector_Matched_Date <= Entry_Date
all Sector_Date_Lag_Days >= 0
```

Print and export median/max lag.

If max lag exceeds 7 calendar days, do not fail automatically; flag the affected trades in validation output for review.

- [ ] **Step 5: Export**

```text
output/t1_sector_joined_trades.csv
```

Sort deterministically by `Entry_Date`, `Symbol`, `Exit_Date`.

---

### Task 5: Produce the four-bucket and binary leadership summaries

- [ ] **Step 1: Four-bucket summary**

Exact order:

```text
LEADING
ACCEPTABLE
WEAK
LAGGING
```

Export:

```text
output/t1_sector_bucket_summary.csv
```

Include metrics from Issue #3.

- [ ] **Step 2: Predeclared binary tests**

Create only these locked comparisons:

```text
LEADING vs NON_LEADING
TOP_HALF (LEADING + ACCEPTABLE) vs LOWER_HALF (WEAK + LAGGING)
LAGGING vs NON_LAGGING
```

Export:

```text
output/t1_sector_binary_tests.csv
```

Do not add a better-looking cutoff after seeing results.

- [ ] **Step 3: Reconciliation checks**

For each partition, group counts must sum to 218 and PnL must reconcile to the fixed input total within 0.01.

---

### Task 6: Produce rank-level diagnostics without optimizing a cutoff

Group by integer `Composite_Rank` exactly 1 through 11.

Export:

```text
output/t1_sector_rank_summary.csv
```

Include metrics plus mean/median `Composite_RS` for audit context.

If a rank has zero trades, include the row with trade count 0 if convenient, or document absence consistently. Do not merge ranks to manufacture sample size.

---

### Task 7: Control for sector identity

This task is mandatory because the fixed 20-stock sample is not sector-balanced.

- [ ] **Step 1: Detailed within-sector bucket table**

Group by:

```text
Sector_Key + Leadership_Bucket
```

Include:
- trades;
- win rate;
- mean return;
- median return;
- return PF;
- total PnL.

- [ ] **Step 2: Simplified within-sector comparison**

Define exactly:

```text
TOP_HALF = LEADING + ACCEPTABLE
LOWER_HALF = WEAK + LAGGING
```

For every sector, output both groups where observed.

Do not suppress poor-looking sectors. For tiny cells, include them but add `Small_Sample = true` when `Trades < 5`.

Export both forms in:

```text
output/t1_sector_within_sector_summary.csv
```

Use a `Comparison_Type` column to distinguish detailed vs top/lower-half rows.

---

### Task 8: Time stability and outlier robustness

- [ ] **Step 1: Entry-year summaries**

Years:

```text
2023
2024
2025
2026
```

For each year produce the three locked binary comparisons from Task 5.

Export:

```text
output/t1_sector_year_summary.csv
```

Do not reinterpret calendar years as market regimes.

- [ ] **Step 2: Outlier robustness**

For each principal binary comparison calculate variants:

```text
ALL_TRADES
EXCLUDE_TOP_1_POSITIVE_PNL
EXCLUDE_TOP_3_POSITIVE_PNL
EXCLUDE_TOP_5_POSITIVE_PNL
```

Remove top positive-PnL trades globally from the full sample for each robustness scenario, then recompute both groups. Do not remove any losers.

Export:

```text
output/t1_sector_outlier_robustness.csv
```

Include the excluded symbols/entry dates in a semicolon-separated audit field.

---

### Task 9: Optional market-regime interaction only if the dependency exists

Search the repository for the previously generated NIFTY 500 daily regime dataset.

Required regime values:

```text
RISK_ON
MIXED
RISK_OFF
```

If no valid regime input exists in the repository:

- do not download/recreate it in this issue;
- do not substitute Nifty 50;
- do not block the sector experiment;
- mark market-sector interaction as `SKIPPED_MISSING_DEPENDENCY` in the validation report;
- do not create a fake matrix.

If it does exist:

- use backward/as-of matching only;
- never use future regime data;
- export the complete `Market_Regime x Leadership_Bucket` matrix;
- also compare exactly:

```text
(Market in RISK_ON/MIXED AND Sector in TOP_HALF)
vs
all other valid trades
```

Export:

```text
output/t1_market_sector_matrix.csv
```

---

### Task 10: Validation report and research report

**Files:**
- Create: `output/validation_report.csv`
- Create: `output/research_report.md`
- Create: `README.md`

- [ ] **Step 1: Write machine-readable validation report**

Include at minimum:

```text
Input_Trade_Count,218
Unique_Symbols,20
Winners,76
Input_Total_PnL,-4631.32
Unmatched_Sector_Trades,0
Future_Sector_Matches,0
NonFullUniverse_Sector_Matches,0
Median_Sector_Lag_Days,<value>
Max_Sector_Lag_Days,<value>
Bucket_Count_Reconciles,true/false
PnL_Reconciles,true/false
Market_Regime_Interaction,<COMPLETED or SKIPPED_MISSING_DEPENDENCY>
```

- [ ] **Step 2: Write concise `research_report.md`**

The report must present facts, not decide the strategy.

Use sections:

```text
# T1 Sector Leadership Validation
## Input Integrity
## Four-Bucket Results
## Locked Binary Comparisons
## Rank Diagnostics
## Within-Sector Controls
## Time Stability
## Outlier Robustness
## Market-Regime Interaction
## Limitations
```

Explicitly mention:
- fixed 20-stock sample;
- sector imbalance;
- small cells;
- outlier dependence where observed;
- no transaction-cost adjustment unless already present in T1 input;
- this report does not authorize changing V1 rules.

Do not write recommendations such as “use rank <= X” or “drop sector Y.”

- [ ] **Step 3: Write README**

Document exact run/test commands from repository root:

```bash
python -m pytest "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py" -v
python "Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py"
```

Document the fixed input payload/decode provenance and full-universe as-of rule.

---

### Task 11: Final verification before completion

Use `superpowers:verification-before-completion` before claiming success.

- [ ] Run tests:

```bash
python -m pytest "Swing Trading/research/swing/t1_sector_validation/tests/test_t1_sector_validation.py" -v
```

Expected: all pass.

- [ ] Run full analysis:

```bash
python "Swing Trading/research/swing/t1_sector_validation/analyze_t1_sector_leadership.py"
```

Expected: exit code 0.

- [ ] Independently verify exported joined file:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

p = Path('Swing Trading/research/swing/t1_sector_validation/output/t1_sector_joined_trades.csv')
df = pd.read_csv(p, parse_dates=['Entry_Date', 'Sector_Matched_Date'])
assert len(df) == 218
assert df['Symbol'].nunique() == 20
assert df['Sector_Count'].eq(11).all()
assert (df['Sector_Matched_Date'] <= df['Entry_Date']).all()
assert (df['Sector_Date_Lag_Days'] >= 0).all()
assert abs(df['PnL'].sum() - (-4631.32)) < 0.01
print('independent joined-trade validation passed')
PY
```

Expected: `independent joined-trade validation passed`.

- [ ] Confirm all required non-optional outputs exist and are non-empty.

- [ ] Review `git diff` and ensure no sector methodology or existing Issue #1 output was modified unintentionally.

- [ ] Commit implementation and generated outputs in logical commits.

- [ ] Open a PR referencing Issue #3 and include in the PR body:
  - exact test command/result;
  - analysis command/result;
  - input SHA validation result;
  - matched/unmatched counts;
  - median/max sector lag;
  - list of generated artifacts;
  - whether market-regime interaction was completed or skipped.

## Completion Rule

The task is complete only when Luna has produced a reproducible, audited 218-trade sector-leadership result set. Luna must **not** make the Portfolio Advisor's final decision about whether sector leadership becomes a hard gate, grading factor, or is rejected. That interpretation happens after the PR outputs are reviewed.