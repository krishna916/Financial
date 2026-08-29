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

The required workflow is:

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

Any later evidence that a price-confirmed earnings strategy might work would be a **new named hypothesis**, not a rescue of E1.

---

## 3. Strategy identity and economic hypothesis

**Name:** E1 — Positive Earnings Surprise Drift

### 3.1 Economic hypothesis

> Stocks reporting a materially positive quarterly earnings surprise subsequently exhibit positive practical returns over the following several weeks because the market does not fully incorporate the earnings information immediately.

E1 tests **unexpected earnings information**, not merely reported growth.

For example:

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
2023-08-01 through 2026-08-25 inclusive
```

A primary event is eligible by its `Event_Public_Date`, not by quarter-end date or entry date.

No extension backward or forward is allowed after observing cohort counts or returns.

### 4.2 EPS history-only seed window

Acquire quarterly-result history from at least:

```text
2020-01-01 onward
```

The period:

```text
2020-01-01 through 2023-07-31
```

is **history-only**. It can contribute to SUE calculation but can never create an E1 trade.

### 4.3 Temporal validation split

The frozen calendar midpoint of the primary event window is `2025-02-11`.

Use exactly:

```text
FIRST:  2023-08-01 through 2025-02-11 inclusive
SECOND: 2025-02-12 through 2026-08-25 inclusive
```

Do not move the split after seeing outcomes.

---

## 5. Universe and point-in-time eligibility

### 5.1 Universe

Primary universe:

> **Point-in-time Nifty 500**

A result event is universe-eligible only if the company is an active PIT Nifty 500 member on `Event_Public_Date`.

Do not use:

- current Nifty 500 membership;
- entry-date membership;
- fiscal-quarter-end membership;
- survivorship backfill.

### 5.2 Existing PIT source

Reuse the repository's existing point-in-time membership source read-only:

`Swing Trading/research/swing/market_breadth/config/nifty500_membership.csv`

The E1 source builder may use the set of symbols that overlap the primary window to know which companies require historical result retrieval, but historical EPS observations do not themselves require the company to have been a Nifty 500 member when those prior quarters were reported.

---

## 6. Official earnings-result sources

E1 uses **official exchange filings** as the source of truth.

### 6.1 NSE role

NSE financial-result / Integrated Filing metadata is an authoritative source for fields such as:

- company/symbol;
- period / period ended;
- audited or unaudited;
- cumulative or non-cumulative;
- standalone or consolidated;
- filing/broadcast date and time;
- XBRL or Integrated Filing document references.

The collector must support both legacy financial-result records and the Integrated Filing form used for newer periods.

### 6.2 BSE role

BSE historical corporate-result records are an authoritative second exchange source for:

- financial year;
- quarter/period;
- standalone/consolidated status;
- `New` versus `Revised` identity;
- filing date/time;
- XBRL/result-detail references;
- structured financial-result fields where available, including Basic EPS for continuing operations.

### 6.3 No third-party primary source

The primary E1 dataset must not source historical earnings values or event timestamps from:

- Screener;
- Trendlyne;
- broker APIs/databases;
- manually curated earnings calendars;
- analyst-data websites;
- paid consensus feeds;
- model-memory or hand-entered values.

Third-party material may be used only to debug a source issue during development; it must never become an authoritative value in the frozen research snapshot.

---

## 7. First-public event identity

### 7.1 Deterministic event key

The normalized event identity should be deterministic around:

```text
Symbol
+ Fiscal_Period_End
+ Reporting_Basis
```

The implementation may add a stable encoded `Event_ID`, but the same economic quarterly result must not become multiple events merely because NSE and BSE both contain a record.

### 7.2 Earliest valid public timestamp

For the selected reporting basis:

```text
Event_Public_Timestamp
    = earliest valid original/public timestamp
      across authoritative NSE and BSE records
