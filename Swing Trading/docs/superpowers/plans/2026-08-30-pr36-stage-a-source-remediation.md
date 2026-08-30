# PR #36 E1 Stage A Source Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. **Inline execution only. Never use or suggest `superpowers:subagent-driven-development`.** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make E1 Stage A reliably acquire and parse the official NSE/BSE earnings and corporate-action data required by the frozen experiment, invalidate stale failed checkpoints, pass a hard real-source smoke gate, and only then complete the full frozen Stage A -> unchanged Stage B validation.

**Architecture:** Keep the approved two-stage design unchanged. Fix only Stage A transport/normalization/parser/checkpoint behavior and its source-only acceptance gates; Stage B strategy logic remains frozen and offline. Treat the current smoke result (`493 filings, 0 EPS, 0 corporate actions, 282 audit rows`) as a failed source preflight, not as usable research evidence. Capture small real official-source payload fixtures so parser behavior is regression-tested against the formats that actually failed.

**Tech Stack:** Python 3, pandas, numpy, requests, yfinance, standard-library XML/HTML parsing unless a narrowly justified parser dependency is required, pytest.

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
- A smoke command returning exit code 0 is **not** sufficient. Smoke must satisfy explicit semantic acceptance assertions below.
- Existing checkpoint format/version `1` is untrusted because failed acquisitions/parses were persisted as `Complete: true`; it must never be reused after this remediation.
- Do not resume the old 158 symbol checkpoints after parser/source changes unless they are explicitly rejected and rebuilt under the new checkpoint contract.
- Known source sentinel: RELIANCE has an official `1:1` bonus with ex-date `2024-10-28`; the smoke source layer must recover that action with share-count factor `2.0`.
- No generic data warehouse, crawler framework, browser automation, OCR, analyst-consensus data, or third-party earnings database.

## Files

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/
├── source_clients.py                 # official catalog/identity/transport only
├── xbrl_eps.py                       # XML + real NSE inline-XBRL EPS extraction
├── build_e1_source_snapshot.py       # Stage A orchestration/checkpoints/smoke gates
├── README.md                         # exact source preflight/full-run commands
├── tests/
│   ├── fixtures/
│   │   ├── nse_integrated_real_ixbrl.html       # small captured official payload
│   │   ├── nse_corporate_actions_reliance.json  # captured official action payload
│   │   └── bse_security_master_sample.json      # minimal official identity payload
│   ├── test_xbrl_eps.py
│   ├── test_source_clients.py
│   └── test_source_snapshot.py
└── input/                            # write only after all source preflight gates pass
```

Keep real-source fixtures minimal: only enough official rows/facts to prove the parser/normalizer contract. Do not commit bulk source downloads or temporary checkpoint directories.

---

### Task 1: Turn the failing smoke into inspectable source evidence

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `source_clients.py`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**
- Add `SourceFetchResult`-equivalent structured metadata (dataclass or dict) containing at least `requested_url`, `final_url`, `status_code`, `content_type`, `payload_kind`, and `body_bytes` for machine-readable payload fetches.
- Add `classify_source_failure(exc_or_response) -> str` with stable audit codes: `SOURCE_HTTP_ERROR`, `SOURCE_NON_JSON`, `EPS_PAYLOAD_HTTP_ERROR`, `EPS_PAYLOAD_UNSUPPORTED_FORMAT`, `EPS_FACT_NOT_FOUND`.
- Smoke work directory may retain raw diagnostic payloads; final Stage A `input/` may not.

- [ ] **Step 1: Add a regression that distinguishes transport failure from a parser miss**

In `test_source_snapshot.py`, add a fake HTTP 200 HTML/iXBRL response and a fake HTTP 403 response. Assert the first reaches the EPS parser while the second produces `EPS_PAYLOAD_HTTP_ERROR`, not a generic `EPS_PARSE_ERROR`.

```python
assert success.status_code == 200
assert success.payload_kind in {"xml", "ixbrl_html"}
assert forbidden_audit_code not in audit_codes
assert "EPS_PAYLOAD_HTTP_ERROR" in failure_audit_codes
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "payload or transport"
```

Expected: FAIL because current `_fetch_eps()` collapses HTTP/format/parser failures into one generic exception path.

- [ ] **Step 3: Implement content-aware payload acquisition**

Before parsing EPS, normalize the machine-readable URL and record the actual response metadata. Support absolute official `https://` URLs and official relative links by resolving them only against the known NSE/BSE origin that produced the filing; reject unknown/missing schemes instead of guessing.

