# E1 Positive Earnings Surprise Drift — Design Specification

**Status:** APPROVED DESIGN — source snapshot, implementation and backtest not yet started  
**Design date:** 29 August 2026  
**Research family:** Candidate 2 — Post-results / Post-earnings drift  
**Primary decision:** Determine whether a clean, point-in-time positive quarterly earnings surprise produces a practical long-only post-announcement drift edge in Indian cash equities after realistic friction and versus appropriate controls.

---

## 1. Project-goal alignment

E1 exists only to advance **Swing Trading Strategy Finalization**. It is not a generic financial-data platform, accounting-research project, dashboard project, or excuse to explore indicator combinations.

The research question is intentionally narrow:

> **Do point-in-time Nifty 500 stocks reporting a materially positive quarterly earnings surprise produce positive practical returns over the following several weeks because the market underreacts to the earnings information?**

Required workflow:

```text
predeclared hypothesis
→ frozen public-data methodology
→ one source snapshot
→ one historical validation
→ PASS / FAIL / INSUFFICIENT_EVIDENCE / INVALID_RESEARCH_RUN
→ next strategy-finalization decision
```

No post-result threshold tuning, holding-period optimization, stop optimization, price-confirmation rescue, sector rescue, or regime rescue is allowed.

If E1 passes signal-level validation, the next phase is **portfolio/execution finalization**, not another signal-family search.

---

## 2. Why E1 exists

The project has already tested and closed multiple price-momentum/reversal hypotheses, including T1, V2, V3, R1 and M1. M1 formally failed even though its independently defined market regime discriminated between relatively better and worse momentum environments.

E1 therefore moves to an economically distinct source of possible edge:

> **information underreaction following an unexpected quarterly earnings outcome.**

E1 is not a rescue of V3 or M1.

### 2.1 Contamination guardrail

The primary E1 signal must not use:

- relative strength;
- price momentum;
- SMA50/SMA200 trend;
- market regime;
- sector regime;
- volume confirmation;
- initial gap direction;
- breakout/pullback structure;
- post-announcement price reaction as a qualification filter.

Any later evidence that a price-confirmed earnings strategy might work is a **new named hypothesis**, not a rescue of E1.

---

## 3. Strategy identity and economic hypothesis

**Name:** E1 — Positive Earnings Surprise Drift

### 3.1 Economic hypothesis

> Stocks reporting a materially positive quarterly earnings surprise subsequently exhibit positive practical returns over the following several weeks because the market does not fully incorporate the earnings information immediately.

E1 tests **unexpected earnings information**, not merely reported growth.

```text
EPS growth of +30% YoY
!= automatically a positive surprise
```

If a company has historically produced much larger seasonal earnings improvements, +30% may be disappointing relative to its own prior earnings process.

### 3.2 Long-only implementation

E1 is an Indian cash-equity, long-only module.

- `POSITIVE_SURPRISE` events can become actual E1 long candidates.
- `NEUTRAL_CONTROL` events are hypothetical long controls only.
- `NEGATIVE_CONTROL` events are hypothetical long controls only.
- E1 never shorts negative-surprise stocks.

---

## 4. Research windows

### 4.1 Primary event window

Freeze exactly:

```text
2023-08-01 through 2026-06-30 inclusive
```

A primary event is eligible by `Event_Public_Date`, not fiscal-period end or entry date.

This cutoff is chosen to prevent right-censoring: every primary event must have enough already-observed market history to complete the frozen 40-session holding horizon.

No extension backward or forward is allowed after observing cohort counts or returns.

### 4.2 Source-data cutoff

The source snapshot may include official result filings through:

```text
2026-08-25
```

Events after `2026-06-30` are **non-primary forward observations**. They may be retained for provenance and future forward work but cannot contribute to the formal historical validation or any E1 PASS/FAIL gate.

### 4.3 EPS history-only seed window

Acquire quarterly-result history from at least:

```text
2020-01-01 onward
```

The period:

```text
2020-01-01 through 2023-07-31
```

