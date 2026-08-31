# RR1 — Objective Range Sweep Reversion — Research Design

**Status:** Design approved in chat; implementation and historical validation not started  
**Design date:** 31 August 2026  
**Issue:** #37  
**Research family:** Objective range reversion / failed-auction mean reversion  
**Research-program role:** Candidate 3, the final predeclared strategy-family test

---

## 1. Objective

RR1 tests one narrow hypothesis:

> Among liquid point-in-time Nifty 500 stocks that have spent roughly three months in an objectively non-directional range, a downside excursion below the established range followed by an EOD close back inside that range represents a failed downside auction often enough that buying at the immediately following market-session open produces positive, practically exploitable reversion toward the pre-signal range midpoint after realistic trading friction.

In compact form:

```text
objective sideways range
-> downside sweep below established range low
-> close back inside range
-> next-session long entry
-> reversion toward pre-signal range midpoint
```

RR1 is deliberately independent from the failed momentum/breakout architectures T1, V2, V3 and M1.

RR1 is also not a rescue of R1. R1 tested:

```text
large one-day negative price shock
+ low participation
-> short-horizon reversal
```

RR1 instead tests:

```text
pre-existing non-directional range
+ failed downside range break
-> range reversion
```

RR1 has no primary low-volume, shock-size, momentum, relative-strength, sector or market-regime condition.

---

## 2. Research discipline and stopping rule

Use the established project discipline:

> **One hypothesis -> one frozen methodology -> one test -> one verdict.**

Hard rules:

- Do not optimize the 60-session range length after outcomes.
- Do not optimize the efficiency-ratio threshold after outcomes.
- Do not change the sweep/reclaim definition after outcomes.
- Do not add RSI, stochastic, Bollinger Bands, SMA trend filters, RS, sector, volume, regime, breadth, candlestick-pattern, event/news or gap filters to rescue RR1.
- Do not change the midpoint target, ATR stop buffer, 2R entry-economics rule, 15-session horizon or friction assumptions after outcomes.
- Do not remove weak years, sectors or symbols after outcomes.
- Diagnostics may explain the result but cannot become RR1 filters retrospectively.

RR1 is the **final planned strategy-family candidate** in the current research budget.

After RR1 receives one formal status:

```text
PASS
FAIL
INSUFFICIENT_EVIDENCE
INVALID_RESEARCH_RUN
```

stop inventing new strategy families and reassess the overall swing-trading program.

---

## 3. Historical universe and signal window

### Primary universe

Use **point-in-time Nifty 500 membership**.

A valid RR1 signal must occur while the symbol is an active point-in-time Nifty 500 member on the signal date.

Do not apply present-day membership retrospectively.

### Signal window

Use:

```text
Signal_Date: 2023-08-01 through 2026-08-25 inclusive
```

This matches the established non-event swing-research window and keeps Candidate 3 comparable with R1/V3-era evidence.

Historical OHLCV before the signal window may be used only to seed range, efficiency, ATR, liquidity and other required lookbacks.

Signals near the observation end that lack sufficient future sessions remain visible as incomplete accepted entries and are not silently dropped.

---

## 4. Price data and canonical sessions

Use the existing project convention of consistently adjusted daily OHLCV:

```text
Yahoo Finance auto_adjust=True
```

Do not mix adjusted and unadjusted fields inside one signal/trade lifecycle.

Reuse existing:

- canonical Nifty 500 market-session infrastructure;
- point-in-time membership data;
- historical provider-identity handling where already available;
- adjusted OHLCV acquisition/cache paths.

Do not build a generic security master, filing warehouse or unrelated data platform for RR1.

For every observation actually used by RR1, data must be accurate enough to satisfy the frozen integrity audit.

A stock need not have perfect historical coverage outside periods required to form or evaluate an RR1 observation.

---

## 5. Required pre-signal history

For a candidate signal session `T`, use the canonical session calendar.

RR1 requires valid adjusted stock bars for:

```text
T-61 through T
```

where the offsets refer to canonical market sessions.

The full prior-history requirement is intentional because the range and directional-efficiency calculation must represent exactly the predeclared number of market sessions rather than silently lengthening across missing stock bars.

If any required pre-signal OHLC bar is unavailable, the session cannot qualify.

The prior 20 sessions used for liquidity must also be present and valid.

---

## 6. Objective 60-session range

For signal session `T`, define the established pre-signal range from the **previous 60 complete canonical sessions only**, excluding the signal session:

```text
Range_Low[T]  = min(Low[T-60 ... T-1])
Range_High[T] = max(High[T-60 ... T-1])
Range_Mid[T]  = (Range_Low[T] + Range_High[T]) / 2
```

Require:

```text
Range_High > Range_Low
```

The signal-day low/high/close must not influence the range boundaries against which that same signal is judged.

The range midpoint is frozen at the signal close and is never recalculated during the trade.

---

## 7. Directional-efficiency qualification

RR1 is intended to test reversion inside an objectively sideways structure, not countertrend buying in a directional decline.

Define the 60-session directional-efficiency ratio using only information known before the signal session:

```text
ER60[T] =
abs(Close[T-1] - Close[T-61])
/
sum(abs(Close[i] - Close[i-1])) for i = T-60 ... T-1
```

The denominator therefore contains exactly 60 one-session absolute close changes ending at `T-1`.

Require the denominator to be finite and positive.

RR1 range qualification requires:

```text
ER60[T] <= 0.25
```

Interpretation:

- values near `0` indicate substantial back-and-forth travel with little net directional progress;
- values near `1` indicate highly directional travel.

Do not tune `0.25` after results.

---

## 8. Liquidity eligibility

Require on the signal date:

```text
Prior20_Median_Traded_Value[T] >= ₹10 crore
```

where:

```text
Daily_Traded_Value = Close × Volume
```

and the median uses only:

```text
T-20 ... T-1
```

The signal session is excluded from its own liquidity baseline.

This matches the established Nifty 500 swing-research liquidity floor.

---

## 9. Primary lower-range sweep/reclaim signal

A session becomes a qualified RR1 lower-range signal when all are true:

1. `Signal_Date` is inside the frozen signal window.
2. Symbol is an active point-in-time Nifty 500 member on `Signal_Date`.
3. Required `T-61..T` adjusted OHLCV history exists.
4. `Prior20_Median_Traded_Value >= ₹10 crore`.
5. `ER60 <= 0.25`.
6. The signal-session Low trades strictly below the pre-signal range low:

```text
Low[T] < Range_Low[T]
```

7. The signal-session Close finishes strictly back above the pre-signal range low:

```text
Close[T] > Range_Low[T]
```

This is the defining failed-downside-auction pattern:

```text
break below established support intraday
+ failure to remain below support by EOD
```

No minimum sweep depth is imposed.

No minimum candle-body, wick, close-location or signal-day volume condition is imposed.

---

## 10. What RR1 deliberately does not require

RR1 has no primary filter for:

- RSI or another oversold oscillator;
- SMA20/SMA50/SMA200 relationship;
- moving-average slope;
- stock relative strength;
- sector strength;
- market breadth;
- market regime;
- index trend;
- signal-day volume ratio;
- large one-day negative return or shock score;
- 52-week-high proximity;
- named candlestick pattern;
- next-day bullish confirmation;
- positive/negative gap filter;
- quarterly results/news interpretation;
- fundamental quality beyond PIT Nifty 500 membership and liquidity.

These may be retained diagnostically only where already available cheaply and safely.

---

## 11. Mirror upper-range falsification cohort

Create one predeclared mirror control using the same PIT universe, history, liquidity and `ER60 <= 0.25` range qualification.

An upper-range mirror signal requires:

```text
High[T] > Range_High[T]
Close[T] < Range_High[T]
```

This represents:

```text
break above established resistance intraday
+ failure to remain above resistance by EOD
```

The mirror cohort is **not a short-trading strategy**. It exists only to falsify the proposed range-reversion mechanism.

The expected directional relationship is:

```text
lower sweep/reclaim -> positive subsequent return
upper sweep/rejection -> negative subsequent return
```

Do not use the mirror cohort to create short trades, leverage or F&O logic.

---

## 12. ATR14 and structural stop

Use **Wilder ATR14**, matching the established project convention.

True Range:

```text
TR[t] = max(
    High[t] - Low[t],
    abs(High[t] - Close[t-1]),
    abs(Low[t] - Close[t-1])
)
```

Initialization and recursion:

```text
first valid ATR14 = mean(first 14 valid True Range observations)

subsequent ATR14 =
(previous_ATR14 × 13 + current_TR) / 14
```

On lower-range signal date `T`, freeze:

```text
Structural_Stop = Low[T] - 0.25 × ATR14_signal
```

The signal low is the failed-auction extreme. A meaningful move below that extreme invalidates the practical reversion thesis.

Do not use:

- fixed-percentage stop;
- entry-based ATR stop;
- moving-average stop;
- trailing stop;
- breakeven stop;
- post-entry stop widening.

---

## 13. Fixed practical target

For every qualified lower-range signal, freeze the target at the **pre-signal range midpoint**:

```text
Target = Range_Mid[T]
```

The target does not move if the rolling 60-session range changes later.

RR1 specifically tests practical reversion toward the midpoint, not a breakout to the opposite edge of the range.

---

## 14. Immediate next-session entry

Each qualified lower-range signal receives exactly one automatic entry opportunity:

```text
Entry = Open of the immediately following canonical market session
```

No same-session close entry is assumed.

A qualified signal may still be cancelled before entry.

### Entry cancellation reasons

Cancel with explicit accounting when any applies:

- `MISSING_NEXT_SESSION`
- `MISSING_NEXT_SESSION_BAR`
- `SIGNAL_ALREADY_AT_OR_ABOVE_TARGET` when `Close[T] >= Target`
- `OPEN_AT_OR_BELOW_STRUCTURAL_STOP` when `Entry_Open <= Structural_Stop`
- `OPEN_AT_OR_ABOVE_TARGET` when `Entry_Open >= Target`
- `INSUFFICIENT_REWARD_RISK` when the frozen target provides less than 2R from the actual entry open
- `SAME_SYMBOL_LOCKOUT`

Define:

```text
Initial_Risk = Entry_Open - Structural_Stop
Reward       = Target - Entry_Open
Initial_RR   = Reward / Initial_Risk
```

Require:

```text
Initial_Risk > 0
Reward > 0
Initial_RR >= 2.0
```

The 2R rule is part of the frozen practical architecture, not a post-hoc filter.

There is no separate gap-up or gap-down filter beyond these economically necessary invalidation/target/RR rules.

---

## 15. Same-symbol lifecycle lockout

RR1 must not repeatedly re-enter the same unresolved range episode.

After one qualified lower-range signal is accepted for a symbol, no second lower-range RR1 entry may be accepted in that symbol until the original signal's scheduled 15-session lifecycle has fully passed.

Define:

```text
Signal session = T
Entry session  = T+1
Scheduled time exit = T+16 Open
```

The position is therefore exposed across 15 complete holding sessions `T+1 ... T+15` unless the practical target or stop exits earlier.

The lockout remains active until the scheduled `T+16` point even if the practical trade exits early.

This avoids overweighting one range-break episode and prevents repeated entries from behaving like averaging down.

Qualified signals during lockout remain visible and are cancelled as:

```text
SAME_SYMBOL_LOCKOUT
```

The mirror upper-range cohort uses its own same-symbol 15-session lifecycle lockout.

Cross-stock overlap is retained at the signal-research stage.

---

## 16. Lens A — raw fixed-horizon range-reversion effect

