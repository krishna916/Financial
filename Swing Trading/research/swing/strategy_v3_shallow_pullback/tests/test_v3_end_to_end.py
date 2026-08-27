import sys
import shutil
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyze_v3_results import (  # noqa: E402
    attach_prior_breadth,
    count_point_in_time_violations,
    evaluate_gates,
    overlap_diagnostic,
    simulate_practical_trade,
    simulate_setup_quality_trade,
    validate_trade_integrity,
    write_evidence_report,
)
from generate_v3_signals import build_entries  # noqa: E402


def _signal(symbol: str) -> dict[str, object]:
    return {
        "Entry_ID": f"{symbol}-2024-01-10",
        "Symbol": symbol,
        "Leader_Date": pd.Timestamp("2024-01-05"),
        "Signal_Date": pd.Timestamp("2024-01-10"),
        "Pullback_Age": 3,
        "Leader_Close": 100.0,
        "ATR14_Seed": 2.0,
        "ATR14_Signal": 4.0,
        "Pullback_Low": 96.0,
        "Pullback_Depth_ATR": 1.0,
        "Close": 99.5,
        "Prior_High": 99.0,
        "SMA20": 98.0,
        "SMA50": 95.0,
        "SMA200": 90.0,
        "Median_Traded_Value_20": 200_000_000.0,
        "Composite_RS": 80.0,
        "RS_Coverage": 1.0,
        "Seed_RS_Coverage_OK": True,
        "Seed_RS_OK": True,
        "Signal_Membership_OK": True,
        "Signal_RS_Coverage_OK": True,
        "Signal_Liquidity_OK": True,
        "Signal_Trend_OK": True,
        "Signal_RS_OK": True,
        "Age_OK": True,
        "Depth_OK": True,
        "Resumption_OK": True,
        "Not_New_Leader_OK": True,
        "Signal_Qualified": True,
        "Signal_Rejection_Reason": "",
    }


def _prices(entry_open: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-10", "2024-01-11", "2024-01-12", "2024-01-13"]),
            "Open": [100.0, entry_open, 98.0, 101.0],
            "High": [102.0, 101.0, 99.0, 102.0],
            "Low": [98.0, 97.0, 96.0, 100.0],
            "Close": [101.0, 99.0, 97.0, 101.0],
            "SMA20": [98.0, 98.0, 98.0, 98.0],
        }
    )


def test_strategy_v3_synthetic_flow_is_network_free_and_reconciles(monkeypatch):
    monkeypatch.setattr("build_v3_features.download_adjusted_ohlcv", lambda *args: (_ for _ in ()).throw(AssertionError("network call")))
    signals = pd.DataFrame([_signal("AAA"), _signal("BBB")])
    sessions = pd.DatetimeIndex(pd.to_datetime(["2024-01-05", "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-13"]))
    prices = {"AAA": _prices(99.0), "BBB": _prices(97.5)}
    entries, cancellations = build_entries(signals, prices, sessions)
    assert len(entries) == 1
    assert len(cancellations) == 1
    assert set(signals["Entry_ID"]) == set(entries["Entry_ID"]) | set(cancellations["Entry_ID"])

    setup = pd.DataFrame([simulate_setup_quality_trade(entries.iloc[0], prices["AAA"])])
    practical = pd.DataFrame([simulate_practical_trade(entries.iloc[0], prices["AAA"])])
    breadth = pd.DataFrame({"Date": [pd.Timestamp("2024-01-10")], "Regime": ["NEUTRAL"]})
    setup = attach_prior_breadth(setup, breadth)
    practical = attach_prior_breadth(practical, breadth)
    validate_trade_integrity(setup, practical)
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB"],
            "Member_From": [pd.Timestamp("2023-01-01")] * 2,
            "Member_To": [pd.Timestamp("2025-01-01")] * 2,
        }
    )
    pit, pit_audit = count_point_in_time_violations(
        signals, entries, setup, practical, membership, sessions
    )
    assert pit == 0
    assert pit_audit.empty
    assert overlap_diagnostic(entries, practical).iloc[0]["Total_Accepted_Entries"] == 1
    gates = evaluate_gates(setup, practical, point_in_time_violations=pit)
    assert gates.loc[gates["Gate"].eq("POINT_IN_TIME_INTEGRITY"), "Value"].iloc[0] == 0

    output = Path(__file__).resolve().parents[4] / ".v3-e2e-output"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    try:
        report = write_evidence_report(
            output,
        validation=pd.DataFrame(),
        rs_audit=pd.DataFrame(),
        states=pd.DataFrame(),
        signals=signals,
        entries=entries,
        cancellations=cancellations,
        setup=setup,
        practical=practical,
        year=pd.DataFrame(),
        outliers=pd.DataFrame(),
        leave_out=pd.DataFrame(),
        breadth=pd.DataFrame(),
        diagnostics=pd.DataFrame(),
        overlap=overlap_diagnostic(entries, practical),
        gates=gates,
        pit_count=pit,
            incomplete=0,
        )
        assert report.read_text(encoding="utf-8").endswith(
            "This report does not tune Strategy V3 or prescribe a follow-up threshold/filter. Portfolio Advisor retains strategy interpretation.\n"
        )
    finally:
        shutil.rmtree(output)