is **history-only**. It may contribute to SUE calculation but can never create an E1 trade.

### 4.4 Temporal validation split

The frozen calendar midpoint of the primary event window is `2025-01-14`.

Use exactly:

```text
FIRST:  2023-08-01 through 2025-01-14 inclusive
SECOND: 2025-01-15 through 2026-06-30 inclusive
```

Do not move this split after seeing outcomes.

---

## 5. Universe and point-in-time eligibility

### 5.1 Universe

Primary universe:

> **Point-in-time Nifty 500**

A result event is universe-eligible only if the company is an active PIT Nifty 500 member on `Event_Public_Date`.

Do not use current Nifty 500 membership, entry-date membership, fiscal-quarter-end membership, or survivorship backfill.

### 5.2 Existing PIT source

Reuse read-only:

`Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`

Historical EPS observations used to calculate a current event's SUE do not themselves require Nifty 500 membership when those earlier quarters were reported.

---

## 6. Official result sources

E1 uses **official exchange filings** as the source of truth.

### 6.1 NSE role

NSE financial-result / Integrated Filing metadata is authoritative for fields such as:

- company/symbol;
- period / period ended;
- audited or unaudited;
- cumulative or non-cumulative;
- standalone or consolidated;
- filing/broadcast date and time;
- XBRL or Integrated Filing document references.

The source collector must support both legacy financial-result records and newer Integrated Filing forms.

### 6.2 BSE role

BSE historical corporate-result records are an authoritative second exchange source for:

- financial year;
- quarter/period;
- standalone/consolidated status;
- `New` versus `Revised` identity;
- filing date/time;
- XBRL/result-detail references;
- structured result fields where available, including Basic EPS for continuing operations.

### 6.3 No third-party primary source

The frozen E1 dataset must not source historical earnings values or event timestamps from Screener, Trendlyne, broker databases, manually curated earnings calendars, analyst-data websites, paid consensus feeds, model memory, or hand-entered values.

Third-party material may be used only to debug a source issue during development; it must never become an authoritative value in the frozen research snapshot.

---

## 7. First-public event identity

### 7.1 Deterministic event key

Normalize around:

```text
Symbol
+ Fiscal_Period_End
+ Reporting_Basis
```

The implementation may encode a stable `Event_ID`, but the same economic quarterly result must not become multiple events merely because NSE and BSE both contain it.

### 7.2 Earliest valid public timestamp

For the selected reporting basis:

```text
Event_Public_Timestamp
    = earliest valid original/public timestamp
      across authoritative NSE and BSE records
```

Normalize timestamps to `Asia/Kolkata`.

### 7.3 Original filing only

For each event key, select the first valid `New`/original financial-result filing.

Later revisions, corrections, resubmissions, duplicate XBRL records, and duplicate exchange copies:

- do not create new primary E1 events;
- do not retrospectively rewrite the EPS that was first public;
- may be retained only as provenance/audit evidence.

### 7.4 PIT historical EPS

Historical quarters used in an event's SUE must use the original point-in-time EPS observation that was public before the current event.

Do not replace old quarters with later revised/restated values merely because a newer archive now contains them.

Mechanical per-share adjustment for corporate actions already effective by the current event is allowed under Section 12.

---

## 8. Timely-result requirement

Only normal timely quarterly reporting events belong in the primary experiment.

Freeze:

```text
Q1 / Q2 / Q3:
Event_Public_Date <= Fiscal_Period_End + 45 calendar days

Final fiscal quarter:
Event_Public_Date <= Fiscal_Period_End + 60 calendar days
```

The company-specific fiscal calendar determines the final fiscal quarter.

Anything later is:

```text
LATE_RESULT
```

and is excluded from the primary experiment.

No discretionary exceptions.

---

## 9. Reporting basis and EPS field

### 9.1 Preferred reporting basis

For each event, prefer:

```text
CONSOLIDATED
+ QUARTERLY
+ NON-CUMULATIVE
```

