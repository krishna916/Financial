# Strategy V2 Design — RS Leader + Quality Base / Volatility-Contraction Breakout

**Status:** In-chat architecture approved; written spec pending review; implementation and validation not started  
**Design date:** 26 August 2026  
**Repository:** `krishna916/Financial`  
**Research family:** New strategy family; T1 remains retired

## 1. Objective

Strategy V2 tests a materially different implementation of the broader long-only momentum thesis for Indian cash equities.

The hypothesis is:

> A stock that already demonstrates relative-strength leadership and an established uptrend, then forms a multi-week constructive base with measurable volatility contraction below a meaningful pivot, should produce better breakout expectancy than a naive fresh 20-day breakout.

The research objective is **not** to rescue T1 and not to optimize previously tested thresholds.

The core sequence is:

```text
Leadership
→ meaningful pivot
→ constructive base
→ volatility contraction
→ structural breakout
→ extension-controlled next-session entry
→ nearby structural invalidation
→ trend-following exit
```

## 2. Research discipline

Use the following process throughout V2:

> **One hypothesis → one predefined change → test → document → decide → move on.**

Rules:

- Do not optimize thresholds after seeing outcomes.
- Do not stack additional filters to rescue weak results.
- Negative results are valid research outcomes.
- Every parameter must have a market-behavior rationale.
- Close-derived context must be strictly known before entry.
- T1 remains retired; V2 is a new strategy family, not T5.

## 3. Universe and eligibility

### Historical validation universe

Use **point-in-time Nifty 500 membership** on the breakout signal date.

Do not apply today's Nifty 500 membership retrospectively.

A symbol may use valid historical OHLCV from before its index-entry date to calculate indicators/base structure, but it can generate a V2 signal only while it belongs to the point-in-time Nifty 500 on the signal date.

### Future/live universe

Use:

- Nifty 500; plus
- manually approved quality additions where appropriate.

### Liquidity

On the breakout signal date require:

```text
20-session median daily traded value >= ₹10 crore
```

Median traded value is preferred to raw volume or average traded value because it is less distorted by abnormal one-day activity.

### Exclusions

Exclude:

- SME securities;
- microcaps;
- materially illiquid securities;
- materially restricted/surveillance-affected securities where reliable point-in-time data is available;
- suspended/problematic securities.

Do not reconstruct historical surveillance status from current status.

### Fundamental/governance safety

Basic governance and fundamental sanity remain part of **live execution**, but should not be reconstructed as a historical kernel filter unless genuinely point-in-time structured data is available.

The historical technical test must not use hindsight-heavy manual governance judgments.

## 4. Price-data treatment

Use a single consistently corporate-action-adjusted daily OHLCV series for strategy calculations where the chosen data source supports it.

The same adjustment convention must be used for:

- High/Low/Close used in pivot/base detection;
- moving averages;
- ATR/True Range;
- breakout returns;
- stop/exit simulation.

Do not mix adjusted and unadjusted price fields inside one trade lifecycle.

Data-source and adjustment conventions must be documented in the implementation README/audit output.

## 5. Trend eligibility

On the breakout signal date require:

```text
Close > SMA50
SMA50 > SMA200
```

Do **not** require SMA50 to be rising versus 20 sessions earlier.

Reason: the earlier T3 experiment already tested the rising-SMA50 idea as an incremental condition and did not justify keeping it as a hard requirement.

SMA50 slope may still be recorded as diagnostic metadata.

## 6. Relative-strength leadership

Use the existing point-in-time cross-sectional stock-RS framework:

```text
RS21 percentile weight  = 30%
RS63 percentile weight  = 40%
RS126 percentile weight = 30%

Composite_RS =
0.30 × RS21
+ 0.40 × RS63
+ 0.30 × RS126
```

On the breakout signal date require:

```text
Composite_RS >= 70
```

Interpretation:

- `70–79.99`: valid leadership;
- `80–89.99`: preferred leadership;
- `>=90`: exceptional leadership, with extension risk requiring particular attention.

Do not introduce a second hard RS threshold before validation.

Store the continuous RS value so 70–80, 80–90 and 90+ can be analyzed diagnostically without permission to retune the strategy after outcomes are known.

## 7. Meaningful pivot and base-state machine

The base is anchored to a meaningful intermediate-term price high rather than an arbitrary recent candle.

### Initial pivot seed

A date `P` may seed a new base when:

```text
High[P] = highest High over sessions P-62 through P
```

