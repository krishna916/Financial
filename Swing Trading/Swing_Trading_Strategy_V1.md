# Swing Trading Strategy V1

**Status:** Strategy design finalized; historical validation/backtesting and forward validation still pending  
**Version date:** 25 August 2026  
**Primary objective:** Rotate a separate pool of working capital through high-quality swing opportunities and capture price moves typically in the ~2%–20% range, while controlling downside and avoiding forced trades.

---

## 1. Purpose and Philosophy

This is a **long-only cash-market swing trading system** for Indian equities. It is designed around:

- capital rotation rather than buy-and-hold;
- mostly end-of-day analysis and next-session execution;
- a small number of high-quality positions;
- momentum/relative-strength leadership;
- defined invalidation before entry;
- disciplined exits;
- willingness to remain fully or partially in cash;
- avoiding conversion of failed trades into long-term investments.

The strategy is **not** intended to maximize trading frequency. Quality takes priority, but filters should not be so restrictive that legitimate opportunities are missed.

The expected holding period is normally **1 day to ~3 weeks**, with an outer horizon of roughly **3 months** in unusual cases. A trade may be exited much earlier if its thesis fails or capital can be rotated into a materially better opportunity.

A 2%–20% move is an **expected swing range, not a mandatory profit target or ceiling**. Exceptional winners may be held longer while their trend remains healthy.

---

# 2. Operating Constraints

| Parameter | Rule |
|---|---|
| Market | NSE/BSE |
| Instruments | Cash equities; ETFs may be used mainly as fallback opportunities |
| F&O / leverage | Strictly excluded |
| Direction | Long-only |
| Intraday | Allowed only occasionally; strategy must not depend on intraday monitoring |
| Normal analysis | End of day |
| Execution | Manual by user |
| Monitoring availability | Minimal during market hours |
| Initial capital | Approximately ₹20,000; final working-capital amount may change |
| Capital pool | Completely separate swing-trading capital |
| Initial positions | Normally 3–5 maximum |
| Preferred holding period | Mostly completed within ~3 weeks |
| Hard/outer horizon | Approximately 3 months, subject to trade review |
| Cash | Fully acceptable when no qualifying setup exists |

**No trade quota exists. Zero trades is a valid outcome.**

---

# 3. Core Setups

Only two setups are part of V1.

## Setup A — Momentum / Breakout

Primary strategy.

Look for:

> Strong stock + strong relative strength + supportive sector + established uptrend + quality consolidation/base + meaningful breakout + acceptable entry economics.

Typical opportunity:

**Prior advance → consolidation/base → breakout → momentum continuation**

## Setup B — Trend Pullback

Secondary strategy.

Look for:

> Strong stock already in an established uptrend temporarily pulling back toward meaningful support, then showing renewed buyer confirmation.

Typical opportunity:

**Strong trend/breakout → orderly pullback → support → stabilization → renewed demand**

### Explicitly excluded from V1

- bottom fishing;
- falling-knife reversals;
- mean-reversion systems;
- RSI oversold trades;
- speculative microcap momentum;
- random candlestick-pattern trading;
- averaging down losing swing trades.

---

# 4. Trading Universe

## Core universe

**Nifty 500**

This provides the primary opportunity set.

## Additional stocks

Quality small-cap names outside the Nifty 500 may be included **only through a manual whitelist**.

### Exclusions

- microcaps;
- SME stocks;
- illiquid securities;
- active GSM / ASM / ESM names;
- trade-to-trade or other materially restricted securities;
- suspended/problematic securities;
- stocks failing governance/fundamental sanity checks.

---

# 5. Liquidity Rules

Liquidity is measured using **median traded value**, not raw share volume.

### Nifty 500 stocks

**20-session median daily traded value ≥ ₹10 crore**

### Manually whitelisted smallcaps

**20-session median daily traded value ≥ ₹20 crore**

Median is preferred over average so that one abnormal high-volume day does not make an otherwise illiquid stock appear liquid.

No arbitrary minimum share price is required.

---

# 6. Fundamental and Governance Safety Filter

