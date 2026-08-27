# Strategy V3 Design — RS Leader + Shallow Pullback + Resumption

**Status:** Design approved in chat; implementation and validation not started  
**Design date:** 27 August 2026  
**Repository:** `krishna916/Financial`  
**Research family:** New strategy family; T1 remains retired and Strategy V2 remains closed research evidence

## 1. Objective

Strategy V3 tests a materially different entry architecture inside the broader long-only momentum thesis.

The hypothesis is:

> Among point-in-time Nifty 500 stocks that already demonstrate relative-strength leadership and an established uptrend, the first controlled resumption after a shallow multi-session pullback should have better expectancy than buying a fresh resistance breakout.

The research objective is **not** to rescue Strategy V2 and not to optimize its thresholds.

The core sequence is:

```text
Relative-strength leader
→ recent 20-session closing high
→ controlled 3–10 session pullback
→ trend remains intact
→ first simple resumption signal
→ controlled next-session entry
→ structural pullback stop
→ SMA20 trend-following exit
```

The key conceptual change versus V2 is the entry architecture. V2 bought a close above a structural pivot after a base. V3 first identifies an existing leader, then waits through a controlled retracement and attempts to enter the continuation before another full breakout develops.

## 2. Research discipline

Use the same research discipline applied to V2:

> **One hypothesis → one predefined change → test → document → decide → move on.**

Rules:

- Do not tune V3 thresholds after seeing outcomes.
- Do not add breadth, volume, sector-RS, RSI, MACD, ADX, candlestick, or pattern-score gates to rescue a weak result.
- Negative results are valid research outcomes.
- T1 remains retired.
- V2 remains closed evidence and must not be retroactively modified to improve its result.
- All close-derived context used to justify a next-session open entry must be strictly known before the entry.
- Diagnostics may explain results, but diagnostic subgroups must not be promoted into V3 entry filters after outcomes are known.

## 3. Historical universe and data treatment

### Historical validation universe

Use **point-in-time Nifty 500 membership**.

A valid V3 leader seed must occur while the symbol belongs to the point-in-time Nifty 500 on the seed date. A valid resumption signal must also occur while the symbol belongs to the point-in-time Nifty 500 on the signal date.

Do not use today's Nifty 500 membership retrospectively.

Historical OHLCV before index entry may be used to warm moving averages, ATR, rolling highs, and RS lookbacks, but cannot create a valid seed or signal while the symbol is inactive.

### Historical signal window

Use the same primary historical comparison window as V2:

```text
2023-08-01 through 2026-08-25 inclusive
```

The final signal date is 2026-08-25 so an immediately following 2026-08-26 entry bar can be evaluated where data exists.

### Download warmup

Reuse the V2 warmup convention where practical:

```text
Download start: 2022-01-01
Download end:   exclusive 2026-08-27
```

### Corporate-action treatment

Use Yahoo Finance adjusted OHLCV with the same convention as V2:

```text
auto_adjust=True
```

The same adjusted series must be used consistently for:

- Open / High / Low / Close;
- moving averages;
- True Range and ATR;
- leader detection;
- pullback depth;
- entry simulation;
- structural stop;
- exits and returns.

Do not mix adjusted and unadjusted fields in one trade lifecycle.

### ATR

Use **Wilder ATR14**, identical to V2:

- first valid ATR = mean of the first 14 True Range observations;
- subsequent ATR = `(previous_ATR × 13 + current_TR) / 14`.

## 4. Liquidity

Require on both the leader-seed date and resumption-signal date:

```text
20-session median daily traded value >= ₹10 crore
```

This is a hard eligibility rule.

Median traded value remains preferable to raw volume because it is less sensitive to abnormal one-day activity.

## 5. Trend eligibility

Require on both the leader-seed date and resumption-signal date:

```text
Close > SMA50
SMA50 > SMA200
```

During the active pullback, apply one additional structural protection rule:

```text
No daily Close < SMA50
```

A close below SMA50 invalidates the active pullback immediately.

Do not require:

- rising SMA50;
- `SMA20 > SMA50`;
- ADX;
- MACD;
- RSI.

