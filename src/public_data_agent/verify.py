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

from public_data_agent.fetch import can_fetch_access_path, fetch_observations
from public_data_agent.registry import Registry, utc_now

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
    # Probed without a period bound, because the resource records no period
    # field. NVDB road objects are not a time series and every one of a sample
    # of 100 was skipped while this counted as a reason not to probe.
    no_period: int = 0
    # Verified with one value pinned per dimension, and verified only after
    # dropping that selection, which a resource holding no cell for the
    # combination needs.
    narrowed: int = 0
    retried_wide: int = 0
    # Capabilities written because a discovery probe returned cells.
    declared: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "probed": self.probed,
            "verified": self.verified,
            "too_large": self.too_large,
            "failed": self.failed,
            "probed_without_period": self.no_period,
            "narrowed": self.narrowed,
            "retried_without_selection": self.retried_wide,
            "capabilities_declared": self.declared,
            # Capped: a report is for reading, and one broken source would
            # otherwise bury every other line in it.
            "errors": self.errors[:20],
        }


def _is_too_large(message: str) -> bool:
    """Whether a failure says the answer is too big rather than unavailable."""

    if "cell budget" in message and "over the" in message:
        return True
    # The source's own limit, e.g. SSB answering "selection is 174,636,000
    # cells, over the 800,000 limit for table ...".
    return "SelectionTooLarge" in message or "over the 800,000 limit" in message


def latest_period_year(
    registry: Registry, dataset_id: str, *, this_year: int | None = None
) -> int | None:
    """A year the resource's own period fields publish, preferring a past one.

    Read from the resource index rather than assumed, because a table that
    ended in 2010 answers a request for 2024 with nothing and that looks
    exactly like a capability that does not work.

    The newest year is not always the right one to ask for. A projection table
    carries two period fields -- fhi:nokkel:171 has a base year with one value
    and 25 projection years out to 2050 -- and a fetch filters the base year,
    so asking for 2050 is refused by a table that works. The newest year that
    has actually happened is the one that exists in both.
    """

    if this_year is None:
        from datetime import datetime, timezone

        this_year = datetime.now(timezone.utc).year
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
    if not years:
        return None
    past = [year for year in years if year <= this_year]
    # A table that only holds future periods is still asked for its earliest,
    # which is the one most likely to be populated.
    return max(past) if past else min(years)


def narrowing_measure(registry: Registry, dataset_id: str) -> str | None:
    """One measure code the resource publishes, to narrow a probe.

    A period bound alone does not make a statistical table small: with a
    200-cell budget, 52 of 100 single-year SSB probes still answered with more.
    One measure of one year usually fits.
    """

    row = registry.conn.execute(
        "SELECT v.value_code FROM resource_field_values v "
        "JOIN resource_fields f ON f.dataset_id = v.dataset_id "
        "AND f.field_code = v.field_code "
        "WHERE v.dataset_id = ? AND f.field_role = 'measure' "
        "ORDER BY v.value_code LIMIT 1",
        (dataset_id,),
    ).fetchone()
    return row[0] if row else None


def narrowing_select(registry: Registry, dataset_id: str) -> dict[str, list[str]]:
    """One value of every dimension that is neither the period nor the measure.

    A probe of one measure in one year is still the whole cross-product of
    everything else: 11418 is sex x sector x occupation x working hours, which
    is thousands of cells. Pinning one value of each brings the same table to
    seven, which is what makes verifying thousands of resources affordable.
    """

    select: dict[str, list[str]] = {}
    for (code,) in registry.conn.execute(
        "SELECT field_code FROM resource_fields WHERE dataset_id = ? "
        "AND field_role NOT IN ('period', 'measure') ORDER BY position",
        (dataset_id,),
    ):
        row = registry.conn.execute(
            "SELECT value_code FROM resource_field_values "
            "WHERE dataset_id = ? AND field_code = ? ORDER BY value_code LIMIT 1",
            (dataset_id, code),
        ).fetchone()
        if row and row[0]:
            select[code] = [row[0]]
    return select


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


