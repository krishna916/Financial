# M1 Regime-Gated Momentum Resumption — Design Specification

**Status:** APPROVED DESIGN — implementation/backtest not yet started  
**Design date:** 29 August 2026  
**Research family:** Candidate 1 — Predeclared Regime-Aware Momentum  
**Primary decision:** Determine whether a simple, independently predeclared broad-market regime gate makes the frozen V3 momentum/resumption setup strong enough to advance toward a final deployable swing strategy.

---

## 1. Project-goal alignment

This experiment exists to advance **Swing Trading Strategy Finalization**. It is not a research-platform, dashboard, analytics, or generic-framework project.

The question is intentionally narrow:

> **Do long-only relative-strength momentum/resumption trades have positive practical expectancy after realistic friction when they are entered only during an independently defined broad-market momentum regime, while otherwise remaining in cash?**

The required workflow is:

```text
predeclared hypothesis
→ frozen M1 methodology
→ one historical validation
→ PASS / FAIL / INSUFFICIENT_EVIDENCE / INVALID_RESEARCH_RUN
→ next strategy-finalization decision
```

No post-result threshold tuning or strategy rescue is allowed.

If M1 passes signal-level validation, the next phase is **portfolio/execution finalization**, not another signal-family search.

---

## 2. Why M1 exists

Strategy V3 — RS Leader → Shallow Pullback → First Resumption — failed overall.

Its frozen historical result was approximately:

- 1,465 completed paired outcomes;
- setup mean return ~+0.16%;
- setup PF ~1.06;
- practical mean ~0R;
- practical R-PF ~1.00.

A post-result diagnostic showed materially different outcomes across market environments, including approximately:

```text
Observed STRONG_MOMENTUM diagnostic:
setup mean        ~ +0.97%
setup PF          ~ 1.35
practical mean    ~ +0.20R
practical R-PF    ~ 1.38
```

That observation **does not rescue V3** because the subgroup was examined after outcomes were known.

M1 is therefore a new hypothesis. Its regime definition is chosen and frozen before M1 outcomes are examined.

### Contamination guardrail

The existing market-breadth research module contains an old diagnostic `STRONG_MOMENTUM` classification defined using:

```text
Nifty500 Close > SMA200
Pct_Above_SMA50 >= 60%
Pct_Above_SMA200 >= 60%
```

**M1 must never use that existing `Regime` label or those 60% thresholds as its eligibility rule.**

M1 may reuse only the underlying point-in-time breadth/membership data and index-price fields required to compute its independently frozen rule.

---

## 3. Strategy identity

**Name:** M1 — Regime-Gated Momentum Resumption

### Economic hypothesis

> Among liquid point-in-time Nifty 500 stocks already exhibiting relative-strength leadership and a shallow-pullback resumption setup, entries taken only while the broad market is in an objectively healthy momentum regime should have positive practical expectancy after realistic friction and should outperform otherwise-identical opportunities occurring while the regime is disabled.

### Strategic change versus V3

M1 changes exactly **one strategic dimension**:

```text
Frozen V3 stock setup
        +
MOMENTUM_ENABLED on signal-date close
        ↓
M1 eligible signal
```

Everything else remains frozen from V3 unless this specification explicitly states otherwise.

---

## 4. Research window and trading model

### Primary signal window

```text
2023-08-01 through 2026-08-25 inclusive
```

### Market/instrument constraints

- Indian cash equities;
- long-only;
- Nifty 500 point-in-time universe;
- no F&O;
- no leverage;
- end-of-day signal formation;
- next canonical-session execution;
- no intraday signal dependency;
- cash is the only action for this module while momentum is disabled.

### Timing principle

All M1 eligibility information must be known by the **signal-date close**.

For a signal generated on session `T`:

```text
T close:
  stock setup is known
  index Close/SMA50/SMA200 are known
  PIT breadth is known
  M1 regime is known

T+1:
  next-session entry opportunity if M1 enabled
```

No future regime observation may be used for the signal.

---

## 5. Frozen M1 market regime

M1 has only two operational states:

```text
MOMENTUM_ENABLED
MOMENTUM_DISABLED
```

There is no reduced-risk middle state during validation.

### 5.1 DATA_SAFE

For session `T`:

```text
SMA50_Breadth_Coverage[T]
    = valid PIT Nifty500 members with usable SMA50 on T
      / active PIT Nifty500 members on T

DATA_SAFE[T] = SMA50_Breadth_Coverage[T] >= 0.80
```