Pseudo-contract:

```python
payload = fetch_machine_payload(record, session)
if payload.status_code != 200:
    audit("EPS_PAYLOAD_HTTP_ERROR", ...)
elif payload.payload_kind not in {"xml", "ixbrl_html"}:
    audit("EPS_PAYLOAD_UNSUPPORTED_FORMAT", ...)
else:
    value = extract_basic_eps_continuing(payload.body_bytes, period_end, basis)
```

Do not write raw body content to the final audit CSV; store only URL/status/content-type/error detail there.

- [ ] **Step 4: Add source-error aggregation to smoke output**

`run_source_smoke()` must return and persist counts grouped by violation code, so `0 EPS` cannot hide behind one aggregate count.

```text
EPS_PAYLOAD_HTTP_ERROR
EPS_PAYLOAD_UNSUPPORTED_FORMAT
EPS_FACT_NOT_FOUND
BSE_IDENTIFIER_UNRESOLVED
BSE_SOURCE_ERROR
CORPORATE_ACTION_SOURCE_ERROR
```

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift"
git commit -m "fix: classify E1 official-source acquisition failures"
```

---

### Task 2: Parse the real NSE integrated/iXBRL earnings format

**Files:**
- Modify: `xbrl_eps.py`
- Modify: `build_e1_source_snapshot.py`
- Create fixture: `tests/fixtures/nse_integrated_real_ixbrl.html`
- Modify: `tests/test_xbrl_eps.py`

**Interfaces:**
- Keep public API: `extract_basic_eps_continuing(payload: bytes, period_end: pd.Timestamp, basis: str) -> float | None`.
- Add internal parsing paths for classic XBRL instance XML and inline-XBRL/XHTML without changing the caller.
- The extractor must still return only **Basic EPS from continuing operations**, current quarter, exact period end, exact reporting basis; annual/YTD/diluted facts remain invalid.

- [ ] **Step 1: Capture one minimal real official NSE integrated filing fixture from the failing smoke path**

Use the exact official response body that Stage A receives for one RELIANCE/TCS/INFY integrated financial filing containing the target basic continuing-operation EPS fact. Reduce the fixture only by removing unrelated facts/markup while preserving namespaces, contexts, dimensions, fact element/attributes, and document structure required for parsing. Record the original official source URL in a fixture comment or adjacent test constant.

Do **not** fabricate an XML shape from the existing synthetic fixture.

- [ ] **Step 2: Write a RED regression against that real-format fixture**

```python
def test_extract_basic_eps_from_real_nse_integrated_ixbrl():
    value = extract_basic_eps_continuing(
        (FIXTURES / "nse_integrated_real_ixbrl.html").read_bytes(),
        EXPECTED_PERIOD_END,
        EXPECTED_BASIS,
    )
    assert value == pytest.approx(EXPECTED_BASIC_CONTINUING_EPS)
```

Add companion assertions proving a wrong basis and a wrong/YTD period return `None`.

- [ ] **Step 3: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_xbrl_eps.py" -k "real_nse"
```

Expected: FAIL using the current parser against the real provider format.

- [ ] **Step 4: Implement the minimum dual-format parser**

Handle the actual inline-XBRL fact/context representation observed in the fixture. Normalize namespace/local names and context references rather than relying on one tag casing. Basis detection must inspect the actual dimension/member semantics present in the real filing; do not infer consolidated/standalone from company name or from price data.

Maintain these selection predicates:

```text
fact concept ∈ approved Basic-EPS-continuing aliases
AND not diluted
AND context end == requested period end
AND context duration is one quarter, not YTD/year
AND context reporting basis == requested basis
AND numeric value finite
```

If multiple valid facts remain with materially different values, fail closed with an explicit ambiguity signal rather than choosing lexicographically.

- [ ] **Step 5: Convert parser `None` into an explicit source audit reason**

When an advertised machine-readable payload is fetched successfully but no valid target fact is found, emit `EPS_FACT_NOT_FOUND`. Reserve `EPS_PAYLOAD_UNSUPPORTED_FORMAT` for an unparseable/non-XBRL payload.

