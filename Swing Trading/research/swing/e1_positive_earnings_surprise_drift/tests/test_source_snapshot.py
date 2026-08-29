from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

import build_e1_source_snapshot as snapshot  # noqa: E402


def _filing(symbol: str, exchange: str = "NSE") -> dict[str, object]:
    return {
        "symbol": symbol,
        "toDate": "30-Jun-2024",
        "broadCastDate": "12-Aug-2024 17:31:22",
        "consolidated": "Consolidated",
        "revised": "No",
        "xbrl": f"https://example.test/{exchange.lower()}-{symbol}.xml",
        "EPS": 12.34,
        "id": f"{exchange}-{symbol}-20240812",
    }


class _FakeNseClient:
    def list_legacy(self, symbol: str) -> list[dict[str, object]]:
        return [_filing(symbol)]

    def list_integrated(self, symbol: str) -> list[dict[str, object]]:
        return []


class _FakeBseClient:
    def list_results(self, symbol: str) -> list[dict[str, object]]:
        return [_filing(symbol, "BSE")]


def test_snapshot_builder_outputs_source_fields_but_no_forward_return_fields(monkeypatch):
    monkeypatch.setattr(snapshot, "NseResultsClient", _FakeNseClient)
    monkeypatch.setattr(snapshot, "BseResultsClient", _FakeBseClient)

    filings, eps, audit = snapshot.build_filing_snapshot(["AAA"], pd.Timestamp("2026-08-25"))

    forbidden = {"Gross_Return", "Net_Return", "Exit_Open", "SUE", "Cohort"}
    assert forbidden.isdisjoint(filings.columns)
    assert forbidden.isdisjoint(eps.columns)
    assert len(filings) == 2
    assert len(eps) == 2
    assert audit.empty


def test_market_snapshot_keeps_symbol_and_benchmark_dates_separate(monkeypatch):
    membership = pd.DataFrame(
        {
            "Symbol": ["AAA"],
            "Yahoo_Ticker": ["AAA.NS"],
            "Downloadable": [True],
            "Member_From": [pd.Timestamp("2023-08-01")],
            "Member_To": [pd.Timestamp("2026-06-30")],
        }
    )

    def fake_download(ticker: str, start: str, end_exclusive: str) -> pd.DataFrame:
        dates = pd.date_range("2023-07-31", periods=3, freq="B")
        values = [100.0, 101.0, 102.0]
        frame = pd.DataFrame(
            {
                "Date": dates,
                "Open": values,
                "High": [value + 1 for value in values],
                "Low": [value - 1 for value in values],
                "Close": values,
                "Volume": [1000, 1100, 1200],
            }
        )
        return frame

    monkeypatch.setattr(snapshot, "download_adjusted_prices", fake_download)
    stocks, index = snapshot.build_market_snapshot(membership)
    assert stocks["Symbol"].unique().tolist() == ["AAA"]
    assert stocks["Yahoo_Ticker"].unique().tolist() == ["AAA.NS"]
    assert set(index.columns) == {"Date", "Open", "High", "Low", "Close"}
    assert stocks["Date"].is_unique
    assert index["Date"].is_unique


def test_repository_root_for_cli_resolves_financial_checkout():
    assert snapshot.repository_root() == Path(__file__).resolve().parents[5]


def test_stage_a_exports_corporate_action_parse_audit(monkeypatch, tmp_path):
    action_audit = pd.DataFrame(
        [{"Symbol": "AAA", "Violation": "UNPARSEABLE_CORPORATE_ACTION_RATIO", "Detail": "split"}]
    )

    monkeypatch.setattr(
        snapshot,
        "build_filing_snapshot",
        lambda symbols, cutoff: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    actions = pd.DataFrame(columns=snapshot.ACTION_COLUMNS)
    actions.attrs["audit"] = action_audit
    monkeypatch.setattr(snapshot, "build_corporate_action_snapshot", lambda symbols, cutoff: actions)
    monkeypatch.setattr(snapshot, "build_market_snapshot", lambda membership: (pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(snapshot, "write_manifest", lambda input_dir, provenance: pd.DataFrame())

    snapshot._write_stage_a(tmp_path, pd.DataFrame(), [])
    written = pd.read_csv(tmp_path / "e1_source_build_audit.csv")
    assert written.iloc[0]["Violation"] == "UNPARSEABLE_CORPORATE_ACTION_RATIO"


@pytest.mark.parametrize(
    ("purpose", "expected_factor"),
    [
        ("2:1 split", 2.0),
        ("1:2 consolidation", 0.5),
        ("1:1 bonus", 2.0),
        ("2:1 bonus", 3.0),
    ],
)
def test_action_normalization_persists_old_to_new_share_count_factor(
    purpose: str, expected_factor: float
):
    action = snapshot._normalize_action(
        {"purpose": purpose, "exDate": "2023-06-01", "id": purpose},
        "AAA",
    )

    assert action is not None
    assert action["Share_Count_Factor"] == pytest.approx(expected_factor)