The strategy is technical-first, but every serious candidate must pass a **basic fundamental/governance sanity check** before becoming actionable.

The purpose is not to decide whether the company is a 10-year investment. It is to avoid technically attractive stocks with obvious structural or governance risks.

Check for:

- severe leverage or solvency concerns appropriate to the industry;
- persistent major operating deterioration;
- significant promoter/governance concerns;
- auditor resignations or accounting red flags;
- major pledge issues where relevant;
- insolvency/restructuring concerns;
- repeated concerning dilution;
- major regulatory/legal problems;
- materially negative exchange disclosures;
- unusual price action driven predominantly by speculation.

**High valuation alone is not a reason to reject a swing trade.**

---

# 7. News and Event Review

Before an actionable signal, review relevant current information such as:

- quarterly results;
- board meetings/result dates;
- material exchange disclosures;
- large orders/contracts;
- regulatory decisions;
- promoter transactions;
- block/bulk deals where relevant;
- corporate actions;
- auditor/governance developments;
- significant litigation;
- material upgrades/downgrades or industry news;
- any catalyst explaining unusual price/volume behaviour.

Holding through earnings or major events is judged **case by case**.

For an ordinary momentum trade without a substantial profit cushion, reducing event risk is generally preferred.

---

# 8. Market Regime

The strategy uses an **adaptive regime**, not a strict market-on/market-off filter.

## Risk-On

Characteristics:

- healthy broad-market trend;
- good breadth;
- multiple sectors participating;
- breakouts generally working.

Implications:

- normal risk per trade;
- breakout and pullback setups allowed;
- portfolio may hold normal number of positions.

## Mixed / Selective

Characteristics:

- headline index may be healthy but breadth/sector participation is mixed;
- leadership concentrated in fewer areas.

Implications:

- prioritize A/A+ setups;
- fewer concurrent positions;
- sector and stock relative strength carry more weight.

## Risk-Off

Characteristics:

- weak breadth;
- broad selling;
- repeated breakout failures;
- deteriorating sector participation.

Implications:

- mostly cash;
- only exceptional stock/sector setups considered;
- reduced exposure and tighter selectivity.

Market regime is a **context modifier**, not an automatic binary veto.

---

# 9. Sector and Relative-Strength Framework

The system evaluates:

> Market → Sector → Industry/Theme where relevant → Stock

Relative strength is used to find where capital is flowing rather than simply identifying stocks that have risen.

## Stock RS percentile

For the eligible universe, calculate return percentile across:

| Horizon | Weight |
|---|---:|
| ~21 trading sessions | 30% |
| ~63 trading sessions | 40% |
| ~126 trading sessions | 30% |

**Composite RS = 0.30 × RS21 + 0.40 × RS63 + 0.30 × RS126**

### Interpretation

- **RS < 60:** reject for primary momentum strategy
- **RS 60–70:** only exceptional circumstances
- **RS ≥ 70:** valid scanner candidate
- **RS ≥ 80:** preferred
- **RS ≥ 90:** exceptional momentum; extension risk must be checked carefully

RS is calculated against the **entire eligible trading universe**.

Also evaluate separately:

- stock vs Nifty 500;
- stock vs its sector;
- sector vs Nifty 500.

## Sector strength

Preferred:

- sector in approximately the top third of sector relative performance.

Acceptable:

- top half.

Bottom half:

- individual stock needs unusually strong stock-specific evidence.

Bottom third:

- normally reject for the primary momentum strategy unless there is a compelling stock-specific catalyst.

---

# 10. Trend Filter

The strategy uses **flexible momentum**, not perfect moving-average alignment.

### Normal hard conditions

- Price > 50 DMA
- 50 DMA > 200 DMA
- 50 DMA rising versus approximately 20 sessions earlier

### Preferred, but not mandatory

- Price > 20 DMA > 50 DMA > 200 DMA

The 20 DMA may flatten or move around the 50 DMA during a healthy consolidation.

## 52-week position

Preferred momentum candidates should generally be:

- within **20% of the 52-week high**;
- preferably within **10%**.