Membership must come from the existing point-in-time Nifty 500 interval manifest.

No constituent survivorship backfill is allowed.

### 5.2 INDEX_TREND_OK

Using the Nifty 500 index on session `T`:

```text
INDEX_TREND_OK[T] =
    Nifty500_Close[T] > Nifty500_SMA200[T]
    AND
    Nifty500_SMA50[T] > Nifty500_SMA200[T]
```

Both conditions are mandatory.

### 5.3 BREADTH_OK

Using active PIT Nifty 500 constituents with valid SMA50 data on `T`:

```text
Pct_Above_SMA50[T]
    = 100 * count(Close > SMA50) / valid SMA50 denominator

BREADTH_OK[T] = Pct_Above_SMA50[T] >= 50.0
```

The 50% threshold represents majority participation. It is not selected from V3 outcomes.

### 5.4 Final regime rule

```text
MOMENTUM_ENABLED[T] =
    DATA_SAFE[T]
    AND INDEX_TREND_OK[T]
    AND BREADTH_OK[T]
```

Otherwise:

```text
MOMENTUM_DISABLED[T]
```

### 5.5 Explicitly excluded regime rules

M1 does **not** use:

- the old `STRONG_MOMENTUM` label;
- 60% breadth thresholds;
- percent above SMA200 as an additional gate;
- VIX/volatility filters;
- sector breadth;
- sector-RS filters;
- trailing market-return filters;
- 3-of-5-day or other persistence/hysteresis logic;
- discretionary regime overrides.

The regime may switch daily.

### 5.6 Regime after entry

The regime is an **entry gate only**.

Once an M1 trade is entered, later `MOMENTUM_DISABLED` observations do not create a new exit rule.

The trade continues under the frozen V3 practical exit mechanics.

---

## 6. Frozen stock-level setup inherited from V3

M1 uses the V3 stock setup without strategic modification.

At seed/signal points as applicable, retain the V3 requirements and semantics:

- point-in-time Nifty 500 membership;
- research-safe point-in-time cross-sectional RS coverage;
- 20-session median traded value >= ₹10 crore;
- `Close > SMA50 > SMA200`;
- Composite RS >= 70;
- Composite RS horizons `21/63/126` with weights `0.30/0.40/0.30`;
- leader seed = 20-session closing high using the frozen equality semantics;
- one active pullback state per symbol;
- valid resumption age 3–10 sessions inclusive;
- running pullback depth normalized by seed ATR14;
- candidate pullback depth >= 0.5 ATR and <= 2.5 ATR;
- no close below SMA50 while state remains valid;
- first valid resumption trigger exactly as frozen in V3;
- no post-hoc volume, RSI, MACD, ADX, candlestick, sector, event, or breadth stock filter.

M1 must not silently alter the V3 state-machine ordering or qualification semantics.

---

## 7. Frozen entry and cancellation mechanics

For a stock setup qualified at signal-date close `T`:

### 7.1 Enabled signal

If:

```text
MOMENTUM_ENABLED[T] == TRUE
```

then the signal proceeds to the exact V3 immediate-next-session entry opportunity.

Retain V3 entry mechanics, including:

- immediate next canonical session Open only;
- `Entry_Open >= SMA20_signal`;
- `Entry_Open <= Leader_Close + 0.5 * ATR14_signal`;
- structural stop = running pullback low through signal bar inclusive minus `0.25 * ATR14_signal`;
- reject if structural stop is not below entry;
- reject if entry-to-stop distance exceeds `2.5 * ATR14_signal`;
- retain the existing deterministic cancellation-reason accounting.

Accepted enabled entries become the M1 trade cohort.

### 7.2 Disabled signal

If:

```text
MOMENTUM_ENABLED[T] == FALSE
```

then M1 takes no trade and remains in cash.

The signal is **not deferred or revived** if the regime becomes enabled later.

A future trade requires a completely new valid stock setup/signal.

---

## 8. Disabled cohort as the regime-control sample

The core M1 hypothesis is not merely that enabled trades are profitable. The regime gate must also discriminate between environments.

Therefore every otherwise-valid V3 stock signal must be assigned exactly once to:

```text
ENABLED
or
DISABLED
```

### 8.1 Apples-to-apples shadow entry treatment

A disabled signal is not automatically treated as an executable control trade.

For control purposes only, the disabled signal must pass through the **same frozen V3 next-session entry/cancellation mechanics** as an enabled signal.

Thus:

```text
DISABLED signal
→ shadow T+1 V3 entry check
→ if V3 entry would be cancelled: record disabled cancellation only
→ if V3 entry would be accepted: create disabled control entry
→ simulate the same frozen V3 outcome mechanics
```

This prevents the control cohort from containing trades that would never have been executable under the stock strategy.

Disabled control entries are hypothetical research observations only. M1 never trades them.

### 8.2 Control comparability

Enabled and disabled completed practical cohorts must use identical:

- stock qualification;
- entry timing;
- entry cancellation rules;
- structural stop;
- exit mechanics;
- friction formulas.

The market regime is the only strategic partition.

---

## 9. Frozen exits

M1 uses the V3 exit mechanics unchanged.

### 9.1 Setup-quality lens

- ignores the structural stop;
- exit at next session Open after the first `Close < SMA20` signal;
- setup lens exists to assess the underlying stock/regime edge before stop mechanics.

### 9.2 Practical lens

Retain V3 precedence exactly:

```text
1. previously scheduled SMA20 exit at current Open
2. gap-through structural stop → current actual Open
3. intraday Low <= structural stop → structural stop
4. if current Close < SMA20 → schedule next-session Open exit
```

No target, breakeven rule, ATR trail, hard time stop, profit-taking rule, pyramiding, averaging down, or regime-triggered exit is added.

---

## 10. Trading friction

M1 must be evaluated after explicit round-trip friction.

```text
Base friction:    0.40%
Stress friction:  0.60%
Severe diagnostic: 0.80%
```

### 10.1 Setup-quality net return

For friction `c`:

```text
Net_Return = Gross_Return - c
```

### 10.2 Practical net R

For accepted practical entries:

```text
Initial_Risk = Entry_Open - Structural_Stop

Net_R =
    ((Exit_Price - Entry_Open) - c * Entry_Open)
    / Initial_Risk
```

Gap-stop losses may be worse than `-1R`.

The 0.80% severe case is diagnostic only and is not a mandatory gate.

---

## 11. Accounting invariants

The implementation must make cohort accounting explicit and auditable.

At minimum:

```text
All otherwise-valid V3 qualified signals
    = ENABLED qualified signals
    + DISABLED qualified signals
```

For enabled signals:

```text
Enabled_Qualified = Enabled_Accepted + Enabled_Cancelled
```

For disabled shadow controls:

```text
Disabled_Qualified = Disabled_Shadow_Accepted + Disabled_Shadow_Cancelled
```

For completed enabled trades:

```text
Setup completed Entry_ID set == Practical completed Entry_ID set
```

Every signal must have exactly one regime classification tied to its signal date.

---

## 12. Integrity requirements

A research run is invalid if the evidence cannot establish the frozen methodology.

The integrity audit must verify at minimum:

- active PIT membership where required;
- point-in-time RS coverage and values under frozen V3 semantics;
- stock signal precedes entry;
- signal date lies inside the primary window;
- regime context date equals the stock `Signal_Date` exactly;
- no future regime row is used;
- M1 regime recomputes from the frozen 50% breadth rule, not the old regime label;
- breadth coverage denominator is PIT-safe;
- Nifty 500 index Close/SMA50/SMA200 values correspond to the signal date;
- each otherwise-valid V3 signal is classified exactly once as ENABLED or DISABLED;
- enabled entry is the immediate next canonical session when accepted;
- disabled shadow entry uses the same next-session rule;
- enabled and disabled cancellation mechanics match frozen V3 semantics;
- structural stop and initial risk recompute correctly;
- setup/practical completed enabled Entry_ID sets match;
- required evidence artifacts are present, readable, and schema-valid.

Any mandatory integrity violation forces:

```text
INVALID_RESEARCH_RUN
```

Profitability must not be interpreted until integrity is clean.

---

## 13. Sample sufficiency

The primary M1 cohort requires:

```text
Completed paired ENABLED M1 trades >= 300
```

If the run is otherwise valid but has fewer than 300 completed enabled trades:

```text
INSUFFICIENT_EVIDENCE
```

Do not loosen the market regime, stock setup, or entry mechanics to manufacture more trades.

Enabled-vs-disabled comparison metrics must also be computable from non-empty completed cohorts. If the control comparison cannot be computed, the evidence is insufficient rather than a PASS.

---

## 14. Mandatory strategy gates

All gates below are frozen before M1 results are examined.

### 14.1 Base-cost setup-quality gates

Using **0.40% friction** on completed enabled setup-quality trades:

```text
Mean Net Return > 0
Net Return PF >= 1.20
```

### 14.2 Base-cost practical gates

