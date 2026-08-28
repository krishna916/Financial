# R1 Short-Term Price-Shock Reversal — Research Design

**Status:** Design approved in chat and self-reviewed; implementation and historical validation not started  
**Design date:** 28 August 2026  
**Repository:** `krishna916/Financial`  
**Research family:** Short-horizon reversal / temporary price-pressure mean reversion  
**Relationship to prior work:** Independent hypothesis. T1 remains retired, Strategy V2 remains closed, and Strategy V3 remains failed as an unconditional swing strategy. R1 is not a rescue or parameter modification of any momentum strategy.

---

## 1. Objective

R1 tests one narrow hypothesis:

> Among liquid point-in-time Nifty 500 stocks, an unusually large one-day decline occurring on relatively low trading volume represents temporary selling pressure often enough that buying at the immediately following market-session open produces positive five-session expectancy after realistic trading friction.

The economic idea is deliberately different from the previous momentum research.

Previous momentum work broadly asked:

```text
strength -> more strength
```

R1 asks:

```text
abnormally sharp weakness
+ relatively low participation
-> temporary pressure
-> short-horizon reversal
```

R1 does **not** assume the hypothesis is true. The design includes a high-volume large-decline control cohort specifically to challenge the proposed low-participation explanation.

---

## 2. Research discipline

Use the same research discipline established in prior swing work:

> **One hypothesis -> one predefined methodology -> test -> document -> decide.**

Hard rules:

- Do not tune thresholds after seeing outcomes.
- Do not add RSI, MACD, ADX, candlestick, trend, relative-strength, sector, breadth, regime, volume-bucket, gap, or confirmation filters to rescue R1.
- Do not change the primary five-session horizon after observing prettier 1-, 3-, 10-, or 20-session results.
- Do not change the shock threshold, volume threshold, liquidity threshold, stop buffer, or friction assumptions after outcomes are known.
- Diagnostic subgroups may generate future hypotheses but cannot be promoted into R1 entry filters.
- A negative result is valid research evidence.
- Cash remains a valid eventual portfolio outcome if no independently validated strategy is eligible.

---

## 3. Historical universe

### Primary universe

Use **point-in-time Nifty 500 membership**.

A valid R1 signal must occur while the symbol is a member of the point-in-time Nifty 500 on the signal date.

Do not apply present-day Nifty 500 membership retrospectively.

Historical OHLCV before a stock enters the index may be used only to warm prior-return, ATR, volume, liquidity, and other diagnostic lookbacks. It cannot create a valid signal while the stock is not an active point-in-time member.

### Signal window

Use the same primary research window as Strategy V3 for comparability:

```text
Shock Signal_Date: 2023-08-01 through 2026-08-25 inclusive
```

Signals near the observation end that do not have sufficient future sessions for both primary lenses remain visible as incomplete accepted entries and are not silently discarded.

### Data treatment

Use adjusted OHLCV consistently across the full lifecycle, matching the established swing-research convention:

```text
Yahoo Finance auto_adjust=True
```

Do not mix adjusted and unadjusted fields inside one signal or trade lifecycle.

Use the existing canonical market-session infrastructure and point-in-time membership manifest where possible.

---

## 4. Core signal definition

For symbol `s` and signal session `T`, define the one-session close-to-close return:

```text
Return[T] = Close[T] / Close[T-1] - 1
```

### Prior volatility

Define prior 20-return volatility using only information available before the signal session closes:

```text
Sigma20[T] = sample standard deviation of daily returns
             from T-20 through T-1
```

The shock-day return itself is **not** included in `Sigma20[T]`.

If fewer than 20 valid prior daily returns exist, the session cannot qualify.

### Shock score

Define:

```text
Shock_Score[T] = Return[T] / Sigma20[T]
```

This field is intentionally named `Shock_Score`, not statistical `Z_Score`, because the numerator is not mean-adjusted.

Require:

```text
Shock_Score[T] <= -2.0
```

If `Sigma20[T]` is missing, non-finite, or non-positive, the session cannot qualify.

---

## 5. Volume conditioning

Define the prior-volume baseline from the 20 sessions immediately preceding the signal session:

```text
Prior20_Median_Volume[T] = median(Volume[T-20 ... T-1])

Volume_Ratio[T] = Volume[T] / Prior20_Median_Volume[T]
```

