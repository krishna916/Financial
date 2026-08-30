# PR #36 E1 SUE-First Price Acquisition Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.**

**Goal:** Stop requiring market-price history for every PIT Nifty 500 symbol. Reuse the already-built official filing/EPS/corporate-action data, compute formal E1 SUE events first, freeze prices only for symbols actually needed by the primary E1 cohorts, then run the unchanged offline validator to obtain the real E1 verdict.

**Architecture:** Keep the existing E1 source, SUE, trade, and gate logic. Change only acquisition order: official filings/EPS/actions -> formal event/SUE classification -> exact price-requirement set -> prices for required symbols + benchmark -> frozen manifest -> unchanged Stage B. A symbol with no finite SUE event in `POSITIVE_SURPRISE`, `NEUTRAL_CONTROL`, or `NEGATIVE_CONTROL` must never block Stage A because its price history is irrelevant to the formal experiment.

**Tech Stack:** Python 3, pandas, yfinance, pytest.

**Frozen spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

**PR:** `https://github.com/krishna916/Financial/pull/36`

## Global Constraints

- Do not change the E1 hypothesis, primary window, source cutoff, SUE formula/history, cohort thresholds, 40-session hold, friction, benchmark, controls, robustness gates, or status precedence.
- Reuse the existing 661 hash-valid v2 filing/EPS checkpoints. Do not refetch them just because price acquisition changes.
- Price acquisition is required only for finite-SUE events in the three formal cohorts: `POSITIVE_SURPRISE`, `NEUTRAL_CONTROL`, `NEGATIVE_CONTROL`.
- `POSITIVE_BUFFER` and `NEGATIVE_BUFFER` remain classified evidence but do not require prices for the formal validation.
- PIT membership remains authoritative for event eligibility. Do not edit the membership manifest to solve provider issues.
- Existing provenance-backed same-security aliases such as `GLS -> ALIVUS.NS` remain valid.
- Never exclude a qualifying event merely because price acquisition is inconvenient. A price failure matters only when the symbol is in the frozen price-requirement set.
- Do not implement generic merger/delisting infrastructure before a qualifying required event actually demonstrates that it is needed.
- Stage B remains network-free.

---

### Task 1: Derive the exact price-requirement set before any stock-price download

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/constants.py`
- Test: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py`

**Add constants:**

```python
PRIMARY_PRICE_COHORTS = frozenset({
    "POSITIVE_SURPRISE",
    "NEUTRAL_CONTROL",
    "NEGATIVE_CONTROL",
})

PRICE_REQUIREMENT_COLUMNS = [
    "Event_ID",
    "Symbol",
    "Cohort",
    "SUE",
    "Event_Public_Date",
    "Fiscal_Period_End",
]
```

Add `e1_price_requirements.csv` to `REQUIRED_INPUT_ARTIFACTS`.

**Add exact helper:**

```python
def build_price_requirements(
    filings: pd.DataFrame,
    eps: pd.DataFrame,
    actions: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    from build_e1_events import build_event_master
    from compute_e1_sue import build_sue_events

    event_master, _, _, _ = build_event_master(
        filings, eps, membership, actions
    )
    _, _, classified, _ = build_sue_events(event_master, eps, actions)

    required = classified.loc[
        classified["Cohort"].isin(PRIMARY_PRICE_COHORTS),
        PRICE_REQUIREMENT_COLUMNS,
    ].copy()
    return required.sort_values(
        ["Event_Public_Date", "Symbol", "Event_ID"], kind="stable"
    ).reset_index(drop=True)
```

- [ ] **Write RED test: irrelevant dead ticker does not enter price requirements**

Create fixtures where `DEAD` is a PIT member but has no formal finite SUE event, while `AAA` has a valid positive SUE event. Assert:

```python
requirements = snapshot.build_price_requirements(filings, eps, actions, membership)
assert set(requirements["Symbol"]) == {"AAA"}
assert "DEAD" not in set(requirements["Symbol"])
```

- [ ] **Write RED test: buffers do not require prices**

Build classified fixtures spanning all five cohorts and assert the returned set contains only the three formal cohorts.

