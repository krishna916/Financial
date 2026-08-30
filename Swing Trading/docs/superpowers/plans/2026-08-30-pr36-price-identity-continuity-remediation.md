# PR #36 E1 Price Identity Continuity Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the frozen E1 Stage A market-price failure caused by historical security-symbol continuity (`GLS` -> `ALIVUS`) without changing PIT membership or strategy rules, then complete the frozen Stage A package and run Stage B offline unchanged.

**Architecture:** Keep PIT research identity separate from market-data provider identity. Research/event symbols and Nifty 500 membership remain exactly as frozen (`GLS` stays `GLS`; `ALIVUS` stays `ALIVUS`). Add a small provenance-backed Yahoo provider-alias registry used only during Stage A price acquisition. Resolve all provider identities before downloading, reject ambiguous/overlapping aliases, download each provider ticker once, copy that frozen provider series to applicable non-overlapping research identities, write a dedicated identity audit, fingerprint the mapping, and leave Stage B completely network-free.

**Tech Stack:** Python 3, pandas, yfinance, pytest. Do not add a new market-data provider or generic security-master framework.

**Frozen spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

**Previous remediation plan:** `Swing Trading/docs/superpowers/plans/2026-08-30-pr36-stage-a-source-remediation.md`

**PR:** `https://github.com/krishna916/Financial/pull/36`

**Blocking review:** `https://github.com/krishna916/Financial/pull/36#pullrequestreview-5060247746`

## Frozen evidence for this remediation

This mapping is an identity correction established before E1 returns are available.

Official NSE evidence:

```text
NSE circular NSE/CML/66114 dated 2025-01-14
Existing symbol: GLS
New symbol: ALIVUS
Effective: 2025-01-20
Existing name: Glenmark Life Sciences Limited
New name: Alivus Life Sciences Limited
Source: https://nsearchives.nseindia.com/content/circulars/CML66114.pdf
```

Official company/NSE evidence preserves the same listed identity while changing the NSE symbol:

```text
BSE code: 543322
NSE symbol: GLS -> ALIVUS effective 2025-01-20
ISIN: INE03Q201024
Source: https://nsearchives.nseindia.com/corporate/GLS_18012025135211_BSE_NSE_Press_Release_180125_Signed.pdf
```

Existing repo evidence in `market_breadth/output/breadth_universe_audit.csv` shows:

```text
ALIVUS,ALIVUS.NS,DOWNLOADED, historical provider data from 2022-08-01 through 2026-08-25
GLS,GLS.NS,NO_USABLE_DATA, no adjusted-close observations returned
```

The PIT membership history keeps `GLS` and `ALIVUS` as separate historical research symbols with non-overlapping active intervals. Do not rewrite those intervals.

## Global Constraints

- Do **not** change the E1 hypothesis, primary window (`2023-08-01..2026-06-30`), source cutoff (`2026-08-25`), SUE formula/history length, cohort thresholds, 40-session hold, friction, benchmark/control mechanics, or PASS/FAIL gates.
- Do **not** modify `market_breadth/config/nifty500_membership.csv` merely to make Yahoo download succeed.
- Research/event identity remains the PIT symbol from membership and official filings. Provider aliasing is Stage A transport metadata only.
- Never auto-guess ticker aliases, append `.BO`, strip characters, use company-name fuzzy matching, or silently exclude a failed symbol.
- A provider alias is allowed only with explicit official identity-continuity provenance.
- Shared provider history may serve multiple research symbols only when their inclusive PIT membership intervals do not overlap.
- Stage A may acquire and freeze prices. Stage B remains offline and consumes only frozen snapshots.
- Existing v2 filing/EPS checkpoints may be reused when their current hash/version/reusability checks pass.
- No alternate market-data provider is introduced here. If a verified Yahoo alias still lacks relevant-period data, fail closed.
- Do not tune E1 after the eventual outcome becomes visible.

