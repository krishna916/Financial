# E1 Positive Earnings Surprise Drift Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, point-in-time E1 source snapshot from official NSE/BSE filings plus frozen market prices, calculate the frozen seasonal SUE signal, construct identical positive/neutral/negative 40-session cohorts, and produce a deterministic offline PASS / FAIL / INSUFFICIENT_EVIDENCE / INVALID_RESEARCH_RUN verdict.

**Architecture:** Add one self-contained `e1_positive_earnings_surprise_drift` research module with two hard-separated stages. Stage A performs all networked source acquisition and freezes immutable official filing/EPS/corporate-action and market-price snapshots with SHA256 provenance; Stage B performs all event normalization, SUE calculation, trade construction, analysis and formal validation strictly offline against those frozen inputs. The implementation must not reuse M1/V3 strategy logic, must not inspect returns while resolving source-data ambiguity, and must not add any post-result rescue filter or alternate threshold.

**Tech Stack:** Python 3, pandas, numpy, requests, lxml/standard-library XML parsing, yfinance, pytest.

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

**Issue:** `https://github.com/krishna916/Financial/issues/33`

## Global Constraints

- Primary event window: `2023-08-01` through `2026-06-30` inclusive, based on `Event_Public_Date`.
- Source-data cutoff: `2026-08-25`; later-than-`2026-06-30` events are non-primary forward observations only.
- EPS history acquisition begins no later than `2020-01-01`; pre-`2023-08-01` rows are history-only.
- Temporal halves are frozen exactly as `2023-08-01..2025-01-14` and `2025-01-15..2026-06-30`.
- Universe is point-in-time Nifty 500 on `Event_Public_Date`, using read-only `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`.
- Official earnings/event sources only: NSE financial-results / Integrated Filing and BSE corporate-result records. No Screener, Trendlyne, broker financial database, analyst consensus, manually curated earnings calendar, or hand-entered EPS.
- Preferred EPS field: Basic EPS from continuing operations, genuine quarterly non-cumulative basis.
- Reporting-basis priority: complete comparable consolidated chain first; otherwise complete comparable standalone chain. Never mix basis inside one SUE chain.
- Timely filing: Q1/Q2/Q3 within 45 calendar days of fiscal-period end; final fiscal quarter within 60 calendar days.
- Original/first-public filing only for SUE. Revisions are provenance only and may never rewrite an earlier event.
- Historical EPS must be point-in-time and corporate-action comparable using only split/bonus/consolidation actions effective on/before the current event.
- SUE formula: `D[t] = EPS[t] - EPS[t-4]`; historical mean/sample SD use exactly `D[t-1]..D[t-8]`; `ddof=1`.
- SUE cohorts: `>= +1.0 POSITIVE_SURPRISE`; `[+0.5,+1.0) POSITIVE_BUFFER`; `(-0.5,+0.5) NEUTRAL_CONTROL`; `(-1.0,-0.5] NEGATIVE_BUFFER`; `<= -1.0 NEGATIVE_CONTROL`.
- Zero/negative EPS is valid. `Historical_SD <= 0` or non-finite means `ZERO_HISTORICAL_SUE_SD`; never add epsilon/winsorization.
- Entry: immediate next canonical session Open. No gap filter, momentum filter, RS filter, SMA filter, regime filter, volume confirmation or price-confirmation rule.
- Primary hold: 40 complete trading sessions; normal exit at the following session Open.
- Earlier exit: next distinct quarterly result for the same symbol, at that result's next eligible session Open, whether or not that new event itself is timely or E1-eligible.
- No price stop, ATR stop, target, trailing stop, breakeven move or alternate 20/60-session primary exit.
- Friction: base `0.004`, stress `0.006`, severe diagnostic `0.008` round-trip of entry value.
- Benchmark: Nifty 500 open-to-open over exactly the stock trade's entry/exit sessions.
- Primary cohort minimums: positive >=300, neutral >=300, negative >=300 completed observations; each temporal half >=100 completed positive observations.
- Mandatory base positive gates: mean net return >=1.00%, median net return >0, return PF >=1.20, mean net excess return >0, excess-return PF >1.00.
- Mandatory stress gates: mean net return >0, return PF >1.00, mean net excess return >0.
- Mandatory directional discrimination: positive mean > neutral mean > negative mean; same ordering for excess means; positive PF > neutral PF and negative PF.
- Mandatory robustness: both temporal halves positive/PF>1/excess>0; every leave-one-year-out sample positive/PF>1/excess>0; top-five gross winners removed positive/PF>1/excess>0; every leave-one-symbol-out sample positive/PF>1/excess>0.
- Technical machine-readable EPS coverage uses the exact objective `Technical_EPS_Candidate` denominator from the spec and must be >=95%; lower coverage is `INVALID_RESEARCH_RUN`.
- Formal status precedence: systemic integrity failure or technical coverage failure -> `INVALID_RESEARCH_RUN`; otherwise insufficient cohort/temporal sample -> `INSUFFICIENT_EVIDENCE`; otherwise all mandatory gates pass -> `PASS`; else `FAIL`.
- Diagnostics may never feed back into qualification or formal gates.
- Stage B formal validation must make zero network calls and must reject missing/hash-mismatched frozen inputs.
- Do not modify V3, R1 or M1 code/output; do not build a generic financial-data warehouse, notebook/dashboard, broker integration, live trader, NLP earnings-call system, analyst-consensus model, PDF OCR rescue or unrelated refactor.

