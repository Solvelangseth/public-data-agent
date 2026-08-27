"""Write a table, lineage file, and chart from derived rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from methods.types import YOY_GROWTH, YOY_GROWTH_FORMULA, SeriesRow


def emit(rows: tuple[SeriesRow, ...], out_dir: Path) -> dict[str, Path]:
    """Persist CSV, markdown, lineage JSON, and a PNG chart next to each other."""

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": out_dir / "table.csv",
        "markdown": out_dir / "table.md",
        "lineage": out_dir / "lineage.json",
        "chart": out_dir / "chart.png",
    }
    _write_csv(rows, paths["csv"])
    _write_markdown(rows, paths["markdown"])
    _write_lineage(rows, paths["lineage"])
    _write_chart(rows, paths["chart"])
    return paths


def _write_csv(rows: tuple[SeriesRow, ...], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "entity",
                "period",
                "measure",
                "value",
                "yoy_growth",
                "observation_id",
                "source",
            ],
        )
        writer.writeheader()
        for row in rows:
            obs = row.observation
            writer.writerow(
                {
                    "entity": obs.entity,
                    "period": obs.period,
                    "measure": obs.measure,
                    "value": _number(obs.value),
                    "yoy_growth": _number(row.yoy_growth.value),
                    "observation_id": obs.id,
                    "source": obs.source,
                }
            )


def _write_markdown(rows: tuple[SeriesRow, ...], path: Path) -> None:
    lines = [
        "# Methods table",
        "",
        f"Derived column `{YOY_GROWTH}` uses `{YOY_GROWTH_FORMULA}`.",
        "The first period has no rate. Values are stored observations, not guesses.",
        "Percent in the last column is display-only: `100 × yoy_growth`.",
        "",
        "| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | observation_id | source |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        obs = row.observation
        rate = row.yoy_growth.value
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(obs.entity),
                    _md(obs.period),
                    _md(obs.measure),
                    _number(obs.value),
                    _number(rate),
                    _percent(rate),
                    _md(obs.id),
                    _md(obs.source),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_lineage(rows: tuple[SeriesRow, ...], path: Path) -> None:
    payload = {
        "derived_columns": [
            {
                "name": YOY_GROWTH,
                "formula": YOY_GROWTH_FORMULA,
                "input_columns": ["value"],
                "units": "ratio",
                "rows": [_lineage_row(row) for row in rows],
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _lineage_row(row: SeriesRow) -> dict[str, object]:
    obs = row.observation
    item = row.yoy_growth.to_dict()
    item.update(
        {
            "entity": obs.entity,
            "period": obs.period,
            "measure": obs.measure,
            "observation_id": obs.id,
        }
    )
    return item


def _write_chart(rows: tuple[SeriesRow, ...], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("no rows to chart")
    periods = [row.observation.period for row in rows]
    values = [row.observation.value for row in rows]
    rates = [row.yoy_growth.value for row in rows]
    xs = list(range(len(rows)))
    entity = rows[0].observation.entity
    measure = rows[0].observation.measure

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(xs, values, color="#1f4e79", marker="o", linewidth=2, label="value")
    ax.set_xticks(xs, periods)
    ax.set_ylabel("value")
    ax.set_xlabel("period")
    ax.set_title(f"{entity}\n{measure}")
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)

    ax2 = ax.twinx()
    pct = [None if rate is None else rate * 100 for rate in rates]
    ax2.plot(
        xs,
        [point if point is not None else float("nan") for point in pct],
        color="#c45911",
        marker="s",
        linewidth=1.5,
        linestyle="--",
        label="yoy_growth × 100",
    )
    ax2.set_ylabel("yoy_growth × 100")

    for x, value, rate in zip(xs, values, rates):
        if rate is None:
            continue
        ax.annotate(
            f"{rate * 100:+.2f}",
            (x, value),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=8,
            color="#c45911",
        )

    fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.88))
    fig.text(
        0.5,
        0.01,
        f"Growth is {YOY_GROWTH_FORMULA}. First period is undefined. "
        "Numbers come from stored observations or that formula.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _number(value: float | None) -> str:
    if value is None:
        return ""
    if value == int(value) and abs(value) < 1e12:
        return str(int(value))
    return f"{value:.10g}"


def _percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.4g}"


def _md(value: str) -> str:
    return value.replace("|", "\\|")