This avoids treating temporary rebounds inside major downtrends as momentum leadership.

---

# 11. Scanner Pipeline

The scanner itself does **not** generate an automatic BUY.

Expected funnel:

1. Eligible universe
2. Liquidity/surveillance filter
3. Fundamental/governance sanity
4. Trend filter
5. Relative-strength ranking
6. Sector/regime overlay
7. Setup detection
8. Manual chart/news validation
9. Entry economics
10. Signal: WATCH / ACTIONABLE / REJECT

---

# 12. Setup States

Every candidate is classified into one of the following.

## BUILDING

A quality stock is forming or approaching a potential setup.

No trade yet.

## READY

Setup is close enough to its trigger that entry, stop, R:R and cancellation conditions can be planned.

Typically price is within roughly **1 ATR** of the breakout area.

## TRIGGERED

The setup has produced the required breakout/reversal confirmation.

It may become ACTIONABLE if entry economics remain valid.

## EXTENDED

The stock has moved too far beyond the logical entry.

A good stock can therefore become a bad trade.

Normal response:

**Do not chase. Wait for a new setup or pullback.**

---

# 13. Base / Consolidation Quality

A valid momentum base should normally occur **inside an established uptrend**, not after a prolonged decline.

## Preferred duration

- Sweet spot: approximately **7–30 sessions**
- Roughly 5–60 sessions may qualify depending on structure

Duration alone is not a pass/fail rule.

## Base depth

No fixed percentage cap.

Evaluate depth relative to:

- stock ATR/normal volatility;
- size of the prior advance;
- support structure;
- quality of selling.

Shallower/tighter bases are generally preferred.

## Preferred base structures

### A. Flat / Horizontal Base

Clear resistance with relatively stable support.

### B. Volatility Contraction

Ranges progressively narrow as supply is absorbed.

### C. Bull Flag / Controlled Pullback

Strong prior advance followed by an orderly sideways/downward drift before continuation.

All three are supported in V1 and should be tracked separately during validation.

## Positive characteristics

- prior momentum;
- clear resistance zone;
- controlled pullback;
- volatility contraction;
- lower volume during consolidation;
- supportive closing behaviour;
- higher lows where appropriate;
- no excessive overhead supply;
- moving averages/structure allowed to catch up.

## Negative characteristics

- wild/expanding volatility;
- repeated heavy-volume selling;
- large uncontrolled correction;
- unclear resistance;
- repeated sharp rejection without constructive higher lows;
- strong deterioration in RS;
- major negative news;
- structural support failure.

Volatility contraction is a strong quality factor and is generally expected for **A+**, unless another feature is exceptionally strong.

---

# 14. Breakout Level

Resistance is treated as a **zone**, not a falsely precise number.

A meaningful breakout area should normally come from:

- repeated price rejection;
- prior important swing high;
- top of a clear consolidation;
- 52-week/all-time high;
- prior major support/resistance area.

Do not call every recent candle high a breakout.

Also inspect what exists **above** the breakout. Heavy overhead supply can make an otherwise good breakout unattractive.

---

# 15. Breakout Confirmation

Normal EOD confirmation requires:

- decisive movement through the resistance zone;
- preferably a close above resistance;
- strong closing location;
- limited bearish upper wick;
- acceptable/strong volume;
- healthy RS;
- no material deterioration in sector/market/setup.

## Candle quality

### Strong

- decisive breakout;
- bullish range expansion;
- close near high;
- good participation;
- limited upper wick.

May justify direct entry.

### Acceptable

- closes above resistance;
- candle/volume merely adequate;
- underlying base, RS and sector strong.

May be tradable or may favour retest.

### Weak

- barely above resistance;
- large upper wick;
- poor close;
- weak participation;
- immediate overhead resistance.

Normally WATCH or REJECT.

---

# 16. Volume Framework

Compare breakout volume with **20-session median volume**.

- **≥1.5×:** strong confirmation
- **1.0–1.5×:** acceptable if price structure is good
- **<1×:** requires additional evidence; normally not A+ on its own

Volume is a **confirmation/quality factor**, not an inflexible gate.