The signal-day volume is not included in its own baseline.

### Low-volume trade cohort

R1's actual trade hypothesis requires:

```text
Volume_Ratio[T] <= 1.0
```

Interpretation: the unusually large decline occurred on no more than the stock's normal median recent volume.

### High-volume falsification/control cohort

Separately retain large negative shocks satisfying:

```text
Shock_Score[T] <= -2.0
Volume_Ratio[T] >= 1.5
```

These signals are **not R1 trades**. They form a control cohort used to test whether the proposed low-participation mechanism has empirical support.

The control cohort must use the same PIT universe, liquidity eligibility, signal window, immediate-next-open forward-return timing, five-session primary horizon, and same-symbol lockout logic as the low-volume cohort.

The control cohort is evaluated only through the fixed-horizon setup-quality return. It does not use R1's structural-stop cancellation or practical-stop exit, because those mechanics are not part of the raw low-volume-versus-high-volume reversal comparison.

### Middle-volume diagnostic cohort

Signals satisfying:

```text
1.0 < Volume_Ratio[T] < 1.5
```

remain visible diagnostically but belong to neither the R1 trade cohort nor the high-volume control cohort.

Do not search these intervals after the fact for a better volume threshold.

---

## 6. Liquidity eligibility

Require on the signal date:

```text
Prior20_Median_Traded_Value[T] >= ₹10 crore
```

where:

```text
Daily_Traded_Value = Close × Volume
```

and the liquidity baseline uses only sessions `T-20 ... T-1`.

The shock session itself is excluded from the liquidity baseline so that an abnormal event cannot make an otherwise illiquid stock qualify because of the shock-day turnover.

If fewer than 20 valid prior traded-value observations exist, the session cannot qualify.

---

## 7. What R1 deliberately does not require

R1 has no primary filter for:

- RSI or any generic oversold oscillator;
- price above/below SMA20, SMA50, or SMA200;
- moving-average slope;
- relative strength;
- sector strength;
- distance from 52-week high;
- market breadth;
- market regime;
- index trend;
- confirmation candle;
- next-day bullish confirmation;
- positive next-day gap;
- news interpretation;
- fundamental quality beyond the point-in-time Nifty 500 + liquidity universe definition.

These may be retained as diagnostics where data already exists, but none may affect primary R1 eligibility.

---

## 8. Signal qualification

A session becomes a qualified low-volume R1 signal only if all are true:

1. `Signal_Date` is inside 2023-08-01 through 2026-08-25 inclusive.
2. Symbol is an active point-in-time Nifty 500 member on `Signal_Date`.
3. At least 20 valid prior returns exist.
4. `Sigma20` is finite and positive.
5. `Shock_Score <= -2.0`.
6. At least 20 valid prior volume observations exist.
7. `Volume_Ratio <= 1.0`.
8. At least 20 valid prior traded-value observations exist.
9. `Prior20_Median_Traded_Value >= ₹10 crore`.

All close-derived signal information is known only after the signal session closes.

No same-session entry is assumed.

The same-symbol lifecycle lockout is intentionally **not** part of signal qualification. A fully qualified low-volume signal that occurs during an active same-symbol lockout remains in the qualified-signal population and is recorded as an entry cancellation with reason `SAME_SYMBOL_LOCKOUT`. This preserves the accounting identity defined later.

---

## 9. ATR and structural stop

Use **Wilder ATR14**, consistent with the established swing-research convention.

True Range is:

```text
TR[t] = max(
    High[t] - Low[t],
    abs(High[t] - Close[t-1]),
    abs(Low[t] - Close[t-1])
)
```

ATR initialization and recursion are frozen as:

```text
first valid ATR14 = mean of the first 14 valid True Range observations

subsequent ATR14 =
(previous_ATR14 × 13 + current_TR) / 14
```

On the signal date define:

```text
Structural_Stop = Shock_Day_Low - 0.25 × ATR14_signal
```

`ATR14_signal` must use only information available by the signal-date close.

The stop is deliberately tied to the shock-day structural extreme. The R1 thesis is that the shock represents temporary selling pressure; a meaningful move beneath that extreme is treated as evidence against the practical trade thesis.

Do not introduce:

- fixed-percentage stops;
- entry-based ATR stops;
- moving-average stops;
- trailing stops;
- breakeven moves;
- profit targets.