```

All timestamps must be normalized to `Asia/Kolkata`.

If one exchange made the result public earlier than the other, the earlier valid timestamp is the event timestamp.

### 7.3 Original filing only

For each event key, select the first valid `New`/original financial-result filing.

Later:

- revisions;
- corrections;
- resubmissions;
- duplicate XBRL records;
- duplicate exchange copies

must not create new primary E1 events and must not retrospectively rewrite the EPS that was first public.

A revision may be retained as provenance/audit evidence only.

### 7.4 No retrospective replacement of historical EPS

Historical quarters used in an event's SUE calculation must use the **original point-in-time EPS observation** that was public before the current event.

Do not replace old quarters with later restatements or revised values merely because a newer database/file now contains them.

Mechanical per-share adjustment for corporate actions effective on or before the current event is allowed under Section 12; that is comparability normalization, not earnings restatement.

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

The company-specific fiscal calendar determines which quarter is the final fiscal quarter.

Anything later is:

```text
LATE_RESULT
```

and is excluded from the primary experiment.

Do not make discretionary exceptions for filings that are only slightly late.

If the fiscal-quarter identity cannot be established reliably, use the appropriate event-level exclusion rather than guessing.

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

Do not switch basis inside a single SUE chain.

If both bases are fully usable, consolidated wins.

### 9.2 EPS field

Use:

> **Basic EPS from continuing operations**

Use genuine quarterly, non-cumulative EPS only.

Do not substitute:

- diluted EPS;
- total-company EPS when continuing-operations EPS is separately available;
- annual EPS;
- nine-month cumulative EPS;
- adjusted/non-GAAP EPS;
- management-defined normalized EPS.

### 9.3 March/final-quarter handling

When a filing exposes both quarter and full-year figures, use the actual quarter EPS.

Do not derive quarterly EPS by subtracting nine-month cumulative EPS from annual EPS unless the exchange filing itself explicitly provides the genuine quarterly value needed by this design.

If genuine quarterly EPS is unavailable, the event is ineligible.

---

## 10. Frozen SUE methodology

E1 uses a **seasonal random-walk-with-drift standardized unexpected earnings measure**.

For company `i`, fiscal quarter `t`:

```text
D[t] = EPS[t] - EPS[t-4]
```

Use exactly the previous eight seasonal changes:

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

Use sample standard deviation with `ddof=1` semantics.

### 10.1 Exact history requirement

All eight prior seasonal changes are mandatory.

This normally requires a clean comparable EPS sequence covering approximately:

```text
t-12 through t
```

No six-observation fallback is allowed.

If any required EPS observation is unavailable or incomparable:

```text
SUE_UNAVAILABLE
```

with an explicit exclusion reason.

### 10.2 Strict PIT history

The current event `t` may not contribute to its own historical mean or standard deviation.

Only historical EPS observations public before `Event_Public_Timestamp[t]` may contribute to:

```text
D[t-1] ... D[t-8]
```

### 10.3 Zero and negative EPS

Do **not** exclude losses merely because EPS is zero or negative.

Examples such as:

- loss -> profit;
- loss -> smaller loss;
- profit -> profit;
- profit -> loss

remain mathematically valid because E1 uses EPS differences rather than percentage growth.

These transitions may be reported diagnostically but are not strategy filters.

### 10.4 Invalid historical volatility

If:

```text
Historical_SD <= 0
```

or is non-finite:

```text
ZERO_HISTORICAL_SUE_SD
```

and SUE is unavailable.

Do not add epsilon values or arbitrary denominator floors.

### 10.5 No primary winsorisation

Do not cap, winsorize or discard extreme SUE values in the primary experiment.

Extreme SUE buckets may be diagnostic only.

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

The boundary values are intentional:

- `+0.5` belongs to `POSITIVE_BUFFER`;
- `-0.5` belongs to `NEGATIVE_BUFFER`;
- `+1.0` belongs to `POSITIVE_SURPRISE`;
- `-1.0` belongs to `NEGATIVE_CONTROL`.

No valid SUE event may be unclassified or appear in more than one cohort.

Only `POSITIVE_SURPRISE` creates an actual E1 long candidate.

`NEUTRAL_CONTROL` and `NEGATIVE_CONTROL` use identical hypothetical long execution mechanics for research comparison.

The buffer cohorts are diagnostics only.

---

## 12. Corporate-action comparability for EPS

Historical EPS must be comparable on a per-share basis at the current event.

Use official exchange corporate-action records for actions such as:

- stock splits;
- share consolidations;
- bonus issues.

### 12.1 PIT adjustment rule

For SUE event `t`, only corporate actions effective on or before `Event_Public_Date[t]` may adjust historical EPS comparability.

A future corporate action must never rewrite an earlier E1 event's SUE.

### 12.2 Adjustment intent

The historical EPS sequence should be normalized to the per-share basis economically comparable with current-quarter EPS after actions already effective by the current event.

Do not use corporate-action adjustment to change underlying earnings, reporting basis or accounting restatements.

If comparable per-share history cannot be established deterministically:

```text
EPS_HISTORY_NOT_COMPARABLE
```

and the event is excluded.

---

## 13. Machine-readable EPS resolution

### 13.1 Preferred numeric resolution

For the selected original event/basis:

1. use a matching BSE structured Basic EPS from continuing operations value when available;
2. otherwise use matching NSE XBRL / Integrated Filing machine-readable value;
3. if neither can produce a trustworthy machine-readable value, classify the event as `EPS_SOURCE_UNRESOLVED`.

Do not build OCR/PDF extraction merely to rescue missing observations in E1 V1.

### 13.2 Cross-exchange numerical check

When both NSE and BSE provide machine-readable EPS for the same selected event/basis, require agreement within either:

```text
absolute difference <= Rs 0.01
OR
relative difference <= 0.5%
```

If they disagree beyond tolerance, record:

```text
CROSS_EXCHANGE_EPS_MISMATCH
```

and resolve the cause deterministically from original exchange evidence before the event can be used.

Do not pick whichever value looks more plausible.

### 13.3 Source-resolution coverage gate

Define a `Source_Resolvable_Candidate` as a PIT Nifty 500 timely quarterly-result event for which the reporting basis is identifiable and for which the official source architecture should be able to resolve a machine-readable EPS.

Across the primary event window require:

```text
Machine_Readable_EPS_Resolution
    = resolved source candidates / source-resolvable candidates