The active pivot initially equals `High[P]`.

Base session 1 is the next trading session after `P`.

Only one active V2 base is tracked per symbol at a time.

### Failed intraday probes

During an active base, if:

```text
High[t] > Active_Pivot
AND
Close[t] <= Active_Pivot
```

then update:

```text
Active_Pivot = High[t]
```

Do **not** restart the base-session count.

The ATR denominator used for the base-depth rule remains `ATR14` from the **original pivot-seed date P**, even if the active pivot later updates after a failed probe.

### Close above pivot before minimum duration

If price closes above the active pivot before 10 base sessions have completed, the candidate has not formed a valid V2 base.

Cancel that active base.

The same day may independently seed a new future base if it satisfies the 63-session-high rule.

### Base expiration

If no qualifying breakout occurs by the end of base session 30, expire the active base.

A later date may independently seed a new base when it satisfies the 63-session-high rule.

### Breakout ends the base

A close above the active pivot on base session 10–30 ends the active base and creates one breakout signal candidate, subject to all signal-date rules.

Once that breakout signal occurs, the old base is not reused for later entries, even if the next-session entry is cancelled by extension/gap rules.

## 8. Base depth

For an active base define:

```text
Base_Depth_ATR =
(Active_Pivot - lowest Low since base session 1) / ATR14_at_original_pivot_seed
```

Require throughout the base and on the breakout signal date:

```text
Base_Depth_ATR <= 4.0
```

If the threshold is breached at any time, invalidate the active base immediately.

Rationale: the base should remain controlled relative to the stock's own normal volatility. Quiet stocks therefore need shallower absolute structures, while naturally volatile stocks receive proportionately more room.

## 9. Volatility contraction

Volatility contraction is the primary new quality condition in Strategy V2.

For the final valid base immediately before breakout calculate:

```text
Initial_Volatility = mean True Range of base sessions 1–5
Final_Volatility   = mean True Range of final 5 pre-breakout base sessions
```

The breakout candle itself is excluded from `Final_Volatility`.

Require:

```text
Final_Volatility <= 0.80 × Initial_Volatility
```

This means the final portion of the base must exhibit at least approximately 20% lower true-range volatility than the beginning of the base.

The intended market behavior is supply contraction: price becomes quieter while holding near resistance before the breakout attempt.

### Deliberately excluded base rules

Do **not** initially require:

- perfect higher lows;
- exact cup-and-handle geometry;
- three sequential VCP contraction legs;
- shrinking volume every week;
- `SMA20 > SMA50`;
- candlestick-pattern gates;
- sector-RS gates.

These would materially increase parameter count before proving that simple structural contraction has edge.

## 10. Breakout trigger

On base session 10–30, a breakout candidate occurs when:

```text
Daily Close > Active_Pivot
```

The signal is known only after that session closes.

A breakout candidate becomes a valid V2 signal only if all signal-date eligibility rules also pass, including:

- point-in-time Nifty 500 membership;
- liquidity;
- trend;
- Composite RS;
- base depth;
- volatility contraction;
- signal-day extension control.

If price closes above the pivot but any required signal-date rule fails, the base is still considered broken/finished and is not reused.

No same-session entry is assumed in the historical test.

## 11. Point-in-time timing rule

The entry occurs no earlier than the next trading session after the breakout signal.

Therefore all daily close-derived data used to justify the trade must satisfy:

```text
Context_Date < Entry_Date
```

Strict `<` is mandatory.

This applies to:

- stock RS;
- market breadth;
- sector context;
- moving averages;
- ATR;
- pivot/base state;
- liquidity calculated from completed daily bars;
- any future daily close-derived research feature.

No same-entry-day close-derived context may be used to justify an entry at that day's open.

## 12. Volume treatment

Do **not** use breakout volume as a hard V2 entry gate.

The earlier T2 experiment did not justify a simple volume-confirmation rule as a mandatory filter.

Still record:

```text
Breakout_Volume_Ratio =
Breakout_Volume / 20-session median Volume
```

Use it only as diagnostic metadata in the initial V2 validation.

## 13. Extension control

Use breakout-signal-day ATR14 for both signal-day and next-session extension checks.

### Signal-day eligibility

Require:

```text
Breakout_Close <= Active_Pivot + 1.0 × ATR14_signal
```

### Immediate next-session entry eligibility

There is exactly **one automatic entry opportunity** from a V2 breakout signal: the open of the immediately following trading session.

Require:

```text
Entry_Open >= Active_Pivot
Entry_Open <= Active_Pivot + 1.0 × ATR14_signal
```

If the next open is above `Active_Pivot + 1 ATR14_signal`:

```text
EXTENDED → cancel trade
```

If the next open is below the active pivot:

```text
Breakout no longer confirmed → cancel trade
```

Do not wait for a later session to enter from the same breakout/base.

A later trade requires a newly qualified base and breakout sequence.

No alternate intraday rescue entry is assumed in the historical kernel.

## 14. Entry mechanics

For the initial V2 historical validation:

```text
Signal = qualifying breakout close above active pivot
Entry  = immediately following trading session open, if extension rules pass
```

No intraday monitoring is required.

This remains compatible with the strategy's intended end-of-day workflow and manual next-session execution.

## 15. Initial structural stop

The initial stop is derived from the final contraction structure rather than the bottom of the entire multi-week base.

Define using data known on the signal date:

```text
Structural_Stop =
lowest Low of the final 5 pre-breakout base sessions
- 0.25 × ATR14_signal
```

The breakout candle is not part of the final-five-session low.

The initial structural stop remains fixed during the first V2 validation; there is no trailing-stop rule before the SMA20 trend exit.

Rationale: losing the final tight consolidation area materially weakens the breakout thesis, while the ATR buffer avoids treating the exact visible low as a hair-trigger invalidation level.

## 16. Stop sanity check

Using the actual next-session entry open, reject the trade before entry if:

```text
Entry_Open - Structural_Stop > 2.5 × ATR14_signal
```

Also reject if the computed structural stop is not below the entry price.

Do not artificially tighten the structural stop to make position sizing or reward/risk look better.

If the logical invalidation is too distant, the trade is rejected.

## 17. Position sizing assumption

For practical-trading analysis and future live deployment:

```text
Planned portfolio risk per trade = 1% of dedicated swing capital
```

Quantity:

```text
Position_Quantity =
Portfolio_Risk_Amount / (Entry_Open - Structural_Stop)
```

Confidence does not override this risk budget.

Portfolio-capacity simulation is not part of the first signal-level edge test.

## 18. Exit architecture and execution

The first V2 validation avoids simultaneously redesigning both entry and exit logic.

### Setup-quality lens

This lens ignores the structural stop and exits only on the trend rule so that raw breakout quality can be compared without stop-shape effects.

Generate a trend-exit signal when:

```text
Daily Close < SMA20
```

Exit at the immediately following trading session open.

### Practical-trading lens

This lens uses both the fixed structural stop and the same SMA20 trend exit.

The structural stop is considered active immediately after entry.

For each session while the position is open:

1. If `Open <= Structural_Stop`, exit at that session's `Open` to model an adverse gap through the stop.
2. Else if `Low <= Structural_Stop`, exit at `Structural_Stop`.
3. Else remain open through that session unless a close-based SMA20 exit signal is generated.
4. If `Close < SMA20`, exit at the next trading session's `Open` unless the position has already exited through the structural stop.

If a prior close generated the SMA20 exit signal, the next session open is the exit price; no later intraday stop logic is needed because the position is closed at that open.

### No fixed profit target

Do not cap winners with an arbitrary percentage target.

### No automatic breakeven rule

Do not automatically move the stop to breakeven at +1R.

### No hard time stop in the initial validation

Record holding duration and stagnation, but do not add a 7-, 10- or 15-day forced exit before seeing whether the entry setup itself has edge.

## 19. Outcome definitions

For each completed trade calculate at minimum:

### Setup-quality lens

```text
Return = (Exit_Price - Entry_Open) / Entry_Open
```

Return profit factor:

```text
sum of positive trade returns / absolute sum of negative trade returns
```

### Practical-trading lens

Define initial risk per share:

```text
Initial_Risk = Entry_Open - Structural_Stop
```

Define realized R:

```text
R_Multiple = (Exit_Price - Entry_Open) / Initial_Risk
```

R profit factor:

```text
sum of positive R multiples / absolute sum of negative R multiples
```

If a gap exits below the structural stop, realized loss may be worse than `-1R`.

## 20. Market breadth treatment

Do **not** use breadth as a V2 entry gate in the primary test.

Attach the existing point-in-time Nifty 500 breadth regime to each V2 trade as diagnostic metadata using strict pre-entry timing.

The earlier T1 breadth study showed meaningful deterioration in HOSTILE conditions, but immediately adding a breadth gate to V2 would prevent clean attribution of any improvement to the new quality-base setup.

