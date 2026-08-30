from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

import build_e1_source_snapshot as snapshot  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str, url: str):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.url = url

    def raise_for_status(self):
        if self.status_code != 200:
            raise ValueError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self.response = response

    def get(self, url: str, timeout: float):
        return SimpleNamespace(
            status_code=self.response.status_code,
            content=self.response.content,
            headers=self.response.headers,
            url=self.response.url,
        )


def test_fetch_machine_payload_classifies_inline_xbrl_html():
    response = _FakeResponse(
        200,
        b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><ix:nonFraction name="x" contextRef="c">1</ix:nonFraction></html>',
        "text/html",
        "https://www.nseindia.com/filing.html",
    )
    payload = snapshot.fetch_machine_payload(
        {"Machine_Readable_URL": "https://www.nseindia.com/filing.html"},
        _FakeSession(response),
    )

    assert payload.status_code == 200
    assert payload.payload_kind == "ixbrl_html"


def test_fetch_machine_payload_classifies_plain_text_as_unsupported():
    response = _FakeResponse(
        200,
        b"not an XBRL payload",
        "text/plain",
        "https://www.nseindia.com/filing.txt",
    )

    payload = snapshot.fetch_machine_payload(
        {"Machine_Readable_URL": "https://www.nseindia.com/filing.txt"},
        _FakeSession(response),
    )

    assert payload.payload_kind == "unsupported"


def test_fetch_machine_payload_surfaces_http_failure():
    response = _FakeResponse(
        403,
        b"forbidden",
        "text/plain",
        "https://www.nseindia.com/filing.xml",
    )

    with pytest.raises(ValueError, match="EPS_PAYLOAD_HTTP_ERROR"):
        snapshot.fetch_machine_payload(
            {"Machine_Readable_URL": "https://www.nseindia.com/filing.xml"},
            _FakeSession(response),
        )


def test_filing_snapshot_separates_missing_eps_fact_from_parse_error():
    record = _filing("AAA")
    record.pop("EPS")
    record["xbrl"] = "https://www.nseindia.com/filing.xml"

    class _Nse:
        def list_legacy(self, symbol):
            return [record]

        def list_integrated(self, symbol):
            return []

    class _Bse:
        def list_results(self, symbol):
            return []

    response = _FakeResponse(
        200,
        b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance' />",
        "application/xml",
        "https://www.nseindia.com/filing.xml",
    )
    _, eps, audit = snapshot._build_filing_snapshot_for_symbol(
        "AAA",
        pd.Timestamp("2026-08-25"),
        _Nse(),
        _Bse(),
        _FakeSession(response),
    )

    assert eps.empty
    assert audit.iloc[0]["Violation"] == "EPS_FACT_NOT_FOUND"
    assert "EPS_PARSE_ERROR" not in audit["Violation"].tolist()


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


def test_reliance_bonus_fixture_normalizes_official_share_count_factor():
    records = json.loads(
        (Path(__file__).parent / "fixtures/nse_corporate_actions_reliance.json").read_text()
    )
    action = snapshot._normalize_action(records[0], "RELIANCE")

    assert action is not None
    assert action["Ex_Date"] == pd.Timestamp("2024-10-28")
    assert action["Old_Shares"] == pytest.approx(1.0)
    assert action["Bonus_Shares"] == pytest.approx(1.0)
    assert action["New_Shares"] == pytest.approx(2.0)
    assert action["Share_Count_Factor"] == pytest.approx(2.0)


def test_bse_bonus_fixture_normalizes_table1_ratio_and_merges_action_audit(monkeypatch):
    payload = json.loads(
        (Path(__file__).parent / "fixtures/bse_corporate_actions_reliance.json").read_text()
    )

    class _FakeNseClient:
        def _get_json(self, url, params):
            return {"data": []}

    class _FakeBseClient:
        def resolve_identifier(self, symbol):
            return {"BSE_Scrip_Code": "500325", "BSE_Scrip_ID": "RELIANCE"}

        def corporate_actions(self, symbol):
            return payload

    monkeypatch.setattr(snapshot, "NseResultsClient", _FakeNseClient)
    monkeypatch.setattr(snapshot, "BseResultsClient", _FakeBseClient)

    actions = snapshot.build_corporate_action_snapshot(
        ["RELIANCE"], pd.Timestamp("2026-08-25")
    )

    bonus = actions.loc[actions["Action_Type"].eq("BONUS")].iloc[0]
    assert bonus["Ex_Date"] == pd.Timestamp("2024-10-28")
    assert bonus["Share_Count_Factor"] == pytest.approx(2.0)
    assert actions.attrs["audit"].empty