Machine_Readable_EPS_Resolution >= 95%
```

Below 95%:

```text
INVALID_RESEARCH_RUN
```

because selective extraction failure could bias the sample.

### 13.4 Structural SUE exclusions do not reduce source coverage

Legitimate economic/history exclusions such as:

- insufficient EPS history;
- fiscal-calendar change;
- incomparable reporting basis;
- zero historical SUE SD;
- corporate restructuring that destroys comparability

are not technical source-resolution failures and do not count against the 95% extraction-quality gate.

They must still be counted and reported separately.

---

## 14. Source snapshot architecture

Data acquisition and strategy validation must be separated.

### 14.1 Stage A — source snapshot

Stage A may access official external sources and normalize them into frozen immutable inputs.

Minimum normalized input package:

```text
Swing Trading/research/swing/e1_positive_earnings_surprise_drift/input/
├── e1_exchange_filings_snapshot.csv
├── e1_eps_snapshot.csv
├── e1_corporate_actions_snapshot.csv
├── e1_source_manifest.csv
└── e1_source_build_audit.csv
```

### 14.2 `e1_exchange_filings_snapshot.csv`

Retain one row per discovered official filing with enough provenance to audit deduplication and first-public identity, including at minimum:

```text
Symbol
Exchange
Fiscal_Period_End
Fiscal_Quarter
Reporting_Basis
Quarterly_or_Annual
Original_or_Revised
Public_Timestamp
Source_URL
Source_Record_ID
```

Do not silently deduplicate the raw normalized exchange records before audit evidence can establish how duplicates/revisions were resolved.

### 14.3 `e1_eps_snapshot.csv`

Retain normalized machine-readable EPS observations including at minimum:

```text
Symbol
Fiscal_Period_End
Reporting_Basis
EPS_Continuing_Operations_Basic
Source_Exchange
Source_URL
Public_Timestamp
Original_or_Revised
```

### 14.4 `e1_corporate_actions_snapshot.csv`

Retain the official per-share comparability actions required by Section 12, including at minimum:

```text
Symbol
Action_Type
Ratio
Ex_Date
Record_Date
Source_URL
```

### 14.5 `e1_source_manifest.csv`

Fingerprint each frozen source artifact and each read-only external repository input actually consumed by validation.

At minimum record:

```text
Artifact
Source
Retrieved_At
Row_Count
SHA256
Primary_Window
Notes
```

Also fingerprint:

- PIT Nifty 500 membership source;
- frozen stock-price corpus;
- frozen Nifty 500 benchmark-price source.

### 14.6 Stage A must be return-blind

Stage A may know filing/EPS/corporate-action facts.

Stage A must **not compute post-event stock returns or judge parsing quality from profitability**.

Source resolution must be completed before E1 returns are interpreted.

---

## 15. Frozen price and benchmark inputs

The formal E1 validator must not download market prices during a run.

Use a frozen price corpus and fingerprint it in `e1_source_manifest.csv`.

### 15.1 Required stock fields

For each potentially executable cohort event, validation needs enough daily data to establish:

- next-session entry Open;
- scheduled/early exit Open;
- daily High/Low during the holding period for MAE/MFE;
- corporate-action-consistent return measurement.

### 15.2 Corporate actions during trade-return measurement

Signal formation remains entirely independent of future price/corporate-action information.

For **ex-post return accounting only**, the price corpus or explicit cash-flow accounting must neutralize mechanical P&L distortions from:

- splits;
- consolidations;
- bonus issues;
- cash dividends/distributions received during the holding interval.

The chosen accounting convention must be deterministic and applied identically to positive, neutral and negative cohorts.

It must not alter entry eligibility, SUE or event timing.

### 15.3 Benchmark

For every completed trade/control, calculate a Nifty 500 total-return-consistent benchmark over the same entry and exit sessions.

The benchmark input must be frozen and deterministic. If the repository stores a price-index Open plus a separate total-return adjustment series, the implementation may deterministically construct a total-return-consistent open series, but the exact transformation must be fixed before outcomes are interpreted and must be covered by tests.

Benchmark receives no fictional E1 trading friction.

### 15.4 Missing/invalid price

If the immediate next canonical-session stock Open is genuinely unavailable/non-executable:

```text
NO_VALID_NEXT_SESSION_OPEN
```

and the event is cancelled/excluded from completed-trade evidence.

Do not defer the entry to a later day.

Genuine suspension, delisting, merger termination or other inability to transact must be explicitly audited; never silently drop an inconvenient outcome.

---

## 16. Frozen event-to-trade timing

### 16.1 Entry

For an eligible event whose result becomes public on date `T`:

```text
no trade on T
→ enter at the next canonical trading-session Open
```

This applies regardless of whether the result was published:

- before market open;
- during trading hours;
- after market close;
- on a weekend/holiday.

E1 deliberately sacrifices same-day responsiveness for a universally reproducible EOD workflow.

### 16.2 No gap filter

All qualifying `POSITIVE_SURPRISE` events use the next-session Open if executable.

Do not reject or require entries based on:

- positive gap;
- negative gap;
- gap size;
- first-day price direction;
- pullback after the result.

Initial reaction remains diagnostic only.

### 16.3 Primary holding period

Freeze a 40-complete-session holding horizon.

If entry occurs at canonical session index `s` Open:

```text
sessions s through s+39 are the 40 completed holding sessions
scheduled exit = session s+40 Open
```

Do not optimize 20/30/60-session alternatives after seeing E1 results.

### 16.4 Next earnings event before scheduled exit

If the same company publishes another valid quarterly earnings event before the scheduled exit Open:

```text
old event exits at the next eligible canonical-session Open
```

with:

```text
EXIT_NEXT_EARNINGS_EVENT
```

If the new event independently qualifies as `POSITIVE_SURPRISE`, it may create a new E1 entry at that same Open as a separate event/trade record.

There is no pyramiding or extension of the old trade.

If the next-event-triggered exit Open is the same as the scheduled fixed-horizon exit Open, use the same price and apply a deterministic documented exit-reason precedence; the economic outcome must not differ.

### 16.5 Primary exit style

Primary E1 uses **fixed-time/event-replacement exits only**.

Do not add:

- ATR stop;
- fixed percentage stop;
- SMA exit;
- trailing stop;
- breakeven stop;
- profit target;
- partial profit taking.

This isolates whether the earnings-surprise signal itself has drift.

---

## 17. Friction and return definitions

Use exactly:

```text
Base round-trip friction:    0.40%
Stress round-trip friction:  0.60%
Severe diagnostic friction: 0.80%
```

For any completed cohort observation:

```text
Gross_Return
    = corporate-action-consistent stock return
      from Entry_Open to Exit_Open

