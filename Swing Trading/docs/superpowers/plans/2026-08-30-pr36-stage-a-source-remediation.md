# PR #36 E1 Stage A Source Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make E1 Stage A reliably acquire and parse the official NSE/BSE earnings and corporate-action data required by the frozen experiment, invalidate stale failed checkpoints, pass a hard real-source smoke gate, and only then complete the full frozen Stage A -> unchanged Stage B validation.

**Architecture:** Keep the approved two-stage design unchanged. Stage A remains the only networked layer; Stage B remains fully offline. Fix only transport, official-response normalization, EPS/iXBRL parsing, corporate-action parsing, checkpoint validity, and source-only acceptance gates. Treat the current smoke result (`493 filings, 0 EPS, 0 corporate actions, 282 audit rows`) as a failed source preflight, never as usable E1 evidence.

**Tech Stack:** Python 3, pandas, numpy, requests, yfinance, `xml.etree.ElementTree`, `html.parser`, pytest. **Do not add a new parsing dependency in this remediation.**

**Spec:** `Swing Trading/docs/superpowers/specs/2026-08-29-e1-positive-earnings-surprise-drift-design.md`

**Previous remediation plan:** `Swing Trading/docs/superpowers/plans/2026-08-29-pr36-e1-integrity-remediation.md`

**PR:** `https://github.com/krishna916/Financial/pull/36`

**Blocking re-review:** `https://github.com/krishna916/Financial/pull/36#pullrequestreview-5058789926`

## Global Constraints

- This is **source-integrity remediation only**. Do not change the E1 hypothesis, event window, source cutoff, SUE formula/history length, cohort thresholds, 40-session hold, friction, benchmark/control mechanics, or PASS/FAIL gates.
- Primary event window remains `2023-08-01..2026-06-30`; source cutoff remains `2026-08-25`.
- Official NSE/BSE filings remain the earnings/event source of truth.
- Stage A must not inspect post-event returns, SUE, cohorts, or profitability while deciding whether source data is valid.
- Stage B must remain network-free and consume only the final frozen snapshot/manifest.
- A smoke command returning exit code 0 is **not** sufficient. Smoke must satisfy the exact semantic gates in Task 6.
- Existing checkpoint format/version `1` is untrusted because failed acquisitions/parses were persisted as `Complete: true`; it must never be reused after this remediation.
- Do not resume the old 158 symbol checkpoints. Rebuild them under checkpoint schema v2 after source/parser fixes.
- Known source sentinel: RELIANCE has an official `1:1` bonus with ex-date `2024-10-28`; smoke must recover it with `Share_Count_Factor == 2.0`.
- No browser automation, OCR, third-party earnings database, analyst consensus, or generic financial-data platform.

## Files

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/
├── source_clients.py
├── xbrl_eps.py
├── build_e1_source_snapshot.py
├── README.md
├── tests/
│   ├── fixtures/
│   │   ├── nse_integrated_real_ixbrl.html
│   │   ├── nse_corporate_actions_reliance.json
│   │   └── bse_security_master_sample.json
│   ├── test_xbrl_eps.py
│   ├── test_source_clients.py
│   └── test_source_snapshot.py
└── input/              # written only by a completed full Stage A run
```

Real-source fixtures must be minimal extracts of actual official responses. Do not commit bulk downloads, temporary raw bodies, or checkpoint directories.

---

### Task 1: Separate transport failures, unsupported payloads, and missing EPS facts

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `source_clients.py`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**

Add exactly this immutable payload type in `build_e1_source_snapshot.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SourcePayload:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    payload_kind: str  # "xml", "ixbrl_html", or "unsupported"
    body_bytes: bytes
```

Add:

```python
def fetch_machine_payload(record: dict[str, object], session: requests.Session, timeout: float = 30.0) -> SourcePayload:
    ...
```

Stable audit codes introduced by this task:

```text
EPS_PAYLOAD_HTTP_ERROR
EPS_PAYLOAD_UNSUPPORTED_FORMAT
EPS_FACT_NOT_FOUND
BSE_SOURCE_NON_JSON
```

- [ ] **Step 1: Write RED transport-vs-parser regressions**

Use fake responses in `test_source_snapshot.py`:

```python
payload = fetch_machine_payload(record_with_valid_ixbrl_url, fake_200_html_session)
assert payload.status_code == 200
assert payload.payload_kind == "ixbrl_html"

