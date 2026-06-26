import xml.etree.ElementTree as ET
from datetime import date

import requests

from tradesignals.data.edgar_client import EdgarClient
from tradesignals.data.edgar_tickers import cik_for_ticker
from tradesignals.data.models import InsiderTransaction

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"


def _recent_form4_filings(client: EdgarClient, cik: str) -> list[dict]:
    payload = client.get(_SUBMISSIONS_URL.format(cik=cik)).json()
    recent = payload["filings"]["recent"]
    return [
        {
            "accessionNumber": recent["accessionNumber"][i],
            "filingDate": recent["filingDate"][i],
            "primaryDocument": recent["primaryDocument"][i],
        }
        for i, form in enumerate(recent["form"])
        if form == "4"
    ]


def _parse_form4_xml(xml_text: str, ticker: str, cik: str, filed_date: date) -> list[InsiderTransaction]:
    root = ET.fromstring(xml_text)
    owner_name_el = root.find(".//reportingOwner/reportingOwnerId/rptOwnerName")
    insider_name = owner_name_el.text if owner_name_el is not None else "UNKNOWN"
    title_el = root.find(".//reportingOwnerRelationship/officerTitle")
    insider_title = title_el.text if title_el is not None else None

    transactions = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        txn_date_el = txn.find("transactionDate/value")
        code_el = txn.find("transactionCoding/transactionCode")
        shares_el = txn.find("transactionAmounts/transactionShares/value")
        price_el = txn.find("transactionAmounts/transactionPricePerShare/value")
        owned_after_el = txn.find("postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        if txn_date_el is None or code_el is None or shares_el is None:
            continue
        transactions.append(
            InsiderTransaction(
                cik=cik,
                ticker=ticker,
                insider_name=insider_name,
                insider_title=insider_title,
                transaction_date=date.fromisoformat(txn_date_el.text),
                filed_date=filed_date,
                transaction_code=code_el.text,
                shares=float(shares_el.text),
                price=float(price_el.text) if price_el is not None and price_el.text else None,
                shares_owned_after=(
                    float(owned_after_el.text) if owned_after_el is not None and owned_after_el.text else None
                ),
            )
        )
    return transactions


def fetch_insider_transactions(client: EdgarClient, ticker: str) -> list[InsiderTransaction]:
    """Form 4 transactions are filed against the issuer's CIK by each
    insider; we discover them via the issuer's filing index, not a
    per-insider lookup."""
    cik = cik_for_ticker(client, ticker)
    if cik is None:
        return []

    results: list[InsiderTransaction] = []
    for filing in _recent_form4_filings(client, cik):
        accession_nodash = filing["accessionNumber"].replace("-", "")
        url = _ARCHIVE_URL.format(
            cik_int=int(cik), accession_nodash=accession_nodash, document=filing["primaryDocument"]
        )
        try:
            xml_text = client.get(url).text
            filed_date = date.fromisoformat(filing["filingDate"])
            results.extend(_parse_form4_xml(xml_text, ticker, cik, filed_date))
        except (requests.RequestException, ET.ParseError):
            # Some older/paper Form 4s don't have a parseable primary XML
            # document; skip rather than failing the whole ticker's fetch.
            continue
    return results