## Locked File Structure

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/
├── constants.py
├── source_clients.py
├── xbrl_eps.py
├── build_e1_source_snapshot.py
├── load_e1_inputs.py
├── build_e1_events.py
├── compute_e1_sue.py
├── build_e1_trades.py
├── analyze_e1_results.py
├── run_e1_validation.py
├── README.md
├── requirements.txt
├── tests/
│   ├── fixtures/
│   │   ├── nse_legacy_results.json
│   │   ├── nse_integrated_results.json
│   │   ├── nse_xbrl_basic_eps.xml
│   │   ├── bse_results.html
│   │   └── corporate_actions.csv
│   ├── test_source_clients.py
│   ├── test_xbrl_eps.py
│   ├── test_source_snapshot.py
│   ├── test_events.py
│   ├── test_sue.py
│   ├── test_trades.py
│   ├── test_analysis.py
│   └── test_end_to_end.py
├── input/
│   ├── e1_exchange_filings_snapshot.csv
│   ├── e1_eps_snapshot.csv
│   ├── e1_corporate_actions_snapshot.csv
│   ├── e1_stock_prices_snapshot.csv
│   ├── e1_nifty500_prices_snapshot.csv
│   ├── e1_source_manifest.csv
│   └── e1_source_build_audit.csv
└── output/
    ├── e1_data_validation.csv
    ├── e1_source_coverage.csv
    ├── e1_event_master.csv
    ├── e1_event_exclusions.csv
    ├── e1_eps_history.csv
    ├── e1_sue_events.csv
    ├── e1_cohort_classification.csv
    ├── e1_positive_trades.csv
    ├── e1_neutral_control.csv
    ├── e1_negative_control.csv
    ├── e1_validation_summary.csv
    ├── e1_cohort_comparison.csv
    ├── e1_benchmark_comparison.csv
    ├── e1_temporal_summary.csv
    ├── e1_year_summary.csv
    ├── e1_leave_one_year_out.csv
    ├── e1_top_five_robustness.csv
    ├── e1_leave_one_symbol_out.csv
    ├── e1_downside_diagnostic.csv
    ├── e1_diagnostic_summary.csv
    ├── e1_overlap_capacity_diagnostic.csv
    ├── e1_integrity_audit.csv
    ├── e1_validation_gates.csv
    └── research_report.md
```

The two price snapshot files are E1-specific frozen measurement inputs. Yahoo/yfinance is allowed only for price measurement, not earnings/event identification, and those downloads must be frozen before Stage B begins. Use adjusted stock OHLCV with `auto_adjust=True`; use Yahoo Nifty 500 `^CRSLDX` for the benchmark. The validator never calls Yahoo.

---

### Task 1: Lock constants, schemas and canonical PIT/session helpers

**Files:**
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/constants.py`
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/load_e1_inputs.py`
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py`
- Read only: `Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`

**Interfaces:**
- `PRIMARY_START: pd.Timestamp`
- `PRIMARY_END: pd.Timestamp`
- `SOURCE_CUTOFF: pd.Timestamp`
- `FIRST_HALF_END: pd.Timestamp`
- `SECOND_HALF_START: pd.Timestamp`
- `BASE_FRICTION`, `STRESS_FRICTION`, `SEVERE_FRICTION`
- `load_membership(path: Path) -> pd.DataFrame`
- `active_members_on(membership: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame`
- `sha256_file(path: Path) -> str`
- `verify_manifest(manifest: pd.DataFrame, root: Path) -> pd.DataFrame`

- [ ] **Step 1: Write frozen-date and PIT-boundary tests**

```python
def test_frozen_windows_are_exact():
    assert PRIMARY_START == pd.Timestamp("2023-08-01")
    assert PRIMARY_END == pd.Timestamp("2026-06-30")
    assert SOURCE_CUTOFF == pd.Timestamp("2026-08-25")
    assert FIRST_HALF_END == pd.Timestamp("2025-01-14")
    assert SECOND_HALF_START == pd.Timestamp("2025-01-15")


def test_active_members_on_uses_inclusive_membership_boundaries():
    membership = pd.DataFrame({
        "Symbol": ["AAA"],
        "Member_From": [pd.Timestamp("2024-01-02")],
        "Member_To": [pd.Timestamp("2024-01-05")],
    })
    assert active_members_on(membership, pd.Timestamp("2024-01-02"))["Symbol"].tolist() == ["AAA"]
    assert active_members_on(membership, pd.Timestamp("2024-01-05"))["Symbol"].tolist() == ["AAA"]
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py::test_frozen_windows_are_exact"
```

Expected: FAIL before constants/helpers exist.

- [ ] **Step 3: Implement constants and membership loader**

Use literal constants from Global Constraints. Membership loader must require `Symbol`, `Member_From`, `Member_To`, `Yahoo_Ticker`, `Downloadable`; normalize dates to timezone-naive local dates; reject blank symbols, invalid intervals and overlapping intervals per symbol.

- [ ] **Step 4: Write manifest-hash tests**

```python
def test_verify_manifest_rejects_hash_mismatch(tmp_path):
    source = tmp_path / "a.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    manifest = pd.DataFrame([{
        "Artifact": "a.csv",
        "SHA256": "0" * 64,
        "Row_Count": 1,
    }])
    audit = verify_manifest(manifest, tmp_path)
    assert "HASH_MISMATCH" in audit["Violation"].tolist()
```