High volume plus poor price action can indicate distribution rather than accumulation.

Inside a high-quality base, ideally:

> strong participation in advance → quieter consolidation → participation expands again on breakout.

---

# 17. Breakout Entry Types

## Entry A — Confirmed Breakout / Next Session

Default workflow.

After EOD confirmation, plan a next-session entry zone.

The plan includes:

- breakout zone;
- acceptable entry range;
- do-not-chase level;
- stop/invalidation;
- position size;
- realistic upside;
- cancellation conditions.

## Entry B — Breakout Retest

Used when price breaks out and revisits the old resistance area.

Healthy retest characteristics:

- lower volume on pullback;
- old resistance holds reasonably well;
- no aggressive selling;
- RS remains healthy;
- buyers reappear.

A retest may materially improve stop placement and R:R.

## Entry C — Selective Intraday / Pre-Close Entry

Allowed only when:

- stock was already in READY state;
- trigger was known beforehand;
- breakout is unusually convincing;
- sector/market confirm;
- user happens to be available.

The strategy must work without using this entry type.

---

# 18. Extension / Chase Rule

Use **14-day ATR** to normalize extension.

From the breakout level:

- **≤0.5 ATR:** generally acceptable entry territory
- **0.5–1 ATR:** conditional; strong setup/R:R required or wait for retest
- **>1 ATR:** normally do not chase

Exceptional catalyst gaps can be assessed separately.

A stock does **not** become more attractive simply because it keeps rising.

---

# 19. Gap-Up Handling

Gap-up entries are allowed when justified.

## Constructive gap

Potentially tradable if:

- genuine catalyst exists;
- setup was already strong;
- price holds the gap;
- participation is healthy;
- extension remains acceptable;
- stop is workable;
- ≥2R remains realistically available.

## Dangerous gap

Normally avoid when:

- unexplained;
- excessively extended;
- immediately fades;
- large upper wick appears;
- stop becomes impractically wide;
- realistic upside no longer provides ≥2R.

---

# 20. Trend Pullback Setup

A pullback is tradable only in an **already-healthy uptrend**.

## Candidate requirements

- passes broad trend framework;
- strong RS;
- sector supportive or at least not weak;
- no material fundamental/news deterioration;
- stock is correcting, not structurally breaking down.

## Preferred pullback behaviour

- orderly red/small candles;
- normal or declining volume;
- controlled volatility;
- no major gap-down damage;
- approaching meaningful support.

## Support areas

Use confluence from:

- previous breakout zone;
- prior swing support;
- 20 DMA;
- 50 DMA;
- rising price structure;
- prior consolidation.

Moving averages are supporting context, not automatic buy signals.

## Confirmation

Do not buy simply because price reaches support.

Wait for evidence of returning demand, such as:

- bullish reversal candle;
- strong close after support test;
- higher low;
- reclaim of short-term resistance;
- mini-range breakout;
- improving volume;
- stabilizing/improving RS.

Sequence:

> Pullback → Support → Stabilization → Buyer Confirmation → Entry

## Highest-quality version

**Base → breakout → rally → controlled retest of breakout area → buyers return**

---

# 21. Pullback Failure

Reject if:

- major swing low breaks;
- trend becomes a lower-high/lower-low structure;
- 50 DMA is lost decisively with poor price action;
- RS collapses;
- sector leadership disappears;
- heavy-volume selling develops;
- major negative catalyst changes the thesis.

A failed pullback is **not** relabelled as a value investment.

---

# 22. Entry Economics

A technically attractive chart is not enough.

Before entry:

1. determine logical entry;
2. determine technical invalidation;
3. sanity-check stop against ATR;
4. calculate realistic upside based on chart structure/resistance;
5. calculate reward/risk;
6. determine position size.

### Minimum expected R:R

**Normally ≥2R**

Preferred A+ opportunity:

**~2.5R or better**

If a great chart only provides 1.3R–1.6R of realistic upside, normally reject the trade.

---

# 23. Stop-Loss Methodology

Stops are based on:

> **Technical invalidation first + ATR/volatility sanity check second**