Lens A asks whether an actionable lower-range sweep/reclaim has positive subsequent return after realistic next-open execution, independent of stop/target path mechanics.

Use the same accepted lower-range `Entry_ID` population as Lens B.

For every primary-complete accepted entry:

```text
Entry = T+1 Open
Exit  = T+16 Open
```

Thus the position is exposed across 15 complete market sessions.

There is no stop or target in Lens A.

Gross return:

```text
Gross_Return_15 = (Exit_Open - Entry_Open) / Entry_Open
```

Return profit factor:

```text
Return_PF = sum(positive returns) / abs(sum(negative returns))
```

Lens A exists to separate:

```text
no underlying reversion effect
```

from:

```text
underlying effect exists but practical stop/target implementation is poor
```

Forward 3-, 5-, 10- and 20-session returns may be retained diagnostically, but cannot replace the primary 15-session lens after results are known.

---

## 17. Mirror-control fixed-horizon outcome

For accepted upper-range mirror signals, use the same next-open and 15-complete-session timing:

```text
Entry_Reference = T+1 Open
Exit_Reference  = T+16 Open
Mirror_Gross_Return_15 = (Exit_Reference - Entry_Reference) / Entry_Reference
```

No short position is simulated.

The mirror cohort tests only whether failed upper breaks are followed by weaker/negative subsequent returns as predicted by a range-reversion mechanism.

---

## 18. Lens B — practical midpoint-reversion trade

Lens B uses the same accepted lower-range `Entry_ID` set and the frozen:

- next-session open entry;
- structural stop;
- pre-signal midpoint target;
- maximum 15-session lifecycle.

For each holding session, apply execution conservatively.

### Session-open precedence

For any holding session after entry:

1. If `Open <= Structural_Stop`, exit at that Open.
2. Else if `Open >= Target`, exit at that Open.
3. Otherwise evaluate intraday stop/target touches.

The entry session itself has already passed the pre-entry `Entry_Open` stop/target checks.

### Intraday precedence

If both are touched inside one daily OHLC bar:

```text
Low <= Structural_Stop
and
High >= Target
```

ordering is unknowable from EOD data, so score the outcome conservatively as **stop first**.

Otherwise:

- if only the stop is touched, exit at `Structural_Stop`;
- if only the target is touched, exit at `Target`;
- otherwise remain open.

### Time exit

If neither stop nor target has occurred through the end of `T+15`, exit at:

```text
T+16 Open
```

No trailing stop, breakeven move, partial profit, opportunity-cost exit or pyramiding is modeled in RR1 signal-level validation.

Gross practical R:

```text
Gross_R = (Exit_Price - Entry_Open) / Initial_Risk
```

Gap losses may be worse than `-1R`.

---

## 19. Friction model

Use the established frozen round-trip friction assumptions:

```text
Base friction   = 0.40% of entry value
Stress friction = 0.60% of entry value
Severe friction = 0.80% of entry value
```

For fixed-horizon returns:

```text
Net_Return_c = Gross_Return - c
```

For practical R:

```text
Net_R_c =
((Exit_Price - Entry_Open) - c × Entry_Open)
/ Initial_Risk
```

Use:

- 0.40% base for primary gates;
- 0.60% stress for mandatory friction robustness;
- 0.80% severe diagnostically only.

Do not tune friction from outcomes.

---

## 20. Nifty 500 excess-return comparison

RR1 must beat passive market exposure over comparable holding windows on average.

Use the frozen Nifty 500 benchmark series and canonical sessions.

### Lens A excess

For each completed lower-range Lens A trade:

```text
Benchmark_Return =
Nifty500_Open[T+16] / Nifty500_Open[T+1] - 1

Base_Excess_Return = Base_Net_Stock_Return - Benchmark_Return
```

### Practical-lens excess

For each completed practical trade, benchmark from the stock entry session Open to the canonical-session Open corresponding to the trade's actual exit date.