- [ ] **Step 5: Implement SHA256 and manifest verifier**

`verify_manifest()` must produce explicit audit rows for missing file, unreadable file, hash mismatch and CSV row-count mismatch. It must not rewrite the manifest.

- [ ] **Step 6: Verify and commit Task 1**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/constants.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/load_e1_inputs.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py"
git commit -m "research: lock E1 constants and frozen-input integrity"
```

---

### Task 2: Implement official NSE/BSE source adapters and machine-readable EPS parsing

**Files:**
- Create: `source_clients.py`
- Create: `xbrl_eps.py`
- Create: `tests/test_source_clients.py`
- Create: `tests/test_xbrl_eps.py`
- Create deterministic fixtures under `tests/fixtures/` from small sanitized official-source samples.

**Interfaces:**
- `NseResultsClient.list_legacy(symbol: str) -> list[dict[str, object]]`
- `NseResultsClient.list_integrated(symbol: str) -> list[dict[str, object]]`
- `BseResultsClient.list_results(symbol: str) -> list[dict[str, object]]`
- `normalize_nse_record(record: dict[str, object], feed: str) -> dict[str, object]`
- `normalize_bse_record(record: dict[str, object]) -> dict[str, object]`
- `extract_basic_eps_continuing(xbrl_bytes: bytes, period_end: pd.Timestamp, basis: str) -> float | None`

**Network endpoints/source families:**
- NSE legacy catalog: `https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol={SYMBOL}`.
- NSE integrated catalog: `https://www.nseindia.com/api/integrated-filing-results` with equities / symbol / filing type `Integrated Filing- Financials`; paginate until exhausted.
- NSE XBRL/iXBRL URLs are taken only from the catalog record returned by NSE.
- BSE: use official `bseindia.com` corporate result listing/detail pages or official BSE JSON endpoints discovered by the page; retain the exact BSE URL/record ID in normalized provenance.

- [ ] **Step 1: Write normalization tests for original/revised identity and timestamps**

```python
def test_normalize_nse_record_preserves_original_and_broadcast_timestamp():
    record = {
        "symbol": "AAA",
        "toDate": "30-Jun-2024",
        "broadCastDate": "12-Aug-2024 17:31:22",
        "consolidated": "Consolidated",
        "xbrl": "https://nsearchives.nseindia.com/example.xml",
        "revised": "No",
    }
    row = normalize_nse_record(record, "legacy")
    assert row["Symbol"] == "AAA"
    assert row["Fiscal_Period_End"] == pd.Timestamp("2024-06-30")
    assert row["Reporting_Basis"] == "CONSOLIDATED"
    assert row["Original_or_Revised"] == "ORIGINAL"
    assert row["Public_Timestamp"].tz.zone == "Asia/Kolkata"
```

Also cover Integrated Filing `Type of Submission=Original` and a revised BSE fixture.

- [ ] **Step 2: Run RED source-client tests**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py"
```

- [ ] **Step 3: Implement resilient clients without strategy logic**

Use a `requests.Session` with browser-like `User-Agent`, explicit timeout, retry only for transient HTTP status, and per-request source URL retention. Source adapters return raw/normalized filing metadata only; they must not calculate SUE, cohort or post-event returns.

- [ ] **Step 4: Write XBRL EPS tests**

Fixture must contain at least current-quarter and YTD contexts so the parser proves it selects the genuine quarter context.

```python
def test_extract_basic_eps_uses_current_quarter_context_not_ytd():
    value = extract_basic_eps_continuing(
        Path(FIXTURES / "nse_xbrl_basic_eps.xml").read_bytes(),
        pd.Timestamp("2024-06-30"),
        "CONSOLIDATED",
    )
    assert value == pytest.approx(12.34)
```

Add tests for standalone/consolidated mismatch and missing EPS -> `None`.

- [ ] **Step 5: Implement taxonomy-tolerant EPS extraction**

Search XBRL facts by normalized local-name aliases representing Basic EPS from continuing operations and require a context whose start/end describe the quarterly period and whose standalone/consolidated dimension matches the selected basis. Support both legacy NSE financial-result namespaces and Integrated Filing `in-capmkt` style without hard-coding one namespace prefix. Never fall back to diluted EPS or annual/YTD EPS.

- [ ] **Step 6: Verify and commit Task 2**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py" \
                         "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_xbrl_eps.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/source_clients.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/xbrl_eps.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "research: add official E1 result-source adapters"
```

---

### Task 3: Build and freeze the Stage A source + market snapshot

**Files:**
- Create: `build_e1_source_snapshot.py`
- Create: `tests/test_source_snapshot.py`
- Generate all files under `input/`.
- Read only: PIT membership manifest.
- Reference only: adjusted-Yahoo conventions in `strategy_v3_shallow_pullback/build_v3_features.py`.