with pytest.raises(ValueError, match="EPS_PAYLOAD_HTTP_ERROR"):
    fetch_machine_payload(record_with_valid_ixbrl_url, fake_403_session)
```

Also assert a 200 plain-text/non-XBRL body produces `payload_kind == "unsupported"`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "payload"
```

- [ ] **Step 3: Implement URL normalization and payload classification**

Rules:

```text
absolute https NSE/BSE URL -> use unchanged
relative NSE filing URL -> resolve only against https://www.nseindia.com or https://nsearchives.nseindia.com according to the source URL/origin
relative BSE filing URL -> resolve only against https://www.bseindia.com or https://api.bseindia.com according to the source URL/origin
unknown/non-http scheme -> EPS_PAYLOAD_UNSUPPORTED_FORMAT
HTTP status != 200 -> EPS_PAYLOAD_HTTP_ERROR
XML/XBRL content -> payload_kind="xml"
HTML/XHTML containing ix:* facts -> payload_kind="ixbrl_html"
otherwise -> payload_kind="unsupported"
```

Do not write `body_bytes` into final CSV evidence.

- [ ] **Step 4: Replace generic `EPS_PARSE_ERROR` aggregation**

When `_fetch_eps` cannot produce a value:

```text
transport failure -> EPS_PAYLOAD_HTTP_ERROR
unsupported body -> EPS_PAYLOAD_UNSUPPORTED_FORMAT
successfully parsed XBRL/iXBRL but target fact absent -> EPS_FACT_NOT_FOUND
```

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift"
git commit -m "fix: classify E1 source acquisition failures"
```

---

### Task 2: Parse the actual NSE integrated/iXBRL EPS representation

**Files:**
- Modify: `xbrl_eps.py`
- Modify: `build_e1_source_snapshot.py`
- Create: `tests/fixtures/nse_integrated_real_ixbrl.html`
- Modify: `tests/test_xbrl_eps.py`

**Interfaces:**

Keep the existing public signature unchanged:

```python
def extract_basic_eps_continuing(payload: bytes, period_end: pd.Timestamp, basis: str) -> float | None:
    ...
```

Add internal helpers with these exact responsibilities:

```python
def _extract_contexts_from_xml(payload: bytes) -> dict[str, dict[str, object]]: ...
def _extract_contexts_from_ixbrl(payload: bytes) -> dict[str, dict[str, object]]: ...
def _extract_eps_candidates(payload: bytes, payload_kind: str) -> list[dict[str, object]]: ...
```

- [ ] **Step 1: Capture one minimal real NSE integrated filing fixture**

From a RELIANCE/TCS/INFY filing that currently fails in smoke, save the smallest official inline-XBRL/XHTML fragment that still contains:

```text
target Basic EPS continuing-operations fact
its context
period start/end
reporting-basis dimension/member
fact numeric value
namespace declarations required to interpret the above
```

Record the original official filing URL in `test_xbrl_eps.py` as `REAL_FIXTURE_SOURCE_URL`.

- [ ] **Step 2: Write RED real-format tests**

```python
def test_extract_basic_eps_from_real_nse_integrated_ixbrl():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_integrated_real_ixbrl.html").read_bytes(),
        REAL_PERIOD_END,
        REAL_BASIS,
    )
    assert value == pytest.approx(REAL_BASIC_CONTINUING_EPS)
```

Add two negative cases:

```text
wrong reporting basis -> None
YTD/annual context for same end date -> not selected
```

- [ ] **Step 3: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_xbrl_eps.py" -k "real_nse"
```

- [ ] **Step 4: Implement dual XML/inline-XBRL extraction**

Selection must remain exactly:

```text
approved Basic-EPS-continuing concept
AND not diluted
AND context end == requested period end
AND one-quarter duration, not YTD/year
AND context basis == requested CONSOLIDATED/STANDALONE
AND finite numeric value
```