def discoverable(registry: Registry, *, source: str | None = None) -> list[tuple[str, str]]:
    """Datasets a connector can fetch that have never declared a capability.

    3,232 of them on 2026-10-03. Nothing is wrong with these: no fetch has
    been tried, so the registry does not know they answer anything, and the
    lane that returns data leaves them out.
    """

    sql = (
        "SELECT d.id, d.source_id, d.access_path FROM datasets d "
        "WHERE NOT EXISTS (SELECT 1 FROM resource_capability c WHERE c.dataset_id = d.id)"
    )
    params: tuple[Any, ...] = ()
    if source:
        sql += " AND d.source_id = ?"
        params = (source,)
    return [
        (row[0], row[1])
        for row in registry.conn.execute(sql + " ORDER BY d.id", params)
        if can_fetch_access_path(row[2])
    ]


def record_discovered(registry: Registry, dataset_id: str, result: Any) -> bool:
    """Write the capability a successful fetch just demonstrated.

    Some fetch branches store cells without recording a capability --
    `_fetch_kikommuner` is one, and kikommuner:3419 held an observation and no
    capability because of it. The evidence is the cells that came back, so the
    count travels with the record and nothing is written when none did.
    """

    cells = getattr(result, "counts", None)
    returned = getattr(cells, "listed", 0) or 0
    if returned <= 0:
        return False
    if registry.get_capability(dataset_id):
        return False
    registry.set_capability(dataset_id, {
        "capability": "observations",
        "record_kind": "observation",
        "endpoint": (registry.get_dataset(dataset_id) or {}).get("access_path"),
        "verified_at": utc_now(),
        "verified_sample_count": returned,
    })
    return True


def verify_capabilities(
    registry: Registry,
    *,
    source: str | None = None,
    sample: int | None = None,
    max_cells: int = DEFAULT_MAX_CELLS,
    seed: int = 0,
    discover: bool = False,
    progress: Any | None = None,
) -> VerifyCounts:
    """Fetch a bounded sample and record what happened.

    By default this confirms capabilities that are declared but unverified.
    With `discover`, it probes datasets a connector can fetch that declare no
    capability at all, and writes the one a successful fetch demonstrates.
    """

    candidates = (
        discoverable(registry, source=source) if discover
        else unverified(registry, source=source)
    )
    if sample is not None and sample < len(candidates):
        candidates = random.Random(seed).sample(candidates, sample)
        candidates.sort()
    counts = VerifyCounts()
    for dataset_id, source_id in candidates:
        counts.probed += 1
        year = latest_period_year(registry, dataset_id)
        if year is None:
            # Probe anyway: a resource without a period is not a resource
            # without data. The cell budget is what protects the disk.
            counts.no_period += 1
        measure = narrowing_measure(registry, dataset_id)
        select = narrowing_select(registry, dataset_id) or None

        def probe(selection: dict[str, list[str]] | None) -> Any:
            return fetch_observations(
                registry, dataset_id, table_id="",
                from_year=year, to_year=year, measure=measure,
                select=selection, max_cells=max_cells,
            )

        error: Exception | None = None
        try:
            result = probe(select)
            counts.verified += 1
            if select:
                counts.narrowed += 1
            if discover and record_discovered(registry, dataset_id, result):
                counts.declared += 1
        except Exception as narrow_error:
            if select is None:
                error = narrow_error
            else:
                # One value of each dimension can be a combination the
                # resource holds no cell for, which is not the same as a
                # resource that cannot be fetched. Ask once more without it.
                try:
                    result = probe(None)
                    counts.verified += 1
                    counts.retried_wide += 1
                    if discover and record_discovered(registry, dataset_id, result):
                        counts.declared += 1
                except Exception as wide_error:
                    error = wide_error

        if error is not None:
            message = f"{type(error).__name__}: {error}"
            # Two different sizes, neither a broken capability: more cells than
            # this probe will store, and more than the source itself will
            # serve in one request. Both mean "narrow the selection".
            if _is_too_large(message):
                counts.too_large += 1
            else:
                counts.failed += 1
                counts.errors.append({"dataset": dataset_id, "error": message[:200]})
        if progress is not None:
            progress(f"  {counts.probed}/{len(candidates)} {source_id}")
    return counts