Do not reject a valid signal merely because the structural stop is wide. Stop width remains diagnostic in this first signal-level edge test.

---

## 10. Immediate next-session entry

Each qualified R1 signal gets exactly one automatic entry opportunity: the **Open of the immediately following canonical market session**.

If that next canonical session or the symbol's bar is unavailable, cancel the entry with a specific reason.

### Structural invalidation before entry

If:

```text
Entry_Open <= Structural_Stop
```

cancel as:

```text
OPEN_BELOW_STRUCTURAL_STOP
```

Do not buy an already-broken setup and immediately count a stop-out.

### No upside-gap cancellation

There is no positive-gap or chase cancellation rule in R1.

If the stock rebounds substantially between the signal close and next-session open, R1 still enters at the actual open. The purpose is to measure whether the reversal remains exploitable after realistic next-session execution, not whether an idealized close-to-close anomaly exists.

---

## 11. Same-symbol lifecycle lockout

R1 must not turn consecutive shock signals in one collapsing stock into de facto averaging down.

After one low-volume R1 signal is accepted for a symbol, no second low-volume R1 entry may be accepted in that same symbol until the original signal's scheduled five-session lifecycle has fully passed.

Define:

```text
Signal session = T
Entry session  = immediate next session after T
Scheduled fixed-horizon exit = Open of the sixth canonical session after T
```

Therefore the position is exposed across five complete sessions beginning with the entry session.

The lockout remains in force until that scheduled exit point even if the practical lens stops out early.

Additional qualified low-volume signals during lockout remain visible and are cancelled with:

```text
SAME_SYMBOL_LOCKOUT
```

This preserves one common underlying signal set for setup-quality and practical lenses and avoids implicit averaging down.

The high-volume control cohort applies the same one-signal-per-symbol five-session lifecycle rule inside the control cohort so repeated collapses do not mechanically overweight one symbol.

Cross-stock signals are **not** suppressed in this first signal-level experiment.

---

## 12. Lens A — setup-quality / raw reversal effect

The setup-quality lens asks whether the low-volume price-shock reversal effect exists after realistic next-open entry, independent of stop mechanics.

For every accepted signal with sufficient future data:

```text
Entry = immediate next-session Open
Exit  = Open of the sixth canonical session after Signal_Date
```

Equivalently, if the signal is `T`, enter `T+1 Open`, remain exposed across sessions `T+1` through `T+5`, and exit `T+6 Open`.

There is:

- no structural stop;
- no profit target;
- no trailing exit;
- no breakeven rule;
- no market/regime exit.

Gross setup return:

```text
Gross_Return = (Exit_Price - Entry_Open) / Entry_Open
```

Return profit factor:

```text
Return_PF = sum(positive returns) / abs(sum(negative returns))
```

Also retain 1-, 3-, 10-, and 20-session forward outcomes as diagnostics only. They cannot replace the primary five-session horizon after results are observed.

---

## 13. Lens B — practical trading

The practical lens uses the same accepted Entry_ID set and the fixed structural stop.

For each holding session from entry through the fifth complete holding session, apply this precedence:

1. If the current session Open is at or below `Structural_Stop`, exit at that Open.
2. Otherwise, if the current session Low is at or below `Structural_Stop`, exit at `Structural_Stop`.
3. Otherwise remain open.
4. If no stop has occurred by the end of the fifth complete holding session, exit at the Open of the immediately following canonical session.

Because entry itself is cancelled when `Entry_Open <= Structural_Stop`, the entry-session open cannot itself create an accepted-trade gap stop. On the entry session, after a valid entry, an intraday `Low <= Structural_Stop` exits at the structural stop. On later sessions, the Open-before-Low precedence applies normally.

No profit target or trailing logic is introduced.

Initial risk:

```text
Initial_Risk = Entry_Open - Structural_Stop
```

Require `Initial_Risk > 0` for every accepted practical trade.

Gross R multiple:

```text
Gross_R = (Exit_Price - Entry_Open) / Initial_Risk
```

Gap losses may be worse than `-1R`.

---

## 14. Friction model

R1 is short horizon, so costs are part of the primary validation rather than a footnote.

Use three frozen round-trip friction assumptions:

```text
Base friction   = 0.40% of entry value
Stress friction = 0.60% of entry value
Severe friction = 0.80% of entry value
```

For completed trades under friction rate `c`:

```text
Net_Return_c = Gross_Return - c
```

For the practical lens:

```text
Net_R_c = ((Exit_Price - Entry_Open) - c × Entry_Open) / Initial_Risk
```

Use the **0.40% base** model for primary net-return and primary practical R gates.

Use **0.60% stress** for mandatory friction robustness gates.

Use **0.80% severe** diagnostically; it does not independently create a PASS/FAIL gate.

These fixed percentages are research assumptions intended to include taxes, fees, DP/brokerage effects in aggregate, and slippage. Broker-specific rupee economics and small-account fixed charges must be modeled separately before live deployment.

---

## 15. Control-cohort falsification test

The low-volume mechanism is not considered supported merely because the low-volume trade cohort is profitable.

Construct the high-volume control cohort using:

```text
Shock_Score <= -2.0
Volume_Ratio >= 1.5
```

with the same PIT membership, liquidity, immediate-next-open timing, fixed five-session horizon, and same-symbol lifecycle construction.

Compare the low-volume trade cohort with the high-volume control cohort using **gross setup-quality five-session returns before friction**.

The control gate requires both:

```text
Mean_Return_LOW_VOLUME > Mean_Return_HIGH_VOLUME
```

and:

```text
Return_PF_LOW_VOLUME > Return_PF_HIGH_VOLUME
```

Also report a bootstrap confidence interval for the difference in mean five-session returns.

If R1 itself is profitable but the low-volume cohort does not outperform the high-volume control on both predeclared comparison metrics, the volume-conditioning thesis gate fails.

Do not change the 1.0 / 1.5 volume boundaries after observing the control result.

---

## 16. Accounting funnel

Track the research funnel explicitly.

At minimum:

```text
All Shock_Score <= -2 sessions
-> PIT + data + liquidity eligible shocks
-> low-volume candidates
-> high-volume control candidates
-> middle-volume diagnostics
```

For the low-volume R1 trade cohort:

```text
Qualified R1 signals
-> accepted entries + entry cancellations
-> completed paired outcomes + incomplete accepted entries
```

A qualified R1 signal has already passed the frozen PIT/data/liquidity/shock/low-volume rules. Entry-stage mechanics may still cancel it.

Entry-cancellation reasons must distinguish at minimum:

- `MISSING_NEXT_SESSION`;
- `MISSING_NEXT_SESSION_BAR`;
- `OPEN_BELOW_STRUCTURAL_STOP`;
- `SAME_SYMBOL_LOCKOUT`.

Require mechanically:

```text
Qualified_R1_Signals = Accepted_Entries + Entry_Cancellations
```

Every accepted entry must reference exactly one qualified signal.

Every cancellation must reference exactly one qualified signal.

No signal may silently disappear.

---

## 17. Paired completed-sample rule

The setup-quality and practical lenses must use the same completed `Entry_ID` set.

Require:

```text
Completed_Setup_Entry_IDs == Completed_Practical_Entry_IDs
```

An accepted entry is primary-complete only when both lenses can be evaluated consistently through the required data horizon.

If the practical lens stops out early but the setup-quality lens lacks enough future sessions to reach its scheduled exit, that accepted entry remains visible as incomplete research evidence and is excluded from the primary paired sample.

This rule prevents sample-composition differences from explaining apparent differences between the lenses.

---

## 18. Cross-stock overlap and capacity diagnostics

Do not suppress otherwise valid R1 signals merely because other symbols already have open signal-level trades.

The first R1 question is individual-signal edge, not constrained portfolio performance.

Calculate at minimum:

- total accepted entries;
- maximum simultaneous signal-level trades;
- average simultaneous signal-level trades;
- maximum same-day entries;
- percentage of accepted entries overlapping at least one other open R1 trade;
- distribution of same-day signal counts;
- broad sector concentration where sector mapping is available;
- implied capital requirement under eventual 1%-risk-per-trade sizing.

If R1 passes, a later research stage must test the actual 3–5-position portfolio constraint and signal-ranking problem independently.

Do not invent ranking rules inside R1.

---

## 19. Point-in-time integrity audit

The final run must derive PIT integrity from persisted numeric/date evidence. It must not rely only on convenience booleans such as `PIT_OK=True`.