If multiple remaining candidates disagree beyond the frozen EPS tolerance (`Rs 0.01 OR 0.5%`), return no value and surface `EPS_FACT_AMBIGUOUS` from the caller. Do not select the first candidate arbitrarily.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_xbrl_eps.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/xbrl_eps.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: parse real NSE integrated EPS filings"
```

---

### Task 3: Make BSE identifier/result acquisition fail explicitly and reproducibly

**Files:**
- Modify: `source_clients.py`
- Create: `tests/fixtures/bse_security_master_sample.json`
- Modify: `tests/test_source_clients.py`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**

Keep:

```python
BseResultsClient.resolve_identifier(symbol: str) -> dict[str, str]
BseResultsClient.list_results(symbol: str) -> list[dict[str, object]]
```

Add to `_OfficialResultsClient`:

```python
def _get_json_checked(self, url: str, params: dict[str, object] | None = None) -> object:
    ...
```

`_get_json_checked` must raise `BseIdentifierError("BSE_SOURCE_NON_JSON", symbol)` through the BSE call path when an HTTP-200 response is HTML/non-JSON.

- [ ] **Step 1: Capture a minimal actual BSE security-master fixture**

Use one smoke symbol. Preserve exact top-level nesting plus the fields containing BSE scrip code and scrip ID/symbol.

- [ ] **Step 2: Write RED identity and blocked-response tests**

```python
identity = resolve_bse_identifier("RELIANCE", fixture_records, source_url="official-fixture")
assert identity["BSE_Scrip_Code"].isdigit()
assert identity["BSE_Scrip_ID"]

with pytest.raises(BseIdentifierError, match="BSE_SOURCE_NON_JSON"):
    client_with_html_200.resolve_identifier("RELIANCE")
```

Also test HTTP 429 is retried according to the existing retry limit and ultimately fails visibly if retries exhaust.

- [ ] **Step 3: Implement only the request flow required by the observed official endpoint**

Set the minimum normal browser headers/referrer/cookie bootstrap demonstrated necessary by the live BSE request. No Selenium/browser automation. Validate response type before `.json()`.

- [ ] **Step 4: Make BSE resolution a smoke gate**

For each smoke symbol, exactly one BSE identifier must resolve. Any `BSE_SOURCE_ERROR`, `BSE_SOURCE_NON_JSON`, `BSE_IDENTIFIER_UNRESOLVED`, or `BSE_IDENTIFIER_AMBIGUOUS` makes smoke FAIL.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/source_clients.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: harden E1 BSE source acquisition"
```

---

### Task 4: Prove corporate-action acquisition using RELIANCE's 2024 bonus

**Files:**
- Modify: `source_clients.py`
- Modify: `build_e1_source_snapshot.py`
- Create: `tests/fixtures/nse_corporate_actions_reliance.json`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**

Keep:

```python
def _normalize_action(record: dict[str, object], symbol: str) -> dict[str, object] | None:
    ...
```

The normalized sentinel must be:

```python
{
    "Symbol": "RELIANCE",
    "Action_Type": "BONUS",
    "Old_Shares": 1.0,
    "Bonus_Shares": 1.0,
    "New_Shares": 2.0,
    "Share_Count_Factor": 2.0,
    "Ex_Date": pd.Timestamp("2024-10-28"),
}
```

- [ ] **Step 1: Capture a minimal actual NSE corporate-action response fixture**

Preserve the real top-level nesting and exact field names for the RELIANCE bonus record.

- [ ] **Step 2: Write RED fixture regression**

```python
rows = records_from_fixture(...)
action = next(_normalize_action(row, "RELIANCE") for row in rows if is_target_bonus(row))
assert action["Ex_Date"] == pd.Timestamp("2024-10-28")
assert action["Share_Count_Factor"] == pytest.approx(2.0)
```

- [ ] **Step 3: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "reliance and bonus"
```

- [ ] **Step 4: Map the observed official fields**

Retain these share-count formulas:

```text
split/consolidation: factor = new_shares / old_shares
bonus B:A: old=A, bonus=B, new=A+B, factor=(A+B)/A
```

Do not infer a ratio if official action text cannot be parsed; emit `UNPARSEABLE_CORPORATE_ACTION_RATIO`.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "action or bonus"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/source_clients.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: validate E1 corporate actions from official data"
```

