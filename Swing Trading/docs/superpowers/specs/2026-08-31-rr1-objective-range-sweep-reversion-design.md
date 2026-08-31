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

RR1 is independent of T1/V2/V3/M1 momentum/breakout research. It is also not a rescue of R1: R1 tested large low-volume negative shocks, whereas RR1 tests a pre-existing range plus a failed downside break. RR1 has no primary shock-size, volume, momentum, RS, sector or market-regime condition.

---

## 2. Research discipline and stopping rule

Use:

> **One hypothesis -> one frozen methodology -> one test -> one verdict.**

Do not change after outcomes:

- 60-session range length;
- `ER60 <= 0.25` range qualification;
- sweep/reclaim definition;
- midpoint target;
- `0.25 × ATR14` stop buffer;
- `Initial_RR >= 2.0` entry economics;
- 15-session horizon;
- friction assumptions;
- sample/gate thresholds.

Do not add RSI, stochastic, Bollinger Bands, SMA filters, momentum/RS, sector, volume, regime, breadth, candle-pattern, event/news or gap filters to rescue RR1. Do not remove bad years/sectors/symbols after results.

Diagnostics may explain the outcome but cannot become RR1 filters retrospectively.

RR1 is the **final planned strategy-family candidate**. After its formal `PASS`, `FAIL`, `INSUFFICIENT_EVIDENCE` or `INVALID_RESEARCH_RUN`, stop inventing new strategy families and reassess the swing program.

---

## 3. Universe, window and data

### Universe

Use **point-in-time Nifty 500 membership**. A signal is eligible only while the symbol is an active member on `Signal_Date`.

### Signal window

```text
2023-08-01 through 2026-08-25 inclusive
```

Historical data before the window may only seed required lookbacks. Signals near the end that lack enough forward sessions remain visible as incomplete observations.

### Price/session convention

Reuse existing project infrastructure for:

- canonical market sessions;
- PIT membership;
- adjusted OHLCV;
- provider identity/cache handling where already available.

Use adjusted daily OHLCV consistently:

```text
Yahoo Finance auto_adjust=True
```

Do not mix adjusted/unadjusted fields.

Do not build a generic historical-security master, filing warehouse, dashboard or unrelated research platform. Accuracy is mandatory for observations RR1 actually uses; universal historical-data perfection is not the objective.

---

## 4. Exact pre-signal history

For candidate signal session `T`, require valid adjusted stock bars on every canonical session:

```text
T-61 through T
```

This prevents a nominal 60-session range from silently spanning a longer period because the stock was missing bars.

If any required pre-signal OHLC bar is unavailable, that session cannot qualify.

---

## 5. Objective 60-session range

Using only the previous 60 complete sessions:

```text
Range_Low[T]  = min(Low[T-60 ... T-1])
Range_High[T] = max(High[T-60 ... T-1])
Range_Mid[T]  = (Range_Low[T] + Range_High[T]) / 2
```

Require:

```text
Range_High > Range_Low
```

The signal session must not influence the boundaries used to judge itself. `Range_Mid` is frozen on the signal date and never recalculated during the trade.

---

## 6. Objective sideways qualification

Define the pre-signal directional-efficiency ratio:

```text
ER60[T] =
abs(Close[T-1] - Close[T-61])
/
sum(abs(Close[i] - Close[i-1])) for i = T-60 ... T-1
```

The denominator therefore contains exactly 60 one-session absolute close changes ending at `T-1`.

Require a finite positive denominator and:

```text
ER60[T] <= 0.25
```

Low ER means the stock travelled back and forth but made relatively little net directional progress. This is RR1's objective definition of a range and prevents the experiment from becoming generic countertrend buying in a directional decline.

---

## 7. Liquidity

Require:

```text
Prior20_Median_Traded_Value[T] >= ₹10 crore
```

where:

```text
Daily_Traded_Value = Close × Volume
```

and the median uses only `T-20 ... T-1`. The signal day is excluded from its own liquidity baseline.

---

## 8. Primary lower-range signal

A session is a qualified lower RR1 signal only when all are true:

1. Signal date is inside the frozen window.
2. Symbol is PIT Nifty 500 member on the signal date.
3. Exact required `T-61..T` history exists.
4. Prior-20 median traded value is at least ₹10 crore.
5. `ER60 <= 0.25`.
6. Signal low sweeps below the pre-signal range:

```text
Low[T] < Range_Low[T]
```

7. Signal close finishes back inside:

```text
Close[T] > Range_Low[T]
```

There is no minimum sweep depth, wick/body rule, close-location requirement or signal-day volume requirement.