Possible structural stops:

- below breakout/retest support;
- below recent meaningful swing low;
- below consolidation support;
- below pullback low.

No universal 3%, 5% or 7% stop exists.

## Wide stops

A 6–7% stop is not automatically rejected.

However, it must still allow:

- sensible position sizing;
- realistic ≥2R upside;
- an expected move compatible with the trade horizon.

If not, reject the trade instead of artificially tightening the stop.

### Hard rule

**Never move the stop farther away simply because price is approaching it.**

---

# 24. Position Sizing

Normal initial risk:

**~1% of total swing capital per trade**

At ₹20,000:

**Planned risk ≈ ₹200 per trade**

Formula:

> Position quantity = Portfolio risk amount ÷ Risk per share

Where:

> Risk per share = Entry price – Stop price

Example:

- Entry ₹500
- Stop ₹485
- Risk/share ₹15
- Portfolio risk ₹200

Maximum quantity ≈ 13 shares  
Position value ≈ ₹6,500

Thus the chart determines the stop, and the stop determines the position size.

**Confidence does not arbitrarily increase position size.**

---

# 25. Portfolio Construction

Initially:

- approximately 3–5 positions maximum;
- avoid unnecessary concentration in the same sector/theme/correlation;
- not all capital must be deployed;
- lower-quality trades are not added simply because cash exists.

As capital grows, the number of positions may increase reasonably, but diversification should not become diworsification.

---

# 26. Trade Management

Every trade begins with:

- entry;
- setup/thesis;
- structural stop;
- planned risk;
- expected move;
- cancellation/invalidation conditions.

## Stop management

Do not automatically move stop to breakeven at +1R.

A stop should normally tighten only after the **chart earns it**, for example:

- successful retest;
- higher low;
- new consolidation/support;
- sufficient trend development.

---

# 27. Partial Profit Taking

Profit-taking is **chart dependent**, not based on a fixed percentage.

Default framework:

- consider booking roughly **25–50%** at a meaningful technical objective;
- commonly around **1.5R–2.5R+**, depending on structure;
- preserve a runner when momentum remains healthy.

Do not manufacture a profit target simply because the stock reaches +3%, +5% or another arbitrary percentage.

---

# 28. Runner Management

The remaining position is allowed to capture outsized moves.

Primary trailing reference:

- meaningful higher lows;
- new consolidation support.

Secondary tools:

- 10 DMA for faster momentum;
- 20 DMA for healthier/slower trends;
- ATR to avoid excessively tight trailing stops.

Moving averages alone are not automatic sell triggers.

---

# 29. Time Stop / Capital Velocity

Because capital rotation is a core objective, a trade can fail **without hitting the price stop**.

## Sessions 1–3

Allow normal price noise unless the breakout/pullback clearly fails.

## Sessions 4–7

Some progress is normally expected.

A healthy tight consolidation near/above entry may still justify holding.

## Roughly sessions 7–10

Consider rotation if:

- little/no progress;
- RS deteriorates;
- sector advances while the stock does not;
- original momentum thesis is no longer developing.

Exception:

A very tight constructive consolidation above support may represent re-accumulation and can remain valid.

Time stop is therefore:

> **time + behaviour**, not time alone.

---

# 30. Early Thesis Deterioration

## Mild warning

Examples:

- momentum slows;
- volume dries up;
- RS flattens.

Typical response:

**Hold / Monitor**

## Material warning

Examples:

- falls back deeply into old base;
- repeated failure to reclaim breakout;
- sector deteriorates materially;
- high-volume bearish candles;
- important higher low breaks;
- RS falls sharply.

Possible response:

**Reduce / Exit Early**

## Thesis failure

Examples:

- structural stop breaks;
- decisive failed breakout;
- material negative information invalidates setup.

Response:

**Exit**

---

# 31. Failed Breakout Rule

A failed breakout is not an averaging opportunity.

Example:

> resistance breaks → stock moves slightly higher → falls back below breakout zone on heavy selling.

Response:

**Exit according to invalidation; do not average down.**

### Hard rule