def test_filing_snapshot_reuses_validated_symbol_checkpoint(monkeypatch, tmp_path):
    checkpoint_dir = tmp_path / "stage-a-work"

    class _CheckpointNseClient:
        calls = 0

        def list_legacy(self, symbol: str) -> list[dict[str, object]]:
            self.calls += 1
            return [_filing(symbol)]

        def list_integrated(self, symbol: str) -> list[dict[str, object]]:
            self.calls += 1
            return []

    class _CheckpointBseClient:
        calls = 0

        def list_results(self, symbol: str) -> list[dict[str, object]]:
            self.calls += 1
            return []

    nse = _CheckpointNseClient()
    bse = _CheckpointBseClient()
    monkeypatch.setattr(snapshot, "NseResultsClient", lambda: nse)
    monkeypatch.setattr(snapshot, "BseResultsClient", lambda: bse)

    first = snapshot.build_filing_snapshot(
        ["AAA"], pd.Timestamp("2026-08-25"), checkpoint_dir=checkpoint_dir
    )
    first_calls = (nse.calls, bse.calls)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("validated checkpoint was not reused")

    monkeypatch.setattr(nse, "list_legacy", fail_if_called)
    monkeypatch.setattr(nse, "list_integrated", fail_if_called)
    monkeypatch.setattr(bse, "list_results", fail_if_called)
    second = snapshot.build_filing_snapshot(
        ["AAA"], pd.Timestamp("2026-08-25"), checkpoint_dir=checkpoint_dir
    )

    assert first_calls == (2, 1)
    pd.testing.assert_frame_equal(first[0], second[0])
    pd.testing.assert_frame_equal(first[1], second[1])
    pd.testing.assert_frame_equal(first[2], second[2])


def test_read_symbol_checkpoint_rejects_hash_valid_v1_metadata(monkeypatch, tmp_path):
    checkpoint_dir = tmp_path / "stage-a-work"

    class _Nse:
        def list_legacy(self, symbol):
            return [_filing(symbol)]

        def list_integrated(self, symbol):
            return []

    class _Bse:
        def list_results(self, symbol):
            return []

    nse = _Nse()
    bse = _Bse()
    monkeypatch.setattr(snapshot, "NseResultsClient", lambda: nse)
    monkeypatch.setattr(snapshot, "BseResultsClient", lambda: bse)
    snapshot.build_filing_snapshot(
        ["AAA"], pd.Timestamp("2026-08-25"), checkpoint_dir=checkpoint_dir
    )

    metadata_path = snapshot._checkpoint_paths(checkpoint_dir, "AAA")["metadata"]
    metadata = json.loads(metadata_path.read_text())
    metadata["Checkpoint_Version"] = 1
    metadata["Complete"] = True
    metadata.pop("Checkpoint_Schema_Version", None)
    metadata.pop("Source_Normalizer_Version", None)
    metadata.pop("EPS_Parser_Version", None)
    metadata.pop("Acquisition_Complete", None)
    metadata.pop("Reusable", None)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert snapshot._read_symbol_checkpoint(
        checkpoint_dir, "AAA", pd.Timestamp("2026-08-25")
    ) is None


def test_transient_v2_checkpoint_is_not_reusable(tmp_path):
    checkpoint_dir = tmp_path / "stage-a-work"
    filings = pd.DataFrame(columns=snapshot.SOURCE_COLUMNS)
    eps = pd.DataFrame(columns=snapshot.EPS_COLUMNS)
    audit = pd.DataFrame(
        [{"Symbol": "AAA", "Source_Record_ID": "", "Violation": "NSE_SOURCE_ERROR", "Detail": "503"}]
    )

    snapshot._write_symbol_checkpoint(
        checkpoint_dir,
        "AAA",
        pd.Timestamp("2026-08-25"),
        filings,
        eps,
        audit,
    )
    metadata = json.loads(
        snapshot._checkpoint_paths(checkpoint_dir, "AAA")["metadata"].read_text()
    )

    assert metadata["Reusable"] is False
    assert snapshot._read_symbol_checkpoint(
        checkpoint_dir, "AAA", pd.Timestamp("2026-08-25")
    ) is None