## Files

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/
├── price_provider_aliases.csv
├── price_identity.py
├── build_e1_source_snapshot.py
├── constants.py
├── README.md
├── tests/
│   ├── test_price_identity.py
│   ├── test_source_snapshot.py
│   └── test_end_to_end.py
├── input/
│   ├── e1_exchange_filings_snapshot.csv
│   ├── e1_eps_snapshot.csv
│   ├── e1_corporate_actions_snapshot.csv
│   ├── e1_stock_prices_snapshot.csv
│   ├── e1_nifty500_prices_snapshot.csv
│   ├── e1_price_identity_audit.csv
│   ├── e1_source_build_audit.csv
│   └── e1_source_manifest.csv
└── output/  # unchanged Stage B evidence package
```

Do not introduce a global security-master abstraction. `price_identity.py` is a focused Stage A helper only.

---

### Task 1: Add a provenance-backed Yahoo provider-alias registry

**Files:**
- Create: `research/swing/e1_positive_earnings_surprise_drift/price_provider_aliases.csv`
- Create: `research/swing/e1_positive_earnings_surprise_drift/price_identity.py`
- Create: `research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py`

**Exact CSV schema:**

```text
Research_Symbol,Provider,Provider_Ticker,Security_ISIN,Identity_Effective_Date,Identity_Source_URL,Reason
```

**Initial row:**

```text
GLS,YAHOO,ALIVUS.NS,INE03Q201024,2025-01-20,https://nsearchives.nseindia.com/content/circulars/CML66114.pdf,NSE renamed GLS to ALIVUS; same listed security
```

**Exact public contracts:**

```text
PriceIdentity dataclass fields:
research_symbol: str
membership_ticker: str
provider: str
provider_ticker: str
alias_applied: bool
security_isin: str
identity_effective_date: pandas.Timestamp | None
identity_source_url: str
reason: str

load_price_aliases(path: pathlib.Path) -> pandas.DataFrame
resolve_price_identity(research_symbol: str, membership_ticker: str, aliases: pandas.DataFrame) -> PriceIdentity
validate_shared_provider_intervals(identities: pandas.DataFrame) -> pandas.DataFrame
```

`validate_shared_provider_intervals()` returns an empty frame when clean and otherwise columns:

```text
Provider,Provider_Ticker,Research_Symbol_A,Research_Symbol_B,Violation,Detail
```

with violation `PROVIDER_ALIAS_MEMBERSHIP_OVERLAP`.

- [ ] **Step 1: Write RED resolution tests**

Assert:

```python
gls = resolve_price_identity("GLS", "GLS.NS", aliases)
assert gls.research_symbol == "GLS"
assert gls.membership_ticker == "GLS.NS"
assert gls.provider_ticker == "ALIVUS.NS"
assert gls.alias_applied is True
assert gls.security_isin == "INE03Q201024"
assert gls.identity_effective_date == pd.Timestamp("2025-01-20")
assert gls.identity_source_url.endswith("CML66114.pdf")

alivus = resolve_price_identity("ALIVUS", "ALIVUS.NS", aliases)
assert alivus.provider_ticker == "ALIVUS.NS"
assert alivus.alias_applied is False

normal = resolve_price_identity("TCS", "TCS.NS", aliases)
assert normal.provider_ticker == "TCS.NS"
assert normal.alias_applied is False
```

- [ ] **Step 2: Write RED registry-integrity tests**

Reject with stable code `PRICE_ALIAS_INVALID_ROW`:

```text
blank Research_Symbol
blank Provider_Ticker
Provider other than YAHOO
blank Security_ISIN
invalid Identity_Effective_Date
non-HTTPS Identity_Source_URL
```

Reject duplicate `Research_Symbol` with `PRICE_ALIAS_DUPLICATE_SYMBOL`.

- [ ] **Step 3: Write RED shared-provider interval tests**

Clean fixture:

```text
GLS    -> ALIVUS.NS, Member_From=2023-09-29, Member_To=2024-09-29
ALIVUS -> ALIVUS.NS, Member_From=2025-03-28, Member_To=2025-09-29
```

Assert zero violations. Then overlap the intervals by one inclusive date and assert exactly one `PROVIDER_ALIAS_MEMBERSHIP_OVERLAP`.

- [ ] **Step 4: Implement exact resolver rules**

```text
exact Research_Symbol alias match -> configured Provider_Ticker
no alias -> membership Yahoo_Ticker unchanged
never fuzzy match
never mutate suffix
never try .BO
never rename research symbol
```

- [ ] **Step 5: Verify and commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py"
git add "research/swing/e1_positive_earnings_surprise_drift/price_provider_aliases.csv" \
        "research/swing/e1_positive_earnings_surprise_drift/price_identity.py" \
        "research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py"
git commit -m "fix: add audited E1 price provider identities"
```

---

