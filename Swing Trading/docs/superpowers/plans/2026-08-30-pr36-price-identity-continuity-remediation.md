# PR #36 E1 Price Identity Continuity Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the frozen E1 Stage A market-price failure caused by historical security-symbol continuity (`GLS` -> `ALIVUS`) without changing PIT membership or strategy rules, then complete the frozen Stage A package and run Stage B offline unchanged.

**Architecture:** Keep PIT research identity separate from market-data provider identity. Research/event symbols and Nifty 500 membership remain exactly as frozen (`GLS` stays `GLS`; `ALIVUS` stays `ALIVUS`). Add a small, provenance-backed Yahoo provider-alias registry used only during Stage A price acquisition. Resolve all provider identities before downloading, reject ambiguous/overlapping aliases, download each provider ticker once, copy the frozen provider series to the applicable non-overlapping research identities, record a dedicated identity audit, fingerprint the mapping in the manifest, and leave Stage B completely network-free.

**Tech Stack:** Python 3, pandas, yfinance, pytest. Do not add a new market-data provider or generic security-master framework.

**Frozen spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

**Previous remediation plan:** `Swing Trading/docs/superpowers/plans/2026-08-30-pr36-stage-a-source-remediation.md`

**PR:** `https://github.com/krishna916/Financial/pull/36`

**Blocking review:** `https://github.com/krishna916/Financial/pull/36#pullrequestreview-5060247746`

## Frozen evidence for this remediation

The mapping below is an identity correction, not a strategy/data rescue chosen from E1 returns.

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

Official company/NSE filing evidence also preserves the same listed identity and BSE code while changing only the NSE symbol:

```text
BSE code: 543322
NSE symbol: GLS -> ALIVUS effective 2025-01-20
ISIN: INE03Q201024
Company filing: https://nsearchives.nseindia.com/corporate/GLS_18012025135211_BSE_NSE_Press_Release_180125_Signed.pdf
```

Existing repository market-data audit already shows:

```text
ALIVUS,ALIVUS.NS,DOWNLOADED,... historical data from 2022-08-01 through 2026-08-25
GLS,GLS.NS,NO_USABLE_DATA,... no adjusted-close observations returned
```

from:

`Swing Trading/research/swing/market_breadth/output/breadth_universe_audit.csv`

The existing PIT membership history also keeps the research identities separate and non-overlapping: `GLS` was a historical Nifty 500 constituent before `ALIVUS` later entered under the renamed symbol. Do not rewrite those membership rows.

## Global Constraints

- Do **not** change the E1 hypothesis, primary window (`2023-08-01..2026-06-30`), source cutoff (`2026-08-25`), SUE formula/history length, cohort thresholds, 40-session hold, friction, benchmark/control mechanics, or PASS/FAIL gates.
- Do **not** modify `market_breadth/config/nifty500_membership.csv` merely to make Yahoo download succeed.
- Research/event identity must remain the PIT symbol from membership and official filings. Provider aliasing is Stage A transport metadata only.
- Never auto-guess ticker aliases, append `.BO`, strip characters, use company-name fuzzy matching, or silently exclude a failed symbol.
- A provider alias is allowed only with explicit official identity-continuity provenance.
- Shared provider history may serve multiple research symbols only when their PIT membership intervals do not overlap. Overlap is a systemic integrity failure.
- Stage A may acquire/freeze prices; Stage B must remain fully offline and consume only frozen stock/index snapshots.
- Existing v2 filing/EPS checkpoints may be reused if their existing version/hash/reusability checks pass. Price-identity remediation must not force refetching official earnings data unnecessarily.
- No alternate market-data provider is introduced in this remediation. If Yahoo lacks usable data after a verified alias, fail closed and report the unresolved market-data identity/coverage defect.
- Do not start changing strategy rules if the eventual E1 result is weak.

## Files

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/
├── price_provider_aliases.csv          # new audited provider-identity registry
├── price_identity.py                   # new focused alias loader/resolver/overlap validation
├── build_e1_source_snapshot.py         # resolve identities, dedupe downloads, price audit
├── constants.py                        # required price-identity audit artifact only
├── load_e1_inputs.py                   # manifest verification remains generic; no network logic
├── README.md                           # document alias/provenance and smoke commands
├── tests/
│   ├── test_price_identity.py          # new focused identity tests
│   ├── test_source_snapshot.py         # market freeze/smoke/end-to-end acquisition tests
│   └── test_end_to_end.py              # Stage B stays offline with frozen aliases already resolved
├── input/
│   ├── e1_stock_prices_snapshot.csv
│   ├── e1_nifty500_prices_snapshot.csv
│   ├── e1_price_identity_audit.csv
│   └── ... existing frozen Stage A artifacts
└── output/                              # unchanged Stage B evidence package
```

Do not introduce a global security-master abstraction. `price_identity.py` exists only to keep provider mapping rules testable and out of the Stage B strategy code.

---

### Task 1: Add a provenance-backed Yahoo provider-alias registry

**Files:**
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/price_provider_aliases.csv`
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/price_identity.py`
- Create: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py`