This is the defining failed downside auction:

```text
break below established support intraday
+ failure to remain below support by EOD
```

---

## 9. What RR1 deliberately does not require

No primary:

- RSI/oversold oscillator;
- SMA20/SMA50/SMA200 relationship or slope;
- stock relative strength;
- sector strength;
- breadth or market regime;
- signal-day volume ratio;
- large one-day shock;
- 52-week-high proximity;
- named candlestick pattern;
- next-day bullish confirmation;
- standalone gap filter;
- quarterly-result/news interpretation;
- fundamental filter beyond PIT Nifty 500 + liquidity.

Existing fields may be retained diagnostically only if cheap and safe.

---

## 10. Mirror upper-range falsification cohort

Construct one predeclared mirror control using the same PIT, exact-history, liquidity and `ER60 <= 0.25` qualification.

A qualified upper mirror signal requires:

```text
High[T] > Range_High[T]
Close[T] < Range_High[T]
```

This is a failed upside auction. The mirror cohort is **not a short-trading strategy**; it is a falsification test of the range-reversion mechanism.

Expected directional relationship:

```text
lower sweep/reclaim -> positive subsequent return
upper sweep/rejection -> negative subsequent return
```

### Mirror lifecycle

A qualified upper mirror signal receives one reference entry at the immediate next canonical-session Open.

Cancel explicitly only for:

- `MISSING_NEXT_SESSION`;
- `MISSING_NEXT_SESSION_BAR`;
- `SAME_SYMBOL_LOCKOUT` within the mirror cohort.

After an upper mirror signal is accepted, no second upper mirror signal for that symbol is accepted until its scheduled `T+16 Open` lifecycle has passed, even if later diagnostics would imply an earlier move.

If the `T+16` reference exit cannot be evaluated, the accepted mirror observation remains visible as incomplete rather than disappearing.

Lower and upper lockouts are cohort-local; the mirror cohort does not suppress a genuine lower RR1 signal and vice versa.

---

## 11. ATR14 and structural stop

Use **Wilder ATR14**.

```text
TR[t] = max(
    High[t] - Low[t],
    abs(High[t] - Close[t-1]),
    abs(Low[t] - Close[t-1])
)
```

Initialization and recursion:

```text
first valid ATR14 = mean(first 14 valid TR observations)
subsequent ATR14 = (previous_ATR14 × 13 + current_TR) / 14
```

Freeze on signal date:

```text
Structural_Stop = Low[T] - 0.25 × ATR14_signal
```

The signal low is the failed-auction extreme. A meaningful move beneath it invalidates the practical trade thesis.

No percentage stop, entry-based ATR stop, MA stop, trailing stop, breakeven move or stop widening.

---

## 12. Fixed practical target

Freeze:

```text
Target = Range_Mid[T]
```

The target never moves with a later rolling range. RR1 tests reversion toward the midpoint, not a rally to the opposite boundary.

---

## 13. Immediate next-session long entry

Each qualified lower signal receives exactly one entry opportunity:

```text
Entry = Open of the immediately following canonical market session
```

No same-session entry is assumed.

A qualified signal is cancelled before entry when any applies:

- `MISSING_NEXT_SESSION`;
- `MISSING_NEXT_SESSION_BAR`;
- `SIGNAL_ALREADY_AT_OR_ABOVE_TARGET` if `Close[T] >= Target`;
- `OPEN_AT_OR_BELOW_STRUCTURAL_STOP` if `Entry_Open <= Structural_Stop`;
- `OPEN_AT_OR_ABOVE_TARGET` if `Entry_Open >= Target`;
- `INSUFFICIENT_REWARD_RISK`;
- `SAME_SYMBOL_LOCKOUT`.

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

There is no separate gap rule beyond these frozen invalidation/target/RR checks.

---

## 14. Lower-cohort same-symbol lockout

After one lower signal is accepted, no second lower RR1 entry for that symbol is accepted until the original signal's scheduled lifecycle passes:

```text
Signal = T
Entry  = T+1 Open
Scheduled lifecycle end = T+16 Open
```

The position is exposed across 15 complete sessions `T+1 ... T+15` unless Lens B exits earlier.

The lockout remains active until scheduled `T+16` even if Lens B stops or hits target early. Later qualified lower signals remain visible and are cancelled as `SAME_SYMBOL_LOCKOUT`.

This prevents clustered re-entries from behaving like averaging down or overweighting one range episode.

Cross-stock signals are retained; portfolio capacity comes later if RR1 passes.

---

