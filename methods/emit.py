"""Write a table, lineage file, and chart from derived rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from methods.types import (
    INDEX,
    INDEX_FORMULA,
    PERIOD_CHANGE,
    PERIOD_CHANGE_FORMULA,
    PERIOD_CHANGE_INPUTS,
    PERIOD_CHANGE_UNITS,
    RANK,
    RANK_CHANGE,
    RANK_CHANGE_FORMULA,
    RANK_FORMULA,
    YOY_GROWTH,
    YOY_GROWTH_FORMULA,
    DerivedValue,
    SeriesRow,
)


def yoy_bar_points(rows: tuple[SeriesRow, ...]) -> tuple[tuple[str, float], ...]:
    """Periods that have a derived YoY rate."""

    return tuple(
        (row.observation.period, row.yoy_growth.value)
        for row in rows
        if row.yoy_growth.value is not None
    )


def index_line_series(
    rows: tuple[SeriesRow, ...],
) -> tuple[tuple[str, str, tuple[tuple[str, float], ...]], ...]:
    """Derived index points grouped by (entity, measure). Null index is omitted."""

    groups: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for row in rows:
        if row.index.value is None:
            continue
        key = (row.observation.entity, row.observation.measure)
        groups.setdefault(key, []).append((row.observation.period, row.index.value))
    return tuple((entity, measure, tuple(points)) for (entity, measure), points in sorted(groups.items()))


def emit(rows: tuple[SeriesRow, ...], out_dir: Path) -> dict[str, Path]:
    """Persist CSV, markdown, lineage JSON, and PNG charts next to each other."""

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": out_dir / "table.csv",
        "markdown": out_dir / "table.md",
        "lineage": out_dir / "lineage.json",
        "chart": out_dir / "chart.png",
        "index_line": out_dir / "index_line.png",
    }
    if yoy_bar_points(rows):
        paths["yoy_bar"] = out_dir / "yoy_bar.png"
    _write_csv(rows, paths["csv"])
    _write_markdown(rows, paths["markdown"])
    _write_lineage(rows, paths["lineage"])
    _write_chart(rows, paths["chart"])
    if "yoy_bar" in paths:
        _write_yoy_bar(rows, paths["yoy_bar"])
    _write_index_line(rows, paths["index_line"])
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
                "period_change",
                "index",
                "rank",
                "rank_change",
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
                    "period_change": _number(row.period_change.value),
                    "index": _number(row.index.value),
                    "rank": _number(row.rank.value),
                    "rank_change": _number(row.rank_change.value),
                    "observation_id": obs.id,
                    "source": obs.source,
                }
            )


def _write_markdown(rows: tuple[SeriesRow, ...], path: Path) -> None:
    lines = [
        "# Methods table",
        "",
        f"Derived column `{YOY_GROWTH}` uses `{YOY_GROWTH_FORMULA}` for adjacent calendar years.",
        f"Derived column `{PERIOD_CHANGE}` uses `{PERIOD_CHANGE_FORMULA}` for other stored steps.",
        "`period_change` describes the stored step. It is not a one-year rate.",
        f"Derived column `{INDEX}` uses `{INDEX_FORMULA}`. The base row is exactly 100.",
        f"Derived column `{RANK}` uses `{RANK_FORMULA}`. 1 is the highest value in `(period, measure)`.",
        "Ties share the minimum (competition) rank; the next rank skips.",
        f"Derived column `{RANK_CHANGE}` uses `{RANK_CHANGE_FORMULA}`. Positive means moved up.",
        "The first period has no prior-period rate and no rank_change. A missing or zero base leaves index undefined.",
        "Values are stored observations, not guesses.",
        "Percent next to yoy_growth is display-only: `100 × yoy_growth`.",
        "",
        "| entity | period | measure | value | yoy_growth (ratio) | yoy_growth × 100 | period_change (ratio) | index | rank | rank_change | observation_id | source |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
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
                    _number(row.period_change.value),
                    _number(row.index.value),
                    _number(row.rank.value),
                    _number(row.rank_change.value),
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
                "rows": [_lineage_row(row, row.yoy_growth) for row in rows],
            },
            {
                "name": PERIOD_CHANGE,
                "formula": PERIOD_CHANGE_FORMULA,
                "input_columns": list(PERIOD_CHANGE_INPUTS),
                "units": PERIOD_CHANGE_UNITS,
                "rows": [_lineage_row(row, row.period_change) for row in rows],
            },
            {
                "name": INDEX,
                "formula": INDEX_FORMULA,
                "input_columns": ["value"],
                "units": "index (base = 100)",
                "rows": [_lineage_row(row, row.index) for row in rows],
            },
            {
                "name": RANK,
                "formula": RANK_FORMULA,
                "input_columns": ["value"],
                "units": "rank (1 = highest)",
                "rows": [_lineage_row(row, row.rank) for row in rows],
            },
            {
                "name": RANK_CHANGE,
                "formula": RANK_CHANGE_FORMULA,
                "input_columns": ["rank"],
                "units": "rank positions (positive = moved up)",
                "rows": [_lineage_row(row, row.rank_change) for row in rows],
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _lineage_row(row: SeriesRow, derived: DerivedValue) -> dict[str, object]:
    obs = row.observation
    item = derived.to_dict()
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
    entity = rows[0].observation.entity
    measure = rows[0].observation.measure
    series = tuple(
        row
        for row in rows
        if row.observation.entity == entity and row.observation.measure == measure
    )
    periods = [row.observation.period for row in series]
    values = [row.observation.value for row in series]
    rates = [row.yoy_growth.value for row in series]
    xs = list(range(len(series)))

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


def _write_yoy_bar(rows: tuple[SeriesRow, ...], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    points = yoy_bar_points(rows)
    if not points:
        raise ValueError("no derived yoy_growth values to chart")
    periods = [period for period, _rate in points]
    rates = [rate for _period, rate in points]
    xs = list(range(len(points)))
    entity = rows[0].observation.entity
    measure = rows[0].observation.measure

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(xs, [rate * 100 for rate in rates], color="#c45911", width=0.6)
    ax.set_xticks(xs, periods)
    ax.set_ylabel("yoy_growth × 100")
    ax.set_xlabel("period")
    ax.set_title(f"{entity} — {measure}\n{YOY_GROWTH} = {YOY_GROWTH_FORMULA}")
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)
    for x, rate in zip(xs, rates):
        ax.annotate(
            f"{rate * 100:+.2f}",
            (x, rate * 100),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            fontsize=8,
        )
    fig.text(
        0.5,
        0.01,
        f"Bars are the derived `{YOY_GROWTH}` column ({YOY_GROWTH_FORMULA}). "
        "The first period has no bar. Rates are not invented.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _write_index_line(rows: tuple[SeriesRow, ...], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = index_line_series(rows)
    if not series:
        raise ValueError("no derived index values to chart")
    periods = sorted({period for _entity, _measure, points in series for period, _value in points})
    xs = {period: index for index, period in enumerate(periods)}
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for entity, measure, points in series:
        label = entity if len({item[1] for item in series}) == 1 else f"{entity} — {measure}"
        ax.plot(
            [xs[period] for period, _value in points],
            [value for _period, value in points],
            marker="o",
            linewidth=2,
            label=label,
        )
    ax.set_xticks(list(range(len(periods))), periods)
    ax.set_ylabel(INDEX)
    ax.set_xlabel("period")
    ax.axhline(100, color="#666666", linewidth=0.8, linestyle=":")
    ax.set_title(f"{INDEX} = {INDEX_FORMULA}")
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)
    if len(series) > 1:
        ax.legend()
    fig.text(
        0.5,
        0.01,
        f"Lines are the derived `{INDEX}` column ({INDEX_FORMULA}). "
        "Each (entity, measure) series has its own base. Values are not invented.",
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