## 6. Relative-strength leadership

Reuse the V2 point-in-time cross-sectional RS framework across the active Nifty 500 universe:

```text
RS21 percentile weight  = 30%
RS63 percentile weight  = 40%
RS126 percentile weight = 30%

Composite_RS =
0.30 × RS21
+ 0.40 × RS63
+ 0.30 × RS126
```

Require on both the leader-seed date and resumption-signal date:

```text
Composite_RS >= 70
```

Interpretation remains diagnostic only:

- `70–79.99`: valid leadership;
- `80–89.99`: preferred leadership;
- `>=90`: exceptional leadership.

Do not introduce a second hard RS threshold during V3 validation.

Use the same per-date RS research-safety rule as V2:

```text
RS coverage >= 80% of the active point-in-time Nifty 500 universe
```

A seed or signal from an unsafe RS date is invalid.

## 7. Leader seed

A date `P` may seed a V3 pullback state when all seed-date eligibility rules pass and:

```text
Close[P] = highest Close over sessions P-19 through P
```

This is a **20-session closing high**. It is evidence of recent momentum leadership; it is **not an entry trigger**.

Store at seed time:

- `Leader_Date = P`;
- `Leader_Close = Close[P]`;
- `ATR14_Seed = ATR14[P]`;
- seed-date RS values;
- seed-date liquidity;
- seed-date trend values.

Only one active V3 pullback is tracked per symbol at a time.

Pullback session 1 is the next trading session after the leader seed.

## 8. Pullback state and age

An active pullback may last from **3 through 10 sessions**.

The state age is defined as:

```text
Pullback_Age = number of trading sessions completed after Leader_Date
```

Therefore:

- leader seed date = age 0;
- immediately following session = age 1;
- earliest valid resumption candidate = age 3;
- latest valid resumption candidate = age 10.

If no resumption candidate occurs by the end of age 10, expire the active pullback.

A later qualifying leader seed may start a new pullback.

## 9. Pullback depth

Measure pullback depth from the original leader close using ATR14 from the original leader-seed date.

Define:

```text
Pullback_Low[t] = lowest Low from pullback session 1 through session t

Pullback_Depth_ATR[t] =
(Leader_Close - Pullback_Low[t]) / ATR14_Seed
```

The denominator never changes during the active pullback.

### Maximum depth

Require throughout the active pullback:

```text
Pullback_Depth_ATR <= 2.5
```

If depth exceeds 2.5 ATR at any time, invalidate the active pullback immediately.

### Minimum depth

A resumption candidate is valid only if the pullback has actually retraced enough to distinguish it from ordinary one-day noise:

```text
Pullback_Depth_ATR >= 0.5
```

This minimum is evaluated when the first resumption trigger occurs.

If a resumption trigger occurs while depth is still below 0.5 ATR, classify the setup as `PULLBACK_TOO_SHALLOW` and end that active pullback. Do not keep waiting for a second resumption trigger from the same leader.

## 10. New leader during an active pullback

V3 is specifically testing a retracement-and-resumption structure rather than another fresh-high breakout.

If during an active pullback:

```text
Close[t] > Leader_Close
```

then the old pullback ends immediately as `NEW_LEADER_CLOSE` and does **not** create a V3 resumption candidate.

After closing the old state, independently test the same bar as a possible new V3 leader seed using the normal 20-session closing-high and seed-eligibility rules.

This same-bar reseeding rule applies after every type of V3 state closure, cancellation, invalidation, or expiry where the closing bar itself qualifies as a fresh leader seed.

## 11. Resumption trigger

The resumption rule is deliberately simple.

During pullback ages 3–10, the **first** session satisfying:

```text
Close[t] > High[t-1]
AND
Close[t] > SMA20[t]
```

creates exactly one resumption candidate from the active pullback.

The trigger means price has closed through the prior session's high and reclaimed/held above the short-term trend reference.

The trigger is evaluated after hard invalidations and the `NEW_LEADER_CLOSE` rule.

### Too-short resumption