---

### Task 5: Reject stale v1 checkpoints and version parser/source semantics

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `README.md`

**Interfaces:**

Add exactly:

```python
CHECKPOINT_SCHEMA_VERSION = 2
SOURCE_NORMALIZER_VERSION = 2
EPS_PARSER_VERSION = 2

TRANSIENT_CHECKPOINT_VIOLATIONS = {
    "NSE_SOURCE_ERROR",
    "BSE_SOURCE_ERROR",
    "BSE_SOURCE_NON_JSON",
    "EPS_PAYLOAD_HTTP_ERROR",
    "CORPORATE_ACTION_SOURCE_ERROR",
}
```

Checkpoint metadata must contain:

```json
{
  "Checkpoint_Schema_Version": 2,
  "Source_Normalizer_Version": 2,
  "EPS_Parser_Version": 2,
  "Symbol": "RELIANCE",
  "Source_Cutoff": "2026-08-25",
  "Acquisition_Complete": true,
  "Reusable": true,
  "Artifacts": {}
}
```

- [ ] **Step 1: Write RED stale-version test**

Construct a hash-valid old metadata file with `Checkpoint_Version: 1` and `Complete: true`. Assert `_read_symbol_checkpoint(...) is None`.

- [ ] **Step 2: Write RED transient-error test**

Write a v2 checkpoint with `NSE_SOURCE_ERROR` in the audit. Assert metadata has `Reusable: false` and the next call reacquires rather than reuses it.

- [ ] **Step 3: Implement exact reuse rules**

A checkpoint is reusable only when all are true:

```text
schema/source-normalizer/EPS-parser versions match current constants
Symbol and Source_Cutoff match
Acquisition_Complete == true
Reusable == true
all artifact hashes and row counts match
no TRANSIENT_CHECKPOINT_VIOLATIONS are present
```

Deterministic `EPS_FACT_NOT_FOUND` rows may be cached only under the matching current `EPS_PARSER_VERSION`.

- [ ] **Step 4: Document clean v2 work directories**

README commands must use:

```text
.e1-stage-a-smoke-v2
.e1-stage-a-work-v2
```

and explicitly state that the previous checkpoint directory must not be reused.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "checkpoint"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "fix: invalidate stale E1 Stage A checkpoints"
```

---

### Task 6: Turn the three-symbol live smoke into a hard semantic acceptance gate

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `README.md`

**Interfaces:**

Add:

```python
def evaluate_source_smoke(
    filings: pd.DataFrame,
    eps: pd.DataFrame,
    actions: pd.DataFrame,
    audit: pd.DataFrame,
    symbols: tuple[str, ...] = ("RELIANCE", "TCS", "INFY"),
) -> tuple[str, pd.DataFrame]:
    ...
```

`run_source_smoke()` must write `smoke_validation.csv` and return `Smoke_Status`. CLI `--smoke` must exit `2` when status is not PASS.

- [ ] **Step 1: Encode these mandatory smoke gates exactly**

```text
for each RELIANCE/TCS/INFY:
  filing rows > 0
  resolved EPS rows > 0
  at least one reporting basis has 13 consecutive quarterly EPS observations usable by basis_chain_status
  exactly one BSE identity resolved

across smoke:
  no TRANSIENT_CHECKPOINT_VIOLATIONS
  RELIANCE action contains BONUS on 2024-10-28 with Share_Count_Factor == 2.0
```

`EPS_FACT_NOT_FOUND` may remain for non-target/annual contexts; it is reported but is not itself a smoke failure if the 13-quarter chain gate passes.

- [ ] **Step 2: Write PASS and FAIL regressions**

One synthetic package satisfies every gate and returns PASS. Another reproduces the current shape (`filings > 0`, `eps == 0`, `actions == 0`) and returns FAIL.

- [ ] **Step 3: Run tests**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "smoke"
```

- [ ] **Step 4: Run the real smoke from a fresh v2 directory**

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --smoke \
  --work-dir .e1-stage-a-smoke-v2
