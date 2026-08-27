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

The key change versus V2 is entry architecture. V2 bought a close above a structural pivot after a base. V3 identifies an existing leader, waits through a controlled retracement, and attempts to enter continuation before another full breakout develops.

## 2. Research discipline

Use the same discipline applied to V2:

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

Do not apply today's Nifty 500 membership retrospectively.

Historical OHLCV before index entry may warm moving averages, ATR, rolling highs and RS lookbacks, but cannot create a valid seed or signal while the symbol is inactive.

### Primary signal window

Use the same primary comparison window as V2:

```text
Resumption Signal_Date: 2023-08-01 through 2026-08-25 inclusive
```

Only **resumption signal dates** are constrained by this primary window.

A leader seed may occur up to 10 trading sessions before 2023-08-01 so that a pullback already in progress can generate a fair in-window signal. Such a pre-window seed is valid only if all normal seed-date PIT membership, RS-safety, liquidity, trend and RS rules are satisfied from information genuinely available on that seed date.

No trade is counted unless its V3 resumption signal date is inside the primary signal window.

The final signal date is 2026-08-25 so an immediately following 2026-08-26 entry bar can be evaluated where data exists.

### Download warmup

Reuse the V2 convention where practical:

```text
Download start: 2022-01-01
Download end:   exclusive 2026-08-27
```

### Corporate-action treatment

Use Yahoo Finance adjusted OHLCV with:

```text
auto_adjust=True
```

Use the same adjusted series consistently for Open/High/Low/Close, moving averages, True Range/ATR, leader detection, pullback depth, entry, stop, exits and returns.

Do not mix adjusted and unadjusted fields in one trade lifecycle.

### ATR

Use **Wilder ATR14**, identical to V2:

- first valid ATR = mean of the first 14 True Range observations;
- subsequent ATR = `(previous_ATR × 13 + current_TR) / 14`.

## 4. Liquidity

Require on both leader-seed and resumption-signal dates:

```text
20-session median daily traded value >= ₹10 crore
```

This is a hard eligibility rule.

## 5. Trend eligibility

Require on both leader-seed and resumption-signal dates:

```text
Close > SMA50
SMA50 > SMA200
```

During an active pullback:

```text
No daily Close < SMA50
```

A close below SMA50 invalidates the active pullback immediately.

Do not require rising SMA50, `SMA20 > SMA50`, ADX, MACD or RSI.

## 6. Relative-strength leadership

Reuse V2's point-in-time cross-sectional RS framework across the active Nifty 500 universe:

```text
Composite_RS = 0.30 × RS21 + 0.40 × RS63 + 0.30 × RS126
```

Require on both leader-seed and resumption-signal dates:

```text
Composite_RS >= 70
```

RS bands remain diagnostic only:

- `70–79.99`: valid;
- `80–89.99`: preferred;
- `>=90`: exceptional.

Use the V2 research-safety rule:

```text
RS coverage >= 80% of the active PIT Nifty 500 universe
```

A seed or signal from an unsafe RS date is invalid.

## 7. Leader seed

A date `P` may seed a V3 pullback when all seed-date eligibility rules pass and:

```text
Close[P] = highest Close over sessions P-19 through P
```

This is a 20-session closing high. Equality is intentional; the rule is not changed to a strict new-high comparison after outcomes are seen.

The seed is evidence of prior leadership, **not an entry**.

Store:

- `Leader_Date = P`;
- `Leader_Close = Close[P]`;
- `ATR14_Seed = ATR14[P]`;
- seed-date RS values and coverage;
- seed-date liquidity;
- seed-date trend values.

Only one active V3 pullback is tracked per symbol. Pullback session 1 is the next trading session after `Leader_Date`.

## 8. Pullback age

```text
Pullback_Age = number of trading sessions completed after Leader_Date
```

Therefore:

- seed date = age 0;
- next session = age 1;
- earliest valid resumption = age 3;
- latest valid resumption = age 10.

If no resumption candidate occurs by the end of age 10, expire the state.

## 9. Pullback depth

Define:

```text
Pullback_Low[t] = lowest Low from pullback session 1 through t

Pullback_Depth_ATR[t] =
(Leader_Close - Pullback_Low[t]) / ATR14_Seed
```

`ATR14_Seed` never changes during the active pullback.

### Maximum depth

Require throughout:

```text
Pullback_Depth_ATR <= 2.5
```

A breach invalidates immediately.

### Minimum depth

At the first resumption trigger require:

```text
Pullback_Depth_ATR >= 0.5
```