If an intraday stop/target exits on date `D`, use Nifty 500 Open-to-Open return from `Entry_Date` to `D` as a conservative reproducible opportunity-cost approximation.

If benchmark evidence required for an accepted completed trade is missing, the final research package fails integrity rather than silently dropping the trade.

---

## 21. Accounting funnel

Track every stage explicitly.

At minimum:

```text
PIT sessions with sufficient prehistory
-> liquidity eligible
-> ER60 <= 0.25 objective-range sessions
-> lower sweep/reclaim signals
-> upper mirror signals
```

For lower RR1:

```text
Qualified lower signals
-> accepted entries + explicit entry cancellations
-> completed paired outcomes + incomplete accepted entries
```

Require mechanically:

```text
Qualified_Lower_Signals
= Accepted_Lower_Entries + Lower_Entry_Cancellations
```

Every accepted entry and cancellation must reference exactly one qualified signal.

No signal may silently disappear.

Mirror-cohort accounting must likewise reconcile accepted/cancelled/incomplete/completed observations.

---

## 22. Paired completed-sample rule

Lens A and Lens B must use the same completed lower-range `Entry_ID` set.

Require:

```text
Completed_LensA_Entry_IDs == Completed_LensB_Entry_IDs
```

An accepted lower entry is primary-complete only when:

- the full scheduled `T+16` fixed-horizon bar exists for Lens A; and
- Lens B can be evaluated consistently through stop/target/time-exit logic; and
- required benchmark observations exist.

A practical trade that exits early but lacks enough future data for Lens A remains visible as incomplete and is excluded from the primary paired sample.

This prevents sample-composition differences from manufacturing apparent differences between the raw and practical lenses.

---

## 23. Point-in-time and formula integrity audit

The final run must independently verify core evidence rather than trust convenience booleans.

Use deterministic numeric tolerance:

```text
np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)
```

unless exact integer/date equality is appropriate.

For every accepted lower-range entry, independently verify at minimum:

1. `Signal_Date < Entry_Date`.
2. Signal is inside the frozen window.
3. Symbol is PIT Nifty 500 member on the signal date.
4. Entry date is the immediate next canonical market session.
5. Exact required `T-61..T` adjusted bars exist.
6. `Range_Low`, `Range_High`, `Range_Mid` use only `T-60..T-1`.
7. Persisted range values match independent recomputation.
8. ER60 uses exactly the frozen pre-signal formula.
9. `ER60 <= 0.25`.
10. Prior-20 median traded value matches recomputation and is >= ₹10 crore.
11. `Low[T] < Range_Low`.
12. `Close[T] > Range_Low`.
13. ATR14 and structural stop match the frozen formulas.
14. Accepted entry has `Signal_Close < Target`.
15. Accepted entry has `Structural_Stop < Entry_Open < Target`.
16. Accepted entry has `Initial_RR >= 2.0`.
17. Same-symbol lockout is respected.
18. Lens A/Lens B completed Entry_ID sets match.
19. Scheduled `T+16` timing is correct.
20. Benchmark dates/opens required for excess-return metrics are valid.
21. Practical exit precedence is reproducible from persisted OHLC evidence.

The mirror cohort must similarly verify PIT, range, ER, liquidity, upper sweep/rejection and fixed-horizon timing.

If any mandatory integrity invariant fails:

```text
FINAL_STATUS = INVALID_RESEARCH_RUN
```

Profitability gates must not be interpreted from an invalid run.

---

## 24. Diagnostics retained but forbidden as rescue filters

Retain where cheap and already available:

### Range/signal diagnostics

- range width as percentage of midpoint;
- sweep depth below `Range_Low` in percentage and ATR units;
- signal close location inside the 60-session range;
- signal-day return;
- signal-day volume ratio;
- signal-day true range;
- `ER60` value;
- signal-close to next-open gap;
- initial stop width;
- initial R:R.

### Context diagnostics