if the complete comparable current-plus-history chain required by Section 10 exists.

Otherwise allow:

```text
STANDALONE
+ QUARTERLY
+ NON-CUMULATIVE
```

if that basis has the complete comparable chain.

Do not switch basis inside a single SUE chain. If both bases are fully usable, consolidated wins.

### 9.2 EPS field

Use:

> **Basic EPS from continuing operations**

Use genuine quarterly, non-cumulative EPS only.

Do not substitute diluted EPS, annual EPS, cumulative nine-month EPS, adjusted/non-GAAP EPS, or management-defined normalized EPS.

### 9.3 Final-quarter handling

When a filing exposes both quarter and full-year figures, use the actual quarter EPS.

Do not derive quarterly EPS by subtracting cumulative values unless the original exchange filing explicitly supplies the required genuine quarterly value.

If genuine quarterly EPS is unavailable, the event is ineligible.

---

## 10. Frozen SUE methodology

E1 uses a **seasonal random-walk-with-drift standardized unexpected earnings measure**.

For company `i`, fiscal quarter `t`:

```text
D[t] = EPS[t] - EPS[t-4]
```

Use exactly:

```text
D[t-1], D[t-2], ..., D[t-8]
```

Then:

```text
Historical_Mean[t]
    = mean(D[t-1] ... D[t-8])

Historical_SD[t]
    = sample standard deviation(D[t-1] ... D[t-8])

SUE[t]
    = (D[t] - Historical_Mean[t]) / Historical_SD[t]
```

Use sample-standard-deviation semantics (`ddof=1`).

### 10.1 Exact history requirement

All eight prior seasonal changes are mandatory, normally requiring comparable quarterly EPS covering approximately `t-12` through `t`.

No six-observation fallback is allowed.

If any required EPS observation is unavailable or incomparable:

```text
SUE_UNAVAILABLE
```

with an explicit exclusion reason.

### 10.2 Strict PIT history

The current event may not contribute to its own historical mean or standard deviation.

Only historical EPS observations public before `Event_Public_Timestamp[t]` may contribute to `D[t-1] ... D[t-8]`.

### 10.3 Zero and negative EPS

Do not exclude zero or negative EPS.

Loss-to-profit, loss-to-smaller-loss, profit-to-profit and profit-to-loss transitions remain valid because E1 uses EPS differences rather than percentage growth.

These transitions are diagnostics only.

### 10.4 Invalid historical volatility

If `Historical_SD <= 0` or is non-finite:

```text
ZERO_HISTORICAL_SUE_SD
```

and SUE is unavailable.

Do not add epsilon values or denominator floors.

### 10.5 No winsorisation

Do not cap, winsorize or discard extreme SUE values in the primary experiment.

Extreme SUE buckets are diagnostics only.

---

## 11. Frozen SUE cohorts

Every valid finite SUE observation must be classified exactly once:

```text
SUE >= +1.0
    -> POSITIVE_SURPRISE

+0.5 <= SUE < +1.0
    -> POSITIVE_BUFFER

-0.5 < SUE < +0.5
    -> NEUTRAL_CONTROL

-1.0 < SUE <= -0.5
    -> NEGATIVE_BUFFER

SUE <= -1.0
    -> NEGATIVE_CONTROL
```

Boundary ownership is intentional:

- `+0.5` → `POSITIVE_BUFFER`
- `-0.5` → `NEGATIVE_BUFFER`
- `+1.0` → `POSITIVE_SURPRISE`
- `-1.0` → `NEGATIVE_CONTROL`

Only `POSITIVE_SURPRISE` creates an actual E1 long candidate.

`NEUTRAL_CONTROL` and `NEGATIVE_CONTROL` use identical hypothetical long execution mechanics. Buffer cohorts are diagnostic only.

---

## 12. Corporate-action comparability for EPS

Historical EPS must be comparable on a per-share basis at the current event.

Use official exchange corporate-action records for stock splits, share consolidations and bonus issues.

### 12.1 PIT adjustment rule