**Interfaces:**
- `build_filing_snapshot(symbols: list[str], cutoff: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- `build_corporate_action_snapshot(symbols: list[str], cutoff: pd.Timestamp) -> pd.DataFrame`
- `download_adjusted_prices(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame`
- `build_market_snapshot(membership: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
- `write_manifest(input_dir: Path, provenance: dict[str, str]) -> pd.DataFrame`

- [ ] **Step 1: Write snapshot-determinism and no-return-leakage tests**

```python
def test_snapshot_builder_outputs_source_fields_but_no_forward_return_fields():
    filings, eps, audit = build_filing_snapshot(["AAA"], pd.Timestamp("2026-08-25"))
    forbidden = {"Gross_Return", "Net_Return", "Exit_Open", "SUE", "Cohort"}
    assert forbidden.isdisjoint(filings.columns)
    assert forbidden.isdisjoint(eps.columns)
```

Use monkeypatched source clients so the test is network-free.

- [ ] **Step 2: Implement first-public raw snapshot retention**

`e1_exchange_filings_snapshot.csv` must retain all discovered original/revised records through `SOURCE_CUTOFF`, with at least:

```text
Symbol, Exchange, Feed, Fiscal_Period_End, Fiscal_Quarter,
Reporting_Basis, Quarterly_or_Annual, Original_or_Revised,
Public_Timestamp, Source_URL, Source_Record_ID, Machine_Readable_URL
```

Do not deduplicate away revisions in Stage A; first-public selection belongs to Stage B.

`e1_eps_snapshot.csv` retains successfully parsed machine-readable EPS observations with the exact filing identity and source. Cross-exchange conflict is preserved, not silently resolved.

- [ ] **Step 3: Implement corporate-action snapshot**

Retain only official exchange split, consolidation and bonus events required for per-share comparability:

```text
Symbol, Action_Type, Ratio_Numerator, Ratio_Denominator,
Ex_Date, Record_Date, Source_URL, Source_Record_ID
```

Reject unparseable ratios into `e1_source_build_audit.csv`; never guess a ratio.

- [ ] **Step 4: Freeze adjusted market prices**

Use:

```text
PRICE_START = 2023-07-31
PRICE_END_EXCLUSIVE = 2026-08-27
NIFTY500_YAHOO_TICKER = ^CRSLDX
```

For every `Downloadable=True` symbol that is active at any point in the primary window, download `auto_adjust=True`, interval `1d`, actions disabled, threads disabled. Write one long stock snapshot:

```text
Symbol, Yahoo_Ticker, Date, Open, High, Low, Close, Volume
```

and one index snapshot:

```text
Date, Open, High, Low, Close
```

Reject duplicate dates; keep missing OHLC rows visible in the source audit.

- [ ] **Step 5: Write source manifest and audit**

Manifest columns:

```text
Artifact, Source, Retrieved_At, Row_Count, SHA256,
Primary_Window, Source_Cutoff, Notes
```

Hash every frozen input file after writing it. Include the PIT membership artifact path + current SHA256 as an external read-only fingerprint row even though it remains outside E1 `input/`.

- [ ] **Step 6: Run Stage A tests**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
```

- [ ] **Step 7: Run the real Stage A builder once and freeze inputs before any profitability analysis**

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py"
```

After this command, inspect only source/build audit and coverage-oriented fields. **Do not calculate or inspect E1 post-event returns yet.** Resolve only source/parser/integrity defects permitted by the spec, rerun Stage A as necessary, then commit the final frozen `input/` package before proceeding to Task 4.

- [ ] **Step 8: Verify hashes and commit frozen Stage A inputs**

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd
import sys
root = Path("Swing Trading/research/swing/e1_positive_earnings_surprise_drift")
sys.path.insert(0, str(root))
from load_e1_inputs import verify_manifest
manifest = pd.read_csv(root / "input/e1_source_manifest.csv")
audit = verify_manifest(manifest, root / "input")
assert audit.empty, audit.to_string(index=False)
print("E1 frozen input hashes verified")
PY

git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git commit -m "research: freeze E1 official source snapshot"
```

---

### Task 4: Normalize primary events, first-public filing, timeliness, PIT membership and source coverage

**Files:**
- Create: `build_e1_events.py`
- Create: `tests/test_events.py`
- Generate: `output/e1_event_master.csv`
- Generate: `output/e1_event_exclusions.csv`
- Generate: `output/e1_source_coverage.csv`

**Interfaces:**
- `select_first_public_filings(filings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
- `is_timely_result(period_end: pd.Timestamp, public_date: pd.Timestamp, fiscal_quarter: str) -> bool`
- `select_reporting_basis(events: pd.DataFrame, eps: pd.DataFrame) -> pd.DataFrame`
- `build_event_master(...) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: Write first-public and date-window tests**

```python
def test_revision_never_replaces_original_event():
    rows = pd.DataFrame([
        {"Symbol":"AAA", "Fiscal_Period_End":"2024-06-30", "Reporting_Basis":"CONSOLIDATED",
         "Original_or_Revised":"ORIGINAL", "Public_Timestamp":"2024-08-10 10:00:00+05:30", "EPS":10.0},
        {"Symbol":"AAA", "Fiscal_Period_End":"2024-06-30", "Reporting_Basis":"CONSOLIDATED",
         "Original_or_Revised":"REVISED", "Public_Timestamp":"2024-08-12 10:00:00+05:30", "EPS":11.0},
    ])
    selected, ignored = select_first_public_filings(rows)
    assert len(selected) == 1
    assert selected.iloc[0]["Original_or_Revised"] == "ORIGINAL"
```

Also test `2023-08-01` and `2026-06-30` are primary, `2026-07-01` is non-primary forward observation, and 45/60-day timeliness boundaries are inclusive.

- [ ] **Step 2: Write PIT membership test**

An event whose `Event_Public_Date` falls one day outside a membership interval must be non-universe; entry-date membership must not rescue it.

- [ ] **Step 3: Implement event key and earliest cross-exchange timestamp**

Canonical `Event_ID` must encode symbol, fiscal-period end and selected reporting basis. For matching original records on NSE/BSE, `Event_Public_Timestamp` is the earliest valid original/public timestamp across exchanges; retain both source records for audit.

- [ ] **Step 4: Implement basis priority and event exclusions**

Prefer consolidated only if current plus required comparable history is potentially available; otherwise allow standalone. At event-normalization stage classify structural blockers with one primary exclusion reason. Keep late result, invalid fiscal-quarter identity and unresolved machine-readable EPS explicit.

- [ ] **Step 5: Implement objective technical EPS coverage**

Exactly:

```python
technical = event_master[
    event_master["PIT_Membership_OK"]
    & event_master["Timely_Result"]
    & event_master["Selected_Basis"].notna()
    & event_master["Machine_Readable_URL"].notna()
]
resolution = technical["EPS_Source_Resolved"].mean() if len(technical) else float("nan")
```

`e1_source_coverage.csv` must retain denominator count, resolved count, unresolved `Event_ID`s, percentage, cross-exchange mismatches, NSE-only/BSE-only/cross-exchange counts, original/revision counts and structural exclusions separately.

- [ ] **Step 6: Verify and commit Task 4**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_events.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_events.py"
git commit -m "research: normalize E1 point-in-time earnings events"
```

---

### Task 5: Apply PIT corporate-action comparability, calculate SUE and classify all cohorts

**Files:**
- Create: `compute_e1_sue.py`
- Create: `tests/test_sue.py`
- Generate: `output/e1_eps_history.csv`
- Generate: `output/e1_sue_events.csv`
- Generate: `output/e1_cohort_classification.csv`

**Interfaces:**
- `adjust_historical_eps_for_actions(eps_history: pd.DataFrame, actions: pd.DataFrame, event_date: pd.Timestamp) -> pd.DataFrame`
- `compute_sue_for_event(event: pd.Series, eps_history: pd.DataFrame, actions: pd.DataFrame) -> tuple[dict[str, object] | None, str]`
- `classify_sue(value: float) -> str`
- `build_sue_events(event_master: pd.DataFrame, eps_snapshot: pd.DataFrame, actions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: Write exact SUE arithmetic test**

```python
def test_sue_uses_exactly_eight_prior_seasonal_changes_and_ddof_one():
    seasonal = pd.Series([1., 2., 3., 4., 5., 6., 7., 8.])
    current = 10.0
    expected = (current - seasonal.mean()) / seasonal.std(ddof=1)
    row = _sue_from_changes(current, seasonal)
    assert row["Historical_Mean"] == pytest.approx(seasonal.mean())
    assert row["Historical_SD"] == pytest.approx(seasonal.std(ddof=1))
    assert row["SUE"] == pytest.approx(expected)
```

- [ ] **Step 2: Write strict PIT-history test**

Add a historical quarter whose original public timestamp is after the current event; SUE must become unavailable rather than using that future-known value.

- [ ] **Step 3: Write corporate-action comparability tests**

For a 2-for-1 split effective before current event, pre-split historical EPS must be divided by 2 for comparability. A split effective after current event must have zero effect. An unparseable action ratio must yield `EPS_HISTORY_NOT_COMPARABLE`.

- [ ] **Step 4: Implement SUE chain with exact quarter identity**

Do not treat "four rows ago" as `t-4`; match fiscal-quarter identity/period end sequence. Require all current `D[t]` inputs plus eight complete prior seasonal differences; never mix consolidated/standalone. Persist every EPS value and `D[t-1]..D[t-8]` actually used in `e1_eps_history.csv`.

- [ ] **Step 5: Implement exact cohort boundaries**

```python
def classify_sue(value: float) -> str:
    if value >= 1.0:
        return "POSITIVE_SURPRISE"
    if value >= 0.5:
        return "POSITIVE_BUFFER"
    if value > -0.5:
        return "NEUTRAL_CONTROL"
    if value > -1.0:
        return "NEGATIVE_BUFFER"
    return "NEGATIVE_CONTROL"
```

Add tests for `1.0`, `0.5`, `-0.5`, `-1.0` and nearby epsilon values. Every finite SUE must appear exactly once.

- [ ] **Step 6: Verify and commit Task 5**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_sue.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/compute_e1_sue.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_sue.py"
git commit -m "research: compute frozen E1 SUE cohorts"
```

---

### Task 6: Construct identical positive/neutral/negative trade lifecycles and Nifty 500 benchmark outcomes

**Files:**
- Create: `build_e1_trades.py`
- Create: `tests/test_trades.py`
- Generate: `output/e1_positive_trades.csv`
- Generate: `output/e1_neutral_control.csv`
- Generate: `output/e1_negative_control.csv`

**Interfaces:**
- `next_session_after(date: pd.Timestamp, sessions: pd.DatetimeIndex) -> pd.Timestamp | None`
- `scheduled_exit_session(entry_date: pd.Timestamp, sessions: pd.DatetimeIndex, completed_sessions: int = 40) -> pd.Timestamp | None`
- `next_distinct_quarterly_result(symbol: str, after_timestamp: pd.Timestamp, all_original_events: pd.DataFrame) -> pd.Series | None`
- `build_trade_for_event(event: pd.Series, stock_prices: pd.DataFrame, index_prices: pd.DataFrame, all_original_events: pd.DataFrame) -> tuple[dict[str, object] | None, str]`

- [ ] **Step 1: Write next-session and 40-session exit tests**

```python
def test_entry_is_immediate_next_session_and_exit_is_after_40_complete_sessions():
    sessions = pd.bdate_range("2024-01-01", periods=50)
    entry = next_session_after(sessions[0], sessions)
    assert entry == sessions[1]
    assert scheduled_exit_session(entry, sessions, 40) == sessions[41]
```

The scheduled exit is the Open immediately after 40 completed sessions beginning with the entry session as session 1.

- [ ] **Step 2: Write no-gap-filter test**

A qualifying event with previous close 100 and next open 120 must still generate a trade at 120; do not cancel because of the +20% reaction.

- [ ] **Step 3: Write next-earnings early-exit test**

Create an open trade whose scheduled session-41 exit is after a second quarterly result. Even if the second result is marked late or has `SUE_UNAVAILABLE`, the old trade must exit at the next session Open after that second original result with `Exit_Reason=EXIT_NEXT_EARNINGS_EVENT`.

- [ ] **Step 4: Implement stock/benchmark accounting**

For each completed observation:

```python
gross = exit_open / entry_open - 1.0
base = gross - BASE_FRICTION
stress = gross - STRESS_FRICTION
severe = gross - SEVERE_FRICTION
benchmark = nifty_exit_open / nifty_entry_open - 1.0
base_excess = base - benchmark
stress_excess = stress - benchmark
```

Use exactly the same entry/exit dates for Nifty 500. If benchmark Open is absent on either date, emit an integrity problem; never nearest-date fill.

- [ ] **Step 5: Calculate diagnostic reaction/MAE/MFE without using them as filters**

Record last uncontaminated pre-announcement Close, entry gap/reaction, minimum Low and maximum High during the trade lifecycle, MAE, MFE and trade drawdown. These columns may only flow to diagnostic outputs.

- [ ] **Step 6: Apply identical mechanics to all three primary cohorts**

Positive, neutral and negative trades must call the same `build_trade_for_event()` function. Cohort name is data, not an execution branch. Buffer cohorts do not create primary trade files.

- [ ] **Step 7: Verify and commit Task 6**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_trades.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_trades.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_trades.py"
git commit -m "research: build E1 event trade outcomes"
```

---

### Task 7: Implement profitability, discrimination and robustness analysis

**Files:**
- Create: `analyze_e1_results.py`
- Create: `tests/test_analysis.py`
- Generate all analysis/diagnostic CSVs except integrity/gates/report.

**Interfaces:**
- `return_profit_factor(values: pd.Series) -> float`
- `summarize_cohort(frame: pd.DataFrame) -> dict[str, float]`
- `cohort_comparison(...) -> pd.DataFrame`
- `temporal_summary(positive: pd.DataFrame) -> pd.DataFrame`
- `year_summary(positive: pd.DataFrame) -> pd.DataFrame`
- `leave_one_year_out(positive: pd.DataFrame) -> pd.DataFrame`
- `top_five_robustness(positive: pd.DataFrame) -> pd.DataFrame`
- `leave_one_symbol_out(positive: pd.DataFrame) -> pd.DataFrame`
- `downside_diagnostic(positive: pd.DataFrame) -> pd.DataFrame`
- `diagnostic_summary(...) -> pd.DataFrame`
- `overlap_capacity_diagnostic(positive: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: Write PF and metric tests**

```python
def test_return_profit_factor_is_sum_wins_over_absolute_sum_losses():
    values = pd.Series([0.10, 0.05, -0.03, -0.02])
    assert return_profit_factor(values) == pytest.approx(3.0)
```

Define zero-loss behavior deterministically (`inf` when gains>0 and losses=0; `nan` when no gains and no losses).

- [ ] **Step 2: Write temporal split test**

Use `Event_Public_Date`, not entry or exit date. `2025-01-14` belongs FIRST; `2025-01-15` belongs SECOND.

- [ ] **Step 3: Write top-five and LOSO tests**

Top five are selected by `Gross_Return` among positive trades before friction. LOSO must generate one row for every distinct positive-trade symbol and compute mean/PF/excess after removing that symbol.

- [ ] **Step 4: Implement approved mandatory metrics**

Positive summary includes completed count, base/stress/severe mean/median/win rate/PF, benchmark mean, base/stress excess mean, excess PF. Comparison includes positive, neutral and negative means/PFs/excess means and explicit ordering booleans.

- [ ] **Step 5: Implement approved diagnostics only**

Generate cuts for SUE bands (`1-2`, `2-3`, `3-5`, `>=5`), EPS transition type, entry-gap bucket, market-cap/liquidity/sector only where already available without new strategic data collection, reporting basis, fiscal quarter, weekday, holding duration and year. Every diagnostic row must carry `Mandatory_Gate=False`.

- [ ] **Step 6: Implement overlap/capacity diagnostics**

From positive trade entry/exit intervals report max/median simultaneous active trades, same-day entries and event-season clustering. Do not truncate to 3–5 slots or rank candidates.

- [ ] **Step 7: Verify and commit Task 7**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_analysis.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/analyze_e1_results.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_analysis.py"
git commit -m "research: analyze frozen E1 outcomes"
```

---

### Task 8: Build the formal offline validator, integrity audit, gate precedence and research report

**Files:**
- Create: `run_e1_validation.py`
- Extend: `tests/test_end_to_end.py`
- Generate: `output/e1_data_validation.csv`
- Generate: `output/e1_integrity_audit.csv`
- Generate: `output/e1_validation_gates.csv`
- Generate: `output/research_report.md`
- Create: `README.md`
- Create: `requirements.txt`

**Interfaces:**
- `build_integrity_audit(...) -> pd.DataFrame`
- `evaluate_gates(...) -> tuple[str, pd.DataFrame]`
- `_final_package_issues(output_dir: Path) -> list[dict[str, object]]`
- `write_research_report(path: Path, status: str, evidence: dict[str, object]) -> None`
- `run_validation(input_dir: Path = INPUT_ROOT, output_dir: Path = OUTPUT_ROOT) -> tuple[str, pd.DataFrame]`

- [ ] **Step 1: Write status-precedence tests**

```python
def test_integrity_failure_beats_every_profitability_gate():
    status, _ = evaluate_gates(..., integrity_count=1, technical_coverage=1.0,
                               positive_count=500, neutral_count=500, negative_count=500)
    assert status == "INVALID_RESEARCH_RUN"


def test_insufficient_sample_beats_strategy_fail():
    status, _ = evaluate_gates(..., integrity_count=0, technical_coverage=1.0,
                               positive_count=299, neutral_count=500, negative_count=500)
    assert status == "INSUFFICIENT_EVIDENCE"
```

Also test technical coverage `0.949999` -> INVALID and exactly `0.95` -> eligible for later precedence.

- [ ] **Step 2: Implement systemic integrity checks**

At minimum audit:

```text
MANIFEST_HASH_MISMATCH
MISSING_REQUIRED_INPUT
PIT_MEMBERSHIP_VIOLATION
EVENT_AFTER_PRIMARY_WINDOW_IN_FORMAL_SAMPLE
EVENT_BEFORE_PRIMARY_WINDOW_IN_FORMAL_SAMPLE
FUTURE_EPS_USED
REVISED_EPS_USED_AS_ORIGINAL
FUTURE_CORPORATE_ACTION_USED
DUPLICATE_EVENT_ID
SUE_COHORT_OVERLAP
UNCLASSIFIED_FINITE_SUE
POSITIVE_ACCOUNTING_MISMATCH
NEUTRAL_ACCOUNTING_MISMATCH
NEGATIVE_ACCOUNTING_MISMATCH
ENTRY_NOT_AFTER_EVENT
BENCHMARK_DATE_MISMATCH
TRADE_MECHANICS_DIVERGED_BY_COHORT
MISSING_FINAL_EVIDENCE
INVALID_FINAL_EVIDENCE
```

Do not silently filter away an integrity violation to make the sample pass.

- [ ] **Step 3: Implement exact mandatory gates**

Create rows with `Gate, Value, Threshold, Pass, Mandatory`. Required rows include source coverage, cohort/temporal sufficiency, all base/stress positive gates, directional/discrimination gates, first/second temporal gates, leave-one-year-out all-pass gates, top-five all-pass gates and LOSO all-pass gates. Severe-friction and diagnostics are `Mandatory=False`.

- [ ] **Step 4: Implement final evidence package verifier**

Explicitly verify every approved output file exists and is readable. Required CSVs must contain their minimum schema; `research_report.md` must exist, decode as UTF-8 and contain non-whitespace content. Any missing/unreadable required final artifact is an integrity violation and forces `INVALID_RESEARCH_RUN`.

- [ ] **Step 5: Implement mechanically generated research report**

Report sections exactly:

```text
1 Frozen E1 hypothesis
2 Source provenance
3 Source coverage
4 PIT/event integrity
5 Event exclusions
6 SUE methodology
7 Cohort counts
8 Positive base results
9 Market-relative results
10 Stress/severe friction
11 Positive vs neutral vs negative discrimination
12 Temporal halves
13 Calendar years
14 Leave-one-year-out
15 Top-five robustness
16 Leave-one-symbol-out
17 Downside diagnostics
18 Capacity/overlap diagnostics
19 Mandatory gate table
20 Formal conclusion and next action
```

Do not print alternate SUE thresholds/holding periods or rescue recommendations.

- [ ] **Step 6: Prove the formal validator is offline**

In an end-to-end test monkeypatch `requests.Session.get`, `requests.get` and `yfinance.download` to raise `AssertionError("network called")`; run `run_validation()` on fixture inputs and assert it completes without triggering those patches.

- [ ] **Step 7: Verify and commit Task 8**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/README.md" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/requirements.txt" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py"
git commit -m "research: add E1 formal validation harness"
```

---

### Task 9: Full regression, one frozen historical run and evidence handoff

**Files:**
- Regenerate all approved `output/` artifacts.
- Do not modify E1 `input/` after the formal run begins.
- Do not modify any V3/R1/M1 file.

- [ ] **Step 1: Run complete E1 unit/integration tests**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
```

Expected: zero failures.

- [ ] **Step 2: Run existing closed-strategy regression suites**

```bash
python -m pytest -q "Swing Trading/research/swing/strategy_v3_shallow_pullback/tests"
python -m pytest -q "Swing Trading/research/swing/r1_price_shock_reversal/tests"
python -m pytest -q "Swing Trading/research/swing/m1_regime_gated_momentum/tests"
```

Expected: zero failures. If a path/name differs on the implementation branch, locate the existing closed module and run its whole test directory; do not alter closed strategy code to make E1 pass.

- [ ] **Step 3: Record a clean pre-run input fingerprint**

```bash
git status --short
sha256sum "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input/"* > /tmp/e1_input_hashes_before.txt
```

The only acceptable working-tree changes before the formal run are implementation/test files already intended for the E1 branch; frozen input hashes must match the committed manifest.

- [ ] **Step 4: Run the frozen historical validator exactly once for the formal result**

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

Do not change SUE thresholds, event window, reporting-basis priority, hold duration, filters, friction or gates based on the result.

- [ ] **Step 5: Verify evidence/integrity mechanically**

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd
root = Path("Swing Trading/research/swing/e1_positive_earnings_surprise_drift/output")
integrity = pd.read_csv(root / "e1_integrity_audit.csv")
gates = pd.read_csv(root / "e1_validation_gates.csv")
coverage = pd.read_csv(root / "e1_source_coverage.csv")
assert integrity.empty, integrity.to_string(index=False)
assert (root / "research_report.md").read_text(encoding="utf-8").strip()
final = gates.loc[gates["Gate"].eq("FINAL_STATUS"), "Value"]
assert len(final) == 1
print("Formal E1 status:", final.iloc[0])
print(coverage.to_string(index=False))
PY
sha256sum "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input/"* > /tmp/e1_input_hashes_after.txt
diff -u /tmp/e1_input_hashes_before.txt /tmp/e1_input_hashes_after.txt
```

Input hash diff must be empty.

- [ ] **Step 6: Inspect only the predeclared result package**

Report exactly:

```text
technical EPS coverage
positive / neutral / negative completed counts
FIRST / SECOND positive counts
base positive mean / median / PF
base excess mean / excess PF
stress mean / PF / excess mean
positive > neutral > negative mean ordering
positive > neutral > negative excess ordering
positive PF discrimination
FIRST and SECOND metrics
leave-one-year-out all-pass status
top-five-removed metrics
LOSO all-pass status
integrity count
formal status
```

Diagnostics may be summarized, but must not be proposed as E1 rescue filters.

- [ ] **Step 7: Run full swing-research regression suite**

Run the repository's full swing research pytest tree (excluding only known non-test generated-data directories if pytest already excludes them):

```bash
python -m pytest -q "Swing Trading/research/swing"
```

Expected: zero test failures. A pytest-cache permission warning is acceptable only if it is the already-known environment warning and tests themselves pass.

- [ ] **Step 8: Commit the frozen formal evidence**

```bash
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/output" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift"
git commit -m "research: validate E1 positive earnings surprise drift"
```

Before committing, verify `git diff --name-only` contains no V3/R1/M1 source or output paths.

- [ ] **Step 9: Prepare the PR handoff**

PR description must include:

```text
Issue #33
Frozen spec path + commit
Plan path + commit
Stage A source snapshot commit
Implementation commit SHAs
E1 test command/pass count
V3/R1/M1 regression command/pass counts
Full swing-research pass count
Frozen input hash verification result
Technical EPS coverage
Primary cohort counts
Formal mandatory-gate result
Final E1 status
Any integrity violations (expected zero for a valid research run)
Confirmation that no threshold/filter/hold/friction rescue was introduced
Confirmation that V3/R1/M1 remain untouched
```

If final status is `PASS`, stop signal research and prepare portfolio-constrained simulation next. If `FAIL`, close E1 permanently and move to the final independent candidate. If `INSUFFICIENT_EVIDENCE`, do not loosen history/SUE/sample rules. If `INVALID_RESEARCH_RUN`, fix only the identified integrity/data defect and rerun the unchanged frozen E1 design.

---

## Self-Review Checklist Before Luna Starts

- [ ] Every spec requirement maps to one task above.
- [ ] Stage A can make network calls; Stage B cannot.
- [ ] Stage A never calculates post-event returns/SUE-based profitability.
- [ ] Frozen input package includes hashes and the formal validator verifies them.
- [ ] Official NSE/BSE source identity and first-public/revision semantics are preserved.
- [ ] Machine-readable EPS coverage denominator is objective and >=95% is a formal integrity requirement.
- [ ] SUE uses exactly 8 prior seasonal changes and `ddof=1`.
- [ ] Cohort boundaries exactly match the spec.
- [ ] Positive/neutral/negative cohorts use one shared execution implementation.
- [ ] No gap filter or technical exit has entered the design.
- [ ] Next distinct quarterly result truncates an open trade regardless of the new event's E1 eligibility.
- [ ] Benchmark dates exactly match stock entry/exit dates.
- [ ] All mandatory gates and status precedence match the spec.
- [ ] Diagnostics cannot affect `evaluate_gates()`.
- [ ] Required evidence package includes non-empty `research_report.md`.
- [ ] No V3/R1/M1 file is modified.
- [ ] No alternate threshold/holding-period rescue appears anywhere in the plan.

## Execution Instruction

Use `superpowers:executing-plans` **inline only**, task by task, with TDD and verification checkpoints. Never use or suggest `superpowers:subagent-driven-development`.