**No averaging down in Swing Strategy V1.**

A losing trade cannot be converted into a long-term holding without an entirely new long-term thesis and separate portfolio decision.

---

# 32. Pyramiding / Adding to Winners

Not used initially.

Although adding to a proven winner after a second high-quality setup may eventually be useful, initial V1 live trading will prioritize clean execution and validation.

**No pyramiding during the initial validation/live-learning stage.**

---

# 33. Capital Rotation / Opportunity-Cost Exit

An open position does not have an entitlement to capital until stop or target.

A sluggish trade may be exited or trimmed if:

- expected move did not develop in the expected timeframe;
- RS/sector position deteriorated;
- setup remains mediocre;
- a materially superior A/A+ opportunity appears.

Question to answer:

> **Which position deserves scarce working capital now?**

Opportunity-cost exits are therefore explicitly allowed.

---

# 34. Overnight Gap Risk

A planned 1% portfolio risk is **not a guaranteed maximum loss**.

Overnight gaps/slippage can cause actual losses to exceed the planned amount.

Therefore:

- avoid unnecessary binary event risk;
- use real broker stop-loss functionality where appropriate;
- understand broker order behaviour;
- if a gap decisively invalidates the thesis, exit rather than waiting for the original stop price to recover.

---

# 35. Earnings / Major Event Management

Judge individually using:

- existing profit cushion;
- momentum strength;
- event significance;
- expected volatility;
- position size;
- technical support;
- whether the event is already part of the setup.

Possible actions:

- hold;
- reduce and keep runner;
- exit before event.

---

# 36. Market Deterioration While Holding

If the market moves into a materially weaker regime:

- avoid adding mediocre positions;
- reduce new exposure;
- consider earlier partial profits;
- tighten scrutiny of weaker holdings;
- rotate weaker positions to cash;
- preserve exceptional leaders where their structure remains intact.

---

# 37. Drawdown Circuit Breaker

Drawdown is measured on the dedicated swing-trading capital.

## Normal Mode

Drawdown < ~5%

**Risk/trade ≈ 1%**

## Defensive Mode

Drawdown reaches approximately **5%**

Actions:

- reduce new-trade risk to ~0.5%;
- increase selectivity;
- reduce unnecessary exposure.

## Pause / Review Mode

Drawdown reaches approximately **8%**

Actions:

- stop opening new trades;
- investigate whether losses are caused by:
  - market regime;
  - scanner weakness;
  - setup rules;
  - stop placement;
  - execution;
  - correlated positions;
  - ordinary statistical losing streak.

Resume only after the cause is reasonably understood and restart conditions are defined.

---

# 38. Candidate Grades

## A+

Highest-priority candidate.

Typical traits:

- RS approximately ≥85;
- strong trend;
- strong/top-third sector;
- excellent base/pullback structure;
- good participation;
- not extended;
- ≥2.5R realistic opportunity;
- clean fundamentals/news;
- supportive enough market regime.

## A

Tradable.

Typical traits:

- RS approximately ≥75;
- healthy trend;
- acceptable sector;
- valid trigger;
- acceptable volume;
- ≥2R;
- no material red flags.

## B

**Watchlist only under normal circumstances.**

Something important is missing:

- confirmation;
- volume;
- sector support;
- entry economics;
- clean resistance/support;
- timing.

## Reject

Does not deserve capital.

---

# 39. User-Facing Signal States

## 🟡 WATCH

Setup developing; no trade yet.

## 🟢 ACTIONABLE

All relevant setup, trigger, risk and economics conditions qualify.

## 🔴 REJECT

Trade should not be taken at the current price/setup.

## CANCELLED

A previously planned entry becomes invalid because conditions changed before execution.

Examples:

- excessive gap/extension;
- failed breakout;
- material negative news;
- market/sector deterioration;
- R:R falls below threshold.

---

# 40. Standard Actionable Signal Format

For every serious signal, provide:

**Stock:**  
**Setup:** Breakout / Pullback  
**Grade:** A+ / A  
**Market regime:**  
**Sector strength:**  
**RS percentile:**  