Base_Net_Return
    = Gross_Return - 0.004

Stress_Net_Return
    = Gross_Return - 0.006

Severe_Net_Return
    = Gross_Return - 0.008
```

There is no R-multiple because E1 has no initial stop defining `1R`.

For benchmark return `B` over exactly the same entry/exit sessions:

```text
Base_Net_Excess_Return
    = Base_Net_Return - B

Stress_Net_Excess_Return
    = Stress_Net_Return - B
```

The severe excess case may be reported diagnostically.

### 17.1 Profit-factor definition

For a return series `x`:

```text
PF(x)
    = sum(all positive x)
      / abs(sum(all negative x))
```

Handle empty positive/negative sides explicitly and deterministically; never silently coerce undefined PF to a convenient passing value.

---

## 18. Control experiment

The `NEUTRAL_CONTROL` and `NEGATIVE_CONTROL` cohorts use the **same hypothetical long mechanics** as the positive cohort:

- same next-session entry Open;
- same cancellation rules;
- same 40-complete-session scheduled hold;
- same earlier exit at next earnings event;
- same corporate-action accounting;
- same benchmark alignment;
- same base/stress/severe friction.

They are never actually traded by E1.

This lets E1 test whether the earnings-surprise direction discriminates outcomes rather than merely riding a generally rising market.

---

## 19. Accounting invariants

The validator must make event/trade accounting explicit.

At minimum:

```text
All valid finite SUE events
    = POSITIVE_SURPRISE
    + POSITIVE_BUFFER
    + NEUTRAL_CONTROL
    + NEGATIVE_BUFFER
    + NEGATIVE_CONTROL