For SUE event `t`, only corporate actions effective on or before `Event_Public_Date[t]` may adjust historical EPS comparability.

A future corporate action must never rewrite an earlier event's SUE.

### 12.2 Adjustment intent

Normalize historical EPS only enough to establish per-share comparability with current EPS after actions already effective by the current event.

Do not use corporate-action adjustment to change underlying earnings, reporting basis or accounting restatements.

If comparable per-share history cannot be established deterministically:

```text
EPS_HISTORY_NOT_COMPARABLE
```

and exclude the event.

---

## 13. Machine-readable EPS resolution

### 13.1 Preferred numeric resolution

For the selected original event/basis:

1. use matching BSE structured Basic EPS from continuing operations when available;
2. otherwise use matching NSE XBRL / Integrated Filing machine-readable EPS;
3. if neither source can provide a trustworthy machine-readable value, use `EPS_SOURCE_UNRESOLVED`.

Do not build OCR/PDF extraction merely to rescue missing observations in E1 V1.

### 13.2 Cross-exchange check

When both NSE and BSE provide machine-readable EPS for the same selected event/basis, require agreement within either:

```text
absolute difference <= Rs 0.01
OR
relative difference <= 0.5%
```

Beyond tolerance:

```text
CROSS_EXCHANGE_EPS_MISMATCH
```

The cause must be deterministically resolved from original exchange evidence before use.

### 13.3 Objective source-coverage denominator

The source-coverage gate must not depend on a subjective judgement that a record "should be resolvable."

Define:

```text
Technical_EPS_Candidate
=
PIT Nifty500 event
AND timely quarterly original filing identified
AND selected reporting basis identified
AND an official machine-readable structured/XBRL result reference exists
for that selected filing/basis
```

Then:

```text
Machine_Readable_EPS_Resolution
=
Technical_EPS_Candidates with successfully parsed valid EPS
/
all Technical_EPS_Candidates
```

Require:

```text
Machine_Readable_EPS_Resolution >= 95%
```

Below 95%:

```text
INVALID_RESEARCH_RUN
```

The denominator and every failed technical candidate must be preserved in source-coverage evidence.

### 13.4 Structural exclusions do not reduce source coverage

Legitimate economic/history exclusions such as insufficient EPS history, fiscal-calendar change, incomparable reporting basis, zero historical SUE SD, or restructuring that destroys comparability are not technical parsing failures.

Report them separately.

---

## 14. Source snapshot architecture

Data acquisition and strategy validation are separate stages.

```text
STAGE A — SOURCE SNAPSHOT
official NSE/BSE filings
+ official corporate actions
        ↓
normalize
        ↓
freeze immutable inputs
        ↓
hash + provenance manifest

STAGE B — VALIDATION
frozen E1 inputs
+ PIT Nifty500 membership
+ frozen stock/index prices
        ↓
SUE
        ↓
cohorts
        ↓
fixed trades
        ↓
controls / benchmark / robustness
        ↓
formal status
```

The formal validator must perform **no network calls**.

### 14.1 Frozen input artifacts

Under the E1 module, freeze at minimum:

```text
input/
├── e1_exchange_filings_snapshot.csv
├── e1_eps_snapshot.csv
├── e1_corporate_actions_snapshot.csv
├── e1_source_manifest.csv
└── e1_source_build_audit.csv
```

### 14.2 Provenance manifest

`e1_source_manifest.csv` must record at minimum:

```text
Artifact
Source
Retrieved_At
Row_Count
SHA256
Primary_Event_Window
Source_Data_Cutoff
Notes
```

Also fingerprint the exact external read-only files used for PIT membership, stock prices and Nifty 500 benchmark prices.

### 14.3 Source acquisition blind to returns

Stage A may know filings, timestamps, EPS, reporting basis, exclusions and corporate actions.

It must not calculate post-event returns or use profitability to decide whether parsing is acceptable.

---

## 15. Frozen price and benchmark inputs

