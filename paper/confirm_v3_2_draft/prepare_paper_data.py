#!/usr/bin/env python3
"""Build small, auditable CSV inputs for the LaTeX paper from frozen results."""

from __future__ import annotations

import csv
import json
import math
import statistics
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = HERE / "data"

COMPARISON_JSON = (
    ROOT
    / "user_data/research/volatility_vs_v32_full_history/report/comparison_data.json"
)

ARCHIVES = {
    "V2": ROOT
    / "user_data/backtest_results/backtest-result-2026-09-02_09-42-00.zip",
    "V3.0": ROOT
    / "user_data/backtest_results/backtest-result-2026-09-02_09-42-00.zip",
    "V3.1": ROOT
    / "user_data/backtest_results/backtest-result-2026-09-02_11-32-11.zip",
    "V3.2": ROOT
    / "user_data/backtest_results/backtest-result-2026-09-03_06-10-14.zip",
}

STRATEGY_KEYS = {
    "V2": "confirm_v2_BTC",
    "V3.0": "confirm_v3_BTC",
    "V3.1": "confirm_v3_1_BTC",
    "V3.2": "confirm_v3_2_BTC",
}


def write_csv(name: str, fieldnames: list[str], rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_archive(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        result_name = next(
            name
            for name in archive.namelist()
            if name.endswith(".json") and not name.endswith("_config.json")
        )
        return json.loads(archive.read(result_name))


def entry_count(trade: dict) -> int:
    return sum(1 for order in trade["orders"] if order.get("ft_is_entry"))


def group_stats(trades: list[dict]) -> dict:
    gross_profit = sum(t["profit_abs"] for t in trades if t["profit_abs"] > 0)
    gross_loss = -sum(t["profit_abs"] for t in trades if t["profit_abs"] < 0)
    return {
        "count": len(trades),
        "profit_abs": sum(t["profit_abs"] for t in trades),
        "mean_pct": 100 * sum(t["profit_ratio"] for t in trades) / len(trades),
        "profit_factor": gross_profit / gross_loss if gross_loss else 0,
    }


def build_comparison_curves(comparison: dict) -> None:
    baseline = comparison["strategies"]["VolatilitySystem"]
    final = comparison["strategies"]["confirm_v3_2_BTC"]
    benchmark = comparison["benchmark"]

    equity_rows = []
    drawdown_rows = []
    for base_point, final_point, bench_point in zip(
        baseline["curve"], final["curve"], benchmark["curve"], strict=True
    ):
        assert base_point["date"] == final_point["date"] == bench_point["date"]
        equity_rows.append(
            {
                "date": f'{base_point["date"]}-01',
                "volatility": f'{base_point["equity"]:.6f}',
                "confirm_v32": f'{final_point["equity"]:.6f}',
                "buy_hold": f'{bench_point["equity"]:.6f}',
            }
        )
        drawdown_rows.append(
            {
                "date": f'{base_point["date"]}-01',
                "volatility": f'{base_point["drawdownPct"]:.6f}',
                "confirm_v32": f'{final_point["drawdownPct"]:.6f}',
                "buy_hold": f'{bench_point["drawdownPct"]:.6f}',
            }
        )

    write_csv(
        "equity_curves.csv",
        ["date", "volatility", "confirm_v32", "buy_hold"],
        equity_rows,
    )
    write_csv(
        "drawdown_curves.csv",
        ["date", "volatility", "confirm_v32", "buy_hold"],
        drawdown_rows,
    )

    path_metric_rows = []
    for label, source in (("Original", baseline), ("V3.2", final)):
        equities = [float(point["equity"]) for point in source["curve"]]
        monthly_returns = [
            equities[index] / equities[index - 1] - 1
            for index in range(1, len(equities))
        ]
        path_metric_rows.append(
            {
                "strategy": label,
                "monthly_return_observations": len(monthly_returns),
                "annualized_monthly_vol_pct": (
                    f"{100 * math.sqrt(12) * statistics.stdev(monthly_returns):.6f}"
                ),
                "monthly_downside_deviation_pct": (
                    f"{100 * math.sqrt(sum(min(value, 0) ** 2 for value in monthly_returns) / len(monthly_returns)):.6f}"
                ),
            }
        )
    write_csv(
        "path_risk_metrics.csv",
        [
            "strategy",
            "monthly_return_observations",
            "annualized_monthly_vol_pct",
            "monthly_downside_deviation_pct",
        ],
        path_metric_rows,
    )

    yearly_by_name = {
        "volatility": {row["year"]: row for row in baseline["yearly"]},
        "confirm_v32": {row["year"]: row for row in final["yearly"]},
        "buy_hold": {row["year"]: row for row in benchmark["yearly"]},
    }
    years = sorted(yearly_by_name["volatility"])
    rows = []
    for year in years:
        rows.append(
            {
                "year": year,
                "volatility": f'{yearly_by_name["volatility"][year]["returnPct"]:.6f}',
                "confirm_v32": f'{yearly_by_name["confirm_v32"][year]["returnPct"]:.6f}',
                "buy_hold": f'{yearly_by_name["buy_hold"][year]["returnPct"]:.6f}',
            }
        )
    write_csv(
        "yearly_returns.csv",
        ["year", "volatility", "confirm_v32", "buy_hold"],
        rows,
    )

    exit_rows = []
    for label, source in (("Original", baseline), ("V3.2", final)):
        for row in source["exits"]:
            exit_rows.append(
                {
                    "strategy": label,
                    "reason": row["reason"],
                    "trades": row["trades"],
                    "profit_abs": f'{row["profitAbs"]:.6f}',
                }
            )
    write_csv(
        "exit_contributions.csv",
        ["strategy", "reason", "trades", "profit_abs"],
        exit_rows,
    )


def build_version_metrics() -> None:
    archive_cache: dict[Path, dict] = {}
    rows = []
    mechanism_rows = []
    for label in ("V2", "V3.0", "V3.1", "V3.2"):
        path = ARCHIVES[label]
        archive_cache.setdefault(path, read_archive(path))
        stats = archive_cache[path]["strategy"][STRATEGY_KEYS[label]]
        trades = stats["trades"]
        winners = sorted(
            (trade["profit_abs"] for trade in trades if trade["profit_abs"] > 0),
            reverse=True,
        )
        gross_profit = sum(winners)
        force_exits = [t for t in trades if t["exit_reason"] == "force_exit"]
        rows.append(
            {
                "version": label,
                "trades": stats["total_trades"],
                "profit_abs": f'{stats["profit_total_abs"]:.6f}',
                "profit_pct": f'{100 * stats["profit_total"]:.6f}',
                "cagr_pct": f'{100 * stats["cagr"]:.6f}',
                "profit_factor": f'{stats["profit_factor"]:.6f}',
                "mean_trade_pct": f'{100 * stats["profit_mean"]:.6f}',
                "max_drawdown_pct": f'{100 * stats["max_relative_drawdown"]:.6f}',
                "legacy_account_dd_pct": f'{100 * stats["max_drawdown_account"]:.6f}',
                "cagr_drawdown": f'{stats["cagr"] / stats["max_relative_drawdown"]:.6f}',
                "force_exit_trades": len(force_exits),
                "top10_gross_profit_pct": f'{100 * sum(winners[:10]) / gross_profit:.6f}',
            }
        )

        if label in {"V3.0", "V3.1", "V3.2"}:
            scout = [trade for trade in trades if entry_count(trade) == 1]
            confirmed = [trade for trade in trades if entry_count(trade) > 1]
            for group_name, group in (("Scout", scout), ("Confirmed", confirmed)):
                group_result = group_stats(group)
                mechanism_rows.append(
                    {
                        "version": label,
                        "group": group_name,
                        **{
                            key: f"{value:.6f}" if isinstance(value, float) else value
                            for key, value in group_result.items()
                        },
                    }
                )

    write_csv(
        "version_metrics.csv",
        [
            "version",
            "trades",
            "profit_abs",
            "profit_pct",
            "cagr_pct",
            "profit_factor",
            "mean_trade_pct",
            "max_drawdown_pct",
            "legacy_account_dd_pct",
            "cagr_drawdown",
            "force_exit_trades",
            "top10_gross_profit_pct",
        ],
        rows,
    )
    write_csv(
        "confirmation_mechanism.csv",
        ["version", "group", "count", "profit_abs", "mean_pct", "profit_factor"],
        mechanism_rows,
    )


def build_small_declared_datasets() -> None:
    write_csv(
        "bear_window.csv",
        ["object", "return_pct", "max_drawdown_pct"],
        [
            {"object": "BTC", "return_pct": "-76.34", "max_drawdown_pct": "77.23"},
            {"object": "Original", "return_pct": "64.66", "max_drawdown_pct": "19.55"},
            {"object": "V3.2", "return_pct": "24.55", "max_drawdown_pct": "6.33"},
        ],
    )
    write_csv(
        "bootstrap_probabilities.csv",
        ["comparison", "train", "check1", "check2"],
        [
            {"comparison": "V3-V2", "train": "0.660", "check1": "0.530", "check2": "0.449"},
            {"comparison": "V31-V3", "train": "0.482", "check1": "0.933", "check2": "0.517"},
            {"comparison": "V32-V31", "train": "0.708", "check1": "0.529", "check2": "0.128"},
        ],
    )
    write_csv(
        "trail_platform.csv",
        ["multiplier", "return_pct", "profit_factor", "drawdown_pct", "legacy_ratio"],
        [
            {"multiplier": "3.7", "return_pct": "13.54", "profit_factor": "1.50", "drawdown_pct": "10.23", "legacy_ratio": "1.323"},
            {"multiplier": "4.3", "return_pct": "10.95", "profit_factor": "1.41", "drawdown_pct": "10.83", "legacy_ratio": "1.011"},
            {"multiplier": "4.5", "return_pct": "10.37", "profit_factor": "1.385", "drawdown_pct": "11.05", "legacy_ratio": "0.939"},
            {"multiplier": "4.7", "return_pct": "9.37", "profit_factor": "1.35", "drawdown_pct": "11.26", "legacy_ratio": "0.832"},
            {"multiplier": "5.0", "return_pct": "8.20", "profit_factor": "1.30", "drawdown_pct": "11.35", "legacy_ratio": "0.723"},
        ],
    )


def main() -> None:
    comparison = json.loads(COMPARISON_JSON.read_text(encoding="utf-8"))
    build_comparison_curves(comparison)
    build_version_metrics()
    build_small_declared_datasets()
    print(f"Wrote paper data to {DATA_DIR}")


if __name__ == "__main__":
    main()