If the first resumption trigger occurs below 0.5 ATR depth, classify `PULLBACK_TOO_SHALLOW`, close the state and do not wait for another trigger from the same leader.

## 10. New leader during a pullback

If:

```text
Close[t] > Leader_Close
```

close the old state as `NEW_LEADER_CLOSE` and do **not** create a V3 resumption candidate from it.

After closing, independently test the same bar as a possible new leader seed using the normal seed rules.

## 11. Resumption trigger

The trigger is deliberately simple:

```text
Close[t] > High[t-1]
AND
Close[t] > SMA20[t]
```

The first such session is the only resumption attempt from the active leader state.

### Too-short resumption

If the condition occurs at age 1 or 2, classify `TOO_SHORT_RESUMPTION`, close the state, and independently test the same bar for a new leader seed.

### Valid timing

If it occurs at age 3–10, create exactly one resumption candidate. The active state closes whether the candidate later passes or fails signal-date gates.

Do not wait for a second resumption trigger.

## 12. Resumption-signal eligibility

A candidate becomes a qualified V3 signal only if all are true on the signal date:

- active PIT Nifty 500 membership;
- RS coverage research-safe;
- 20-session median traded value >= ₹10 crore;
- `Close > SMA50 > SMA200`;
- `Composite_RS >= 70`;
- `Pullback_Age` 3–10 inclusive;
- `0.5 <= Pullback_Depth_ATR <= 2.5`;
- no earlier close in this active pullback below SMA50;
- resumption trigger is true;
- `Close <= Leader_Close`.

`Close <= Leader_Close` preserves the distinction from a fresh-high breakout entry.

## 13. Point-in-time timing

No same-session entry is assumed.

All close-derived context must satisfy:

```text
Context_Date < Entry_Date
```

This includes membership, RS, RS coverage, liquidity, moving averages, ATR, leader state, pullback state, resumption trigger, breadth and any future daily close-derived field.

No entry-day close may justify an entry at that day's open.

## 14. Immediate next-session entry

Each qualified signal gets exactly one automatic opportunity: the **immediately following market-session Open**.

Require:

```text
Entry_Open >= SMA20_signal
```

and:

```text
Entry_Open <= Leader_Close + 0.5 × ATR14_signal
```

where signal-day SMA20 and ATR14 are fully known before entry.

Cancellation reasons must distinguish at minimum:

- `MISSING_NEXT_SESSION`;
- `MISSING_NEXT_SESSION_BAR`;
- `OPEN_BELOW_SMA20_SIGNAL`;
- `OPEN_ABOVE_EXTENSION_LIMIT`;
- structural-stop rejection reasons.

Do not delay or rescue the same signal on a later session.

## 15. Structural stop

On the resumption signal date define:

```text
Structural_Stop =
lowest Low from pullback session 1 through the resumption-signal session, inclusive
- 0.25 × ATR14_signal
```

Reject before entry if:

```text
Structural_Stop >= Entry_Open
```

or:

```text
Entry_Open - Structural_Stop > 2.5 × ATR14_signal
```

Do not tighten the stop artificially to make a trade pass.

## 16. Position sizing assumption

For eventual live deployment:

```text
Planned portfolio risk per trade = 1% of dedicated swing capital
```

```text
Position_Quantity =
Portfolio_Risk_Amount / (Entry_Open - Structural_Stop)
```

Position sizing and 3–5-position capital constraints are not part of this first signal-level V3 edge test.

## 17. Exit lenses

Reuse V2's exit architecture so V3 primarily changes the entry family.

### Lens A — setup quality

Ignore the structural stop.

```text
Close < SMA20 → exit at immediately following trading-session Open
```

### Lens B — practical trading

Use the fixed structural stop plus the same SMA20 trend exit.

Per open position, precedence is:

1. prior-close SMA20 exit signal → current Open exit first;
2. otherwise `Open <= Structural_Stop` → exit at Open;
3. otherwise `Low <= Structural_Stop` → exit at Structural_Stop;
4. otherwise `Close < SMA20` → schedule next-session Open exit;
5. otherwise remain open.

No fixed profit target, breakeven rule, trailing ATR stop or hard time stop is introduced.

## 18. Outcomes

### Setup-quality lens

```text
Return = (Exit_Price - Entry_Open) / Entry_Open
```

Return PF = sum positive returns / absolute sum negative returns.

### Practical lens

```text
Initial_Risk = Entry_Open - Structural_Stop
R_Multiple = (Exit_Price - Entry_Open) / Initial_Risk
```

R PF = sum positive R multiples / absolute sum negative R multiples.