### Task 2: Resolve identities before download and download each provider ticker once

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`

**Exact contracts:**

```text
build_price_identity_table(membership: pandas.DataFrame, aliases: pandas.DataFrame) -> pandas.DataFrame

build_market_snapshot(
    membership: pandas.DataFrame,
    aliases: pandas.DataFrame,
    downloader: Callable[[str, str, str], pandas.DataFrame] = download_adjusted_prices,
) -> tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]
```

Identity table columns exactly:

```text
Research_Symbol
Membership_Yahoo_Ticker
Provider
Provider_Ticker
Alias_Applied
Security_ISIN
Identity_Effective_Date
Identity_Source_URL
Reason
Member_From
Member_To
```

`build_market_snapshot()` returns `(stock_prices, benchmark_prices, price_identity_audit)`.

- [ ] **Step 1: Write RED one-download regression**

Use non-overlapping GLS/ALIVUS membership fixtures and a fake downloader with call recording. Its `ALIVUS.NS` frame must span both intervals.

Assert:

```python
stocks, benchmark, audit = build_market_snapshot(membership, aliases, fake_download)
assert fake_download.calls.count("ALIVUS.NS") == 1
assert "GLS.NS" not in fake_download.calls
assert "GLS.BO" not in fake_download.calls
assert set(stocks.loc[stocks["Provider_Ticker"].eq("ALIVUS.NS"), "Symbol"]) == {"GLS", "ALIVUS"}
```

- [ ] **Step 2: Prove research identity stays unchanged**

GLS price rows:

```text
Symbol=GLS
Membership_Yahoo_Ticker=GLS.NS
Provider_Ticker=ALIVUS.NS
Alias_Applied=True
```

ALIVUS price rows:

```text
Symbol=ALIVUS
Membership_Yahoo_Ticker=ALIVUS.NS
Provider_Ticker=ALIVUS.NS
Alias_Applied=False
```

- [ ] **Step 3: Write RED overlap fail-closed test**

If GLS and ALIVUS intervals overlap while sharing `ALIVUS.NS`, fail before any download with `PROVIDER_ALIAS_MEMBERSHIP_OVERLAP`.

- [ ] **Step 4: Implement this exact execution order**

```text
select membership intervals overlapping PRIMARY_START..PRIMARY_END
resolve every PriceIdentity
validate shared-provider interval overlap
group by Provider + Provider_Ticker
download each unique provider ticker exactly once
validate provider dates and duplicate dates
copy/tag the same downloaded frame to each associated research symbol
download benchmark exactly once
return stock snapshot, benchmark snapshot, identity audit
```

Retain the full downloaded provider range on each research-symbol copy; PIT membership independently controls event eligibility.

- [ ] **Step 5: Fail on stock snapshot ambiguity**

Require:

```text
no duplicate Symbol + Date
Provider_Ticker nonblank
Membership_Yahoo_Ticker nonblank
all dates within PRICE_START <= Date < PRICE_END_EXCLUSIVE
```

Do not silently deduplicate.

- [ ] **Step 6: Verify and commit**

```bash
cd "Swing Trading"
python -m pytest -q \
  "research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py" \
  "research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git add "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git commit -m "fix: preserve E1 identity across provider symbol changes"
```

---

### Task 3: Freeze and fingerprint price-identity provenance

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `constants.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `tests/test_end_to_end.py`

**New required Stage A artifact:** `input/e1_price_identity_audit.csv`

Columns exactly:

```text
Research_Symbol
Membership_Yahoo_Ticker
Provider
Provider_Ticker
Alias_Applied
Security_ISIN
Identity_Effective_Date
Identity_Source_URL
Reason
Member_From
Member_To
Provider_Data_Min
Provider_Data_Max
Provider_Row_Count
Active_Interval_Row_Count
Coverage_Status
Violation
```

Allowed `Coverage_Status` values:

```text
OK
NO_PROVIDER_DATA_IN_ACTIVE_INTERVAL
```

- [ ] **Step 1: Write RED provenance assertions**

```python
gls = audit.loc[audit["Research_Symbol"].eq("GLS")].iloc[0]
assert gls["Provider_Ticker"] == "ALIVUS.NS"
assert bool(gls["Alias_Applied"])
assert gls["Security_ISIN"] == "INE03Q201024"
assert gls["Identity_Source_URL"].endswith("CML66114.pdf")
assert gls["Coverage_Status"] == "OK"
assert gls["Violation"] == ""
```

- [ ] **Step 2: Add active-interval coverage failure test**