If V2 independently demonstrates edge, a later isolated hypothesis may test:

> Does blocking new V2 entries during HOSTILE breadth improve robustness?

Test HOSTILE exclusion before considering a STRONG-only entry requirement.

## 21. Sector relative strength

Do not use sector RS as a mandatory V2 entry gate in the first validation.

Record available sector-RS context as metadata where point-in-time data is reliable.

Earlier sector-RS evidence was not strong or monotonic enough to justify a hard filter.

Sector strength may later be evaluated as a ranking/tiebreaking feature in a separate hypothesis.

## 22. Event-risk treatment

Historical kernel validation should not synthesize a hindsight-heavy news filter.

For live execution, retain the operational V1 safety review for:

- earnings/results;
- board meetings;
- material exchange disclosures;
- regulatory decisions;
- major promoter/governance developments;
- significant corporate actions;
- other binary events likely to dominate ordinary technical behavior.

The live default is to avoid initiating an ordinary momentum trade immediately before a major binary event unless event risk is consciously accepted.

## 23. Overlapping signals and capital constraints

The first V2 validation asks:

> Does an individual V2 signal possess edge?

Therefore do **not** initially constrain the sample using the user's approximately ₹20,000 starting capital or a 3–5-position portfolio cap.

If signal-level V2 passes, run a separate portfolio-level validation incorporating:

- 3–5 concurrent positions;
- 1% risk per trade;
- simultaneous signals;
- sector/correlation concentration;
- capital availability;
- candidate prioritization.

Do not allow portfolio simulation to hide whether the underlying setup itself works.

## 24. Two validation lenses

Use the same V2 signal set for two complementary analyses.

### A. Setup-quality lens

Purpose: measure whether the new base/contraction entry architecture improves raw post-breakout behavior.

Use:

```text
Entry = immediately following eligible session open
Exit  = immediately following session open after Daily Close < SMA20
```

The structural stop is ignored in this lens.

### B. Practical-trading lens

Purpose: measure whether the setup can be traded with realistic structural risk control.

Use:

- the identical V2 signal/entry set;
- the fixed initial structural stop;
- the same next-session SMA20 trend exit;
- R-normalized outcomes based on initial risk.

Do not change the signal set between the two lenses.

## 25. Precommitted validation gate

The following gates are locked before observing V2 outcomes.

### Minimum evidence

Require:

```text
Completed trades >= 100
```

The count refers to V2 entries with completed outcomes in both validation lenses.

If fewer than 100 completed trades exist, classify the result as **INSUFFICIENT_EVIDENCE**, not success or failure.

### Setup-quality requirements

Require:

```text
Mean return > 0
Return profit factor >= 1.20
```

### Practical-trading requirement

Require:

```text
Mean expectancy >= +0.15R per trade
```

Also report practical R profit factor as a primary metric even though no additional precommitted pass threshold beyond the expectancy gate is introduced here.

### Temporal robustness

Use calendar-year entry cohorts as the predefined temporal robustness test.

A **qualifying calendar year** contains at least 20 completed V2 trades.

Require:

- at least two qualifying calendar years; and
- at least two qualifying calendar years with both setup-quality mean return `> 0` and practical mean R `> 0`.

If the overall sample has at least 100 trades but fewer than two qualifying calendar years, classify temporal robustness as **INSUFFICIENT_EVIDENCE** rather than silently redefining time periods after seeing outcomes.

### Positive-winner outlier robustness

Run the test independently for each validation lens:

- setup-quality lens: remove the five trades with the highest percentage returns;
- practical lens: remove the five trades with the highest R multiples.

After removal require:

```text
Setup-quality Return PF >= 1.0
Practical R PF >= 1.0
```

Do not choose a different outlier count after seeing results.

### Single-symbol dependence

Run leave-one-symbol-out analysis across every symbol represented in the completed V2 trade set.

For every leave-one-symbol-out sample require:

```text
Setup-quality Mean Return > 0
Setup-quality Return PF >= 1.0
Practical Mean R > 0
```

If excluding any single symbol causes those minimum edge conditions to fail, classify the strategy as failing the single-symbol robustness gate.

### Point-in-time integrity

Require zero lookahead violations.

Audit at minimum:

- signal date < entry date;
- RS context date < entry date;
- breadth context date < entry date;
- indicator/base inputs do not use bars after the signal date;
- point-in-time index membership is evaluated on the signal date;
- no exit uses a close before that close is known.

