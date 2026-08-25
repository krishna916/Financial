# NIFTY 500 Regime Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible historical NIFTY 500 daily market-regime dataset and its change/summary validation artifacts from Yahoo Finance ticker `^CRSLDX`.

**Architecture:** A single Python script downloads daily raw OHLC data with `yfinance`, normalizes any single- or multi-level column shape, computes trailing 50- and 200-session SMAs from the unadjusted `Close`, classifies rows using the locked point-in-time rules, validates invariants, and writes three CSV files. The generated CSVs are written in the workspace root beside the script for direct handoff to the next analysis session.

**Tech Stack:** Python 3, `yfinance`, `pandas`, CSV.

**Spec:** `C:\Users\acer\.codex\attachments\2c5a9f2e-aca0-47c5-92e6-c09524e55495\pasted-text.txt`

## Global Constraints

- Use only Yahoo Finance ticker `^CRSLDX`; do not substitute another index.
- Fetch `2022-01-01` through `2026-08-25`, using `interval="1d"`, `auto_adjust=False`, and an exclusive end date that includes `2026-08-25`.
- Calculate ordinary trailing `Close.rolling(50).mean()` and `Close.rolling(200).mean()` with no interpolation, forward fill, or lookahead.
- Classify exactly `RISK_ON`, `MIXED`, or `RISK_OFF` using the user-locked inequalities.
- Export only rows with an available `SMA200`, sorted ascending and dated `YYYY-MM-DD`.
- Do not inspect trade outcomes or optimize any threshold.

### Task 1: Reproducible generator and output artifacts

**Files:**
- Create: `build_nifty500_regime.py`
- Create: `nifty500_regime_daily.csv`
- Create: `nifty500_regime_changes.csv`
- Create: `nifty500_regime_summary.csv`

**Interfaces:**
- `download_history()` returns a normalized raw OHLC DataFrame and raises a clear error for an empty or failed `^CRSLDX` download.
- `build_dataset(raw)` returns the validated daily, change, and summary DataFrames.
- `main()` writes the requested files and prints the validation report.

- [ ] Implement the download with `yf.download("^CRSLDX", start="2022-01-01", end="2026-08-26", interval="1d", auto_adjust=False, progress=False, group_by="column", multi_level_index=False)` and normalize the date index.
- [ ] Compute `SMA50`, `SMA200`, and exact regime values from the same raw `Close` series; drop rows before `SMA200` exists.
- [ ] Create change rows by comparing each exported regime to the immediately previous exported trading session.
- [ ] Create one summary row per regime with counts, percentages of the exported regime dataset, and first/last dates.
- [ ] Validate date uniqueness, non-missing price/SMA fields, allowed labels, RISK_ON/RISK_OFF inequalities, and required output schemas before writing.
- [ ] Write CSV dates as ISO `YYYY-MM-DD` and numeric fields without index columns.

### Task 2: Execute and independently verify outputs

**Files:**
- Verify: `build_nifty500_regime.py`
- Verify: `nifty500_regime_daily.csv`
- Verify: `nifty500_regime_changes.csv`
- Verify: `nifty500_regime_summary.csv`

- [ ] Run the script against Yahoo Finance using the required ticker and date window.
- [ ] Check the printed validation report for the earliest/latest raw dates, raw row count, exported row count, duplicate dates, missing values, regime counts, allowed labels, and inequality violations.
- [ ] Independently reload all three CSVs and reconcile summary counts to the daily dataset and change rows to actual regime transitions.
- [ ] Report any Yahoo Finance or validation failure exactly and do not substitute data.