**Setup summary:**  
**Breakout/support zone:**  
**Entry zone:**  
**Trigger:**  
**Do-not-chase level:**  

**Structural stop:**  
**Risk per share:**  
**Suggested quantity / position value:**  
**Portfolio risk:**  

**First meaningful objective/resistance:**  
**Initial expected R:R:**  
**Expected holding window:**  

**Volume/price confirmation:**  
**Fundamental/news check:**  
**Important event risk:**  

**Cancellation conditions:**  
**Initial management plan:**  

A signal is always tied to:

> **Stock + Setup + Price + Time**

Not merely “Stock XYZ is bullish.”

---

# 41. Daily / Session Workflow

The intended operating workflow is:

## After market close

1. Determine market regime.
2. Rank sector strength.
3. Run eligible-universe filters.
4. Calculate RS.
5. Identify BUILDING / READY / TRIGGERED setups.
6. Review charts of highest-quality candidates.
7. Review current news/fundamental safety.
8. Calculate stop and R:R.
9. Rank opportunities against open positions.
10. Produce:
   - WATCH list;
   - ACTIONABLE trades;
   - REJECT/CANCELLED items;
   - management actions for existing positions.

## Before next-session execution

Recheck:

- overnight material news;
- results/events;
- meaningful index/sector change;
- gap-up/gap-down;
- whether entry remains inside permitted range;
- whether ≥2R still exists.

If conditions materially change, the previous signal can be cancelled.

---

# 42. Non-Negotiable Rules

1. **No F&O or leverage.**
2. **No microcaps.**
3. **No forced trades.**
4. **No averaging down.**
5. **Never widen a stop just to avoid a loss.**
6. **Do not chase excessively extended breakouts.**
7. **A good company is not automatically a good swing entry.**
8. **Purchase price does not create a holding thesis.**
9. **Failed swing trades do not become long-term holdings automatically.**
10. **Cash is a valid position.**
11. **Opportunity cost matters.**
12. **Risk is defined before upside.**
13. **Actual trade selection normally requires A or A+ quality.**
14. **B setups are normally watchlist-only.**
15. **No pyramiding initially.**
16. **Current news/event risk must be checked before action.**
17. **Market and sector context must be considered.**
18. **Every actionable signal requires explicit invalidation and cancellation conditions.**

---

# 43. Responsibility Split

The user is still developing technical-analysis expertise and should **not** be expected to choose technical scanner/chart parameters.

## Assistant responsibility

Recommend and assess:

- technical setup quality;
- base/pullback structure;
- ATR and volatility;
- resistance/support;
- relative strength;
- volume behaviour;
- breakout/retest quality;
- entry timing;
- stop placement;
- reward/risk;
- technical exit/trailing decisions;
- current news/fundamental safety checks.

Explain technical concepts in plain language when relevant.

## User decisions

Ask the user primarily when a choice materially depends on:

- risk tolerance;
- available trading capital;
- monitoring/execution constraints;
- acceptable drawdown;
- whether to hold event risk;
- other genuinely personal preferences.

Do not repeatedly ask the user to choose technical parameters that can be reasonably recommended by the assistant.

---

# 44. Validation Status

**Important: this strategy is not yet considered validated or ready for normal-capital deployment.**

The next phase is:

1. historical/backtest design;
2. historical sample testing;
3. analysis of win rate, expectancy, R multiples, drawdown and holding periods;
4. identify whether Breakout and Pullback should retain the same rules;
5. forward/paper validation;
6. small-capital live deployment;
7. only then consider scaling.

The initial ~₹20,000 deployment is intended as **small working capital for controlled live validation**, not evidence that the strategy already has a proven edge.

---

# 45. Core Principle

The strategy is not trying to predict every market move.

It is trying to repeatedly find situations where:

> **the stock is already strong, the market/sector context is favorable enough, the entry structure is identifiable, downside is controlled, realistic upside materially exceeds risk, and capital can be rotated when the thesis stops working.**

Sometimes the correct signal is:

> **Great stock. No trade yet.**

And sometimes the best portfolio action is:

> **Stay in cash.**
