import json
from pathlib import Path

from tradesignals.regime.composite import MarketOutlook


def render_markdown(outlook: MarketOutlook) -> str:
    lines = [
        f"# Market Outlook — {outlook.as_of_date.isoformat()}",
        "",
        f"## Overall Regime: {outlook.overall_regime.value.upper()}",
        "",
        "| Signal | Value |",
        "|--------|-------|",
        f"| Trend | {outlook.trend.value} |",
        f"| Breadth | {outlook.breadth:.1%} |",
        f"| Volatility | {outlook.volatility.value} |",
        f"| Yield curve inverted | {'Yes' if outlook.details.get('yield_curve_inverted') else 'No'} |",
        f"| Risk tilt | {outlook.risk_tilt.value} |",
        "",
        "## Sector Rotation",
    ]
    if outlook.sector_tiers:
        lines.append("| Ticker | Tier |")
        lines.append("|--------|------|")
        for ticker, tier in outlook.sector_tiers.items():
            lines.append(f"| {ticker} | {tier.value} |")
    else:
        lines.append("No sector data available.")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_json(outlook: MarketOutlook) -> str:
    payload = {
        "as_of_date": outlook.as_of_date.isoformat(),
        "overall_regime": outlook.overall_regime.value,
        "trend": outlook.trend.value,
        "breadth": outlook.breadth,
        "volatility": outlook.volatility.value,
        "risk_tilt": outlook.risk_tilt.value,
        "sector_tiers": {ticker: tier.value for ticker, tier in outlook.sector_tiers.items()},
        "details": outlook.details,
    }
    return json.dumps(payload, indent=2, default=str)


def write_report(outlook: MarketOutlook, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"outlook-{outlook.as_of_date.isoformat()}.md"
    json_path = output_dir / f"outlook-{outlook.as_of_date.isoformat()}.json"
    md_path.write_text(render_markdown(outlook))
    json_path.write_text(render_json(outlook))
    return md_path, json_path