For independent numeric comparisons in the audit, use the deterministic tolerance convention:

```text
np.isclose(observed, recomputed, rtol=1e-9, atol=1e-12)
```

unless exact integer/date equality is appropriate.

For every accepted low-volume R1 entry, independently verify at minimum:

1. `Signal_Date < Entry_Date`.
2. `Signal_Date` is inside the frozen signal window.
3. Symbol is a point-in-time Nifty 500 member on `Signal_Date`.
4. `Entry_Date` is the immediately following canonical market session.
5. Twenty valid prior returns genuinely precede the signal date.
6. Persisted `Sigma20` matches a recomputation from only prior returns.
7. Persisted `Shock_Score` matches persisted signal return and recomputed `Sigma20` within the frozen tolerance.
8. `Shock_Score <= -2.0` for every accepted low-volume trade.
9. Twenty valid prior volume observations genuinely precede the signal date.
10. Persisted prior median volume and `Volume_Ratio` match an independent recomputation.
11. `Volume_Ratio <= 1.0` for every accepted low-volume trade.
12. Twenty valid prior traded-value observations genuinely precede the signal date.
13. Persisted prior median traded value matches an independent recomputation.
14. Prior median traded value is at least ₹10 crore.
15. `ATR14_signal` and `Shock_Day_Low` are known no later than the signal close.
16. Persisted structural stop matches `Shock_Day_Low - 0.25 × ATR14_signal` within the frozen tolerance.
17. `Entry_Open > Structural_Stop` for every accepted trade.
18. The same-symbol lockout was respected.
19. Setup/practical completed Entry_ID sets match exactly.
20. Scheduled fixed-horizon exit session ordering is correct.

The audit should similarly validate core timing and cohort membership for the high-volume control sample.

If:

```text
PIT_VIOLATION_COUNT > 0
```

or another mandatory integrity invariant fails, abort profitability interpretation and classify the run as `INVALID_RESEARCH_RUN`.

Do not report profitability gates as meaningful when the run is invalid.

---

## 20. Diagnostics retained but forbidden as post-hoc filters

Retain, where practical, enough context to understand the result without changing R1.

### Shock diagnostics

- `Shock_Score`;
- absolute shock-day return;
- ATR-normalized decline;
- `Volume_Ratio`;
- signal-day range;
- close location within signal-day range;
- signal-close to next-open gap.

### Stock context

- SMA20 / SMA50 / SMA200 relationship;
- relative-strength percentile where existing PIT RS infrastructure permits it safely;
- prior 21/63/126-session returns;
- distance from 52-week high;
- recent realized volatility;
- sector mapping where available.

### Market context

- broad-index return;
- existing breadth metrics;
- existing broad-market regime classification if available;
- market volatility;
- number of simultaneous qualifying shocks.

### Trade-path diagnostics

- 1-, 3-, 5-, 10-, and 20-session forward returns;
- maximum favorable excursion;
- maximum adverse excursion;
- time to MFE;
- time to MAE;
- structural-stop width in price percentage and ATR units;
- practical exit reason;
- calendar year.

These fields are explanatory only.

If a subgroup appears materially better after outcomes are known, it may seed a separately named, separately designed future hypothesis. It cannot become part of R1.

---

## 21. Regime treatment

Market regime is **diagnostic only** in R1.

Do not exclude signals based on `HOSTILE`, `NORMAL`, `STRONG_MOMENTUM`, or any later regime label.

The purpose is partly to discover whether short-horizon reversal behaves differently from momentum across environments without presupposing the answer.

Any future regime-conditioned reversal strategy requires its own predeclared design and validation.

---

## 22. Bootstrap robustness

Use deterministic bootstrap reporting for uncertainty around key averages.

Frozen reporting convention:

```text
Bootstrap resamples = 10,000
RNG seed            = 20260828
Confidence interval = 95%
```

Report bootstrap confidence intervals for at least:

- gross five-session mean setup return;
- base-friction five-session mean setup return;
- base-friction practical mean R;
- low-volume minus high-volume difference in gross five-session mean return.

Bootstrap intervals are robustness evidence, not an independent arbitrary p-value PASS/FAIL gate.

---

## 23. Temporal robustness

Use a predeclared fixed calendar split of the signal window:

```text
First half:  2023-08-01 through 2025-02-11 inclusive
Second half: 2025-02-12 through 2026-08-25 inclusive
```

For completed low-volume paired trades in each half, compute base-friction setup-quality net mean return and base-friction net PF.

The mandatory temporal gate requires in **both** halves:

```text
Base_Net_Mean_Return > 0
```

and:

```text
Base_Net_Return_PF > 1.0
```

Also report calendar-year summaries diagnostically.

Do not move the split after results are observed.

---

## 24. Outlier robustness

### Top-five winner removal

Rank completed low-volume setup-quality trades by gross return and remove the top five individual winners.

Recompute the **base-friction** setup-quality metrics on the remaining sample.

Mandatory gate:

```text
Remaining_Base_Net_Mean_Return > 0
```

and:

```text
Remaining_Base_Net_Return_PF > 1.0
```

### Leave-one-symbol-out robustness

For each symbol represented in the completed low-volume paired sample, remove all completed trades from that symbol and recompute base-friction setup-quality results.

Mandatory gate: every leave-one-symbol-out sample must satisfy:

```text
Base_Net_Mean_Return > 0
```

and:

```text
Base_Net_Return_PF > 1.0
```

This ensures no single stock is necessary for the observed edge.

---

## 25. Precommitted validation gates

R1 passes historical signal-level validation only if every mandatory gate below passes.

### Research validity

```text
PIT / integrity violations = 0
Accounting invariants       = PASS
Setup/practical Entry_IDs    = identical
```

Any failure here produces `INVALID_RESEARCH_RUN`, not a strategy FAIL.

### Sample sufficiency

```text
Completed paired low-volume outcomes >= 300
```

If fewer than 300 completed paired outcomes exist and the run is otherwise valid, final status is `INSUFFICIENT_EVIDENCE`.

### Setup-quality expectancy

```text
Gross_Mean_Return > 0
Base_Net_Mean_Return >= +0.20% per completed trade
Base_Net_Return_PF >= 1.20
```

where base friction is 0.40% round trip.

### Stress-friction robustness

At 0.60% round-trip friction:

```text
Stress_Net_Mean_Return > 0
Stress_Net_Return_PF > 1.00
```

### Practical trading expectancy

Using the structural-stop practical lens and **0.40% base friction**:

```text
Base_Practical_Mean_R >= +0.15R
Base_Practical_R_PF >= 1.20
```

### Volume-conditioning falsification

Using gross five-session setup-quality returns:

```text
Mean_Return_LOW_VOLUME > Mean_Return_HIGH_VOLUME
Return_PF_LOW_VOLUME > Return_PF_HIGH_VOLUME
```

### Temporal robustness

Both frozen calendar halves must have:

```text
Base_Net_Mean_Return > 0
Base_Net_Return_PF > 1.0
```

### Top-five-winner robustness

After removing the five largest gross winners:

```text
Base_Net_Mean_Return > 0
Base_Net_Return_PF > 1.0
```

### Leave-one-symbol-out robustness

Every symbol omission must retain:

```text
Base_Net_Mean_Return > 0
Base_Net_Return_PF > 1.0
```

The severe 0.80% friction scenario, bootstrap confidence intervals, regime splits, trend splits, shock-magnitude buckets, gap buckets, and all other diagnostics do not independently create extra primary gates.

---

## 26. Final status hierarchy

Assign exactly one formal status.

### `INVALID_RESEARCH_RUN`

Use when any mandatory research-integrity condition fails, including non-zero PIT violations, unreconciled accounting, mismatched completed Entry_ID sets, missing required artifacts, or corrupted/unverifiable core timing evidence.

Profitability interpretation must stop.

### `INSUFFICIENT_EVIDENCE`

Use when the run is valid but fewer than 300 completed paired low-volume outcomes are available.

Observed performance may be described but cannot receive PASS.

### `PASS`

Use only when the run is valid, sample sufficiency passes, and **all** mandatory expectancy, friction, practical, falsification, temporal, outlier, and leave-one-symbol-out gates pass.

PASS means:

> R1 has sufficient historical signal-level evidence to proceed to portfolio-constrained and forward validation.

PASS does **not** mean ready for normal-capital live deployment.

### `FAIL`

Use when the run is valid and has sufficient evidence but one or more mandatory strategy gates fail.