```

with no overlap.

For each primary execution cohort:

```text
qualified cohort events
    = completed observations
    + explicit entry cancellations/exclusions
```

For every completed observation:

```text
stock Entry_Date == benchmark Entry_Date
stock Exit_Date  == benchmark Exit_Date
```

No completed observation may lack its exact benchmark pairing.

Every source candidate/event that disappears from execution evidence must have an explicit reason in the event/exclusion audit trail.

---

## 20. Integrity requirements

A research run is invalid if the evidence cannot establish the frozen methodology.

The integrity audit must verify at minimum:

- source snapshot artifacts exist, are readable and match their manifest hashes;
- PIT Nifty 500 membership input matches its frozen manifest fingerprint;
- stock and benchmark price inputs match their frozen manifest fingerprints;
- event timestamps are parseable and normalized consistently;
- the selected event is the earliest valid original public filing for its event key;
- revisions/duplicates never create additional primary events;
- later revisions/restatements never rewrite an earlier SUE history;
- every historical EPS used in `D[t-1]...D[t-8]` was public before the current event;
- current `D[t]` never contributes to the historical mean/SD;
- reporting basis remains identical throughout each SUE chain;
- fiscal-quarter identity is comparable throughout each SUE chain;
- corporate-action EPS adjustments use only actions effective on/before the event date;
- future corporate actions never alter earlier SUE values;
- cross-exchange EPS conflicts are either within tolerance or deterministically resolved;
- source technical resolution coverage is measured from the frozen candidate denominator;
- every valid SUE is classified exactly once;
- positive/neutral/negative execution cohorts use identical trade mechanics;
- `Event_Public_Date < Entry_Date` for completed/cancelled execution attempts;
- no same-day result trade exists;
- fixed-horizon exit session indexing is exact;
- next-earnings early exits use only a later public earnings event;
- completed stock/benchmark dates align exactly;
- all completed/cancelled cohort accounting reconciles;
- diagnostic fields do not alter mandatory eligibility or gates;
- the validator performs no network calls and does not modify frozen inputs.

Any systemic integrity failure takes precedence over profitability.

---

## 21. Sample sufficiency

Require at least:

```text
POSITIVE_SURPRISE completed observations >= 300
NEUTRAL_CONTROL completed observations  >= 300
NEGATIVE_CONTROL completed observations >= 300
```

Also require positive-surprise completed observations in each temporal half:

```text
FIRST positive completed  >= 100
SECOND positive completed >= 100
```

If integrity is clean but any of these counts fails:

```text
INSUFFICIENT_EVIDENCE
```

Do not loosen SUE, history length, universe or primary date window to manufacture more trades.

---

## 22. Mandatory E1 profitability gates

For the completed `POSITIVE_SURPRISE` cohort under **base 0.40% friction**, require all:

```text
Base_Mean_Net_Return >= +1.00%
Base_Median_Net_Return > 0
Base_Return_PF >= 1.20
Base_Mean_Net_Excess_Return > 0
Base_Excess_Return_PF > 1.00
```

The +1.00% mean threshold is intentionally economically meaningful for a roughly two-month holding period.

---

## 23. Mandatory stress-friction gates

At **0.60% round-trip friction**, require:

```text
Stress_Mean_Net_Return > 0
Stress_Return_PF > 1.00
Stress_Mean_Net_Excess_Return > 0
```

The 0.80% severe case is diagnostic only.

---

## 24. Mandatory earnings-surprise discrimination gates

Using base-friction completed cohorts, require mean stock returns to order:

```text
Positive_Mean_Net_Return
    > Neutral_Mean_Net_Return
    > Negative_Mean_Net_Return
```

Also require benchmark-adjusted means to order:

```text
Positive_Mean_Net_Excess_Return
    > Neutral_Mean_Net_Excess_Return
    > Negative_Mean_Net_Excess_Return