## 15. Lens A — raw fixed-horizon reversion

Lens A asks whether the **actionable accepted lower cohort** has a positive effect independent of target/stop path mechanics.

Use exactly the same accepted lower `Entry_ID` population as Lens B.

```text
Entry = T+1 Open
Exit  = T+16 Open
```

No stop/target in Lens A.

```text
Gross_Return_15 = (Exit_Open - Entry_Open) / Entry_Open
Return_PF = sum(positive returns) / abs(sum(negative returns))
```

3/5/10/20-session forward returns may be diagnostics only; they cannot replace the frozen 15-session primary horizon.

---

## 16. Mirror fixed-horizon outcome

For every accepted, complete upper mirror observation:

```text
Entry_Reference = T+1 Open
Exit_Reference  = T+16 Open
Mirror_Gross_Return_15 = (Exit_Reference - Entry_Reference) / Entry_Reference
```

No short position, stop or target is simulated.

---

## 17. Lens B — practical midpoint-reversion trade

Lens B uses the same accepted lower `Entry_ID` set with the frozen stop, midpoint target and maximum 15-session lifecycle.

### Open precedence

For each holding session after entry:

1. If `Open <= Structural_Stop`, exit at that Open.
2. Else if `Open >= Target`, exit at that Open.
3. Otherwise evaluate intraday stop/target touches.

The entry Open has already passed pre-entry stop/target checks.

### Intraday precedence

If the same daily bar satisfies both:

```text
Low <= Structural_Stop
High >= Target
```

EOD data cannot determine ordering, so score **stop first** conservatively.

Otherwise:

- only stop touched -> exit at `Structural_Stop`;
- only target touched -> exit at `Target`;
- neither -> remain open.

### Time exit

If neither occurs through the end of `T+15`:

```text
Exit = T+16 Open
```

No trailing stop, breakeven move, partial profit, opportunity-cost exit or pyramiding is modeled.

```text
Gross_R = (Exit_Price - Entry_Open) / Initial_Risk
```

Gap losses may exceed `-1R`.

---

## 18. Friction

Frozen round-trip assumptions:

```text
Base   = 0.40% of entry value
Stress = 0.60%
Severe = 0.80%
```

Fixed-horizon net return:

```text
Net_Return_c = Gross_Return - c
```

Practical net R:

```text
Net_R_c = ((Exit_Price - Entry_Open) - c × Entry_Open) / Initial_Risk
```

Base creates primary gates, stress creates mandatory robustness gates, severe is diagnostic only.

---

## 19. Nifty 500 excess-return comparison

Compare stock outcomes with Nifty 500 over equivalent dates.

### Lens A

```text
Benchmark_Return = Nifty500_Open[T+16] / Nifty500_Open[T+1] - 1
Base_Excess_Return = Base_Net_Stock_Return - Benchmark_Return
```

### Lens B

Benchmark from the stock `Entry_Date` Open to the Nifty 500 Open on the stock's actual exit date. For an intraday stock exit, this Open-to-Open benchmark is the frozen reproducible opportunity-cost approximation.

Missing benchmark evidence for a completed accepted lower trade is an integrity failure; do not silently drop the trade.

---

## 20. Accounting and paired samples

At minimum track:

```text
PIT sessions with exact prehistory
-> liquidity eligible
-> ER60 <= 0.25 range sessions
-> lower qualified signals
-> upper qualified signals
```

Lower accounting:

```text
Qualified_Lower_Signals
= Accepted_Lower_Entries + Lower_Entry_Cancellations

Accepted_Lower_Entries
= Completed_Paired_Lower + Incomplete_Accepted_Lower
```

Upper mirror accounting:

```text
Qualified_Upper_Signals
= Accepted_Upper_References + Upper_Cancellations

Accepted_Upper_References
= Completed_Upper + Incomplete_Upper
```

No observation may silently disappear.

Lens A and Lens B must use the same completed lower IDs:

```text
Completed_LensA_Entry_IDs == Completed_LensB_Entry_IDs
```

A lower accepted entry is primary-complete only when Lens A, Lens B and required benchmark evidence can all be evaluated consistently. An early practical exit does not permit dropping the later fixed-horizon Lens A requirement.

---

## 21. Integrity audit

Use independent recomputation, with deterministic numeric tolerance where appropriate:

```text
np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)
```

For every accepted lower trade verify at minimum:

1. signal is inside frozen window;
2. PIT Nifty 500 membership on signal date;
3. exact `T-61..T` bars exist;
4. range uses only `T-60..T-1`;
5. range values recompute exactly/tolerantly;
6. ER60 formula and `ER60 <= 0.25`;
7. prior-20 median traded value and threshold;
8. `Low[T] < Range_Low` and `Close[T] > Range_Low`;
9. ATR14 and structural stop recompute;
10. immediate next canonical-session entry;
11. accepted trade has `Close[T] < Target`;
12. `Structural_Stop < Entry_Open < Target`;
13. `Initial_RR >= 2.0`;
14. lower same-symbol lockout respected;
15. Lens A/Lens B completed IDs match;
16. scheduled `T+16` timing is correct;
17. benchmark observations/dates are valid;
18. practical stop/target precedence is reproducible.

For upper mirror observations likewise verify PIT/history/range/ER/liquidity, `High[T] > Range_High`, `Close[T] < Range_High`, immediate-next-open timing, mirror lockout and `T+16` timing.

Any mandatory integrity failure produces:

```text
INVALID_RESEARCH_RUN
```

and profitability interpretation stops.

---

## 22. Diagnostics only

Retain where practical:

- range width %;
- sweep depth % and ATR units;
- signal close location in range;
- signal-day return/volume ratio/true range;
- ER60;
- signal-close to next-open gap;
- stop width and initial R:R;
- SMA/RS/regime/sector context where existing data already supports it;
- target/stop/time-exit rates;
- time to target/stop;
- MFE/MAE;
- 3/5/10/15/20-session forward returns;
- same-day stop+target ambiguity count;
- calendar year.

None can become a post-hoc RR1 filter.

---

## 23. Bootstrap reporting

Use:

```text
resamples = 10,000
seed      = 20260831
CI        = 95%
```

Report CIs for at least:

- lower gross 15-session mean return;
- lower base-net 15-session mean return;
- base practical mean R;
- base practical mean excess return;
- lower-minus-upper gross 15-session mean-return difference.

Bootstrap evidence is diagnostic robustness, not an independent p-value gate.

---

## 24. Temporal robustness

Frozen split:

```text
FIRST:  2023-08-01 through 2025-02-11 inclusive
SECOND: 2025-02-12 through 2026-08-25 inclusive
```

For each half report:

- completed paired lower count;
- base practical mean R;
- base practical RPF;
- base practical mean excess return;
- Lens A base-net mean return.

Do not move the split after results.

---

## 25. Outlier/concentration robustness

### Top-five winner removal

Remove the five completed lower practical trades with largest `Gross_R`, then recompute base practical metrics.

### Leave-one-year-out

For every calendar year represented, remove all completed lower trades with a signal in that year and recompute. Keep partial 2023 and 2026 as their actual cohorts.

### Leave-one-symbol-out

For every represented symbol, remove all its completed lower trades and recompute.

These are mandatory gates below.

---

## 26. Sample sufficiency

Require at least:

```text
Completed paired lower trades >= 300
FIRST completed paired lower  >= 100
SECOND completed paired lower >= 100
Completed upper mirror        >= 100
```

If the run is valid but any minimum is missed:

```text
FINAL_STATUS = INSUFFICIENT_EVIDENCE
```

Do not lower rules or extend the experiment merely to hit sample targets.

---

## 27. Precommitted PASS gates

RR1 passes only if **all** mandatory gates pass.

### A. Research validity

```text
PIT/integrity violations    = 0
Accounting invariants       = PASS
Lens A/Lens B completed IDs = identical
Required evidence           = complete
```

Failure -> `INVALID_RESEARCH_RUN`.

### B. Sample sufficiency

All Section 26 minimums must pass.

Failure -> `INSUFFICIENT_EVIDENCE`.

### C. Raw lower reversion — Lens A, 0.40% base friction

```text
Base_Net_Mean_Return > 0
Base_Net_Return_PF > 1.00
Mean_Base_Excess_Return > 0
```

### D. Practical expectancy — Lens B, 0.40% base friction

```text
Base_Practical_Mean_R >= +0.15R
Base_Practical_R_PF >= 1.20
Mean_Base_Practical_Excess_Return > 0
```

Median practical R and win rate are **diagnostics, not hard gates**. Because entries require at least 2R to target, a profitable strategy can legitimately win fewer than half its trades; a positive-median gate would impose an unjustified high-win-rate requirement.

### E. Stress friction — 0.60%

```text
Stress_Practical_Mean_R > 0
Stress_Practical_R_PF > 1.00
```

0.80% severe remains diagnostic.

### F. Mirror falsification — gross fixed-horizon returns

```text
Mean_Return_LOWER > Mean_Return_UPPER
Mean_Return_UPPER < 0
```