```

Do not proceed unless the command exits `0` and `smoke_validation.csv` shows every mandatory gate PASS.

- [ ] **Step 5: If live smoke fails, stop**

For each failed gate, add a regression from the actual failing official response and repair only that source contract. Do **not** start a full-universe acquisition while smoke is FAIL.

- [ ] **Step 6: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift"
git commit -m "test: gate E1 Stage A on real official-source smoke"
```

---

### Task 7: Complete Stage A, verify source coverage, and run Stage B unchanged

**Files:**
- Generated: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input/*.csv`
- Generated: `Swing Trading/research/swing/e1_positive_earnings_surprise_drift/output/*`
- Modify: PR description only after fresh verification evidence exists

- [ ] **Step 1: Run fresh test suites after the final source-code commit**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
python -m pytest -q research/swing
```

Record exact exit codes and pass/fail counts. Previous `64/310` counts are stale after source changes.

- [ ] **Step 2: Run full Stage A with fresh v2 checkpoints**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --work-dir .e1-stage-a-work-v2
```

Do not impose an arbitrary five-minute stop. Resume only hash-valid/reusable v2 checkpoints until final `input/` artifacts and manifest are produced.

- [ ] **Step 3: Verify frozen Stage A before Stage B**

Required evidence:

```text
all required Stage A input artifacts exist
manifest hash verification has zero violations
no transient/systemic source errors remain in e1_source_build_audit.csv
primary-window machine-readable EPS resolution >= 95%
PIT membership fingerprint matches manifest
RELIANCE 2024-10-28 bonus factor 2.0 exists in corporate-actions snapshot
```

If coverage is `<95%`, keep the frozen outcome `INVALID_RESEARCH_RUN`. Do not lower the gate or substitute third-party EPS data.

- [ ] **Step 4: Run Stage B offline and unchanged**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

Once outcomes are visible, do not change SUE, filters, holding period, friction, controls, benchmark, or strategy gates. A later code change is allowed only for a separately demonstrated integrity defect with a regression test.

- [ ] **Step 5: Verify the formal evidence package**

Inspect:

```text
e1_integrity_audit.csv
e1_source_coverage.csv
e1_validation_gates.csv
research_report.md
```

Status precedence remains:

```text
systemic integrity/source failure -> INVALID_RESEARCH_RUN
clean but insufficient frozen sample -> INSUFFICIENT_EVIDENCE
sufficient clean run + all mandatory gates -> PASS
sufficient clean run + any mandatory strategy gate fails -> FAIL
```

- [ ] **Step 6: Commit reproducibility evidence**

Commit the frozen inputs/outputs if repository size/policy permits. If bulk frozen inputs are intentionally stored outside Git, commit the manifest, hashes, source audit, validation outputs, and the exact immutable storage location; do not omit provenance silently.

Suggested commit:

```bash
git add "research/swing/e1_positive_earnings_surprise_drift/input" \
        "research/swing/e1_positive_earnings_surprise_drift/output" \
        "research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "research: complete frozen E1 Stage A and validation"
```

---

## Final review checklist

```text
[ ] v1 checkpoints are rejected; smoke/full runs use fresh v2 directories.
[ ] Real NSE integrated/iXBRL fixture resolves quarterly Basic EPS continuing operations.
[ ] BSE identity/result source works for all three smoke symbols or smoke fails explicitly.
[ ] RELIANCE 2024-10-28 1:1 bonus is recovered with factor 2.0.
[ ] Old 493-filings / 0-EPS / 0-actions shape produces Smoke_Status=FAIL and non-zero CLI exit.
[ ] Live smoke has a usable 13-quarter EPS basis chain for RELIANCE, TCS, and INFY.
[ ] Full Stage A finishes and writes a verified manifest.
[ ] Technical EPS coverage is >=95%, otherwise formal status is INVALID without threshold changes.
[ ] Stage B is rerun offline with unchanged strategy logic.
[ ] Fresh E1 and full-research test results are recorded after final source changes.
[ ] No strategy parameter changed during remediation.
```

If the first six checks are not satisfied, do not run the full historical experiment and do not request merge.