Do not rescue a FAIL by modifying R1 from its post-hoc diagnostics.

---

## 27. Required final reporting

The final research report must state at minimum:

- frozen hypothesis and rules;
- historical data window and PIT universe treatment;
- usable-symbol/data coverage counts;
- all large-shock counts;
- low-volume / middle-volume / high-volume cohort counts;
- qualified / accepted / cancelled / completed / incomplete accounting;
- cancellation reasons;
- gross setup-quality metrics;
- base/stress/severe friction setup metrics;
- gross practical metrics;
- base-friction practical R metrics;
- high-volume control comparison;
- fixed-half temporal summary;
- calendar-year diagnostic summary;
- top-five-winner robustness;
- leave-one-symbol-out robustness;
- overlap/capacity diagnostics;
- bootstrap intervals;
- regime and other diagnostic summaries;
- PIT/integrity audit result;
- each precommitted validation gate with PASS/FAIL;
- exactly one final formal status.

The report must clearly distinguish primary gates from diagnostics.

---

## 28. Interpretation discipline after results

Examples of conclusions that are allowed:

- `R1 PASS: proceed to portfolio-constrained/forward validation.`
- `R1 FAIL: low-volume shock reversal did not survive practical costs.`
- `R1 FAIL: reversal existed, but low volume did not outperform the high-volume control.`
- `R1 FAIL: edge depended excessively on a few winners or one period.`
- `R1 INSUFFICIENT_EVIDENCE: sample below 300 completed paired trades.`
- `R1 INVALID_RESEARCH_RUN: PIT/accounting audit failed; profitability cannot be interpreted.`

Examples of post-hoc rescue that are prohibited:

- changing `Shock_Score <= -2.0` to the best-performing shock bucket;
- changing low volume from `<=1.0` to the best observed threshold;
- adding `Close > SMA200` because that subgroup worked;
- excluding HOSTILE markets because they performed badly;
- switching from five sessions to ten because the 10-session diagnostic was prettier;
- adding gap cancellation because overnight reversal consumed the edge;
- excluding sectors or years after outcomes are known;
- changing the stop buffer because another value backtested better.

Any such observation can motivate a separately designed future hypothesis only.

---

## 29. Relationship to future regime-aware framework

R1 is one candidate independent strategy module in the broader regime-aware research program.

The eventual architecture remains conceptually:

```text
independently validated strategy modules
-> systematic eligibility / regime layer
-> portfolio and risk layer
-> trade or cash
```

R1 must first prove itself **unconditionally under this frozen specification**.

The regime router is not part of R1 and must not be implemented or optimized from R1 outcomes.

---

## 30. Core frozen specification summary

```text
Universe:
    point-in-time Nifty 500

Signal window:
    2023-08-01 through 2026-08-25

Liquidity:
    prior-20-session median traded value >= ₹10 crore

Shock:
    Return[T] = Close[T] / Close[T-1] - 1
    Sigma20 = prior 20 daily-return standard deviation
    Shock_Score = Return[T] / Sigma20
    require Shock_Score <= -2.0

Low-volume R1 cohort:
    signal-day Volume <= prior-20 median Volume

High-volume control:
    signal-day Volume >= 1.5 × prior-20 median Volume

Entry:
    immediately following market-session Open

Pre-entry cancellation:
    Entry_Open <= Structural_Stop
    or active SAME_SYMBOL_LOCKOUT

Structural stop:
    Shock_Day_Low - 0.25 × ATR14_signal

Primary setup horizon:
    T+1 Open entry
    T+6 Open exit
    five complete holding sessions

Practical exit:
    structural stop or fixed-horizon exit, whichever occurs first

Same-symbol rule:
    one accepted signal per five-session lifecycle
    no averaging down / repeated entries during lockout

Cross-stock overlap:
    retained for signal-level testing

Friction:
    base 0.40%
    stress 0.60%
    severe 0.80%

No primary:
    RSI
    trend filter
    RS filter
    sector filter
    regime filter
    breadth filter
    confirmation candle
    gap-up cancellation
    profit target
    parameter rescue
```

R1 therefore asks exactly one primary research question:

> **Does abnormal low-participation short-term selling pressure produce a robust, practically exploitable five-session reversal in liquid Indian equities after realistic next-session execution and trading friction?**