If failed upper breaks do not have negative subsequent mean return, the proposed symmetric range-reversion mechanism fails even if lower trades happen to be profitable.

### G. Temporal robustness — both halves

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
Mean_Base_Practical_Excess_Return > 0
```

### H. Top-five removal

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

### I. Every leave-one-year-out sample

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

### J. Every leave-one-symbol-out sample

```text
Base_Practical_Mean_R > 0
Base_Practical_R_PF > 1.00
```

No diagnostic subgroup creates another post-hoc gate.

---

## 28. Formal status precedence

Assign exactly one status:

1. Integrity/accounting/evidence failure -> `INVALID_RESEARCH_RUN`.
2. Valid run but any frozen sample minimum missed -> `INSUFFICIENT_EVIDENCE`.
3. Valid + sufficient + every mandatory strategy gate passes -> `PASS`.
4. Otherwise -> `FAIL`.

`PASS` means RR1 may proceed toward portfolio-constrained and forward validation, not normal-capital deployment.

Never rescue `FAIL` by changing RR1 from its diagnostics.

---

## 29. Cross-stock overlap / future portfolio stage

Do not suppress valid lower signals because other stocks already have signal-level RR1 trades.

Report:

- accepted entries;
- maximum/average simultaneous trades;
- maximum same-day entries;
- overlap percentage;
- sector concentration where mapping already exists;
- rough capital requirement under eventual ~1%-risk-per-trade sizing.

If RR1 passes, 3–5-position capacity/ranking belongs to later portfolio simulation. Do not invent ranking rules in RR1.

---

## 30. Required final report

The evidence package must include at minimum:

- frozen hypothesis/rules;
- PIT universe/window/data coverage;
- objective-range session count;
- lower and upper signal counts;
- all accepted/cancelled/completed/incomplete accounting and reasons;
- Lens A gross/base/stress/severe results;
- Lens B gross/base/stress/severe R results;
- benchmark excess;
- target/stop/time-exit diagnostics;
- mirror result;
- temporal halves and calendar-year diagnostics;
- top-five removal;
- leave-one-year-out;
- leave-one-symbol-out;
- bootstrap intervals;
- overlap/capacity diagnostics;
- integrity audit;
- every mandatory gate;
- exactly one formal status.

Clearly separate gates from diagnostics.

---

## 31. Prohibited post-result rescue

Do not after outcomes:

- change `ER60 <= 0.25`;
- change 60 sessions to a prettier lookback;
- add RSI/volume/trend/RS/regime/sector filters;
- change midpoint target to the upper boundary;
- change `0.25 × ATR14` stop buffer;
- lower the 2R requirement;
- switch from 15 sessions to a prettier horizon;
- exclude weak years/sectors/symbols;
- use gap buckets or sweep-depth buckets as new rules.

Interesting diagnostics do not create Candidate 4. RR1 is the final family test.

---

## 32. Core frozen summary

```text
Universe:
    point-in-time Nifty 500

Signal window:
    2023-08-01 .. 2026-08-25

Prehistory:
    exact canonical bars T-61..T

Range:
    Low/High over T-60..T-1
    fixed midpoint target

Sideways qualification:
    ER60 <= 0.25

Liquidity:
    prior-20 median traded value >= ₹10 crore

Lower signal:
    Low[T] < Range_Low
    Close[T] > Range_Low

Upper mirror:
    High[T] > Range_High
    Close[T] < Range_High

Entry:
    immediate next canonical-session Open

Stop:
    Signal_Low - 0.25 × ATR14_signal

Entry economics:
    Stop < Entry < Target
    Initial_RR >= 2.0

Same-symbol:
    cohort-local lockout through scheduled T+16

Lens A:
    T+1 Open -> T+16 Open

Lens B:
    structural stop / midpoint target / T+16 time exit
    stop-first if same OHLC bar touches both

Friction:
    0.40% base
    0.60% stress
    0.80% severe diagnostic

Sample minimums:
    lower paired >= 300
    FIRST lower >= 100
    SECOND lower >= 100
    upper mirror >= 100

Primary practical hurdle:
    base mean >= +0.15R
    base RPF >= 1.20
    mean practical excess > 0
```

RR1 asks exactly one final Candidate-3 question:

> **Does an objectively range-bound liquid Indian stock that sweeps below its established range and closes back inside offer a robust, practically exploitable next-session long reversion toward the pre-signal range midpoint after realistic friction?**

After this experiment receives its formal verdict, the current strategy-family research program stops and is reassessed rather than expanded.