```

And require:

```text
Positive_Return_PF > Neutral_Return_PF
Positive_Return_PF > Negative_Return_PF
```

If the positive cohort makes money but does not discriminate according to earnings surprise, E1 fails.

---

## 25. Mandatory temporal robustness

For each frozen temporal half independently, on the positive cohort require:

```text
Base_Mean_Net_Return > 0
Base_Return_PF > 1.00
Base_Mean_Net_Excess_Return > 0
```

The sample sufficiency rule in Section 21 also requires at least 100 completed positive events in each half.

Calendar-year results remain diagnostic except for the leave-one-year-out test below.

---

## 26. Mandatory leave-one-calendar-year-out robustness

For every calendar year represented by the primary positive cohort:

1. remove all positive-cohort completed observations whose `Event_Public_Date` belongs to that year;
2. recompute the remaining positive-cohort metrics;
3. require all:

```text
Remaining Base_Mean_Net_Return > 0
Remaining Base_Return_PF > 1.00
Remaining Base_Mean_Net_Excess_Return > 0
```

Every year omission must pass.

Do not cherry-pick only unusual years.

---

## 27. Mandatory top-five-winner robustness

Rank completed positive-cohort observations by **gross stock return**.

Remove exactly the five highest gross-return winners.

On the remaining positive cohort require:

```text
Base_Mean_Net_Return > 0
Base_Return_PF > 1.00
Base_Mean_Net_Excess_Return > 0
```

This prevents a few extraordinary post-result winners from manufacturing the entire edge.

---

## 28. Mandatory leave-one-symbol-out robustness

For every distinct symbol appearing in completed positive-cohort evidence:

1. remove all completed positive observations for that symbol;
2. recompute the remaining metrics;
3. require all:

```text
Base_Mean_Net_Return > 0
Base_Return_PF > 1.00
Base_Mean_Net_Excess_Return > 0
```

Every symbol omission must pass.

---

## 29. Downside diagnostics — mandatory to report, not gates

Because E1 intentionally has no technical stop, the evidence package must report at minimum:

- worst completed positive trade;
- 1st percentile positive-cohort return;
- 5th percentile positive-cohort return;
- maximum adverse excursion distribution;
- maximum favourable excursion distribution;
- median within-trade drawdown;
- maximum within-trade drawdown;
- entry-gap / initial-reaction distribution;
- next-earnings-event truncated exits;
- suspension/termination edge cases if any.

These diagnostics may reveal implementation risk but cannot be retrofitted into the E1 signal after results are known.

---

## 30. Approved non-gating diagnostics

The following cuts may be reported without affecting the primary result:

- SUE `1-2`, `2-3`, `3-5`, `>=5`;
- profit -> profit;
- loss -> profit;
- loss -> smaller loss;
- profit -> loss;
- entry-gap / initial-reaction buckets;
- market-cap bucket;
- liquidity bucket;
- sector;
- reporting basis;
- fiscal quarter;
- announcement weekday;
- calendar year;
- holding duration / next-event truncation.

The diagnostic output must structurally mark these as non-mandatory or keep them outside `evaluate_gates()`.

A diagnostic cannot become a rescue filter inside E1.

---

## 31. Capacity diagnostics — mandatory to report, not gates

Signal-level validation retains every qualifying observation independently.

Do not impose the eventual 3-5-position portfolio limit yet.

Report at minimum:

- maximum simultaneous active positive trades;
- median simultaneous active positive trades;
- same-day positive entry counts;
- event-season clustering;
- sector clustering/concentration;
- capital-utilization implications if useful.

If E1 passes, portfolio-constrained simulation becomes the next experiment.

---

## 32. Minimum source input package

Stage A must freeze at least:

```text
e1_exchange_filings_snapshot.csv
e1_eps_snapshot.csv
e1_corporate_actions_snapshot.csv
e1_source_manifest.csv
e1_source_build_audit.csv
```

These files are immutable inputs to formal validation.

The formal validator must reject missing or fingerprint-mismatched inputs rather than silently rebuilding them.

---

## 33. Minimum validation evidence package

Formal validation must generate at least:

```text
output/
├── e1_data_validation.csv
├── e1_source_coverage.csv
├── e1_event_master.csv
├── e1_event_exclusions.csv
├── e1_eps_history.csv
├── e1_sue_events.csv
├── e1_cohort_classification.csv
│
├── e1_positive_trades.csv
├── e1_neutral_control.csv
├── e1_negative_control.csv
│
├── e1_validation_summary.csv
├── e1_cohort_comparison.csv
├── e1_benchmark_comparison.csv
├── e1_temporal_summary.csv
├── e1_year_summary.csv
├── e1_leave_one_year_out.csv
├── e1_top_five_robustness.csv
├── e1_leave_one_symbol_out.csv
│
├── e1_downside_diagnostic.csv
├── e1_diagnostic_summary.csv
├── e1_overlap_capacity_diagnostic.csv
│
├── e1_integrity_audit.csv
├── e1_validation_gates.csv
└── research_report.md
```

No dashboard or notebook is required for the formal result.

---

## 34. Core evidence semantics

### 34.1 `e1_event_master.csv`

Every PIT Nifty 500 timely-result candidate before SUE eligibility, retaining at minimum:

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
```

### 34.2 `e1_event_exclusions.csv`