Using **0.40% friction** on completed enabled practical trades:

```text
Mean Net R >= +0.15R
Net R-PF >= 1.20
```

These are the primary deployability gates.

### 14.3 Stress-cost practical gates

Using **0.60% friction**:

```text
Mean Net R > 0
Net R-PF > 1.00
```

The edge must survive modestly worse implementation friction.

### 14.4 Regime-discrimination gates

Using **0.40% base-cost practical outcomes** from otherwise-identical executable cohorts:

```text
Mean_Net_R_ENABLED > Mean_Net_R_DISABLED
AND
Net_R_PF_ENABLED > Net_R_PF_DISABLED
```

The disabled cohort does not need to be negative. The gate tests whether the M1 market filter actually improves momentum economics.

If enabled is profitable but does not beat disabled on both measures, the regime-gating hypothesis fails.

### 14.5 Fixed temporal robustness

Use the same fixed chronological split as prior research:

```text
FIRST_HALF:
2023-08-01 through 2025-02-11 inclusive

SECOND_HALF:
2025-02-12 through 2026-08-25 inclusive
```

Within **each half**, using base-cost practical enabled trades:

```text
Mean Net R > 0
Net R-PF > 1.00
```

Calendar-year summaries are diagnostic only.

### 14.6 Top-five-winner robustness

Rank completed enabled practical trades by **Gross R** and remove the five largest winners.

On the remaining base-cost practical sample:

```text
Mean Net R > 0
Net R-PF > 1.00
```

### 14.7 Leave-one-symbol-out robustness

For every symbol represented in the enabled completed practical cohort:

```text
remove every trade for that symbol
recompute base-cost practical results
```

Every omission sample must satisfy:

```text
Mean Net R > 0
Net R-PF > 1.00
```

---

## 15. Diagnostics only — never post-hoc filters

Report, but do not gate or optimize on:

- percentage/number of sessions with M1 momentum enabled;
- enabled vs disabled qualified/accepted/cancelled counts;
- calendar-year performance;
- win rate;
- gross and net return distributions;
- gross and net R distributions;
- median/mean holding sessions;
- exit-reason distribution;
- breadth distribution;
- Nifty 500 distance from SMA200;
- stock Composite RS bands;
- pullback age/depth;
- entry extension;
- signal clustering;
- maximum simultaneous accepted signals;
- same-day signal count distribution;
- sector concentration where a reliable mapping already exists;
- implied capital/capacity under eventual ~1% portfolio-risk sizing.

Diagnostics may motivate future research notes but **must not change M1 after outcomes are known**.

No diagnostic subgroup can rescue a failed M1 run.

---

## 16. Minimum evidence package

The implementation should produce only the evidence needed to make the strategy decision.

At minimum persist:

```text
M1 module output/
├── m1_data_validation.csv
├── m1_regime_daily.csv
├── m1_regime_audit.csv
├── m1_signal_classification.csv
├── m1_enabled_entries.csv
├── m1_enabled_cancellations.csv
├── m1_disabled_shadow_entries.csv
├── m1_disabled_shadow_cancellations.csv
├── m1_setup_quality_trades.csv
├── m1_practical_trades.csv
├── m1_disabled_setup_control.csv
├── m1_disabled_practical_control.csv
├── m1_validation_summary.csv
├── m1_regime_comparison.csv
├── m1_temporal_summary.csv
├── m1_year_summary.csv
├── m1_top_five_robustness.csv
├── m1_leave_one_symbol_out.csv
├── m1_overlap_capacity_diagnostic.csv
├── m1_integrity_audit.csv
├── m1_validation_gates.csv
└── research_report.md
```

Do not build a dashboard, generic strategy engine, interactive UI, or unrelated analytics system for M1.

Raw Yahoo downloads and giant reusable feature caches should not be committed unless already part of an existing repository convention and strictly required.

---

## 17. Final report structure

`research_report.md` should conclude mechanically with:

1. frozen M1 hypothesis and rules;
2. data/PIT coverage;
3. M1 regime distribution;
4. signal/cohort accounting;
5. base setup-quality results;
6. base practical results;
7. stress/severe friction results;
8. enabled-vs-disabled regime comparison;
9. temporal halves;
10. calendar-year diagnostics;
11. top-five-winner robustness;
12. leave-one-symbol-out robustness;
13. overlap/capacity diagnostics;
14. integrity audit;
15. mandatory gate table;
16. one formal final status.

The report must not recommend threshold changes or rescue experiments.

---

## 18. Formal status hierarchy

