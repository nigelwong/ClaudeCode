import xml.etree.ElementTree as ET
from datetime import date

import requests

from tradesignals.data.edgar_client import EdgarClient
from tradesignals.data.models import InstitutionalHolding

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"
_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"

# Curated list of well-known institutional 13F filers tracked as the
# "smart money" cohort for Phase 1, rather than attempting full-market
# 13F coverage. CIKs are stable EDGAR identifiers (verify before relying
# on them, same caveat as cusip_map.yaml).
TRACKED_FILERS: dict[str, str] = {
    "0001067983": "Berkshire Hathaway Inc",
    "0001037389": "Renaissance Technologies LLC",
    "0001423053": "Citadel Advisors LLC",
    "0001350694": "Bridgewater Associates LP",
    "0001364742": "BlackRock Inc",
}


def _local_tag(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def _recent_13f_filings(client: EdgarClient, cik: str) -> list[dict]:
    payload = client.get(_SUBMISSIONS_URL.format(cik=cik)).json()
    recent = payload["filings"]["recent"]
    return [
        {
            "accessionNumber": recent["accessionNumber"][i],
            "filingDate": recent["filingDate"][i],
            "reportDate": recent["reportDate"][i],
        }
        for i, form in enumerate(recent["form"])
        if form in ("13F-HR", "13F-HR/A")
    ]


def _find_infotable_document(client: EdgarClient, cik_int: int, accession_nodash: str) -> str | None:
    payload = client.get(_INDEX_URL.format(cik_int=cik_int, accession_nodash=accession_nodash)).json()
    items = payload.get("directory", {}).get("item", [])
    names = [item["name"] for item in items]
    infotable = [n for n in names if "infotable" in n.lower()]
    if infotable:
        return infotable[0]
    other_xml = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    return other_xml[0] if other_xml else None


def _parse_infotable_xml(
    xml_text: str,
    cik: str,
    filer_name: str,
    report_period: date,
    filed_date: date,
    cusip_to_ticker: dict[str, str],
) -> list[InstitutionalHolding]:
    root = ET.fromstring(xml_text)
    holdings = []
    for info_table in root:
        if _local_tag(info_table) != "infoTable":
            continue
        cusip = shares = value_usd = None
        for child in info_table:
            tag = _local_tag(child)
            if tag == "cusip":
                cusip = child.text
            elif tag == "value":
                value_usd = int(float(child.text)) * 1000  # reported in thousands of USD
            elif tag == "shrsOrPrnAmt":
                for grandchild in child:
                    if _local_tag(grandchild) == "sshPrnamt":
                        shares = int(float(grandchild.text))
        if cusip is None or shares is None or value_usd is None:
            continue
        ticker = cusip_to_ticker.get(cusip)
        if ticker is None:
            continue  # outside our watchlist-scoped CUSIP map; not tracked
        holdings.append(
            InstitutionalHolding(
                cik=cik,
                filer_name=filer_name,
                cusip=cusip,
                ticker=ticker,
                report_period=report_period,
                filed_date=filed_date,
                shares=shares,
                value_usd=value_usd,
            )
        )
    return holdings


def fetch_institutional_holdings(client: EdgarClient, cusip_to_ticker: dict[str, str]) -> list[InstitutionalHolding]:
    """Fetches recent 13F holdings for the curated TRACKED_FILERS cohort,
    filtered to CUSIPs present in cusip_to_ticker (the watchlist-scoped
    mapping) -- a 13F infotable lists a filer's entire portfolio, most of
    which is outside our scope."""
    all_holdings: list[InstitutionalHolding] = []
    for cik, filer_name in TRACKED_FILERS.items():
        for filing in _recent_13f_filings(client, cik):
            accession_nodash = filing["accessionNumber"].replace("-", "")
            document = _find_infotable_document(client, int(cik), accession_nodash)
            if document is None:
                continue
            try:
                xml_text = client.get(
                    _DOC_URL.format(cik_int=int(cik), accession_nodash=accession_nodash, document=document)
                ).text
                filed_date = date.fromisoformat(filing["filingDate"])
                report_period = date.fromisoformat(filing["reportDate"]) if filing.get("reportDate") else filed_date
                all_holdings.extend(
                    _parse_infotable_xml(xml_text, cik, filer_name, report_period, filed_date, cusip_to_ticker)
                )
            except (requests.RequestException, ET.ParseError):
                continue
    return all_holdings
