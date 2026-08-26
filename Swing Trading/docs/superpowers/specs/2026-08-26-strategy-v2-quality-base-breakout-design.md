# Strategy V2 Design — RS Leader + Quality Base / Volatility-Contraction Breakout

**Status:** Approved design; implementation and validation not started  
**Design date:** 26 August 2026  
**Repository:** `krishna916/Financial`  
**Research branch:** New strategy family; T1 remains retired

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

Use **point-in-time Nifty 500 membership**.

Do not apply today's Nifty 500 membership retrospectively.

### Future/live universe

Use:

- Nifty 500; plus
- manually approved quality additions where appropriate.

### Liquidity

Require:

```text
20-session median daily traded value >= ₹10 crore
```

Median traded value is preferred to raw volume or average traded value because it is less distorted by abnormal one-day activity.

### Exclusions

Exclude:

- SME securities;
- microcaps;
- materially illiquid securities;
- materially restricted/surveillance-affected securities where applicable;
- suspended/problematic securities.

### Fundamental/governance safety

Basic governance and fundamental sanity remain part of **live execution**, but should not be reconstructed as a historical kernel filter unless genuinely point-in-time structured data is available.

The historical technical test should not use hindsight-heavy manual governance judgments.

## 4. Trend eligibility

A candidate must satisfy, using information available on the signal date:

```text
Close > SMA50
SMA50 > SMA200
```

Do **not** require SMA50 to be rising versus 20 sessions earlier.

Reason: the earlier T3 experiment already tested the rising-SMA50 idea as an incremental condition and did not justify keeping it as a hard requirement.

SMA50 slope may still be recorded as diagnostic metadata.

## 5. Relative-strength leadership

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

### Entry eligibility

Require:

```text
Composite_RS >= 70
```

Interpretation:

- `70–79.99`: valid leadership;
- `80–89.99`: preferred leadership;
- `>=90`: exceptional leadership, with extension risk requiring particular attention.

Do not introduce a second hard RS threshold before validation.

Store the continuous RS value so 70–80, 80–90 and 90+ can be analyzed diagnostically without permission to retune the strategy after outcomes are known.

## 6. Meaningful pivot

The base is anchored to a meaningful intermediate-term price high rather than an arbitrary recent candle.

Define the initial pivot as a:

```text
63-session high
```

The pivot represents the resistance area that the future base is consolidating beneath.

### Failed probes during the base

If price trades intraday above the current pivot but **does not close above it**, the pivot may update to that higher failed-probe high without restarting the base.

A successful closing breakout above the active pivot ends the base and creates the breakout signal.

This rule prevents a small intraday overshoot from falsely invalidating an otherwise intact consolidation.

## 7. Base duration

A valid base must contain:

```text
10–30 trading sessions
```

Rationale:

- fewer than 10 sessions is often ordinary short-term noise rather than meaningful consolidation;
- more than 30 sessions begins to mix this swing setup with materially longer-duration bases;
- 10–30 sessions approximately represents a 2–6 week consolidation.

The range is locked for the first V2 validation and must not be adjusted after seeing results merely to improve performance.

## 8. Base depth

Do not use one fixed percentage-depth limit across stocks with different volatility profiles.

Define:

```text
Base_Depth_ATR =
(Pivot - Base_Low) / ATR14_at_pivot
```

Require:

```text
Base_Depth_ATR <= 4.0
```

Rationale: the base should remain controlled relative to the stock's own normal volatility. Quiet stocks therefore need shallower absolute structures, while naturally volatile stocks receive proportionately more room.

## 9. Volatility contraction

Volatility contraction is the primary new quality condition in Strategy V2.

For the final valid base immediately before breakout, calculate:

```text
Initial_Volatility = mean True Range of first 5 base sessions
Final_Volatility   = mean True Range of final 5 pre-breakout sessions
```

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

After at least 10 valid base sessions and no more than 30 sessions, generate a breakout signal when:

```text
Daily Close > active Pivot
```

The signal is known only after that session closes.

No same-session entry is assumed in the historical test.

## 11. Point-in-time timing rule

The entry occurs no earlier than the next trading session after the breakout signal.

Therefore all close-derived data used to justify the trade must satisfy:

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

Use signal-day ATR14 to prevent chasing breakouts that have already moved too far beyond the pivot.

### Signal-day eligibility

Require:

```text
Breakout_Close <= Pivot + 1.0 × ATR14
```

### Next-session entry eligibility

At the next session open, require:

```text
Entry_Open >= Pivot
Entry_Open <= Pivot + 1.0 × ATR14
```

If the next open is above `Pivot + 1 ATR`:

```text
EXTENDED → no trade
```

If the next open is below the pivot:

```text
Breakout no longer confirmed → no automatic entry
```

No alternate intraday rescue entry is assumed in the historical kernel.

## 14. Entry mechanics

For the initial V2 historical validation:

```text
Signal = breakout close above pivot
Entry  = next eligible session open
```

Entry must pass the extension-control rules above.

No intraday monitoring is required.

This remains compatible with the strategy's intended end-of-day workflow and manual next-session execution.

## 15. Initial structural stop

The initial stop is derived from the final contraction structure rather than the bottom of the entire multi-week base.

Define:

```text
Structural_Stop =
Final_5_Session_Low - 0.25 × ATR14
```

Use ATR known before entry.

Rationale: losing the final tight consolidation area materially weakens the breakout thesis, while the ATR buffer avoids treating the exact visible low as a hair-trigger invalidation level.

## 16. Stop sanity check

Reject a trade if:

```text
Entry - Structural_Stop > 2.5 × ATR14
```

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
Portfolio_Risk_Amount / (Entry - Structural_Stop)
```

Confidence does not override this risk budget.

Portfolio-capacity simulation is not part of the first signal-level edge test.

## 18. Exit architecture

The first V2 validation should avoid simultaneously redesigning both entry and exit logic.

### Initial protection

Use the structural stop defined above.

### Trend exit

Generate an exit signal when:

```text
Daily Close < SMA20
```

Exit on the next trading session.

### No fixed profit target

Do not cap winners with an arbitrary percentage target.

### No automatic breakeven rule

Do not automatically move the stop to breakeven at +1R.

### No hard time stop in the initial validation

Record holding duration and stagnation, but do not add a 7-, 10- or 15-day forced exit before seeing whether the entry setup itself has edge.

## 19. Market breadth treatment

Do **not** use breadth as a V2 entry gate in the primary test.

Attach the existing point-in-time Nifty 500 breadth regime to each V2 trade as diagnostic metadata using strict pre-entry timing.

The earlier T1 breadth study showed meaningful deterioration in HOSTILE conditions, but immediately adding a breadth gate to V2 would prevent clean attribution of any improvement to the new quality-base setup.

If V2 independently demonstrates edge, a later isolated hypothesis may test:

> Does blocking new V2 entries during HOSTILE breadth improve robustness?

Test HOSTILE exclusion before considering a STRONG-only entry requirement.

## 20. Sector relative strength

Do not use sector RS as a mandatory V2 entry gate in the first validation.

Record available sector-RS context as metadata where point-in-time data is reliable.

Earlier sector-RS evidence was not strong or monotonic enough to justify a hard filter.

Sector strength may later be evaluated as a ranking/tiebreaking feature in a separate hypothesis.

## 21. Event-risk treatment

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

## 22. Overlapping signals and capital constraints

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

## 23. Two validation lenses

Use the same V2 signal set for two complementary analyses.

### A. Setup-quality lens

Purpose: measure whether the new base/contraction entry architecture improves raw post-breakout behavior.

Use:

```text
Entry = next eligible session open
Exit  = next-session execution after Daily Close < SMA20
```

This lens isolates breakout quality as cleanly as practical.

### B. Practical-trading lens

Purpose: measure whether the setup can be traded with realistic structural risk control.

Use:

- the same V2 entry;
- the initial structural stop;
- next-session SMA20 trend exit;
- R-normalized outcomes based on initial risk.

Do not change the signal set between the two lenses.

## 24. Precommitted validation gate

The following gates are locked before observing V2 outcomes.

### Minimum evidence

Require:

```text
Completed trades >= 100
```

If fewer than 100 completed trades exist, classify the result as **insufficient evidence**, not success or failure.

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

### Robustness requirements

Require all of the following:

- positive evidence across at least two materially distinct market periods/episodes where sample size permits;
- after removing the top five positive-P&L winners, profit factor remains `>= 1.0`;
- no single stock explains the strategy's edge;
- no point-in-time/lookahead violations;
- no outcome-driven parameter changes.

Year/episode summaries, leave-one-symbol-out tests and positive-winner outlier diagnostics should be produced as audit outputs.

## 25. Interpretation rules after validation

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

## 26. Streak vs custom research decision

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

Custom research should remain narrow and research-oriented rather than becoming production infrastructure.

## 27. Locked V2 kernel

```text
POINT-IN-TIME NIFTY 500
        ↓
20-session median traded value >= ₹10 crore
        ↓
Close > SMA50 > SMA200
        ↓
Composite_RS >= 70
        ↓
Establish 63-session pivot/high
        ↓
10–30 session base
        ↓
Base depth <= 4 ATR14-at-pivot
        ↓
Final 5-session mean True Range
<= 80% of initial 5-session mean True Range
        ↓
Daily Close breaks active pivot
        ↓
Breakout Close <= Pivot + 1 ATR14
        ↓
Next-session Open remains >= Pivot
and <= Pivot + 1 ATR14
        ↓
ENTRY
        ↓
Structural Stop = final 5-session low - 0.25 ATR14
        ↓
Reject if Entry - Stop > 2.5 ATR14
        ↓
Practical risk normalization at 1% swing-capital risk
        ↓
Hold while trend survives
        ↓
Daily Close < SMA20 → exit next session
```

## 28. Explicitly not part of initial V2

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

## 29. Research handoff after design approval

Once this design document is reviewed and accepted, the next workflow is:

1. create a dedicated GitHub issue for Strategy V2 historical validation;
2. create a mechanical implementation plan under `Swing Trading/docs/superpowers/plans/`;
3. execute the plan inline only;
4. build point-in-time/audit tests before trusting outcomes;
5. produce reproducible trade-level and robustness outputs;
6. return the PR to Portfolio Advisor for research-integrity review and the keep/retire decision.

No implementation or backtest is authorized by this design document alone.