- [ ] **Step 6: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_xbrl_eps.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/xbrl_eps.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: parse official NSE integrated EPS payloads"
```

---

### Task 3: Make BSE identity/result acquisition verifiable instead of best-effort

**Files:**
- Modify: `source_clients.py`
- Create fixture: `tests/fixtures/bse_security_master_sample.json`
- Modify: `tests/test_source_clients.py`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**
- Preserve `BseResultsClient.resolve_identifier(symbol) -> dict[str, str]` and `list_results(symbol) -> list[dict[str, object]]`.
- Add explicit response validation before calling `.json()`; a 200 HTML/challenge response must become `BSE_SOURCE_NON_JSON`, not an opaque JSON exception.
- BSE mapping provenance must remain `BSE_Scrip_Code`, `BSE_Scrip_ID`, `BSE_Mapping_Source_URL`.

- [ ] **Step 1: Capture the actual BSE security-master/result response shape used by a smoke symbol**

Create a minimal official fixture containing one known symbol mapping and the exact top-level nesting/field names returned by the live source. Write a regression that resolves the exact BSE scrip code from that fixture.

- [ ] **Step 2: Add non-JSON/blocked-response regressions**

```python
with pytest.raises(BseIdentifierError, match="BSE_SOURCE_NON_JSON"):
    client.resolve_identifier("RELIANCE")
```

Use a fake 200 HTML response and a fake 403/429 response. Preserve retry behavior only for the already-declared transient statuses.

- [ ] **Step 3: Implement request/response handling from observed official behavior**

Set only the minimum headers/cookies/referrer flow actually required by the observed official BSE endpoint. Do not add browser automation or undocumented scraping services. Validate `Content-Type`/body before JSON decoding and emit stable audit codes.

- [ ] **Step 4: Add a live-smoke assertion for BSE mapping**

For each of `RELIANCE`, `TCS`, `INFY`, smoke must either resolve one unambiguous official BSE identity or fail the smoke gate with the explicit reason. A source exception cannot be treated as an acceptable warning.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_clients.py" \
  "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/source_clients.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: harden official BSE source acquisition"
```

---

### Task 4: Prove corporate-action acquisition with the RELIANCE bonus sentinel

**Files:**
- Modify: `source_clients.py` only if the live action transport belongs there
- Modify: `build_e1_source_snapshot.py`
- Create fixture: `tests/fixtures/nse_corporate_actions_reliance.json`
- Modify: `tests/test_source_snapshot.py`

**Interfaces:**
- Keep `_normalize_action(record, symbol) -> dict | None` semantics.
- Add source-normalization support for the **actual NSE corporate-action field names** observed in the official RELIANCE payload.
- A normalized `1:1 bonus` must persist `Old_Shares=1`, `Bonus_Shares=1`, `New_Shares=2`, `Share_Count_Factor=2.0`.

- [ ] **Step 1: Capture a minimal official RELIANCE corporate-action fixture containing the 2024 bonus record**

The regression must assert:

```python
assert action["Symbol"] == "RELIANCE"
assert action["Action_Type"] == "BONUS"
assert action["Ex_Date"] == pd.Timestamp("2024-10-28")
assert action["Share_Count_Factor"] == pytest.approx(2.0)
```

- [ ] **Step 2: Run RED against the real field names**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "reliance and bonus"
```

Expected: FAIL if the current `_records()`/field mapping cannot see the real action row.

- [ ] **Step 3: Implement the minimal real-source normalization**

Map only observed official fields for purpose/action text, ex-date, record date, source id, and ratio. Keep the already-correct share-count semantics:

```text
split/consolidation factor = new_shares / old_shares
bonus B:A -> old=A, bonus=B, new=A+B, factor=(A+B)/A
```

- [ ] **Step 4: Make the known sentinel a smoke acceptance condition**

`run_source_smoke()` must fail (`Smoke_Status = FAIL`) if the RELIANCE 2024-10-28 bonus is absent or does not normalize to factor 2.0. This is a source-integrity sentinel, not a strategy filter.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "action or bonus or smoke"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/source_clients.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git commit -m "fix: validate E1 corporate-action acquisition"
```

---

### Task 5: Invalidate failed v1 checkpoints and make reuse parser/source-version aware

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `README.md`

**Interfaces:**
- Add constants such as:

```python
CHECKPOINT_SCHEMA_VERSION = 2
SOURCE_NORMALIZER_VERSION = 2
EPS_PARSER_VERSION = 2
```

- Checkpoint metadata must include all three versions plus `Reusable`.
- `_read_symbol_checkpoint()` must return `None` for any v1 checkpoint, version mismatch, hash mismatch, cutoff mismatch, or `Reusable is not True`.

- [ ] **Step 1: Write a RED regression proving current v1 failed checkpoints cannot be reused**