If the same technical resumption condition occurs at pullback age 1 or 2, classify the setup as `TOO_SHORT_RESUMPTION` and end the active pullback.

The same bar may independently seed a new leader state if it satisfies all leader-seed rules.

### Candidate does not imply acceptance

Once the first resumption trigger occurs, the active pullback is finished whether the candidate ultimately passes or fails the other signal-date rules.

Do not wait for another resumption trigger from the same leader.

## 12. Resumption-signal eligibility

A resumption candidate becomes a valid V3 signal only if all of the following are true on the signal date:

- point-in-time Nifty 500 membership is active;
- RS coverage is research-safe;
- 20-session median traded value >= ₹10 crore;
- `Close > SMA50 > SMA200`;
- `Composite_RS >= 70`;
- `Pullback_Age` is between 3 and 10 inclusive;
- `0.5 <= Pullback_Depth_ATR <= 2.5`;
- no prior daily close during the active pullback was below SMA50;
- resumption trigger is true;
- `Close <= Leader_Close`.

The final condition preserves the intended distinction from a breakout entry. If the signal-day close is already above the original leader close, it is not a V3 pullback-resumption entry.

## 13. Point-in-time timing rule

No same-session entry is assumed.

All close-derived justification must satisfy:

```text
Context_Date < Entry_Date
```

This applies to:

- point-in-time membership;
- stock RS;
- RS universe coverage;
- liquidity;
- moving averages;
- ATR;
- leader state;
- pullback age/depth;
- resumption trigger;
- market breadth diagnostics;
- any future close-derived V3 feature.

No entry-day close may be used to justify an entry at that day's open.

## 14. Immediate next-session entry

Each qualified V3 signal receives exactly **one automatic entry opportunity**: the open of the immediately following market session.

Do not delay entry to a later session if that immediate opportunity fails.

Require:

```text
Entry_Open >= SMA20_signal
```

and:

```text
Entry_Open <= Leader_Close + 0.5 × ATR14_signal
```

where `SMA20_signal` and `ATR14_signal` are known from the completed resumption-signal bar.

Cancellation reasons must distinguish at minimum:

- `MISSING_NEXT_SESSION`;
- `MISSING_NEXT_SESSION_BAR`;
- `OPEN_BELOW_SMA20_SIGNAL`;
- `OPEN_ABOVE_EXTENSION_LIMIT`;
- structural-stop rejection reasons defined below.

There is no later rescue entry from the same pullback.

## 15. Structural stop

The V3 practical stop is anchored to the actual pullback structure.

Define on the resumption signal date:

```text
Structural_Stop =
lowest Low from pullback session 1 through the resumption-signal session, inclusive
- 0.25 × ATR14_signal
```

Including the resumption bar makes the definition deterministic and ensures the complete known pullback/resumption structure is respected.

Reject the trade before entry if:

```text
Structural_Stop >= Entry_Open
```

Also reject if:

```text
Entry_Open - Structural_Stop > 2.5 × ATR14_signal
```

Do not artificially tighten the stop to make the setup pass.

## 16. Position sizing assumption

For eventual live use:

```text
Planned portfolio risk per trade = 1% of dedicated swing capital
```

Quantity would be:

```text
Position_Quantity =
Portfolio_Risk_Amount / (Entry_Open - Structural_Stop)
```

Confidence does not override the risk budget.

Position sizing and a 3–5-position capital-capacity simulation are **not** part of the first V3 signal-level edge test. They may be evaluated only if signal-level V3 demonstrates sufficient edge.

## 17. Exit lenses

Reuse the V2 exit architecture to isolate the change to the entry family.

### Lens A — setup quality

Ignore the structural stop.

Generate an exit signal when:

```text
Close < SMA20
```

Exit at the immediately following trading session open.

This lens measures whether the V3 entry itself captures favorable continuation without stop-shape effects.

### Lens B — practical trading

Use the fixed V3 structural stop plus the same SMA20 trend exit.

For each session while open, use this precedence:

1. If a prior close generated the SMA20 exit signal, exit at the current session Open before any intraday stop logic.
2. Otherwise, if `Open <= Structural_Stop`, exit at that Open to model a gap through the stop.
3. Otherwise, if `Low <= Structural_Stop`, exit at `Structural_Stop`.
4. Otherwise, if `Close < SMA20`, schedule an exit for the next session Open.
5. Otherwise remain open.

No target, breakeven rule, or hard time stop is introduced in the initial V3 validation.

## 18. Outcome definitions

### Setup-quality lens

```text
Return = (Exit_Price - Entry_Open) / Entry_Open
```

Return profit factor:

```text
sum positive trade returns / absolute sum negative trade returns
```

### Practical lens

```text
Initial_Risk = Entry_Open - Structural_Stop

R_Multiple =
(Exit_Price - Entry_Open) / Initial_Risk
```

R profit factor:

```text
sum positive R multiples / absolute sum negative R multiples
```

Adverse gaps may produce realized losses worse than `-1R`.

## 19. Breadth treatment

Do **not** use market breadth as a V3 entry gate.

Attach the existing point-in-time Nifty 500 breadth regime using the latest available breadth row strictly before entry:

```text
Breadth_Context_Date < Entry_Date
```

Breadth remains diagnostic only.

In particular, do not test a HOSTILE exclusion as part of the primary V3 run. V2 did not demonstrate sufficient standalone entry quality to justify treating breadth as the next rescue mechanism.

## 20. Volume treatment

Do **not** use volume as a hard V3 gate.

Record diagnostic metadata such as:

```text
Resumption_Volume_Ratio =
Resumption_Volume / 20-session median Volume
```

Do not promote an observed favorable volume subgroup into V3 after results are known.

## 21. Diagnostics

Record continuous raw variables so behavior can be understood without creating post-result filters.

At minimum summarize results by:

- pullback duration;
- pullback-depth bands;
- Composite RS bands (`70–79.99`, `80–89.99`, `>=90`);
- breadth regime;
- resumption volume ratio bands;
- entry extension relative to Leader_Close and ATR;
- holding duration;
- exit reason.

These are explanatory diagnostics only.

## 22. State-machine ordering

For each symbol and each new session while a V3 pullback is active, apply this deterministic order:

1. Increment `Pullback_Age`.
2. Add the current session to the pullback window and update `Pullback_Low`.
3. Recalculate `Pullback_Depth_ATR` using the original `ATR14_Seed`.
4. If the current Close is below SMA50, close as `SMA50_INVALIDATED`.
5. Else if depth exceeds 2.5 ATR, close as `DEPTH_INVALIDATED`.
6. Else if `Close > Leader_Close`, close as `NEW_LEADER_CLOSE`; do not create a V3 candidate from the old state.
7. Else evaluate the resumption condition `Close > prior session High AND Close > SMA20`.
8. If resumption occurs at age 1–2, close as `TOO_SHORT_RESUMPTION`.
9. If resumption occurs at age 3–10, create exactly one candidate; evaluate minimum-depth and all signal-date gates; close the active state regardless of acceptance.
10. If no resumption occurred and age reaches 10, close as `EXPIRED`.
11. After **any** state close/cancel/invalidation above, independently test the same bar as a possible new leader seed. If all seed rules pass, create a fresh state with age 0; its pullback session 1 begins on the following market session.

This ordering is locked before historical outcomes are observed.

## 23. Candidate and entry accounting

Keep the research accounting explicit:

```text
All resumption candidates
→ qualified signals
→ accepted next-session entries
   + entry cancellations
→ completed setup/practical outcomes
   + accepted entries still incomplete at observation end
```

Require:

```text
Qualified_Signals = Accepted_Entries + Entry_Cancellations
```

Every accepted entry must reference exactly one qualified signal.

Setup-quality and practical completed outcomes must use the same completed `Entry_ID` set.

Incomplete accepted positions must remain visible in entry/overlap diagnostics rather than disappearing from accepted-entry counts.

## 24. Overlap diagnostic

The initial V3 question is signal-level edge, not constrained portfolio performance.

Do not suppress otherwise valid signals because capital would have been occupied by another signal.