The run has exactly four formal outcomes.

### `INVALID_RESEARCH_RUN`

Use when any mandatory integrity issue exists, including missing/corrupt required evidence or unverifiable timing/cohort logic.

Integrity takes precedence over all profitability interpretation.

### `INSUFFICIENT_EVIDENCE`

Use when the run is valid but has fewer than 300 completed paired enabled trades, or required enabled-vs-disabled comparison metrics cannot be computed.

Do not loosen the regime to increase sample size.

### `PASS`

Use only when:

- integrity is clean;
- evidence is sufficient;
- **every mandatory strategy gate passes**.

### `FAIL`

Use when the run is valid and sufficiently sampled but at least one mandatory strategy gate fails.

A valid FAIL is a successful research execution and closes M1.

---

## 19. Post-result stopping rule

### If M1 = PASS

Stop signal-level strategy research for M1.

The next work is:

```text
M1 signal-level PASS
→ portfolio-constrained simulation
→ 3–5 maximum concurrent positions
→ ~1% portfolio-risk sizing
→ ranking when eligible signals exceed available slots
→ sector/correlation concentration
→ portfolio drawdown
→ cash utilisation
→ realistic Indian transaction friction
→ paper/forward validation
→ small-capital live validation
→ gradual scaling only after evidence
```

Do **not** automatically move to Candidate 2 merely because another strategy would be interesting.

A passing M1 is a candidate final swing module and should be made executable first.

### If M1 = FAIL

Close M1 permanently.

Do not rescue by changing:

- breadth 50% to another threshold;
- SMA50/SMA200 regime definitions;
- persistence/hysteresis;
- RS threshold;
- pullback depth/age;
- stock trend rule;
- extension threshold;
- structural stop;
- SMA20 exit;
- friction assumption;
- sector filters;
- year filters;
- old `STRONG_MOMENTUM` labels.

Proceed directly to:

```text
Candidate 2 — Post-Results / Post-Earnings Drift
```

### If M1 = INSUFFICIENT_EVIDENCE

Do not loosen M1 to manufacture trades.

Proceed to Candidate 2 while retaining M1 as unproven.

### If M1 = INVALID_RESEARCH_RUN

Fix only the research-integrity/data/implementation defect necessary to execute the frozen design correctly, then rerun M1 unchanged.

---

## 20. Non-negotiable anti-drift guardrails

1. **M1 tests regime gating, not a redesign of V3.**
2. **The old post-hoc `STRONG_MOMENTUM` bucket is forbidden as an M1 filter.**
3. **No outcome-driven threshold changes.**
4. **No post-hoc subgroup rescue.**
5. **No new market/sector/indicator filter unless a future separately named hypothesis is approved before seeing its outcomes.**
6. **Research infrastructure must remain minimal and strategy-decision-oriented.**
7. **PASS means move toward portfolio/execution finalization.**
8. **FAIL means close M1 and move to the next predeclared candidate.**
9. **Cash while disabled is part of the strategy, not a missing trade.**
10. **The purpose is to finish with a swing strategy that can actually be used.**

---

## 21. Frozen M1 summary

```text
M1 — Regime-Gated Momentum Resumption

Signal-date market gate:
    SMA50 breadth coverage >= 80%
    Nifty500 Close > SMA200
    Nifty500 SMA50 > SMA200
    >= 50% of valid PIT Nifty500 constituents above SMA50

If all true:
    MOMENTUM_ENABLED
Else:
    MOMENTUM_DISABLED → CASH

Stock setup:
    frozen V3 RS-leader shallow-pullback first-resumption rules

Entry:
    frozen V3 immediate next-session entry/cancellation rules

Exit:
    frozen V3 setup-quality and practical mechanics

Friction:
    0.40% base
    0.60% stress
    0.80% diagnostic

Minimum enabled completed sample:
    300 paired trades

Primary base practical gates:
    Mean Net R >= +0.15R
    Net R-PF >= 1.20

Stress practical gates:
    Mean Net R > 0
    Net R-PF > 1.00

Regime discrimination:
    enabled Mean Net R > disabled Mean Net R
    enabled Net R-PF > disabled Net R-PF

Robustness:
    both fixed temporal halves positive/PF > 1
    top-five-winner removal positive/PF > 1
    every leave-one-symbol-out sample positive/PF > 1

Formal result:
    INVALID_RESEARCH_RUN
    INSUFFICIENT_EVIDENCE
    PASS
    FAIL
```

This specification is frozen before M1 backtest outcomes are examined.