# T1 Breadth Regime Data-Source Note

This note supplements Issue #9 and `2026-08-26-t1-breadth-regime-validation.md`.

## Preferred universe method

Use **POINT_IN_TIME** Nifty 500 membership, reconstructed from official NSE Indices material rather than a current-constituent proxy.

NSE Indices states that Nifty 500 is reconstituted semi-annually, effective on the last working day of March and September, while additional changes can occur for corporate actions/suspension/delisting. Therefore the implementation must account for both scheduled and ad-hoc Nifty 500 changes.

## Reconstruction direction

1. Download the official Nifty 500 constituent file representing the latest membership that is already effective within the research window (do not apply announced future-effective changes).
2. Walk official NSE Indices press releases **backward** from that effective membership through 2023-08-01.
3. For every press release that changes Nifty 500 membership, record each inclusion/exclusion and its stated effective date.
4. Reverse those changes to reconstruct the prior membership state.
5. Convert the reconstructed states into inclusive `Member_From` / `Member_To` intervals.
6. Validate that each effective state has approximately 500 members and reconcile every membership change in the manifest.

## Official source roots

- NSE Indices Nifty 500 page: `https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500`
- NSE Indices press-release archive: `https://www.niftyindices.com/press-release`
- NSE Indices reconstitution calendar: `https://www.niftyindices.com/resources/index-rebalancing-schedule`

Do not use Wikipedia/current-only lists as the historical source of truth.

## Audit requirement

Create a committed manifest alongside membership data with one row per applied change:

```text
Effective_Date,Symbol,Action,Press_Release_Date,Source_URL,Notes
```

Allowed `Action` values:

```text
INCLUDE
EXCLUDE
INCLUSION_REVOKED
EXCLUSION_REVOKED
```

For revocations, apply the factual final effect described by the later press release and retain the revocation row for audit.

The manifest must cover every official Nifty 500 membership change between the research start and the latest effective seed membership. The builder should fail if a reconstructed state falls materially away from the expected 500-member index without an explicitly documented source reason.

## Stop rule

If official press-release reconstruction cannot be made complete enough to establish point-in-time membership, stop before T1 outcome validation. Do not automatically fall back to `FIXED_UNIVERSE_PROXY`; bring the missing-change/source problem back to the Portfolio Advisor first.