Gap losses may be worse than `-1R`.

## 19. Breadth

Breadth is **diagnostic only**.

Attach the latest available existing Nifty 500 breadth row strictly before entry:

```text
Breadth_Context_Date < Entry_Date
```

Do not test HOSTILE exclusion or STRONG-only entry as part of primary V3.

## 20. Volume

Volume is **diagnostic only**.

Record, where available:

```text
Resumption_Volume_Ratio =
Resumption_Volume / 20-session median Volume
```

Do not promote an observed favorable volume subgroup into V3 after results are known.

## 21. Diagnostics

At minimum retain/summarize:

- pullback duration;
- pullback depth;
- RS band;
- breadth regime;
- resumption-volume ratio;
- entry extension versus `Leader_Close` and ATR;
- holding duration;
- exit reason.

Diagnostic subgroup results are explanatory only.

## 22. Locked state-machine ordering

For each active symbol/session:

1. Increment `Pullback_Age`.
2. Add current bar to the pullback window and update `Pullback_Low`.
3. Recalculate depth using original `ATR14_Seed`.
4. If `Close < SMA50`, close as `SMA50_INVALIDATED`.
5. Else if depth >2.5 ATR, close as `DEPTH_INVALIDATED`.
6. Else if `Close > Leader_Close`, close as `NEW_LEADER_CLOSE`; no candidate from old state.
7. Else evaluate `Close > prior High AND Close > SMA20`.
8. If resumption occurs at age 1–2, close as `TOO_SHORT_RESUMPTION`.
9. If resumption occurs at age 3–10, create exactly one candidate, evaluate minimum depth and signal gates, then close the state regardless of acceptance.
10. If no resumption occurred and age reaches 10, close as `EXPIRED`.
11. After **any** state closure/invalidation/expiry above, independently test the same bar as a new leader seed. If eligible, create a fresh age-0 state whose session 1 begins on the following market session.

This ordering is frozen before historical outcomes are observed.

## 23. Accounting

Track explicitly:

```text
All resumption candidates
→ qualified signals
→ accepted entries + entry cancellations
→ completed paired outcomes + incomplete accepted entries
```

Require:

```text
Qualified_Signals = Accepted_Entries + Entry_Cancellations
```

Every accepted entry must reference one qualified signal.

Setup-quality and practical completed outcomes must use the same completed `Entry_ID` set.

Incomplete accepted entries remain visible in entry and overlap diagnostics.

## 24. Overlap

The first question is individual-signal edge, not constrained portfolio performance.

Do not suppress otherwise valid entries due to capital occupancy.

Calculate overlap across **all accepted entries**, including incomplete positions through observation end:

- total accepted entries;
- entries overlapping another open trade in the same symbol;
- maximum simultaneous signal-level trades;
- maximum same-day entries.

## 25. PIT integrity audit

The final result must derive PIT integrity from actual artifacts; it must never default to zero.

Audit at minimum:

- accepted entry has a qualified V3 signal;
- `Leader_Date < Signal_Date < Entry_Date`;
- every counted resumption `Signal_Date` is within 2023-08-01 through 2026-08-25 inclusive;
- a pre-window leader seed is at most 10 market sessions before 2023-08-01 and satisfies all normal PIT seed rules;
- seed and signal are active PIT Nifty 500 members;
- seed and signal have research-safe RS coverage;
- seed and signal have `Composite_RS >=70`;
- accepted entry is the immediate next market session after signal;
- breadth context is strictly before entry;
- setup/practical completed Entry_ID sets match.

Any non-zero PIT violation count must create an explicit audit artifact and abort profitability interpretation.

## 26. Precommitted validation gates

Reuse V2's main gates.

### Sample sufficiency

```text
Completed paired trades >=100
```

Below 100, final formal status is `INSUFFICIENT_EVIDENCE`. Strongly negative observed evidence should still be described as negative rather than neutral.

### Setup edge

```text
Setup mean return >0
Setup Return PF >=1.20
```

### Practical edge

```text
Practical mean >= +0.15R/trade
Practical R PF >=1.20
```

### Temporal robustness

A calendar year qualifies only with >=20 completed paired trades and:

```text
Setup mean return >0
Setup Return PF >=1.0
```

Require >=2 qualifying years.

Do **not** add Practical_Mean_R to the year qualification rule.

### Winner-removal robustness

Remove top 1/3/5 setup winners. After top-5 removal require:

```text
Setup mean return >0
Setup Return PF >=1.0
```

### Leave-one-symbol-out

