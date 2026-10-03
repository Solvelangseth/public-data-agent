"""Check whether a declared fetch capability actually fetches.

A capability read from published metadata is a claim; one with `verified_at`
and a sample count is evidence. On 2026-10-03, 5,157 datasets declared a
capability and 578 were verified, so most of the registry's fetchability was
unproven. A sample of 122 then fetched 118 successfully -- the claims were
good -- but the probes wrote 1.73 million cells doing it, because a request
bounded only by a year is not bounded at all.

So a probe here asks for one period, the latest the resource itself publishes,
under a cell budget. Over the budget nothing is stored and the resource is
reported as needing a narrower selection, which is a different answer from a
capability that does not work.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from public_data_agent.fetch import fetch_observations
from public_data_agent.registry import Registry

# Enough cells to prove a fetch returns data, small enough that verifying
# thousands of resources does not fill a disk.
DEFAULT_MAX_CELLS = 200
YEAR = re.compile(r"(?:19|20)\d{2}")


@dataclass
class VerifyCounts:
    probed: int = 0
    verified: int = 0
    too_large: int = 0
    failed: int = 0
    no_period: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "probed": self.probed,
            "verified": self.verified,
            "too_large": self.too_large,
            "failed": self.failed,
            "no_period": self.no_period,
            # Capped: a report is for reading, and one broken source would
            # otherwise bury every other line in it.
            "errors": self.errors[:20],
        }


def latest_period_year(registry: Registry, dataset_id: str) -> int | None:
    """The newest year the resource's own period field publishes.

    Read from the resource index rather than assumed, because a table that
    ended in 2010 answers a request for 2024 with nothing and that looks
    exactly like a capability that does not work.
    """

    years: list[int] = []
    for (label,) in registry.conn.execute(
        "SELECT v.value_label FROM resource_field_values v "
        "JOIN resource_fields f ON f.dataset_id = v.dataset_id "
        "AND f.field_code = v.field_code "
        "WHERE v.dataset_id = ? AND f.field_role = 'period'",
        (dataset_id,),
    ):
        found = YEAR.search(label or "")
        if found:
            years.append(int(found.group(0)))
    return max(years) if years else None


def unverified(registry: Registry, *, source: str | None = None) -> list[tuple[str, str]]:
    """Datasets that declare a capability nothing has ever verified."""

    sql = (
        "SELECT d.id, d.source_id FROM datasets d "
        "JOIN resource_capability c ON c.dataset_id = d.id "
        "WHERE c.verified_at IS NULL"
    )
    params: tuple[Any, ...] = ()
    if source:
        sql += " AND d.source_id = ?"
        params = (source,)
    return [(row[0], row[1]) for row in registry.conn.execute(sql + " ORDER BY d.id", params)]


def verify_capabilities(
    registry: Registry,
    *,
    source: str | None = None,
    sample: int | None = None,
    max_cells: int = DEFAULT_MAX_CELLS,
    seed: int = 0,
    progress: Any | None = None,
) -> VerifyCounts:
    """Fetch a bounded sample for unverified capabilities and record what happened."""

    candidates = unverified(registry, source=source)
    if sample is not None and sample < len(candidates):
        candidates = random.Random(seed).sample(candidates, sample)
        candidates.sort()
    counts = VerifyCounts()
    for dataset_id, source_id in candidates:
        counts.probed += 1
        year = latest_period_year(registry, dataset_id)
        if year is None:
            counts.no_period += 1
            continue
        try:
            fetch_observations(
                registry, dataset_id, table_id="",
                from_year=year, to_year=year, max_cells=max_cells,
            )
            counts.verified += 1
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            # Over the budget is not a broken capability: the resource answered,
            # with more than this probe is willing to store.
            if "over the" in message and "cell budget" in message:
                counts.too_large += 1
            else:
                counts.failed += 1
                counts.errors.append({"dataset": dataset_id, "error": message[:200]})
        if progress is not None:
            progress(f"  {counts.probed}/{len(candidates)} {source_id}")
    return counts
