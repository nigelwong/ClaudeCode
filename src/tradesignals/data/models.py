from datetime import date

from pydantic import BaseModel


class Bar(BaseModel):
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float


class InstitutionalHolding(BaseModel):
    cik: str
    filer_name: str
    cusip: str
    ticker: str | None
    report_period: date
    filed_date: date
    shares: int
    value_usd: int


class InsiderTransaction(BaseModel):
    cik: str
    ticker: str
    insider_name: str
    insider_title: str | None = None
    transaction_date: date
    filed_date: date
    transaction_code: str
    shares: float
    price: float | None = None
    shares_owned_after: float | None = None