Still calculate overlap over **all accepted entries**, including incomplete positions through the observation end:

- total accepted entries;
- entries overlapping another open trade in the same symbol;
- maximum simultaneous signal-level trades;
- maximum same-day accepted entries.

If V3 passes signal-level validation, portfolio-capacity constraints can be tested separately.

## 25. Point-in-time integrity audit

The final validation must derive integrity from actual artifacts; it must not default to zero.

Audit at minimum:

- accepted entry has a qualified V3 signal;
- leader seed date precedes resumption signal date;
- resumption signal date strictly precedes entry date;
- leader seed and signal dates are inside the historical research window where required;
- seed and signal occur while the symbol is an active point-in-time Nifty 500 member;
- RS coverage is research-safe on seed and signal dates;
- seed and signal `Composite_RS >= 70`;
- breadth diagnostic date is strictly before entry;
- accepted entry is the immediate next market session after the signal;
- setup/practical completed `Entry_ID` sets match.

Any non-zero integrity violation count must abort profitability interpretation and produce an explicit audit artifact.

## 26. Precommitted validation gates

Reuse the V2 gates so the standard is not weakened after V2's negative result.

### Sample sufficiency

```text
Completed paired trades >= 100
```

If completed trades are below 100, formal final status is:

```text
INSUFFICIENT_EVIDENCE
```

This does not require describing strongly negative observed metrics as neutral.

### Setup-quality expectancy

Require:

```text
Setup mean return > 0
Setup Return PF >= 1.20
```

### Practical expectancy

Require:

```text
Practical mean >= +0.15R per trade
Practical R PF >= 1.20
```

### Temporal robustness

A calendar year qualifies only if it contains at least 20 completed paired trades and:

```text
Setup mean return > 0
Setup Return PF >= 1.0
```

Require at least **two qualifying calendar years**.

Do not add a practical-R requirement to the per-year temporal gate.

### Winner-removal robustness

Remove the top 1, top 3, and top 5 setup-quality winners by return.

For the top-5 removal test require the remaining sample to satisfy:

```text
Setup mean return > 0
Setup Return PF >= 1.0
```

### Leave-one-symbol-out robustness

For every symbol represented among completed accepted entries, remove all completed entries from that symbol and recompute setup metrics.

Every leave-one-symbol-out sample must satisfy:

```text
Setup mean return > 0
Setup Return PF >= 1.0
```

### Point-in-time integrity

Require:

```text
PIT violations = 0
```

### Final decision

If completed trades >=100:

```text
PASS only if every precommitted gate passes
otherwise FAIL
```

If completed trades <100:

```text
INSUFFICIENT_EVIDENCE
```

## 27. Required historical outputs

Use a dedicated research directory, suggested:

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/
```

and write generated evidence under:

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/output/
```

At minimum produce:

- `v3_data_validation.csv`;
- `v3_universe_rs_audit.csv`;
- `v3_pullback_state_audit.csv`;
- `v3_signal_candidates.csv`;
- `v3_entries.csv`;
- `v3_entry_cancellations.csv`;
- `v3_setup_quality_trades.csv`;
- `v3_practical_trades.csv`;
- `v3_validation_summary.csv`;
- `v3_year_summary.csv`;
- `v3_outlier_robustness.csv`;
- `v3_leave_one_symbol_out.csv`;
- `v3_breadth_summary.csv`;
- `v3_pullback_diagnostics.csv`;
- `v3_overlap_diagnostic.csv`;
- `v3_validation_gates.csv`;
- `research_report.md`;
- `v3_point_in_time_violations.csv` only if violations exist.

The research report must present evidence and methodology only. It must not tune thresholds or prescribe post-result rescue changes.

## 28. Reuse versus new implementation

Reuse proven V2 infrastructure where semantics are identical:

- point-in-time Nifty 500 membership loading;
- adjusted Yahoo OHLCV convention;
- price features and Wilder ATR14;
- point-in-time cross-sectional RS ranking and 80% coverage safety;
- liquidity calculation;
- immediate-next-session market-session handling;
- setup-quality and practical SMA20 exit simulators where compatible;
- breadth strict-prior join;
- safe profit-factor calculation;
- year summary, outlier robustness, LOSO, overlap, and gate patterns where semantics remain unchanged.