- [ ] **Implement the helper using existing event/SUE functions only**

Do not duplicate eligibility or SUE logic in `build_e1_source_snapshot.py`.

- [ ] **Run tests**

```bash
cd "Swing Trading"
python -m pytest -q research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py
```

- [ ] **Commit**

```bash
git add research/swing/e1_positive_earnings_surprise_drift
 git commit -m "fix: derive E1 price needs after SUE"
```

---

### Task 2: Download prices only for symbols in the frozen requirement set

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Keep: `price_identity.py`, `price_provider_aliases.csv`

**Change exact signature:**

```python
def build_market_snapshot(
    membership: pd.DataFrame,
    aliases: pd.DataFrame,
    required_symbols: set[str],
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_prices,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ...
```

Add helper:

```python
def membership_for_required_symbols(
    membership: pd.DataFrame,
    required_symbols: set[str],
) -> pd.DataFrame:
    active = _symbols_active_in_window(membership)
    required = {str(s).strip().upper() for s in required_symbols if str(s).strip()}
    available = set(active["Symbol"].astype(str).str.upper())
    missing = sorted(required - available)
    if missing:
        raise ValueError(
            "PRICE_REQUIREMENT_SYMBOL_MISSING_MEMBERSHIP: " + ",".join(missing)
        )
    return active.loc[
        active["Symbol"].astype(str).str.upper().isin(required)
    ].copy()
```

`build_price_identity_table()` must operate on this filtered membership frame. It must not resolve or download provider identities for unrelated symbols.

- [ ] **Write RED regression using a dead irrelevant ticker**

Membership:

```text
AAA -> AAA.NS
DEAD -> DEAD.NS
```

Call with `required_symbols={"AAA"}` and a fake downloader that raises if `DEAD.NS` is requested.

Assert:

```python
assert "AAA.NS" in calls
assert "DEAD.NS" not in calls
assert set(stocks["Symbol"]) == {"AAA"}
```

- [ ] **Write regression preserving GLS alias only when GLS is required**

With `required_symbols={"GLS"}` assert `ALIVUS.NS` is requested and `GLS.NS` is not.

With `required_symbols=set()` assert no stock provider ticker is requested; only the Nifty 500 benchmark is downloaded.

- [ ] **Implement filtering before identity resolution/download**

Exact order:

```text
required symbols
-> active PIT membership rows for only those symbols
-> provider identity resolution
-> shared-provider overlap validation
-> unique provider downloads
-> frozen stock rows
-> benchmark download
```

- [ ] **Run focused tests and commit**

```bash
cd "Swing Trading"
python -m pytest -q \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py \
  research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py

git add research/swing/e1_positive_earnings_surprise_drift
 git commit -m "fix: limit E1 prices to required SUE symbols"
```

---

### Task 3: Freeze the requirement artifact and prove Stage B uses the same set

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `run_e1_validation.py`
- Modify: `tests/test_end_to_end.py`

Change `_write_stage_a()` to this exact sequence:

```text
1. build/reuse filings + EPS checkpoints
2. build corporate actions
3. write filing/EPS/action/source-audit CSVs
4. build_price_requirements(...) using those exact in-memory frames
5. write e1_price_requirements.csv
6. required_symbols = unique requirement Symbol values
7. build_market_snapshot(..., required_symbols)
8. write stock/index/price-identity CSVs
9. fail on price-identity violations for required symbols only
10. write final manifest
```

Do not calculate stock returns anywhere in Stage A.

**Add Stage B integrity check:** after `classified` is rebuilt from frozen source inputs:

```python
expected_price_ids = set(
    classified.loc[
        classified["Cohort"].isin(PRIMARY_PRICE_COHORTS), "Event_ID"
    ].astype(str)
)
actual_price_ids = set(
    loaded["e1_price_requirements.csv"]["Event_ID"].astype(str)
)
```

If unequal, add one systemic violation:

```text
Check=PRICE_REQUIREMENTS
Violation=PRICE_REQUIREMENT_SET_MISMATCH
Count=<symmetric difference count>
Detail=<sorted differing Event_IDs>
```

This must force `INVALID_RESEARCH_RUN` through the existing integrity precedence.

