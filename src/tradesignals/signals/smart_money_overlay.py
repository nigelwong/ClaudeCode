from tradesignals.signals.base import FundamentalData, ScoreComponents


def _institutional_score(ticker: str, holdings) -> ScoreComponents:
    ticker_holdings = holdings[holdings["ticker"] == ticker]
    if ticker_holdings.empty:
        return ScoreComponents(score=0.0)
    by_period = ticker_holdings.groupby("report_period")["shares"].sum().sort_index()
    if len(by_period) < 2:
        return ScoreComponents(score=0.0)
    prev, latest = by_period.iloc[-2], by_period.iloc[-1]
    if prev <= 0:
        return ScoreComponents(score=0.0)
    pct_change = (latest - prev) / prev
    score = max(-1.0, min(1.0, pct_change * 5))
    return ScoreComponents(score=score, details={"qoq_shares_change_pct": round(float(pct_change) * 100, 2)})


def _insider_score(ticker: str, transactions) -> ScoreComponents:
    ticker_txns = transactions[transactions["ticker"] == ticker]
    if ticker_txns.empty:
        return ScoreComponents(score=0.0)
    buys = ticker_txns.loc[ticker_txns["transaction_code"] == "P", "shares"].sum()
    sells = ticker_txns.loc[ticker_txns["transaction_code"] == "S", "shares"].sum()
    total = buys + sells
    if total <= 0:
        return ScoreComponents(score=0.0)
    score = max(-1.0, min(1.0, (buys - sells) / total))
    return ScoreComponents(score=score, details={"insider_buy_shares": float(buys), "insider_sell_shares": float(sells)})


def compute_overlay(ticker: str, fundamental_data: FundamentalData) -> ScoreComponents:
    """Smart-money tilt for one ticker: institutional accumulation (QoQ
    change in tracked-filer 13F shares) averaged with net insider buying
    (Form 4 open-market buys minus sales). Each sub-signal defaults to 0
    (neutral) when there isn't enough data, rather than skipping the
    ticker -- this is a tilt applied on top of technical scores, not a
    standalone strategy, so "no smart-money data" should mean "no opinion,"
    not "exclude this ticker.\""""
    institutional = _institutional_score(ticker, fundamental_data.institutional_holdings)
    insider = _insider_score(ticker, fundamental_data.insider_transactions)
    combined = (institutional.score + insider.score) / 2
    return ScoreComponents(
        score=combined,
        details={"institutional": institutional.details, "insider": insider.details},
    )


def compute_overlay_for_tickers(tickers: list[str], fundamental_data: FundamentalData) -> dict[str, ScoreComponents]:
    return {ticker: compute_overlay(ticker, fundamental_data) for ticker in tickers}
