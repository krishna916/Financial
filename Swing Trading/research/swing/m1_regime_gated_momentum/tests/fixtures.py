from pathlib import Path

import pandas as pd


def write_minimal_v3_package(root: Path) -> None:
    signals = pd.DataFrame(
        [
            {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Signal_Qualified": True},
            {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": "2024-01-03", "Signal_Qualified": True},
            {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": "2024-01-04", "Signal_Qualified": True},
            {"Entry_ID": "DDD-2024-01-05", "Symbol": "DDD", "Signal_Date": "2024-01-05", "Signal_Qualified": False},
        ]
    )
    entries = pd.DataFrame(
        [
            {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0},
            {"Entry_ID": "BBB-2024-01-03", "Symbol": "BBB", "Signal_Date": "2024-01-03", "Entry_Date": "2024-01-04", "Entry_Open": 200.0, "Structural_Stop": 190.0, "Initial_Risk": 10.0},
        ]
    )
    cancellations = pd.DataFrame(
        [
            {"Entry_ID": "CCC-2024-01-04", "Symbol": "CCC", "Signal_Date": "2024-01-04", "Cancellation_Reason": "STOP_TOO_WIDE"},
        ]
    )
    setup = pd.DataFrame(
        [
            {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0, "Exit_Date": "2024-01-10", "Exit_Price": 110.0, "Return": 0.10},
        ]
    )
    practical = pd.DataFrame(
        [
            {"Entry_ID": "AAA-2024-01-02", "Symbol": "AAA", "Signal_Date": "2024-01-02", "Entry_Date": "2024-01-03", "Entry_Open": 100.0, "Structural_Stop": 95.0, "Initial_Risk": 5.0, "Exit_Date": "2024-01-10", "Exit_Price": 110.0, "R_Multiple": 2.0, "Holding_Sessions": 5, "Exit_Reason": "SMA20"},
        ]
    )
    gates = pd.DataFrame(
        [
            {"Gate": "POINT_IN_TIME_INTEGRITY", "Passed": True, "Value": 0, "Status": "PASS"},
            {"Gate": "FINAL_STATUS", "Passed": False, "Value": "FAIL", "Status": "FAIL"},
        ]
    )
    frames = {
        "v3_signal_candidates.csv": signals,
        "v3_entries.csv": entries,
        "v3_entry_cancellations.csv": cancellations,
        "v3_setup_quality_trades.csv": setup,
        "v3_practical_trades.csv": practical,
        "v3_validation_gates.csv": gates,
    }
    root.mkdir(parents=True, exist_ok=True)
    for filename, frame in frames.items():
        frame.to_csv(root / filename, index=False)