Do **not** mutate V2 outputs or V2 research code in a way that changes its historical evidence.

V3 should have its own state machine, signal artifacts, tests, and outputs.

## 29. Required regression tests

Implementation must include deterministic tests covering at minimum:

1. 20-session closing-high leader seed.
2. Seed requires PIT membership, safe RS coverage, liquidity, trend, and `Composite_RS >=70`.
3. Pullback age starts at 1 on the session after the leader.
4. Depth uses `Leader_Close`, running lowest Low, and original `ATR14_Seed`.
5. Depth >2.5 ATR invalidates immediately.
6. Close below SMA50 invalidates immediately.
7. Resumption at age 1–2 is too short and closes the state.
8. Resumption at age 3 is valid timing.
9. Resumption at age 10 is valid timing.
10. No resumption by age 10 expires the state.
11. Resumption trigger is exactly `Close > previous High AND Close > SMA20`.
12. First resumption ends the pullback even if minimum depth or another signal gate fails.
13. Minimum depth <0.5 ATR rejects as `PULLBACK_TOO_SHALLOW`.
14. `Close > Leader_Close` ends old state without a V3 candidate.
15. Same-bar reseeding works after invalidation, too-short resumption, new leader close, candidate closure, and expiry when the bar qualifies.
16. Qualified signal requires `Close <= Leader_Close`.
17. Entry is only the immediate next market session.
18. Missing immediate symbol bar cancels rather than delays.
19. Entry open below `SMA20_signal` cancels.
20. Entry open above `Leader_Close + 0.5 ATR14_signal` cancels.
21. Structural stop uses the lowest Low through the resumption signal session inclusive minus `0.25 ATR14_signal`.
22. Structural stop not below entry cancels.
23. Stop distance >2.5 ATR14_signal cancels.
24. Setup-quality SMA20 exit occurs at the next open.
25. Practical prior-close SMA20 scheduled exit precedes same-day stop checks.
26. Practical gap stop and intraday stop behavior.
27. Breadth context is strictly prior to entry.
28. PIT audit detects same-day/same-entry-date leakage.
29. Setup/practical completed `Entry_ID` mismatch is detected.
30. Overlap counts all accepted entries, including incomplete ones.
31. Temporal gate uses only the locked setup-quality year conditions.
32. Final status is `INSUFFICIENT_EVIDENCE` below 100 completed paired trades.

## 30. What V3 deliberately does not test

Do not add any of the following to the initial V3 kernel:

- HOSTILE breadth exclusion;
- STRONG-only breadth requirement;
- sector-RS gate;
- breakout-volume requirement;
- low-volume pullback requirement;
- RSI threshold;
- MACD crossover;
- ADX threshold;
- candlestick pattern scoring;
- higher-low count;
- Fibonacci retracement bands;
- exact support-line geometry;
- earnings/news hindsight filters;
- profit target;
- automatic breakeven stop;
- trailing ATR stop;
- hard time exit;
- 3–5 position capital constraint;
- outcome-driven tuning of pullback duration/depth/RS thresholds.

Each is a separate future hypothesis only if the evidence justifies testing it.

## 31. Research interpretation after the run

The first question after V3 is not “which threshold would make it win?”

Interpret results in this order:

1. Did the entry family demonstrate positive raw setup expectancy?
2. Did the structural stop preserve or destroy that edge?
3. Is the result robust across years and symbols?
4. Is performance dominated by a handful of winners?
5. Do diagnostics reveal a plausible market-behavior explanation without being used as a retroactive filter?
6. Does the evidence justify continuing this strategy family at all?

If V3 fails materially, do not rescue it by narrowing to the best observed pullback-depth, duration, RS, or breadth subgroup.

If V3 passes, the next isolated research stage may evaluate portfolio capacity and/or one predeclared contextual filter, but only after the base V3 edge is established.