The validator consumes frozen price data; it must not fetch fresh Yahoo or other live market data on each rerun.

For each eligible event, require:

- stock next-session Open;
- stock session-41 Open or earlier deterministic exit Open;
- daily High/Low during holding for MAE/MFE;
- Nifty 500 Open on the exact stock entry and exit sessions.

Trade-return measurement must be **corporate-action consistent** so splits/bonuses/dividends do not manufacture P&L. This adjustment is return accounting only and must not alter event eligibility or SUE formation.

Missing or inconsistent temporal price alignment is an integrity failure unless explicitly classified as an allowed event-level execution cancellation.

---

## 16. Frozen entry mechanics

For a qualifying primary event with `SUE >= +1.0`:

```text
result becomes public on Event_Public_Date T
        ↓
no same-day trade
        ↓
enter at next canonical trading-session Open
```

The same timing applies to neutral and negative shadow controls.

### 16.1 No gap filter

Do not reject or require any entry based on initial price reaction or gap size/direction.

Record initial reaction diagnostically only.

### 16.2 Entry unavailable

If there is no valid executable next-session Open because of suspension or missing valid price:

```text
NO_VALID_NEXT_SESSION_OPEN
```

and cancel the event. Do not defer to a later day.

---

## 17. Frozen holding period and exits

### 17.1 Primary exit

Freeze:

> **40 complete trading sessions after entry, then exit at the following session Open.**

Conceptually:

```text
Entry Open
→ 40 completed sessions
→ session-41 Open exit
```

No alternative 20/60-day primary exits.

### 17.2 No technical stop or target

Primary E1 has no ATR stop, fixed-percentage stop, SMA exit, trailing stop, profit target or breakeven rule.

This isolates the event-underreaction hypothesis.

### 17.3 Next distinct quarterly result while holding

If the same company publishes its **next distinct quarterly financial result** before the scheduled time exit:

```text
old trade
→ exit at next canonical session Open after that new result becomes public
```

Use:

```text
EXIT_NEXT_EARNINGS_EVENT
```

This early-exit trigger applies whether or not the new result:

- is itself timely;
- has enough EPS history;
- has a valid SUE;
- belongs to the primary E1 event window;
- would qualify as a new E1 trade.

It exists to prevent one trade's return from being contaminated by a new quarterly information event.

If that new result independently qualifies as a new primary `POSITIVE_SURPRISE`, it may open a new E1 trade at the same eligible Open as a separate `Event_ID`.

No pyramiding and no extension of the old trade.

### 17.4 Genuine security termination

Delisting, merger termination, prolonged suspension or another genuine inability to transact must be explicitly audited. Do not silently drop such trades.

---

## 18. Friction and return formulas

Round-trip friction:

```text
Base:   0.40%
Stress: 0.60%
Severe: 0.80% diagnostic only
```

For friction `c`:

```text
Gross_Return = Exit_Open / Entry_Open - 1

Net_Return = Gross_Return - c
```

Benchmark:

```text
Benchmark_Return
    = Nifty500_Exit_Open / Nifty500_Entry_Open - 1

Net_Excess_Return
    = Net_Return - Benchmark_Return
```

The benchmark is not charged fictional trading friction.

There is no R-multiple because E1 intentionally has no initial stop defining `1R`.

---

## 19. Signal-level sample and portfolio treatment

At signal-level validation, every eligible event remains an independent observation.

Do not impose the eventual 3–5-position limit, portfolio capital constraint, sector cap or candidate ranking yet.

Record:

- same-day qualifying events;
- simultaneous active trades;
- sector clustering;
- event-season clustering;
- implied capital demand.

If E1 passes, portfolio-constrained simulation is the next experiment.

---

## 20. Mandatory integrity rules

Any systemic violation makes the run:

```text
INVALID_RESEARCH_RUN
```

At minimum verify:

- PIT Nifty 500 membership integrity;
- event timestamp provenance;
- original versus revised filing identity;
- historical EPS uses only information public before the current event;
- no future corporate action alters earlier SUE;
- same reporting basis throughout each SUE chain;
- fiscal-quarter comparability;
- every valid SUE event classified exactly once;
- no cohort overlap;
- original event deduplication across NSE/BSE;
- source technical coverage calculation is objective and >=95%;
- unresolved cross-exchange EPS conflicts do not enter the sample;
- `Event_Public_Date < Entry_Date`;
- exact stock/benchmark entry-exit session alignment;
- primary events lie inside `2023-08-01..2026-06-30`;
- non-primary July-August 2026 observations never enter formal gates;
- completed/cancelled event accounting reconciles;
- positive, neutral and negative primary cohorts use identical execution mechanics.

Repair integrity only; never change strategy mechanics in response to `INVALID_RESEARCH_RUN`.

---

## 21. Event-level exclusions

Expected event-level exclusions/cancellations include:

```text
LATE_RESULT
INSUFFICIENT_EPS_HISTORY
INCOMPARABLE_REPORTING_BASIS
FISCAL_CALENDAR_CHANGE
ZERO_HISTORICAL_SUE_SD
EPS_SOURCE_UNRESOLVED
EPS_HISTORY_NOT_COMPARABLE
NO_VALID_NEXT_SESSION_OPEN
```

Every excluded event must retain an explicit reason. Nothing disappears silently.

A systemic pattern of technical extraction failure is still governed by the 95% source-coverage integrity gate.

---

## 22. Control cohorts

Primary controls use exactly the same execution mechanics as E1:

```text
NEUTRAL_CONTROL:
-0.5 < SUE < +0.5

NEGATIVE_CONTROL:
SUE <= -1.0
```

They are hypothetical longs only.

`POSITIVE_BUFFER` and `NEGATIVE_BUFFER` remain diagnostic cohorts.

---

## 23. Mandatory sample sufficiency

Require completed observations:

```text
POSITIVE_SURPRISE >= 300
NEUTRAL_CONTROL   >= 300
NEGATIVE_CONTROL  >= 300
```

Also require in each temporal half:

```text
POSITIVE_SURPRISE completed >= 100
```

If integrity is clean but any requirement is missed:

```text
INSUFFICIENT_EVIDENCE
```

Do not loosen SUE/history thresholds or extend the historical window.

---

## 24. Mandatory profitability gates

For `POSITIVE_SURPRISE` under base 0.40% friction:

```text
Mean Net Return >= +1.00%
Median Net Return > 0
Return Profit Factor >= 1.20
Mean Net Excess Return > 0
Excess-Return Profit Factor > 1.00
```

At stress 0.60% friction:

```text
Mean Net Return > 0
Return Profit Factor > 1.00
Mean Net Excess Return > 0
```

The 0.80% severe case is diagnostic only.

---

## 25. Mandatory surprise-discrimination gates

Base-friction mean returns must satisfy:

```text
POSITIVE_SURPRISE
    >
NEUTRAL_CONTROL
    >
NEGATIVE_CONTROL
```

Base benchmark-adjusted mean returns must also satisfy the same ordering.

Additionally:

```text
Positive Return PF > Neutral Return PF
Positive Return PF > Negative Return PF
```

A profitable positive cohort without correct surprise ordering is a FAIL.

---

## 26. Mandatory temporal robustness

For both frozen halves:

```text
Base Mean Net Return > 0
Base Return PF > 1.00
Mean Net Excess Return > 0
```

Each half must also meet the >=100 positive-event sufficiency rule.

Calendar-year results are diagnostic only except through the leave-one-year-out robustness gate below.

---

## 27. Mandatory robustness gates

### 27.1 Leave one calendar year out

For every calendar year represented in primary positive trades, remove that year's positive trades.

Every remaining sample must retain:

```text
Base Mean Net Return > 0
Base Return PF > 1.00
Mean Net Excess Return > 0
```

### 27.2 Top-five winner removal

Remove the five largest positive trades by **gross stock return**.

Remaining sample must retain:

```text
Base Mean Net Return > 0
Base Return PF > 1.00
Mean Net Excess Return > 0
```

### 27.3 Leave one symbol out

For every symbol appearing in the positive cohort, remove that symbol.

Every omission must retain:

```text
Base Mean Net Return > 0
Base Return PF > 1.00
Mean Net Excess Return > 0
```

No single stock may be required for the edge.

---

## 28. Mandatory diagnostics, not gates

Because E1 has no price stop, report:

- maximum adverse excursion;
- maximum favourable excursion;
- worst completed trade;
- 1st percentile return;
- 5th percentile return;
- median trade drawdown;
- maximum trade drawdown;
- entry-gap distribution;
- next-earnings truncated exits;
- simultaneous active trades.

Also report non-gating cuts for:

- SUE 1–2, 2–3, 3–5, >=5;
- profit→profit;
- loss→profit;
- loss→smaller loss;
- profit→loss;
- initial reaction/gap buckets;
- market cap;
- liquidity;
- sector;
- reporting basis;
- fiscal quarter;
- announcement weekday;
- calendar year.

These may motivate a **new named hypothesis** only. They cannot rescue E1.

---

## 29. Required frozen evidence package

Under:

`Swing Trading/research/swing/e1_positive_earnings_surprise_drift/output/`

generate at minimum:

```text
e1_data_validation.csv
e1_source_coverage.csv
e1_event_master.csv
e1_event_exclusions.csv
e1_eps_history.csv
e1_sue_events.csv
e1_cohort_classification.csv

e1_positive_trades.csv
e1_neutral_control.csv
e1_negative_control.csv

e1_validation_summary.csv
e1_cohort_comparison.csv
e1_benchmark_comparison.csv
e1_temporal_summary.csv
e1_year_summary.csv
e1_leave_one_year_out.csv
e1_top_five_robustness.csv
e1_leave_one_symbol_out.csv

e1_downside_diagnostic.csv
e1_diagnostic_summary.csv
e1_overlap_capacity_diagnostic.csv

e1_integrity_audit.csv
e1_validation_gates.csv
research_report.md
```

No dashboard is required for the formal result.

### 29.1 Event master

`e1_event_master.csv` must retain at minimum:

```text
Event_ID
Symbol
Fiscal_Period_End
Event_Public_Timestamp
Event_Public_Date
Reporting_Basis
Timely_Result
PIT_Membership_OK
EPS_Source_Status
Primary_Event
```

### 29.2 Exclusions

`e1_event_exclusions.csv` must preserve every excluded event with exactly one primary reason.

### 29.3 EPS history

For every calculable event, retain:

```text
Event_ID
Current_EPS
EPS_t_minus_4
D_t
D_t_minus_1
...
D_t_minus_8
Historical_Mean
Historical_SD
SUE
```

### 29.4 Trade evidence

Positive, neutral and negative completed-trade files must share comparable fields:

```text
Event_ID
Symbol
SUE
Event_Public_Date
Entry_Date
Entry_Open
Exit_Date
Exit_Open
Exit_Reason
Holding_Sessions
Gross_Return
Base_Net_Return
Stress_Net_Return
Severe_Net_Return
Nifty500_Entry_Open
Nifty500_Exit_Open
Benchmark_Return
Base_Net_Excess_Return
Stress_Net_Excess_Return
```

Include diagnostic fields needed for MAE/MFE and initial reaction.

---

## 30. Accounting invariants

At minimum:

```text
all valid finite SUE events
=
POSITIVE_SURPRISE
+ POSITIVE_BUFFER
+ NEUTRAL_CONTROL
+ NEGATIVE_BUFFER
+ NEGATIVE_CONTROL
```

No overlap.

For each primary traded/control cohort:

```text
qualified events
=
completed outcomes
+ explicit entry cancellations
```

Every completed outcome must have exact benchmark entry/exit dates.

Primary and non-primary event sets must be disjoint.

---

## 31. Formal gate artifact and status hierarchy