- [ ] **Write RED end-to-end mismatch test**

Create a frozen fixture where classified primary Event_ID is `A`, but `e1_price_requirements.csv` contains `B`. Assert final status is `INVALID_RESEARCH_RUN` and integrity audit contains `PRICE_REQUIREMENT_SET_MISMATCH`.

- [ ] **Write passing fixture where requirement set matches classified primary events**

Buffers may exist in classification but must not be required.

- [ ] **Run tests and commit**

```bash
cd "Swing Trading"
python -m pytest -q research/swing/e1_positive_earnings_surprise_drift/tests

git add research/swing/e1_positive_earnings_surprise_drift
 git commit -m "research: freeze E1 price requirement evidence"
```

---

### Task 4: Run the shortened real pipeline and obtain the verdict

**No more full-universe price preflight.**

- [ ] **Run fresh tests**

```bash
cd "Swing Trading"
python -m pytest -q research/swing/e1_positive_earnings_surprise_drift/tests
python -m pytest -q research/swing
```

Record exact fresh counts.

- [ ] **Run the already-existing official-source smoke**

```bash
python research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py \
  --smoke \
  --work-dir .e1-stage-a-smoke-v2
```

Must PASS. Do not refetch the 661 valid checkpoints unnecessarily.

- [ ] **Run full Stage A with the new SUE-first ordering**

```bash
python research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py \
  --work-dir .e1-stage-a-work-v2
```

Before doing any new ticker investigation, inspect only:

```text
input/e1_price_requirements.csv
```

and the set of provider failures among those required symbols.

### Required failure policy

If an old Yahoo-dead symbol such as `GSPL`, `IDFC`, `ISEC`, etc. is **not present** in `e1_price_requirements.csv`, do nothing. It is irrelevant to E1 and must not block the run.

If a required symbol fails price acquisition:

```text
1. print/report its exact required Event_ID(s) and Cohort(s);
2. if official evidence proves same-security ticker continuity, use the existing provenance-backed alias mechanism;
3. otherwise stop on that concrete required observation and report it as the only remaining market-data integrity issue;
4. do not build generic merger/delisting handling unless a required event actually needs it.
```

No `.BO` guessing, universe exclusion, membership edits, or strategy changes.

- [ ] **If Stage A completes, verify frozen inputs immediately**

Require:

```text
e1_price_requirements.csv exists and is non-ambiguous
manifest hashes/row counts verify
price identity audit has no violation for required symbols
stock snapshot contains every required symbol and no duplicate Symbol+Date
benchmark dates are unique
technical EPS coverage remains >=95% or Stage B must return INVALID
```

- [ ] **Run Stage B offline unchanged**

```bash
python research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py
```

The authoritative result is only:

```text
output/e1_validation_gates.csv -> FINAL_STATUS
```

Do not tune E1 after seeing it.

- [ ] **Commit the completed evidence and update PR #36**

PR comment/description must report only:

```text
fresh E1 test count
fresh full research test count
source smoke status
number of finite-SUE primary events
number of unique required price symbols
any required price failures (if any)
technical EPS coverage
FINAL_STATUS if Stage B completed
```

Do not report or investigate unrelated Yahoo-dead universe symbols.

---

## Completion Checklist

```text
[ ] Price acquisition occurs after formal SUE classification.
[ ] Only POSITIVE_SURPRISE / NEUTRAL_CONTROL / NEGATIVE_CONTROL events create price requirements.
[ ] Non-required PIT symbols cannot block Stage A price acquisition.
[ ] Existing GLS -> ALIVUS provider alias still works when GLS is actually required.
[ ] e1_price_requirements.csv is frozen and manifest-hashed.
[ ] Stage B recomputes and verifies the exact requirement Event_ID set.
[ ] No return data is consulted while deriving price requirements.
[ ] 661 valid official-source checkpoints are reused.
[ ] No generic dead-ticker/merger cleanup is performed unless a required E1 event needs it.
[ ] Stage A either completes or stops only on a genuinely required price observation.
[ ] Stage B runs offline unchanged and emits the formal FINAL_STATUS.
```