### No outcome-driven parameter changes

The parameters in this spec are frozen for the first V2 validation.

Changing any of them after observing outcomes creates a **new hypothesis/version** and must be documented as such rather than replacing the original V2 result.

## 26. Required research outputs

The implementation must generate reproducible machine-readable outputs sufficient to audit the strategy without rerunning calculations by hand.

At minimum produce:

- signal/trade-level dataset with pivot/base/RS/trend/ATR/entry/stop/exit fields;
- rejected/cancelled-signal audit with explicit reason codes;
- overall setup-quality summary;
- overall practical-trading summary;
- calendar-year summary;
- leave-one-symbol-out summary;
- top-five-winner-removal robustness summary;
- breadth-regime diagnostic summary;
- validation/invariant report;
- concise research report stating factual results without tuning recommendations.

## 27. Interpretation rules after validation

### If V2 passes

Do **not** immediately optimize it.

Proceed to one predefined next hypothesis at a time, with likely candidates including:

1. HOSTILE breadth exclusion;
2. portfolio-capacity simulation;
3. diagnostic volume usefulness;
4. sector strength as ranking/tiebreaker;
5. time/behavior capital-rotation logic.

### If V2 fails

Do not tune RS thresholds, base duration, ATR limits, contraction percentage, pivot window or exit period merely to obtain better historical results.

Diagnose the failure mode first:

- insufficient signal count;
- base detector too crude;
- contraction hypothesis not predictive;
- poor entry economics;
- structural stop behavior;
- regime dependence;
- excessive single-period or single-stock dependence.

Then decide whether a **new hypothesis** deserves testing.

## 28. Streak vs custom research decision

### Decision: `CUSTOM_REQUIRED`

The complete V2 hypothesis cannot be faithfully represented in Streak because it requires:

- point-in-time Nifty 500 membership;
- historical same-day cross-sectional RS percentiles;
- persistent base/pivot state tracking;
- failed-probe pivot updates;
- first-versus-final base volatility comparison;
- strict point-in-time research joins;
- structural-stop and robustness audit outputs.

Do not replace this with a simplified Streak proxy if doing so changes the hypothesis back into a generic recent-high breakout plus indicators.

Custom research must remain narrow and research-oriented rather than becoming production infrastructure.

## 29. Locked V2 kernel

```text
POINT-IN-TIME NIFTY 500 ON SIGNAL DATE
        ↓
20-session median traded value >= ₹10 crore
        ↓
Close > SMA50 > SMA200
        ↓
Composite_RS >= 70
        ↓
63-session High seeds one active base
        ↓
10–30 base sessions
        ↓
Base depth <= 4 ATR14-at-original-pivot
        ↓
Final 5-session mean True Range
<= 80% of initial 5-session mean True Range
        ↓
Daily Close breaks active pivot
        ↓
Breakout Close <= Pivot + 1 ATR14_signal
        ↓
Immediate next-session Open remains >= Pivot
and <= Pivot + 1 ATR14_signal
        ↓
Structural Stop = final 5 pre-breakout session low - 0.25 ATR14_signal
        ↓
Reject if Entry - Stop > 2.5 ATR14_signal
        ↓
ENTRY AT THAT NEXT OPEN
        ↓
Setup-quality lens: SMA20 close exit only
Practical lens: fixed structural stop + SMA20 close exit
        ↓
Daily Close < SMA20 → exit next session open
```

## 30. Explicitly not part of initial V2

The first validation must not add:

- breadth entry gates;
- sector-RS entry gates;
- volume multipliers as entry gates;
- RSI;
- MACD;
- ADX;
- candlestick-pattern scoring;
- textbook VCP multi-leg requirements;
- pyramiding;
- fixed profit targets;
- hard time stops;
- portfolio-position limits in the signal-level test;
- parameter sweeps intended to maximize backtest performance.

## 31. Research handoff after written-spec approval

Once this written design document is reviewed and accepted, the next workflow is:

1. create a dedicated GitHub issue for Strategy V2 historical validation;
2. create a mechanical implementation plan under `Swing Trading/docs/superpowers/plans/`;
3. execute the plan inline only;
4. build point-in-time/audit tests before trusting outcomes;
5. produce reproducible trade-level and robustness outputs;
6. return the PR to Portfolio Advisor for research-integrity review and the keep/retire decision.

No implementation or backtest is authorized by this design document alone.