- SMA20/SMA50/SMA200 relationship;
- stock RS percentile where existing infrastructure supports it safely;
- market regime where already available;
- sector mapping where already available;
- Nifty 500 return/volatility;
- calendar year.

### Path diagnostics

- target-hit rate;
- stop-hit rate;
- time-exit rate;
- time to target;
- time to stop;
- MFE/MAE;
- 3/5/10/15/20-session forward returns;
- gap-stop frequency;
- same-day stop-and-target ambiguity count.

These are explanatory only.

No diagnostic subgroup may be promoted into RR1 after outcomes.

---

## 25. Bootstrap reporting

Use deterministic bootstrap reporting for uncertainty around key averages:

```text
Bootstrap resamples = 10,000
RNG seed            = 20260831
Confidence interval = 95%
```

Report bootstrap confidence intervals for at least:

- lower-cohort gross 15-session mean return;
- lower-cohort base-net 15-session mean return;
- base practical mean R;
- base practical mean excess return;
- lower minus upper mirror difference in gross 15-session mean return.

Bootstrap intervals are robustness evidence, not an independent p-value gate.

---

## 26. Temporal robustness

Use the same fixed calendar split as R1:

```text
FIRST:  2023-08-01 through 2025-02-11 inclusive
SECOND: 2025-02-12 through 2026-08-25 inclusive
```

For completed paired lower-range trades in each half, compute at minimum:

- base practical mean R;
- base practical R-profit factor;
- base practical mean excess return;
- fixed-horizon base-net mean return.

Do not move the split after results.

---

## 27. Outlier and concentration robustness

### Top-five winner removal

Rank completed lower-range practical trades by `Gross_R` and remove the five largest winners.

Recompute base practical metrics on the remaining sample.

### Leave-one-year-out

For each calendar year represented by completed lower-range trades, remove all trades whose `Signal_Date` falls in that year and recompute base practical metrics.

The partial 2023 and 2026 windows are retained as their actual calendar-year cohorts; do not merge or remove them merely because they are partial.

### Leave-one-symbol-out

For each symbol represented in the completed paired sample, remove all completed trades for that symbol and recompute base practical metrics.

These robustness tests are mandatory PASS gates as defined below.

---

## 28. Sample sufficiency

A valid RR1 run requires at least:

```text
Completed paired lower-range trades >= 300
FIRST completed paired lower trades  >= 100
SECOND completed paired lower trades >= 100
Completed upper mirror outcomes      >= 100
```

If any of these minimums are not met and the run is otherwise valid:

```text
FINAL_STATUS = INSUFFICIENT_EVIDENCE
```

Do not lower thresholds/history requirements or extend the experiment merely to manufacture sample size.

---

## 29. Precommitted validation gates

RR1 receives `PASS` only if every mandatory gate below passes.

### A. Research validity

```text
PIT/integrity violations       = 0
Accounting invariants          = PASS
Lens A/Lens B completed IDs    = identical
Required evidence artifacts    = complete
```

Any failure produces `INVALID_RESEARCH_RUN`.

### B. Sample sufficiency

All minimums in Section 28 must pass.

Otherwise status is `INSUFFICIENT_EVIDENCE`.

### C. Raw lower-range reversion effect

Using Lens A and 0.40% base friction:

```text
Base_Net_Mean_Return > 0
Base_Net_Return_PF > 1.00
Mean_Base_Excess_Return > 0
```

### D. Practical trading expectancy

Using Lens B and 0.40% base friction:

```text
Base_Practical_Mean_R >= +0.15R
Base_Practical_R_PF >= 1.20
Mean_Base_Practical_Excess_Return > 0
```

Median practical R and win rate are reported but are **diagnostic, not hard gates**. A 2R-minimum architecture can legitimately have positive expectancy with a sub-50% win rate, so a median-R gate would impose an unjustified high-win-rate requirement.

### E. Stress-friction robustness

At 0.60% round-trip friction:

```text
Stress_Practical_Mean_R > 0
Stress_Practical_R_PF > 1.00
```

The 0.80% severe scenario is diagnostic only.

### F. Mirror falsification

Using gross 15-session fixed-horizon returns:

```text
Mean_Return_LOWER > Mean_Return_UPPER
Mean_Return_UPPER < 0
```

Because the lower cohort must already pass positive net-return gates, the first condition tests separation while the second tests the predicted opposite directional behavior of failed upper breaks.

If the upper mirror cohort is not negative, the proposed symmetric range-reversion mechanism fails even if lower trades happen to be profitable.

### G. Temporal robustness

Both FIRST and SECOND halves must satisfy:

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
Mean_Base_Practical_Excess_Return > 0
```

### H. Top-five-winner robustness

After removing the five largest gross-R winners:

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

### I. Leave-one-year-out robustness

Every leave-one-year-out sample must retain:

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

### J. Leave-one-symbol-out robustness

Every leave-one-symbol-out sample must retain:

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

No regime, sector, range-width, sweep-depth, volume, gap, ER bucket or other diagnostic creates an extra post-hoc gate.

---

## 30. Final status hierarchy

Assign exactly one status using this precedence.

### `INVALID_RESEARCH_RUN`

Use when any mandatory research-integrity condition fails.

Profitability interpretation stops.

### `INSUFFICIENT_EVIDENCE`

Use when the run is valid but any frozen minimum sample requirement is unmet.

Observed economics may be described, but the strategy cannot receive PASS or FAIL.

### `PASS`

Use only when the run is valid, sample sufficiency passes, and **all** mandatory economic, practical, stress, mirror, temporal and robustness gates pass.

PASS means:

> RR1 has enough historical signal-level evidence to proceed toward portfolio-constrained and forward validation.

It does not mean ready for normal-capital live deployment.

### `FAIL`

Use when the run is valid and sufficiently sampled but one or more mandatory strategy gates fail.

Do not rescue a FAIL with post-result filters or parameter changes.

---

## 31. Cross-stock overlap and future portfolio work

Do not suppress valid cross-stock RR1 entries merely because other symbols already have active signal-level trades.

RR1 first tests individual-signal edge.

Report at minimum:

- total accepted entries;
- maximum simultaneous RR1 trades;
- average simultaneous RR1 trades;
- maximum same-day entries;
- percentage of accepted entries overlapping another RR1 trade;
- broad sector concentration where mapping already exists;
- rough implied capital requirement under eventual 1%-risk-per-trade sizing.

If RR1 passes, portfolio-capacity/ranking logic belongs to the later 3–5-position portfolio simulation.

Do not invent ranking rules inside RR1.

---

## 32. Required final reporting

The final RR1 evidence package/report must state at minimum:

- frozen hypothesis and methodology;
- PIT universe and signal window;
- usable data coverage;
- objective-range session count;
- lower sweep/reclaim count;
- upper mirror count;
- qualified/accepted/cancelled/completed/incomplete lower accounting;
- cancellation reasons;
- mirror accounting;
- Lens A gross/base/stress/severe metrics;
- Lens B gross/base/stress/severe practical R metrics;
- benchmark excess metrics;
- target/stop/time-exit diagnostics;
- temporal-half results;
- calendar-year diagnostics;
- top-five-winner robustness;
- leave-one-year-out robustness;
- leave-one-symbol-out robustness;
- mirror falsification result;
- bootstrap intervals;
- overlap/capacity diagnostics;
- PIT/formula integrity audit;
- every precommitted gate with PASS/FAIL;
- exactly one final formal status.

Clearly distinguish mandatory gates from diagnostics.

---

## 33. Interpretation discipline after results

Allowed conclusions include:

- `RR1 PASS: proceed to portfolio-constrained/forward validation.`
- `RR1 FAIL: lower-range reversion did not survive practical execution/costs.`
- `RR1 FAIL: lower signals were profitable but the mirror falsification contradicted the range-reversion mechanism.`
- `RR1 FAIL: the effect depended on a few winners, one year or one symbol.`
- `RR1 INSUFFICIENT_EVIDENCE: frozen sample minimums were not met.`
- `RR1 INVALID_RESEARCH_RUN: integrity/accounting failed; profitability cannot be interpreted.`

Prohibited rescue examples:

- changing `ER60 <= 0.25` to the best-performing ER bucket;
- changing 60 sessions to 40/90/120 because another lookback looked better;
- adding RSI because oversold signals worked better;
- requiring high/low volume because one bucket outperformed;
- excluding HOSTILE markets or weak sectors after seeing results;
- changing midpoint target to upper range boundary;
- changing 15 sessions because another forward horizon looked better;
- changing the `0.25 ATR` stop buffer;
- lowering the 2R requirement;
- removing poor years or symbols.

RR1 remains frozen regardless of outcome.

---

## 34. Minimal infrastructure principle

The north-star implementation question is:

> **Does this directly help validate RR1?**

RR1 requires only enough infrastructure to:

- construct the PIT Nifty 500 observation set;
- obtain accurate adjusted OHLCV for relevant observations;
- use canonical sessions;
- compute the frozen range/ER/liquidity/ATR formulas;
- simulate the frozen entry/exit mechanics;
- benchmark against Nifty 500;
- audit integrity/accounting;
- calculate the precommitted gates.

Do not build:

- a generic historical-security master;
- a financial-statement warehouse;
- a dashboard;
- a general-purpose research framework;
- a news/event archive;
- unrelated ticker cleanup for securities that never materially affect RR1 observations.

Accuracy is mandatory for observations RR1 actually uses. Universal historical-data perfection is not the goal.

---

## 35. Core frozen specification summary

```text
Universe:
    point-in-time Nifty 500