Every excluded event with one primary reason and enough detail for audit.

Approved reasons include, as applicable:

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

Additional integrity-oriented reason codes may be introduced only where necessary to describe a frozen requirement precisely; they must not create new strategy filters.

### 34.3 `e1_eps_history.csv`

For every calculable event retain enough data to independently reproduce SUE, including:

```text
Event_ID
Current_EPS
EPS_t_minus_4
D_t
D_t_minus_1
D_t_minus_2
D_t_minus_3
D_t_minus_4
D_t_minus_5
D_t_minus_6
D_t_minus_7
D_t_minus_8
Historical_Mean
Historical_SD
SUE
```

### 34.4 `e1_cohort_classification.csv`

Every valid finite SUE event exactly once with its frozen cohort label.

### 34.5 Trade/control evidence

All positive/neutral/negative primary execution files use the same core fields, including at minimum:

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
Nifty500_Entry_Value
Nifty500_Exit_Value
Benchmark_Return
Base_Net_Excess_Return
Stress_Net_Excess_Return
```

Include the fields required to reproduce MAE/MFE and initial-reaction diagnostics.

---

## 35. Source-coverage evidence

`e1_source_coverage.csv` must expose at minimum:

```text
PIT timely-result candidates
source-resolvable candidates
machine-readable EPS resolved
technical EPS unresolved
machine-readable resolution percentage
consolidated selected
standalone fallback selected
NSE-only resolved
BSE-only resolved
cross-exchange resolved
cross-exchange mismatches
original filings selected
revisions ignored
SUE available
SUE unavailable by reason
```

The frozen 95% technical source-resolution gate must be explicit in evidence and in the final gate table.

---

## 36. Formal gate artifact and status precedence

`e1_validation_gates.csv` is the only authority for formal E1 status.

Each gate must record at minimum:

```text
Gate
Value
Threshold
Pass
Mandatory
```

The final status precedence is exactly:

```text
if systemic integrity violations > 0:
    INVALID_RESEARCH_RUN

elif machine-readable source resolution < 95%:
    INVALID_RESEARCH_RUN

elif positive completed < 300
     or neutral completed < 300
     or negative completed < 300
     or FIRST positive completed < 100
     or SECOND positive completed < 100:
    INSUFFICIENT_EVIDENCE

elif every mandatory strategy gate passes:
    PASS

else:
    FAIL
```

There is no fifth state such as:

- promising;
- borderline;
- conditional pass;
- needs tuning.

---

## 37. Mandatory gate checklist

A valid and sufficient E1 run passes only if **every** mandatory strategy gate below passes.

### Integrity / sufficiency

```text
SYSTEMIC_INTEGRITY_ZERO
SOURCE_TECHNICAL_RESOLUTION >= 95%
POSITIVE_SAMPLE >= 300
NEUTRAL_SAMPLE >= 300
NEGATIVE_SAMPLE >= 300
FIRST_POSITIVE_SAMPLE >= 100
SECOND_POSITIVE_SAMPLE >= 100
```

### Base positive-cohort economics

```text
BASE_MEAN_NET_RETURN >= +1.00%
BASE_MEDIAN_NET_RETURN > 0
BASE_RETURN_PF >= 1.20
BASE_MEAN_NET_EXCESS_RETURN > 0
BASE_EXCESS_RETURN_PF > 1.00
```

### Stress economics

```text
STRESS_MEAN_NET_RETURN > 0
STRESS_RETURN_PF > 1.00
STRESS_MEAN_NET_EXCESS_RETURN > 0
```

### Surprise discrimination

```text
POSITIVE_MEAN > NEUTRAL_MEAN > NEGATIVE_MEAN
POSITIVE_EXCESS_MEAN > NEUTRAL_EXCESS_MEAN > NEGATIVE_EXCESS_MEAN
POSITIVE_PF > NEUTRAL_PF
POSITIVE_PF > NEGATIVE_PF
```

### Temporal robustness

```text
FIRST_MEAN > 0
FIRST_PF > 1.00
FIRST_EXCESS_MEAN > 0

SECOND_MEAN > 0
SECOND_PF > 1.00
SECOND_EXCESS_MEAN > 0
```

### Robustness

```text
EVERY_LEAVE_ONE_YEAR_OUT:
    mean > 0
    PF > 1.00
    excess mean > 0

TOP_FIVE_WINNERS_REMOVED:
    mean > 0
    PF > 1.00
    excess mean > 0

EVERY_LEAVE_ONE_SYMBOL_OUT:
    mean > 0
    PF > 1.00
    excess mean > 0
