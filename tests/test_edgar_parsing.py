from datetime import date
from pathlib import Path

import pytest

from tradesignals.data import form4, form13f
from tradesignals.data.form4 import _parse_form4_xml, fetch_insider_transactions
from tradesignals.data.form13f import _parse_infotable_xml, fetch_institutional_holdings

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _FakeResponse:
    def __init__(self, json_data=None, text_data=None):
        self._json_data = json_data
        self.text = text_data

    def json(self):
        return self._json_data


class _FakeEdgarClient:
    """No live network calls -- responses are canned, keyed by exact URL."""

    def __init__(self, responses: dict[str, _FakeResponse]):
        self._responses = responses

    def get(self, url: str, max_retries: int = 5):
        return self._responses[url]


def test_parse_form4_xml_extracts_buy_and_sell():
    xml_text = (_FIXTURES_DIR / "sample_form4.xml").read_text()

    transactions = _parse_form4_xml(xml_text, ticker="AAPL", cik="0001234567", filed_date=date(2024, 2, 12))

    assert len(transactions) == 2
    buy, sell = transactions

    assert buy.insider_name == "Jane Q. Doe"
    assert buy.insider_title == "Chief Financial Officer"
    assert buy.transaction_date == date(2024, 2, 10)
    assert buy.filed_date == date(2024, 2, 12)
    assert buy.transaction_code == "P"
    assert buy.shares == 1000.0
    assert buy.price == pytest.approx(150.25)
    assert buy.shares_owned_after == 5000.0

    assert sell.transaction_code == "S"
    assert sell.shares == 200.0
    assert sell.price == pytest.approx(151.00)
    assert sell.shares_owned_after == 4800.0


def test_parse_infotable_xml_filters_to_watchlist_cusips():
    xml_text = (_FIXTURES_DIR / "sample_13f_infotable.xml").read_text()
    cusip_to_ticker = {"037833100": "AAPL"}  # the second fixture CUSIP is deliberately unmapped

    holdings = _parse_infotable_xml(
        xml_text,
        cik="0001067983",
        filer_name="Berkshire Hathaway Inc",
        report_period=date(2024, 3, 31),
        filed_date=date(2024, 4, 10),
        cusip_to_ticker=cusip_to_ticker,
    )

    assert len(holdings) == 1
    holding = holdings[0]
    assert holding.ticker == "AAPL"
    assert holding.cusip == "037833100"
    assert holding.shares == 10000
    assert holding.value_usd == 1_500_000_000  # reported in thousands of USD
    assert holding.report_period == date(2024, 3, 31)
    assert holding.filed_date == date(2024, 4, 10)


def test_fetch_insider_transactions_filters_form_4_and_parses_fixture(monkeypatch):
    cik = "0001234567"
    monkeypatch.setattr(form4, "cik_for_ticker", lambda client, ticker: cik)

    submissions_url = "https://data.sec.gov/submissions/CIK0001234567.json"
    doc_url = "https://www.sec.gov/Archives/edgar/data/1234567/000123456724000010/form4.xml"
    xml_text = (_FIXTURES_DIR / "sample_form4.xml").read_text()

    submissions_payload = {
        "filings": {
            "recent": {
                "form": ["4", "3"],
                "accessionNumber": ["0001234567-24-000010", "0001234567-24-000011"],
                "filingDate": ["2024-02-12", "2024-02-13"],
                "primaryDocument": ["form4.xml", "form3.xml"],
            }
        }
    }
    client = _FakeEdgarClient(
        {
            submissions_url: _FakeResponse(json_data=submissions_payload),
            doc_url: _FakeResponse(text_data=xml_text),
        }
    )

    transactions = fetch_insider_transactions(client, "AAPL")

    assert len(transactions) == 2  # the form="3" filing must be excluded entirely
    buy, sell = transactions
    assert buy.ticker == "AAPL"
    assert buy.cik == cik
    assert buy.filed_date == date(2024, 2, 12)
    assert buy.transaction_code == "P"
    assert sell.transaction_code == "S"


def test_fetch_institutional_holdings_filters_to_tracked_filers_and_watchlist(monkeypatch):
    cik = "0009999999"
    monkeypatch.setattr(form13f, "TRACKED_FILERS", {cik: "Test Capital LLC"})

    submissions_url = "https://data.sec.gov/submissions/CIK0009999999.json"
    index_url = "https://www.sec.gov/Archives/edgar/data/9999999/000999999924000005/index.json"
    doc_url = "https://www.sec.gov/Archives/edgar/data/9999999/000999999924000005/form13fInfoTable.xml"
    xml_text = (_FIXTURES_DIR / "sample_13f_infotable.xml").read_text()

    submissions_payload = {
        "filings": {
            "recent": {
                "form": ["13F-HR"],
                "accessionNumber": ["0009999999-24-000005"],
                "filingDate": ["2024-04-10"],
                "reportDate": ["2024-03-31"],
            }
        }
    }
    index_payload = {"directory": {"item": [{"name": "primary_doc.xml"}, {"name": "form13fInfoTable.xml"}]}}

    client = _FakeEdgarClient(
        {
            submissions_url: _FakeResponse(json_data=submissions_payload),
            index_url: _FakeResponse(json_data=index_payload),
            doc_url: _FakeResponse(text_data=xml_text),
        }
    )

    holdings = fetch_institutional_holdings(client, cusip_to_ticker={"037833100": "AAPL"})

    assert len(holdings) == 1  # the unmapped CUSIP in the fixture must be filtered out
    holding = holdings[0]
    assert holding.ticker == "AAPL"
    assert holding.filer_name == "Test Capital LLC"
    assert holding.report_period == date(2024, 3, 31)
    assert holding.filed_date == date(2024, 4, 10)
    assert holding.value_usd == 1_500_000_000