`e1_validation_gates.csv` is the authority for strategy status.

Each gate should expose:

```text
Gate
Value
Threshold
Pass
Mandatory
```

Status precedence:

```text
if systemic integrity violation:
    INVALID_RESEARCH_RUN

elif Machine_Readable_EPS_Resolution < 95%:
    INVALID_RESEARCH_RUN

elif primary cohort sample requirements fail
     or temporal-half positive counts fail:
    INSUFFICIENT_EVIDENCE

elif every mandatory strategy gate passes:
    PASS

else:
    FAIL
```

No fifth state such as "promising", "borderline", "conditional pass", or "needs tuning".

---

## 32. Research report

`research_report.md` must be generated mechanically from frozen evidence and contain:

1. Frozen E1 hypothesis
2. Source provenance
3. Source coverage
4. PIT / event integrity
5. Event exclusions
6. SUE methodology
7. Cohort counts
8. Positive-cohort base results
9. Market-relative results
10. Stress/severe friction
11. Positive vs neutral vs negative discrimination
12. Temporal halves
13. Calendar years
14. Leave-one-year-out
15. Top-five robustness
16. Leave-one-symbol-out
17. Downside diagnostics
18. Capacity / overlap diagnostics
19. Mandatory gate table
20. One formal conclusion and next action

No alternate thresholds or rescue suggestions.

---

## 33. One-command formal run

After source inputs are frozen:

```text
python run_e1_validation.py
```

must generate the complete evidence package.

It must:

- make no network calls;
- not modify input snapshots;
- not modify V3/M1/R1 artifacts;
- be deterministic against identical input hashes;
- fail loudly on missing/mismatched required fingerprints.

The source-snapshot builder is a separate explicit process.

---

## 34. Hard out-of-scope list

E1 V1 explicitly excludes:

- analyst-consensus estimates;
- revenue surprise;
- EBITDA surprise;
- management-guidance NLP;
- earnings-call sentiment;
- news sentiment;
- price momentum filters;
- RS filters;
- SMA filters;
- market-regime filters;
- volume confirmation;
- positive-gap requirement;
- gap-size exclusion;
- ATR stop;
- fixed-percentage stop;
- trailing stop;
- profit target;
- alternative 20/60-day primary exits;
- SUE threshold optimization;
- retrospective top-decile ranking;
- sector filtering;
- profit-only-company filter;
- loss-company exclusion;
- machine learning;
- PDF OCR rescue;
- dashboards;
- generic financial-data warehouse.

---

## 35. Final decision and next action

### PASS

Stop signal research.

Proceed to:

```text
3–5 position portfolio simulation
→ event collisions / candidate ranking
→ position sizing
→ portfolio drawdown
→ cash utilisation
→ small-account feasibility
→ forward/paper validation
```

### FAIL

Close E1 permanently under this specification.

Move to the final remaining independent candidate:

> objective range reversion **or** volatility compression → expansion

No PEAD rescue.

### INSUFFICIENT_EVIDENCE

Do not extend history or loosen SUE/history requirements to manufacture trades.

Move on.

### INVALID_RESEARCH_RUN

Repair only the research/data integrity defect and rerun E1 unchanged.

---

## 36. Frozen summary

```text
Official NSE/BSE original quarterly filings
                ↓
PIT Nifty500
                ↓
timely quarterly result
                ↓
consistent machine-readable EPS history
                ↓
8 prior seasonal EPS changes
                ↓
SUE >= +1.0
                ↓
next-session Open
                ↓
no gap / momentum / regime filter
                ↓
40-session fixed hold
or next quarterly-result early exit
                ↓
0.40% base friction
                ↓
Nifty500-relative comparison
                ↓
neutral + negative controls
                ↓
hard temporal / concentration / winner robustness
                ↓
PASS / FAIL / INSUFFICIENT_EVIDENCE / INVALID_RESEARCH_RUN
```

This specification is the frozen methodology for E1. Implementation must follow it mechanically and must not introduce new strategic degrees of freedom.