Create a synthetic metadata file with:

```json
{"Checkpoint_Version": 1, "Complete": true}
```

and valid artifact hashes. Assert `_read_symbol_checkpoint(...) is None`.

- [ ] **Step 2: Add a transient-source-error reuse regression**

A newly written checkpoint whose audit contains `NSE_SOURCE_ERROR`, `BSE_SOURCE_ERROR`, `SOURCE_HTTP_ERROR`, `EPS_PAYLOAD_HTTP_ERROR`, or `CORPORATE_ACTION_SOURCE_ERROR` must have `Reusable=false` and must be reacquired on the next run.

Parser-level deterministic misses may be cached only under the exact current `EPS_PARSER_VERSION`; bumping the parser version invalidates them.

- [ ] **Step 3: Implement the versioned checkpoint contract**

Metadata shape:

```json
{
  "Checkpoint_Schema_Version": 2,
  "Source_Normalizer_Version": 2,
  "EPS_Parser_Version": 2,
  "Symbol": "RELIANCE",
  "Source_Cutoff": "2026-08-25",
  "Acquisition_Complete": true,
  "Reusable": true,
  "Artifacts": {"filings": {}, "eps": {}, "audit": {}}
}
```

Do not migrate old v1 checkpoints. Reject and rebuild them.

- [ ] **Step 4: Document the required clean restart**

README must explicitly tell Luna/user to use a new work directory (for example `.e1-stage-a-work-v2`) or delete the prior v1 checkpoint directory before the next live run.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "checkpoint"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" \
        "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "fix: invalidate stale E1 Stage A checkpoints"
```

---

### Task 6: Make the three-symbol smoke a hard semantic gate

**Files:**
- Modify: `build_e1_source_snapshot.py`
- Modify: `tests/test_source_snapshot.py`
- Modify: `README.md`

**Interfaces:**
- Add `evaluate_source_smoke(filings, eps, actions, audit, symbols) -> tuple[str, pd.DataFrame]`.
- `run_source_smoke()` must return `Smoke_Status` and write `smoke_validation.csv`.
- CLI `--smoke` must exit non-zero when `Smoke_Status != PASS`.

- [ ] **Step 1: Encode these mandatory smoke gates exactly**

For `RELIANCE`, `TCS`, `INFY`:

```text
FILINGS_PRESENT_PER_SYMBOL                 > 0
EPS_ROWS_PRESENT_PER_SYMBOL                > 0
AT_LEAST_ONE_13_QUARTER_BASIS_CHAIN        == true per symbol
BSE_IDENTITY_RESOLVED                      == true per symbol
NO_TRANSIENT_SOURCE_ERRORS                 == true
RELIANCE_2024_10_28_BONUS_FACTOR           == 2.0
```

A smoke may still report deterministic `EPS_FACT_NOT_FOUND` rows for non-target/annual/malformed filings, but it cannot pass with zero EPS or missing the required 13-quarter chain.

- [ ] **Step 2: Write PASS and FAIL fixture tests**

One fixture package must pass all gates. Another must reproduce the current failure shape (`filings>0, eps=0, actions=0`) and assert `Smoke_Status == "FAIL"`.

- [ ] **Step 3: Run RED**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests/test_source_snapshot.py" -k "smoke"
```

- [ ] **Step 4: Implement gate evaluation and CLI exit code**

```python
status, gates = evaluate_source_smoke(...)
gates.to_csv(work_dir / "smoke_validation.csv", index=False)
if status != "PASS":
    raise SystemExit(2)
```

Do not use `EPS_Rows > 0` alone as the acceptance criterion; complete historical-chain availability is the important E1 feasibility check.

- [ ] **Step 5: Run the real smoke from a fresh v2 work directory**

```bash
python "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --smoke \
  --work-dir .e1-stage-a-smoke-v2
```

Required evidence before proceeding:

```text
Smoke_Status = PASS
all mandatory smoke_validation.csv gates = true
EPS rows > 0 for RELIANCE/TCS/INFY
one complete 13-quarter basis chain per symbol
RELIANCE bonus sentinel present with factor 2.0
no transient source errors
```

If smoke fails, stop and repair only the failing source/parser contract with a regression test. **Do not start the full universe.**

- [ ] **Step 6: Commit smoke evidence summary, not bulk raw payloads**

Update the PR body or a small text/CSV evidence artifact only with gate counts/status and audit-code counts. Temporary raw source bodies/checkpoints remain untracked.