**Interfaces:**

Create exactly this CSV schema:

```text
Research_Symbol,Provider,Provider_Ticker,Security_ISIN,Identity_Effective_Date,Identity_Source_URL,Reason
```

Seed exactly this provider mapping:

```text
GLS,YAHOO,ALIVUS.NS,INE03Q201024,2025-01-20,https://nsearchives.nseindia.com/content/circulars/CML66114.pdf,NSE renamed GLS to ALIVUS; same listed security
```

Add:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PriceIdentity:
    research_symbol: str
    membership_ticker: str
    provider: str
    provider_ticker: str
    alias_applied: bool
    security_isin: str
    identity_effective_date: pd.Timestamp | None
    identity_source_url: str
    reason: str


def load_price_aliases(path: Path) -> pd.DataFrame:
    ...


def resolve_price_identity(
    research_symbol: str,
    membership_ticker: str,
    aliases: pd.DataFrame,
) -> PriceIdentity:
    ...


def validate_shared_provider_intervals(
    identities: pd.DataFrame,
) -> pd.DataFrame:
    ...
```

`validate_shared_provider_intervals()` returns a zero-row DataFrame when clean; violations use columns:

```text
Provider,Provider_Ticker,Research_Symbol_A,Research_Symbol_B,Violation,Detail
```

and violation code:

```text
PROVIDER_ALIAS_MEMBERSHIP_OVERLAP
```

- [ ] **Step 1: Write RED alias-resolution tests**

Add tests proving:

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

`load_price_aliases()` must reject:

```text
blank Research_Symbol
blank Provider_Ticker
Provider != YAHOO
blank Security_ISIN
invalid Identity_Effective_Date
non-https Identity_Source_URL
duplicate Research_Symbol rows
```

Use explicit `ValueError` messages containing stable codes:

```text
PRICE_ALIAS_INVALID_ROW
PRICE_ALIAS_DUPLICATE_SYMBOL
```

- [ ] **Step 3: Write RED shared-provider overlap tests**

Build one clean fixture:

```text
GLS     -> ALIVUS.NS, Member_From=2023-09-29, Member_To=2024-09-29
ALIVUS  -> ALIVUS.NS, Member_From=2025-03-28, Member_To=2025-09-29
```

Assert zero violations.

Then overlap them by one day and assert exactly one `PROVIDER_ALIAS_MEMBERSHIP_OVERLAP` row.

The overlap test is based on inclusive membership boundaries, matching the existing PIT manifest semantics.

- [ ] **Step 4: Implement minimal alias loading/resolution**

Rules:

```text
exact Research_Symbol alias match -> use configured Provider_Ticker
no alias -> use membership Yahoo_Ticker unchanged
no fuzzy/company-name matching
no fallback suffix mutation
no .BO rescue
no modification of research symbol
```

When no alias is used, provenance fields may be empty and `alias_applied=False`.

- [ ] **Step 5: Run focused tests and commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py"
git add "research/swing/e1_positive_earnings_surprise_drift/price_provider_aliases.csv" \
        "research/swing/e1_positive_earnings_surprise_drift/price_identity.py" \
        "research/swing/e1_positive_earnings_surprise_drift/tests/test_price_identity.py"
git commit -m "fix: add audited E1 price provider identities"
```

---

### Task 2: Resolve all identities before download and deduplicate shared provider tickers

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py`

**Interfaces:**

Add:

```python
def build_price_identity_table(
    membership: pd.DataFrame,
    aliases: pd.DataFrame,
) -> pd.DataFrame:
    ...