If `ALIVUS.NS` has data overall but zero valid rows during GLS's PIT active interval, emit:

```text
Coverage_Status=NO_PROVIDER_DATA_IN_ACTIVE_INTERVAL
Violation=PRICE_PROVIDER_ACTIVE_INTERVAL_EMPTY
```

and fail Stage A before final manifest creation. Do not require every market day here; Stage B already handles individual missing execution Opens.

- [ ] **Step 3: Persist audit and required-input declaration**

Write `e1_price_identity_audit.csv` before `write_manifest()` and add it to `REQUIRED_INPUT_ARTIFACTS`.

- [ ] **Step 4: Fingerprint alias registry**

Add a manifest fingerprint for `price_provider_aliases.csv` using its exact SHA256 and note:

```text
provider identity registry; acquisition provenance only
```

The generated `e1_price_identity_audit.csv` is hashed as a normal input artifact.

- [ ] **Step 5: Prove Stage B never resolves aliases or accesses network**

Extend `test_end_to_end.py` with a prebuilt frozen input package. Patch network/provider functions to raise if called, run the validator, and assert no provider function is invoked.

- [ ] **Step 6: Verify and commit**

```bash
cd "Swing Trading"
python -m pytest -q \
  "research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" \
  "research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py"
git add "research/swing/e1_positive_earnings_surprise_drift"
git commit -m "research: audit E1 frozen price identities"
```

---

### Task 4: Add a hard GLS/ALIVUS price-identity smoke gate

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `README.md`

**Exact contract:**

```text
run_price_identity_smoke(
    work_dir: pathlib.Path | str,
    downloader: Callable[[str, str, str], pandas.DataFrame] = download_adjusted_prices,
) -> dict[str, object]
```

Add CLI flag `--price-smoke`; write `price_identity_smoke.csv`; exit `0` only when every gate passes, otherwise exit `2`.

- [ ] **Step 1: Encode mandatory smoke gates**

```text
GLS membership ticker GLS.NS resolves to ALIVUS.NS via the configured official alias
GLS ISIN == INE03Q201024
GLS Identity_Source_URL == NSE CML66114 URL
ALIVUS membership ticker ALIVUS.NS resolves to ALIVUS.NS without alias
GLS and ALIVUS E1 membership intervals do not overlap
ALIVUS.NS download succeeds
provider data has >=1 valid row during GLS active interval
provider data has >=1 valid row during ALIVUS active interval
ALIVUS.NS downloaded exactly once
GLS.NS never requested
GLS.BO never requested
```

- [ ] **Step 2: Write PASS/FAIL unit tests**

PASS: one ALIVUS.NS frame spans both intervals.

FAIL separately for:

```text
no GLS-era provider rows
missing/invalid official alias provenance
overlapping GLS/ALIVUS PIT intervals
```

- [ ] **Step 3: Keep smoke scopes separate**

Existing `--smoke` remains official earnings-source-only. `--price-smoke` uses membership + aliases + market downloader only; it must not acquire filings, compute SUE, construct trades, or inspect returns.

- [ ] **Step 4: Document command**

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --price-smoke \
  --work-dir .e1-price-identity-smoke
```

- [ ] **Step 5: Run real price smoke**

Do not proceed to full Stage A unless the real command exits 0 and `price_identity_smoke.csv` confirms GLS/ALIVUS both use provider `ALIVUS.NS` while retaining distinct research symbols.

- [ ] **Step 6: Verify and commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
git add "research/swing/e1_positive_earnings_surprise_drift"
git commit -m "test: gate E1 on price identity continuity"
```

---

### Task 5: Resume and verify the full frozen Stage A package

**Files:** generated `input/*.csv`; temporary `.e1-stage-a-work-v2/` only.

- [ ] **Step 1: Run fresh suites after final code change**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
python -m pytest -q research/swing
```

Record exact counts and exit codes. Previous `90 / 336` counts are stale.

- [ ] **Step 2: Re-run both acquisition smoke gates**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --smoke \
  --work-dir .e1-stage-a-smoke-v2

python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --price-smoke \
  --work-dir .e1-price-identity-smoke
```

Both must exit 0.