For every represented symbol, remove all its completed entries. Every remaining sample must satisfy:

```text
Setup mean return >0
Setup Return PF >=1.0
```

### PIT integrity

```text
PIT violations = 0
```

### Final status

If completed paired trades >=100: `PASS` only if every gate passes, else `FAIL`.

If completed paired trades <100: `INSUFFICIENT_EVIDENCE`.

## 27. Required outputs

Use:

```text
Swing Trading/research/swing/strategy_v3_shallow_pullback/
Swing Trading/research/swing/strategy_v3_shallow_pullback/output/
```

At minimum generate:

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
- `v3_point_in_time_violations.csv` only when violations exist.

The report is evidence-only and must not prescribe post-result threshold tuning.

## 28. Reuse versus new code

Reuse proven V2 infrastructure where semantics are identical:

- PIT Nifty 500 membership;
- adjusted Yahoo OHLCV;
- price features/Wilder ATR14;
- PIT cross-sectional RS and 80% coverage safety;
- median traded-value liquidity;
- immediate-next-session market-session handling;
- SMA20 exit simulation where compatible;
- strict-prior breadth join;
- profit-factor calculation;
- year/outlier/LOSO/overlap/gate patterns where semantics remain unchanged.

Do not alter V2 evidence.

V3 gets its own state machine, signal artifacts, tests and outputs.

## 29. Required regression coverage

Implementation must deterministically test at minimum:

1. 20-session closing-high leader seed.
2. Seed PIT membership, safe RS coverage, liquidity, trend and `Composite_RS >=70`.
3. Age 1 starts on the session after seed.
4. Depth uses `Leader_Close`, running lowest Low and original `ATR14_Seed`.
5. >2.5 ATR depth invalidation.
6. Close below SMA50 invalidation.
7. Age-1/2 resumption is too short.
8. Age-3 resumption is valid timing.
9. Age-10 resumption is valid timing.
10. No resumption by age 10 expires.
11. Trigger is exactly `Close > previous High AND Close > SMA20`.
12. First trigger closes state even when another signal gate fails.
13. <0.5 ATR depth rejects `PULLBACK_TOO_SHALLOW`.
14. `Close > Leader_Close` closes old state without candidate.
15. Same-bar reseeding after every closure type when eligible.
16. Qualified signal requires `Close <= Leader_Close`.
17. Immediate-next-market-session entry only.
18. Missing immediate symbol bar cancels instead of delaying.
19. Open below `SMA20_signal` cancellation.
20. Open above `Leader_Close + 0.5 ATR14_signal` cancellation.
21. Stop uses lowest Low through signal bar inclusive minus `0.25 ATR14_signal`.
22. Stop not below entry cancellation.
23. Stop distance >2.5 ATR cancellation.
24. Setup SMA20 next-open exit.
25. Practical prior-close SMA20 exit precedence.
26. Practical gap/intraday stop behavior.
27. Strict-prior breadth.
28. PIT audit catches timing leakage.
29. Lens Entry_ID mismatch detection.
30. Overlap includes incomplete accepted entries.
31. Temporal gate uses only locked setup-year conditions.
32. Final status is `INSUFFICIENT_EVIDENCE` below 100 completed paired trades.
33. A seed up to 10 market sessions before 2023-08-01 can generate an in-window signal, while an out-of-window signal is excluded.

## 30. Deliberately excluded from initial V3

Do not add:

- HOSTILE breadth exclusion;
- STRONG-only breadth requirement;
- sector-RS gate;
- breakout-volume gate;
- low-volume-pullback gate;
- RSI/MACD/ADX;
- candlestick scoring;
- higher-low count;
- Fibonacci bands;
- exact support-line geometry;
- hindsight earnings/news filters;
- profit target;
- breakeven move;
- trailing ATR stop;
- hard time exit;
- 3–5 position cap;
- outcome-driven tuning of pullback duration/depth/RS thresholds.

Each is a separate future hypothesis only if evidence later justifies testing it.

## 31. Interpretation after the run

Interpret in this order:

1. Did V3 show positive raw setup expectancy?
2. Did the practical structural stop preserve or destroy that edge?
3. Is performance robust across years and symbols?
4. Is performance dominated by a few winners?
5. Do diagnostics suggest a plausible market-behavior explanation without becoming retroactive filters?
6. Does evidence justify continuing this strategy family?

If V3 fails materially, do not rescue it by narrowing to the best observed pullback-depth, duration, RS, breadth or volume subgroup.

If V3 passes, portfolio capacity and any contextual filter must be separate, predeclared research stages.