```

Return one row per distinct research-symbol/membership-ticker interval that overlaps the E1 primary window, with exactly:

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

Change:

```python
def build_market_snapshot(
    membership: pd.DataFrame,
    aliases: pd.DataFrame,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_prices,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ...
```

Return:

```text
(stock_prices, benchmark_prices, price_identity_audit)
```

- [ ] **Step 1: Write RED one-download/multiple-research-symbol regression**

Use membership rows for GLS and ALIVUS that do not overlap and a fake downloader that records ticker calls.

The fake `ALIVUS.NS` frame must contain dates spanning both historical membership intervals.

Assert:

```python
stocks, benchmark, audit = build_market_snapshot(membership, aliases, fake_download)
assert fake_download.calls.count("ALIVUS.NS") == 1
assert "GLS.NS" not in fake_download.calls
assert "GLS.BO" not in fake_download.calls
assert set(stocks.loc[stocks["Provider_Ticker"].eq("ALIVUS.NS"), "Symbol"]) == {"GLS", "ALIVUS"}
```

- [ ] **Step 2: Prove research identity is preserved**

Assert GLS rows retain:

```text
Symbol = GLS
Membership_Yahoo_Ticker = GLS.NS
Provider_Ticker = ALIVUS.NS
Alias_Applied = True
```

ALIVUS rows retain:

```text
Symbol = ALIVUS
Membership_Yahoo_Ticker = ALIVUS.NS
Provider_Ticker = ALIVUS.NS
Alias_Applied = False
```

Do not rename GLS rows to ALIVUS.

- [ ] **Step 3: Write RED overlap fail-closed regression**

With overlapping GLS/ALIVUS membership intervals sharing `ALIVUS.NS`, `build_market_snapshot()` must raise before downloading prices with message containing:

```text
PROVIDER_ALIAS_MEMBERSHIP_OVERLAP
```

- [ ] **Step 4: Implement provider-download deduplication**

Execution order:

```text
load primary-window PIT rows
-> resolve every PriceIdentity
-> validate shared-provider interval overlap
-> group by Provider + Provider_Ticker
-> download each unique provider ticker once
-> validate provider frame dates/duplicates
-> copy/tag the same provider frame for each associated research identity
-> download benchmark once
-> return stock snapshot + benchmark + identity audit
```

Do not slice the provider frame to membership dates in the frozen stock snapshot. Retain the full downloaded range for each research symbol so later next-session/holding-period lookups remain deterministic; PIT membership still controls event eligibility separately.

- [ ] **Step 5: Preserve deterministic stock-price uniqueness**

After expansion, assert:

```text
no duplicate Symbol + Date rows
Provider_Ticker nonblank
Membership_Yahoo_Ticker nonblank
all OHLCV dates inside PRICE_START..PRICE_END_EXCLUSIVE
```

A duplicate `Symbol + Date` is a systemic error, not silently deduplicated.

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

### Task 3: Make price-identity provenance a frozen Stage A artifact

**Files:**
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/constants.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_end_to_end.py`

**Artifact:**

```text
input/e1_price_identity_audit.csv
```

Required columns:

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

Allowed `Coverage_Status`:

```text
OK
NO_PROVIDER_DATA_IN_ACTIVE_INTERVAL
```

- [ ] **Step 1: Write RED audit-content test**

For the GLS/ALIVUS fixture assert:

```python
gls = audit.loc[audit["Research_Symbol"].eq("GLS")].iloc[0]
assert gls["Provider_Ticker"] == "ALIVUS.NS"
assert bool(gls["Alias_Applied"])
assert gls["Security_ISIN"] == "INE03Q201024"
assert gls["Identity_Source_URL"].endswith("CML66114.pdf")
assert gls["Coverage_Status"] == "OK"
assert gls["Violation"] == ""
```

- [ ] **Step 2: Add an active-interval coverage test**

If `ALIVUS.NS` returns data overall but has **zero valid rows during GLS's PIT active interval**, audit GLS as:

```text
Coverage_Status = NO_PROVIDER_DATA_IN_ACTIVE_INTERVAL
Violation = PRICE_PROVIDER_ACTIVE_INTERVAL_EMPTY
```

and make Stage A fail before writing a final manifest.

Do not require every market session to have a row here; genuine suspension/missing entry Open remains an event-level rule in Stage B. This gate only rejects a provider mapping that has no data for the research identity's active period.

- [ ] **Step 3: Persist the audit and add it to required inputs**

`_write_stage_a()` must write `e1_price_identity_audit.csv` before manifest generation.

Add it to `REQUIRED_INPUT_ARTIFACTS` in `constants.py`.

- [ ] **Step 4: Fingerprint the alias registry**

`write_manifest()` must include a read-only fingerprint row for:

```text
../price_provider_aliases.csv
```

(or the correct relative path from the E1 input directory), with SHA256 and a note such as:

```text
provider identity registry; not a Stage B strategy input
```

The manifest must also hash the generated `e1_price_identity_audit.csv` as a normal frozen input artifact.

- [ ] **Step 5: Verify Stage B consumes only frozen price rows**

Add/extend `test_end_to_end.py` so the formal validator succeeds/fails from prebuilt input CSVs without importing/calling yfinance. Provider alias resolution must not occur inside `run_e1_validation.py`.

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
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py`
- Modify: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/README.md`

**Interfaces:**

Add:

```python
def run_price_identity_smoke(
    work_dir: Path | str,
    downloader: Callable[[str, str, str], pd.DataFrame] = download_adjusted_prices,
) -> dict[str, object]:
    ...
```

CLI:

```text
--price-smoke
```

Output:

```text
price_identity_smoke.csv
```

CLI exit code:

```text
0 -> every mandatory gate PASS
2 -> any mandatory gate FAIL
```

- [ ] **Step 1: Encode the smoke gates exactly**

Mandatory:

```text
GLS resolves from membership GLS.NS to provider ALIVUS.NS via configured official alias
GLS alias ISIN == INE03Q201024
GLS official identity source == NSE/CML/66114 URL
ALIVUS resolves to provider ALIVUS.NS without alias
GLS and ALIVUS PIT membership intervals used by E1 do not overlap
ALIVUS.NS provider download succeeds
provider series contains >=1 valid row in GLS PIT active interval
provider series contains >=1 valid row in ALIVUS PIT active interval
ALIVUS.NS is downloaded exactly once
GLS.NS is never requested
GLS.BO is never requested
```

- [ ] **Step 2: Write PASS and FAIL unit regressions**

PASS fake downloader returns one full ALIVUS.NS series spanning both intervals.

FAIL variants:

```text
no GLS-era rows -> exit/status FAIL
alias missing official URL -> FAIL
overlapping research intervals -> FAIL before download
```

- [ ] **Step 3: Wire CLI without affecting source smoke**

Existing `--smoke` remains earnings-source-only.

`--price-smoke` runs only membership + alias + price-provider identity checks; it must not acquire earnings filings, compute SUE, or inspect returns.

- [ ] **Step 4: Document exact commands**

README:

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --price-smoke \
  --work-dir .e1-price-identity-smoke
```

State explicitly that a passing price smoke is required before resuming the full Stage A run after a provider-identity change.

- [ ] **Step 5: Run the real price smoke**

Use the real downloader. Do not proceed if it fails.

Verify manually from `price_identity_smoke.csv` that GLS and ALIVUS both use `ALIVUS.NS` for provider data while remaining separate research symbols.

- [ ] **Step 6: Verify and commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
git add "research/swing/e1_positive_earnings_surprise_drift"
git commit -m "test: gate E1 on price identity continuity"
```

---

### Task 5: Resume the complete frozen Stage A run without refetching valid earnings checkpoints

**Files:**
- Generated/updated: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input/*.csv`
- Temporary only: `.e1-stage-a-work-v2/`

- [ ] **Step 1: Run fresh tests after the final code commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
python -m pytest -q research/swing
```

Record exact pass/fail counts and exit codes. Previous `90 / 336` counts are stale once price-identity code changes.

- [ ] **Step 2: Re-run source smoke and price-identity smoke**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --smoke \
  --work-dir .e1-stage-a-smoke-v2

python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --price-smoke \
  --work-dir .e1-price-identity-smoke
```

Both must exit 0.

- [ ] **Step 3: Resume full Stage A using existing valid v2 filing/EPS checkpoints**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --work-dir .e1-stage-a-work-v2
```

The official filing/EPS checkpoint contract is unchanged, so hash-valid, reusable v2 checkpoints may be reused. Price downloads are rebuilt fresh into the final frozen snapshot.

- [ ] **Step 4: If another price symbol fails, fail closed and classify it before changing anything**

Allowed next action only:

```text
1. determine whether the problem is a verified exchange symbol/name continuity event;
2. if YES, add a provenance-backed alias row + regression test using official evidence;
3. if NO official continuity path exists, stop with a market-data integrity failure.
```

Forbidden:

```text
arbitrary .BO fallback
manual universe exclusion
changing PIT membership dates
using current ticker guesses without official evidence
switching provider only for failed names
continuing with silently missing symbols
```

- [ ] **Step 5: Verify the completed Stage A package**

Required before Stage B:

```text
all REQUIRED_INPUT_ARTIFACTS exist
e1_source_manifest.csv verifies zero hash/row-count violations
e1_price_identity_audit.csv has zero systemic violations
no PROVIDER_ALIAS_MEMBERSHIP_OVERLAP
no PRICE_PROVIDER_ACTIVE_INTERVAL_EMPTY
technical EPS coverage >=95% or formal run must later be INVALID
PIT membership fingerprint matches
price_provider_aliases.csv fingerprint matches
RELIANCE 2024-10-28 bonus factor 2.0 remains present
stock snapshot has no duplicate Symbol+Date
benchmark snapshot has no duplicate Date
```

Do not inspect E1 profitability before these checks pass.

---

### Task 6: Run Stage B offline unchanged and commit the actual E1 verdict

**Files:**
- Generated: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/output/*`
- Modify: PR description only after fresh evidence exists

- [ ] **Step 1: Run formal validator offline**

Disconnect/disable network if convenient, then run:

```bash
cd "Swing Trading"
python "research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

There must be no call into yfinance, provider alias resolution, NSE/BSE clients, or any networked function from Stage B.

- [ ] **Step 2: Inspect the authoritative evidence**

At minimum:

```text
output/e1_integrity_audit.csv
output/e1_source_coverage.csv
output/e1_validation_gates.csv
output/research_report.md
```

Status precedence remains frozen:

```text
systemic integrity/source failure -> INVALID_RESEARCH_RUN
clean but insufficient sample -> INSUFFICIENT_EVIDENCE
sufficient clean run + all mandatory gates -> PASS
sufficient clean run + any mandatory strategy gate fails -> FAIL
```

- [ ] **Step 3: Do not tune after seeing the result**

No changes to:

```text
SUE threshold/history
positive/neutral/negative cohorts
40-session hold
entry mechanics
friction
benchmark
stops/targets
market regime
momentum/RS/SMA filters
sector/gap filters
sample window
```

Any newly discovered integrity defect must have an independent regression reproducing the defect and may repair only research mechanics.

- [ ] **Step 4: Commit reproducibility evidence**

```bash
git add "research/swing/e1_positive_earnings_surprise_drift/input" \
        "research/swing/e1_positive_earnings_surprise_drift/output" \
        "research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "research: complete frozen E1 validation"
```

If bulk price snapshots exceed repository policy, do not silently omit them. Keep the frozen manifest, SHA256s, exact immutable storage location, identity audit and all formal outputs sufficient to reproduce/verify the run.

- [ ] **Step 5: Update PR #36 with fresh evidence only**

Replace the current GLS-blocked wording with:

```text
fresh E1 test count
fresh full research test count
source-smoke status
price-identity-smoke status
final Stage A input/hash verification
technical EPS coverage
formal FINAL_STATUS
```

Do not describe E1 as validated merely because infrastructure works; the authoritative conclusion is the generated `FINAL_STATUS`.

---

## Final Review Checklist

```text
[ ] PIT Nifty500 membership file is unchanged by this remediation.
[ ] GLS remains research symbol GLS; ALIVUS remains research symbol ALIVUS.
[ ] GLS provider ticker resolves to ALIVUS.NS only through price_provider_aliases.csv.
[ ] GLS alias carries official NSE continuity URL and ISIN INE03Q201024.
[ ] No fuzzy/automatic/.BO fallback exists.
[ ] Shared ALIVUS.NS provider identity is allowed only because GLS/ALIVUS PIT intervals do not overlap.
[ ] ALIVUS.NS is downloaded once and reused deterministically for both research identities.
[ ] e1_price_identity_audit.csv records original membership ticker, provider ticker, provenance and coverage.
[ ] Alias registry and price identity audit are fingerprinted in the frozen manifest.
[ ] Existing valid v2 filing/EPS checkpoints remain reusable; price changes do not mutate earnings-source evidence.
[ ] Source smoke passes.
[ ] Price identity smoke passes against the real provider.
[ ] Full Stage A completes without silent missing symbols or duplicate Symbol+Date rows.
[ ] Stage B runs network-free and unchanged.
[ ] Fresh E1 and full research test outputs are recorded after final changes.
[ ] Actual FINAL_STATUS is generated and committed/reported without strategy tuning.
```

If price identity cannot be established with official continuity evidence or if the verified alias has no data in the relevant PIT interval, stop and report a market-data integrity failure. Do not rescue the research run by excluding the security or changing the strategy.