import json
from datetime import date
from pathlib import Path

import pandas as pd


def render_markdown(run_date: date, signals: pd.DataFrame) -> str:
    lines = [f"# Trading Signals — {run_date.isoformat()}", ""]
    if signals.empty:
        lines.append("No signals generated (insufficient data or no scores above threshold).")
        return "\n".join(lines) + "\n"

    lines.append("| Rank | Ticker | Direction | Score |")
    lines.append("|------|--------|-----------|-------|")
    for _, row in signals.iterrows():
        lines.append(f"| {row['rank']} | {row['ticker']} | {row['direction']} | {row['score']:.3f} |")
    lines.append("")
    lines.append("## Details")
    for _, row in signals.iterrows():
        lines.append(f"### {row['ticker']} (score {row['score']:.3f}, {row['direction']})")
        for strategy_name, component in row["components"].items():
            lines.append(f"- **{strategy_name}**: {component}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_json(run_date: date, signals: pd.DataFrame) -> str:
    payload = {
        "run_date": run_date.isoformat(),
        "signals": signals.to_dict("records") if not signals.empty else [],
    }
    return json.dumps(payload, indent=2, default=str)


def write_report(run_date: date, signals: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / f"{run_date.isoformat()}.md"
    json_path = output_dir / f"{run_date.isoformat()}.json"
    md_path.write_text(render_markdown(run_date, signals))
    json_path.write_text(render_json(run_date, signals))
    return md_path, json_path