Signal window:
    2023-08-01 through 2026-08-25

Required prehistory:
    exact canonical-session bars T-61..T

Objective range:
    Range_Low  = min Low over T-60..T-1
    Range_High = max High over T-60..T-1
    Range_Mid  = midpoint of those boundaries

Directional efficiency:
    ER60 = abs net close movement / sum absolute close changes
    require ER60 <= 0.25

Liquidity:
    prior-20 median traded value >= ₹10 crore

Lower RR1 signal:
    Low[T] < Range_Low
    Close[T] > Range_Low

Upper mirror signal:
    High[T] > Range_High
    Close[T] < Range_High

Entry:
    immediate next canonical-session Open

Structural stop:
    Signal_Low - 0.25 × ATR14_signal

Target:
    frozen pre-signal Range_Mid

Practical entry economics:
    Structural_Stop < Entry_Open < Target
    Initial_RR >= 2.0

Same-symbol rule:
    one accepted lower signal per scheduled 15-session lifecycle

Lens A:
    T+1 Open -> T+16 Open fixed-horizon return

Lens B:
    stop / midpoint target / T+16 time exit
    conservative stop-first ambiguity handling

Friction:
    base 0.40%
    stress 0.60%
    severe 0.80% diagnostic

Sample minimums:
    lower paired >= 300
    FIRST lower >= 100
    SECOND lower >= 100
    upper mirror >= 100

Primary practical gate:
    base mean >= +0.15R
    base RPF >= 1.20
    mean practical excess > 0

No primary:
    RSI
    SMA/trend filter
    momentum/RS
    sector
    regime/breadth
    volume filter
    news/event filter
    candle taxonomy
    parameter rescue
```

RR1 therefore asks exactly one final Candidate-3 question:

> **Does an objectively range-bound liquid Indian stock that sweeps below its established range and closes back inside offer a robust, practically exploitable next-session long reversion toward the pre-signal range midpoint after realistic friction?**

After this experiment receives its formal verdict, the current strategy-family research program stops and is reassessed rather than expanded.