```

The 0.80% severe-friction case, diagnostic buckets, downside statistics and capacity statistics are not mandatory gates.

---

## 38. Research report

`research_report.md` must be generated mechanically from formal evidence and contain exactly these decision-focused sections:

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
20. One formal conclusion and explicit next action

The report must not recommend alternate thresholds, stop rules, gap filters, sectors, regimes or holding periods after seeing results.

---

## 39. One-command formal validation

After the source snapshot and market-price inputs are frozen:

```bash
python run_e1_validation.py
```

must generate the complete evidence package.

The formal validation run must:

- perform no network calls;
- not modify frozen source snapshots;
- not modify V3/M1 or their evidence;
- be deterministic for identical manifest hashes;
- fail loudly on missing/mismatched input fingerprints;
- produce one formal E1 status.

Source acquisition is a separate explicit process/command and is not allowed to run implicitly inside `run_e1_validation.py`.

---

## 40. Hard out-of-scope list for E1 V1

Explicitly prohibited:

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
- sector filters;
- volume confirmation;
- positive-gap requirement;
- gap-size exclusion;
- ATR stop;
- fixed percentage stop;
- trailing stop;
- profit target;
- alternate 20/60-day primary exits;
- SUE threshold optimization;
- retrospective top-decile SUE ranking;
- profit-only company filter;
- loss-company exclusion;
- machine learning;
- PDF/OCR rescue;
- dashboard building;
- generic financial-data warehouse/platform work.

These may be separate future hypotheses only if the project still has research budget and the primary E1 result is already formally closed.

---

## 41. Explicit no-rescue rule

If E1 fails, do **not** rescue it by trying:

- `SUE >= 1.5` or `SUE >= 2`;
- six historical seasonal changes;
- 20-day/30-day/60-day exits;
- positive initial gap only;
- excluding large gaps;
- trend/RS confirmation;
- market-regime filters;
- sector filters;
- only profit-making companies;
- excluding loss-to-profit events;
- optimized stop losses;
- only specific years.

Any such idea would require a new named predeclared hypothesis and would consume separate research budget.

The default next action after a valid E1 `FAIL` or `INSUFFICIENT_EVIDENCE` is to move to the final remaining independent non-event candidate rather than continue PEAD strategy shopping.

---

## 42. Decision path after the run

### 42.1 PASS

If every mandatory gate passes:

```text
PASS
→ stop signal-family research
→ portfolio-constrained simulation
→ 3-5 position slots
→ event collisions / candidate ranking
→ position sizing
→ cash utilization
→ portfolio drawdown
→ small-account feasibility
→ forward/paper validation
```

Historical PASS is not immediate permission to deploy live capital.

### 42.2 FAIL

If integrity and sample are sufficient but any mandatory strategy gate fails:

```text
FAIL
→ close E1 permanently as specified
→ no PEAD rescue
→ move to final remaining independent non-event candidate
```

The remaining research candidate is expected to be one of:

- objective range reversion; or
- volatility compression -> expansion.

Choose that separately before implementation; do not blend it into E1.

### 42.3 INSUFFICIENT_EVIDENCE

If primary or temporal cohort sufficiency fails:

```text
INSUFFICIENT_EVIDENCE
→ do not extend history opportunistically
→ do not loosen SUE/history requirements
→ move on
```

### 42.4 INVALID_RESEARCH_RUN

If systemic integrity/source-quality requirements fail:

```text
INVALID_RESEARCH_RUN
→ repair only the research/data-integrity defect
→ rerun the unchanged frozen E1 methodology
```

---

## 43. Final frozen E1 summary

```text
Official NSE/BSE original quarterly filings
                ↓
PIT Nifty500 on Event_Public_Date
                ↓
timely result (45d / 60d rule)
                ↓
consistent quarterly reporting basis
                ↓
Basic EPS from continuing operations
                ↓
corporate-action comparable 13-quarter history
                ↓
8 prior seasonal EPS changes
                ↓
SUE = (current seasonal change - prior mean) / prior sample SD
                ↓
SUE >= +1.0
                ↓
next-session Open
                ↓
no gap / momentum / regime / trend filter
                ↓
40 complete sessions
(or earlier next quarterly earnings event)
                ↓
fixed exit, no technical stop/target
                ↓
0.40% base / 0.60% stress / 0.80% severe diagnostic
                ↓
Nifty500 total-return-consistent benchmark
                ↓
neutral + negative long-control cohorts
                ↓
temporal / year / top-five / symbol robustness
                ↓
PASS / FAIL / INSUFFICIENT_EVIDENCE / INVALID_RESEARCH_RUN
```

This specification is the frozen methodology for E1. Implementation must follow it mechanically and must not introduce new strategic degrees of freedom.