- [ ] **Step 7: Verify and commit**

```bash
python -m pytest -q "Swing Trading/research/swing/e1_positive_earnings_surprise_drift/tests"
git add "Swing Trading/research/swing/e1_positive_earnings_surprise_drift"
git commit -m "test: gate E1 Stage A on real-source smoke"
```

---

### Task 7: Complete the frozen Stage A package, then run Stage B unchanged

**Files:**
- Generated: `research/swing/e1_positive_earnings_surprise_drift/input/*.csv`
- Generated: `research/swing/e1_positive_earnings_surprise_drift/output/*`
- Modify PR body/report evidence only as needed; do not change strategy code after outcomes are visible.

**Interfaces:**
- Stage A final package remains the approved six frozen input artifacts plus manifest.
- Stage B remains `python run_e1_validation.py` with no network calls.

- [ ] **Step 1: Run fresh full tests before live acquisition**

```bash
cd "Swing Trading"
python -m pytest -q "research/swing/e1_positive_earnings_surprise_drift/tests"
python -m pytest -q research/swing
```

Record exact pass/fail counts and exit codes. Do not reuse prior `64/310` claims after changing source code.

- [ ] **Step 2: Run full Stage A with a fresh v2 checkpoint directory and no arbitrary five-minute stop**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/build_e1_source_snapshot.py" \
  --work-dir .e1-stage-a-work-v2
```

The command may be resumed using only v2 reusable checkpoints. It is not complete until the final frozen `input/` files and manifest are written.

- [ ] **Step 3: Verify the frozen source package before Stage B**

Check and record:

```text
all required input files exist and are non-empty where structurally expected
manifest SHA256 verification = zero violations
source-build audit contains no transient/systemic source acquisition failures
technical primary-window machine-readable EPS resolution >= 95%
PIT membership fingerprint matches the manifest
known RELIANCE bonus sentinel survives into corporate-actions snapshot
```

If technical coverage is `<95%`, the run is `INVALID_RESEARCH_RUN`; do not lower the threshold or substitute a third-party EPS source.

- [ ] **Step 4: Run Stage B unchanged and offline**

```bash
python "research/swing/e1_positive_earnings_surprise_drift/run_e1_validation.py"
```

No code, threshold, parser selection, event eligibility, or holding-period changes are permitted after seeing this output except a separately demonstrated integrity bug.

- [ ] **Step 5: Verify final evidence package and formal status**

Inspect:

```text
e1_integrity_audit.csv
e1_source_coverage.csv
e1_validation_gates.csv
research_report.md
```

Required interpretation hierarchy remains:

```text
systemic integrity/source failure -> INVALID_RESEARCH_RUN
clean run but insufficient frozen sample -> INSUFFICIENT_EVIDENCE
sufficient clean run + all gates -> PASS
sufficient clean run + any mandatory strategy gate fails -> FAIL
```

- [ ] **Step 6: Commit final frozen evidence**

```bash
git add "research/swing/e1_positive_earnings_surprise_drift/input" \
        "research/swing/e1_positive_earnings_surprise_drift/output" \
        "research/swing/e1_positive_earnings_surprise_drift/README.md"
git commit -m "research: complete frozen E1 Stage A and validation"
```

If bulk source inputs are intentionally excluded by repo policy/size, commit the approved reproducibility manifest/evidence and document the exact immutable storage path instead; do not silently omit the required frozen-data provenance.

---

## Final review checklist

Before asking for another PR review, verify all of the following:

```text
[ ] Existing v1 checkpoints are rejected; next run uses fresh v2 checkpoints.
[ ] Real NSE integrated/iXBRL fixture parses the target quarterly basic continuing EPS.
[ ] Live RELIANCE/TCS/INFY smoke has EPS rows and one complete 13-quarter basis chain per symbol.
[ ] Live BSE identities resolve or smoke fails explicitly.
[ ] RELIANCE 2024-10-28 1:1 bonus is present with factor 2.0.
[ ] Smoke exits non-zero for the old 493-filings / 0-EPS / 0-actions failure shape.
[ ] Full Stage A produces final frozen inputs and a verified manifest.
[ ] Primary-window technical EPS coverage is >=95% or formal status is INVALID without threshold changes.
[ ] Stage B is rerun offline and unchanged.
[ ] Fresh E1 and full research test commands are recorded after the final source-code commit.
[ ] No strategy parameter changed during this remediation.
```

If the first six source checks are not satisfied, do not run the full historical experiment and do not request merge.