def test_corporate_action_snapshot_records_bse_mapping_source_error(monkeypatch):
    class _FakeNseClient:
        def _get_json(self, url, params):
            return {"data": []}

    class _FakeBseClient:
        def resolve_identifier(self, symbol):
            raise ValueError("official BSE response was not JSON")

    monkeypatch.setattr(snapshot, "NseResultsClient", _FakeNseClient)
    monkeypatch.setattr(snapshot, "BseResultsClient", _FakeBseClient)

    actions = snapshot.build_corporate_action_snapshot(["AAA"], pd.Timestamp("2026-08-25"))

    audit = actions.attrs["audit"]
    assert "BSE_SOURCE_ERROR" in audit["Violation"].tolist()


def _smoke_eps(symbol: str) -> pd.DataFrame:
    periods = [
        pd.Timestamp(year, month, 30 if month in {6, 9} else 31)
        for year, month in (
            (2023, 6), (2023, 9), (2023, 12), (2024, 3), (2024, 6), (2024, 9),
            (2024, 12), (2025, 3), (2025, 6), (2025, 9), (2025, 12), (2026, 3), (2026, 6),
        )
    ]
    return pd.DataFrame(
        {
            "Symbol": symbol,
            "Fiscal_Period_End": periods,
            "Reporting_Basis": "CONSOLIDATED",
            "EPS": [float(index + 1) for index in range(len(periods))],
            "Original_or_Revised": "ORIGINAL",
            "Public_Timestamp": [period + pd.Timedelta(days=20) for period in periods],
            "EPS_Source_Resolved": True,
        }
    )


def _passing_smoke_package():
    symbols = ("RELIANCE", "TCS", "INFY")
    filings = pd.DataFrame(
        [
            {
                "Symbol": symbol,
                "Exchange": "BSE",
                "BSE_Scrip_Code": str(index + 500000),
                "BSE_Scrip_ID": symbol,
            }
            for index, symbol in enumerate(symbols)
        ]
    )
    eps = pd.concat([_smoke_eps(symbol) for symbol in symbols], ignore_index=True)
    actions = pd.DataFrame(
        [
            {
                "Symbol": "RELIANCE",
                "Action_Type": "BONUS",
                "Old_Shares": 1.0,
                "Bonus_Shares": 1.0,
                "New_Shares": 2.0,
                "Share_Count_Factor": 2.0,
                "Ex_Date": pd.Timestamp("2024-10-28"),
            }
        ]
    )
    audit = pd.DataFrame(columns=["Symbol", "Violation", "Detail"])
    return filings, eps, actions, audit


def test_source_smoke_passes_only_when_all_semantic_gates_pass():
    filings, eps, actions, audit = _passing_smoke_package()

    status, validation = snapshot.evaluate_source_smoke(filings, eps, actions, audit)

    assert status == "PASS"
    assert validation["Status"].eq("PASS").all()


def test_source_smoke_fails_old_zero_eps_zero_actions_shape():
    filings = pd.DataFrame(
        [{"Symbol": symbol, "BSE_Scrip_Code": "500001", "BSE_Scrip_ID": symbol}]
        for symbol in ("RELIANCE", "TCS", "INFY")
    )
    eps = pd.DataFrame(columns=["Symbol", "Fiscal_Period_End", "Reporting_Basis", "EPS"])
    actions = pd.DataFrame(columns=snapshot.ACTION_COLUMNS)
    audit = pd.DataFrame(columns=["Symbol", "Violation", "Detail"])

    status, validation = snapshot.evaluate_source_smoke(filings, eps, actions, audit)

    assert status == "FAIL"
    assert validation["Status"].eq("FAIL").any()