- [ ] **Step 3: Resume full Stage A**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --work-dir .e1-stage-a-work-v2
```

Keep using only hash-valid/reusable v2 filing/EPS checkpoints. Rebuild final price snapshots with current price-identity rules.

- [ ] **Step 4: Fail closed on any next failed market ticker**

Only this sequence is allowed:

```text
verify whether an official symbol/name continuity event exists
if yes -> add official-provenance alias + regression
if no -> stop with market-data integrity failure
```

Forbidden: `.BO` guessing, universe exclusion, PIT-date edits, provider switching for individual failures, current-name guesses without official evidence, or silent omission.

- [ ] **Step 5: Verify Stage A before inspecting strategy returns**

Require:

```text
all REQUIRED_INPUT_ARTIFACTS present
manifest verification: zero hash/row-count violations
price identity audit: zero violations
no PROVIDER_ALIAS_MEMBERSHIP_OVERLAP
no PRICE_PROVIDER_ACTIVE_INTERVAL_EMPTY
PIT membership fingerprint matches
price_provider_aliases.csv fingerprint matches
RELIANCE bonus sentinel remains present
stock snapshot has no duplicate Symbol+Date
benchmark has no duplicate Date
```

Technical EPS coverage remains the frozen >=95% gate; if it is below 95%, Stage B must end INVALID rather than changing the threshold.

---

### Task 6: Run Stage B offline unchanged and record the actual E1 verdict

**Files:** generated `output/*`; PR description after verification.

- [ ] **Step 1: Run formal validator offline**

```bash
cd "Swing Trading"
python "research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

No yfinance, alias resolution, NSE/BSE client, or network path may be called by Stage B.

- [ ] **Step 2: Inspect authoritative artifacts**

```text
output/e1_integrity_audit.csv
output/e1_source_coverage.csv
output/e1_validation_gates.csv
output/research_report.md
```

Frozen status precedence:

```text
systemic integrity/source failure -> INVALID_RESEARCH_RUN
clean but insufficient sample -> INSUFFICIENT_EVIDENCE
sufficient clean run + all mandatory gates -> PASS
sufficient clean run + any mandatory strategy gate fails -> FAIL
```

- [ ] **Step 3: Do not tune after seeing results**

No changes to SUE threshold/history, cohorts, hold, entry, friction, benchmark, stops/targets, market regime, RS/SMA/momentum, sector/gap filters, or sample window.

A later code change is allowed only for a separately demonstrated integrity defect with a regression test.

- [ ] **Step 4: Commit reproducibility evidence**

```bash
git add "research/swing/e1_positive_earnings_surprise_drift/input" \
        "research/swing/e1_positive_earnings_surprise_drift/output" \
        "research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "research: complete frozen E1 validation"
```

If bulk price snapshots exceed repo policy, do not silently omit provenance: keep manifest hashes, exact immutable storage location, identity audit, and formal outputs.

- [ ] **Step 5: Update PR #36 only with fresh evidence**

Report:

```text
fresh E1 test count
fresh full research-suite count
source-smoke status
price-identity-smoke status
Stage A manifest/integrity verification
technical EPS coverage
formal FINAL_STATUS
```

The generated `FINAL_STATUS` is the only E1 verdict.

---

## Final Review Checklist

```text
[ ] PIT Nifty500 membership file unchanged.
[ ] GLS remains research symbol GLS; ALIVUS remains research symbol ALIVUS.
[ ] GLS resolves to ALIVUS.NS only via price_provider_aliases.csv.
[ ] Alias carries official NSE CML66114 provenance and ISIN INE03Q201024.
[ ] No fuzzy/automatic/.BO fallback.
[ ] Shared ALIVUS.NS is permitted only with non-overlapping PIT intervals.
[ ] ALIVUS.NS downloaded once and expanded deterministically to GLS/ALIVUS research identities.
[ ] e1_price_identity_audit.csv preserves membership ticker, provider ticker, provenance, interval and coverage.
[ ] Alias registry and price identity audit fingerprinted in manifest.
[ ] Valid v2 filing/EPS checkpoints remain reusable.
[ ] Source smoke PASS.
[ ] Price-identity smoke PASS against real provider.
[ ] Full Stage A completes with no silent missing symbol or duplicate Symbol+Date.
[ ] Stage B runs network-free and unchanged.
[ ] Fresh E1/full-suite tests recorded after final changes.
[ ] Actual FINAL_STATUS generated and reported without strategy tuning.
```

If official continuity cannot be proven or the verified alias lacks data in the relevant PIT interval, stop and report a market-data integrity failure. Do not rescue the run by excluding the security or changing E1.