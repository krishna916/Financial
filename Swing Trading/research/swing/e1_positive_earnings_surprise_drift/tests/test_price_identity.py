from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT))

from price_identity import (  # noqa: E402
    ALIAS_COLUMNS,
    load_price_aliases,
    resolve_price_identity,
    validate_shared_provider_intervals,
)


def _aliases() -> pd.DataFrame:
    return load_price_aliases(MODULE_ROOT / "price_provider_aliases.csv")


def test_resolves_explicit_alias_and_preserves_normal_identities():
    aliases = _aliases()

    gls = resolve_price_identity("GLS", "GLS.NS", aliases)
    assert gls.research_symbol == "GLS"
    assert gls.membership_ticker == "GLS.NS"
    assert gls.provider_ticker == "ALIVUS.NS"
    assert gls.alias_applied is True
    assert gls.security_isin == "INE03Q201024"
    assert gls.identity_effective_date == pd.Timestamp("2025-01-20")
    assert gls.identity_source_url.endswith("CML66114.pdf")

    alivus = resolve_price_identity("ALIVUS", "ALIVUS.NS", aliases)
    assert alivus.provider_ticker == "ALIVUS.NS"
    assert alivus.alias_applied is False

    normal = resolve_price_identity("TCS", "TCS.NS", aliases)
    assert normal.provider_ticker == "TCS.NS"
    assert normal.alias_applied is False


@pytest.mark.parametrize(
    "change",
    [
        {"Research_Symbol": ""},
        {"Provider_Ticker": ""},
        {"Provider": "OTHER"},
        {"Security_ISIN": ""},
        {"Identity_Effective_Date": "not-a-date"},
        {"Identity_Source_URL": "http://example.test/evidence"},
    ],
)
def test_rejects_invalid_alias_rows_with_stable_code(tmp_path: Path, change: dict[str, str]):
    values = {
        "Research_Symbol": "GLS",
        "Provider": "YAHOO",
        "Provider_Ticker": "ALIVUS.NS",
        "Security_ISIN": "INE03Q201024",
        "Identity_Effective_Date": "2025-01-20",
        "Identity_Source_URL": "https://example.test/evidence.pdf",
        "Reason": "same listed security",
    }
    values.update(change)
    path = tmp_path / "aliases.csv"
    pd.DataFrame([values], columns=ALIAS_COLUMNS).to_csv(path, index=False)

    with pytest.raises(ValueError, match="PRICE_ALIAS_INVALID_ROW"):
        load_price_aliases(path)


def test_rejects_duplicate_alias_symbols(tmp_path: Path):
    values = {
        "Research_Symbol": "GLS",
        "Provider": "YAHOO",
        "Provider_Ticker": "ALIVUS.NS",
        "Security_ISIN": "INE03Q201024",
        "Identity_Effective_Date": "2025-01-20",
        "Identity_Source_URL": "https://example.test/evidence.pdf",
        "Reason": "same listed security",
    }
    path = tmp_path / "aliases.csv"
    pd.DataFrame([values, values], columns=ALIAS_COLUMNS).to_csv(path, index=False)

    with pytest.raises(ValueError, match="PRICE_ALIAS_DUPLICATE_SYMBOL"):
        load_price_aliases(path)


def _intervals(overlap: bool = False) -> pd.DataFrame:
    alivus_from = "2024-09-29" if overlap else "2025-03-28"
    return pd.DataFrame(
        [
            {
                "Research_Symbol": "GLS",
                "Provider": "YAHOO",
                "Provider_Ticker": "ALIVUS.NS",
                "Member_From": "2023-09-29",
                "Member_To": "2024-09-29",
            },
            {
                "Research_Symbol": "ALIVUS",
                "Provider": "YAHOO",
                "Provider_Ticker": "ALIVUS.NS",
                "Member_From": alivus_from,
                "Member_To": "2025-09-29",
            },
        ]
    )


def test_shared_provider_intervals_are_clean_when_non_overlapping():
    violations = validate_shared_provider_intervals(_intervals())
    assert violations.empty


def test_shared_provider_intervals_fail_on_inclusive_overlap():
    violations = validate_shared_provider_intervals(_intervals(overlap=True))
    assert len(violations) == 1
    assert violations.iloc[0]["Violation"] == "PROVIDER_ALIAS_MEMBERSHIP_OVERLAP"
