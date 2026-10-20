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
    # Verifications written because a probe returned cells, either onto a
    # capability that had none or as a new row in discovery mode.
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
            "evidence_recorded": self.declared,
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


# What `records.kind` means as a capability. The two vocabularies are separate
# because one names a row and the other names a resource.
_KIND_CAPABILITY = {
    "observation": ("observations", "observation"),
    "entity": ("entities", "entity"),
    "feature": ("features", "feature"),
    "document": ("documents", "document"),
}

# A publisher's way of writing "no value here". A cell that carries one is still
# an observation, so an empty sample must not be read as a resource that
# publishes labels.
_EMPTY_VALUES = frozenset({"", ":", "..", ".", "-", "none", "null", "na"})

# A code list addresses a code and returns its label, and that is the whole of
# its shape. `Bydelsinndeling 2020` stores `Gamle Oslo` against
# `{"code": "030101", "level": "1"}`: join keys, not facts.
_CODE_LIST_DIMENSIONS = frozenset({
    "classification", "klassifikasjon",
    "code", "kode", "level", "nivaa", "nivå", "parent", "parentcode", "parent_code",
    "shortname", "kortnavn", "name", "navn", "notes", "validfrom", "validto",
    "valid_from", "valid_to", "gyldigfra", "gyldigtil",
})
# The measure a code list stores its label under when it has no classification
# title to use. GREP files every curriculum code this way.
_CODE_MEASURES = frozenset({"kode", "code", "codevalue", "kodeverdi"})

# A feature is a thing in a place, so a coordinate or a feature id is what
# separates one from a plain entity record.
_GEOMETRY_DIMENSIONS = frozenset({
    "lat", "latitude", "lon", "long", "longitude", "geometry", "geom", "wkt",
    "fid", "objectid", "east", "north", "easting", "northing", "utm_east", "utm_north",
})

# How many stored rows to read before deciding. The question is what kind of
# thing the resource returns, which the first rows answer as well as all of
# them, and reading all of them is a full scan per probed dataset.
_EVIDENCE_SAMPLE = 200


def _is_number(value: Any) -> bool:
    """Whether a stored value is a measurement rather than a label.

    Numbers arrive as JSON strings often enough that type alone misreads them:
    Norges Bank publishes the key policy rate as `"4.25"`, and reading that as a
    label would file an interest-rate series as a list of things.
    """

    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.strip().replace(",", ".").replace("\u00a0", "").replace(" ", ""))
        except ValueError:
            return False
        return True
    return False


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip().casefold() in _EMPTY_VALUES


def _is_code_list(registry: Registry, dataset_id: str) -> bool:
    """Whether a dataset's entity records are a vocabulary rather than things.

    Both shapes are entities -- a Klass item and a company are each a named
    thing with an identifier -- and what separates them is what else the
    publisher says about them. A code list says only where the code sits in its
    hierarchy and when it was valid; a register says what the thing is. So a
    record addressed by a code and carrying nothing but hierarchy and validity
    is a join key, and `lookup` is the capability that names that role.
    """

    rows = registry.conn.execute(
        "SELECT subject_code, subject_label, measure, value_json, attributes_json FROM records "
        "WHERE dataset_id = ? AND kind = 'entity' LIMIT ?",
        (dataset_id, _EVIDENCE_SAMPLE),
    ).fetchall()
    if not rows:
        return False
    import json as _json

    # A resource whose rows are all code and no name does not publish named
    # things, whatever else it attaches to them. Udir's curriculum vocabularies
    # are the case in point: every item carries a code, a status and a
    # modified date, and the title that would make it a thing sits in a nested
    # object the connector does not copy.
    if all(row["subject_code"] and not row["subject_label"] for row in rows):
        return True

    for row in rows:
        if not row["subject_code"] or row["measure"] or row["value_json"] is not None:
            return False
        try:
            attributes = _json.loads(row["attributes_json"] or "{}")
        except ValueError:
            return False
        if not isinstance(attributes, dict):
            return False
        keys = {str(key).strip().casefold() for key in attributes}
        if not keys <= _CODE_LIST_DIMENSIONS:
            return False
    return True


def demonstrated_capability(
    registry: Registry, dataset_id: str
) -> tuple[str, str | None] | None:
    """The capability the stored rows demonstrate, or None when nothing is stored.

    `record_evidence` used to write `observations` for every discovered
    resource, which recorded a claim no fetch had made. `crinst:1000` stores one
    cell -- `institution_name = "AOF Haugaland"` -- and was filed as an
    observation source, so an organisation's name card competed in the lane
    whose job is answering numeric questions. The fix is to read what came back:
    a resource returns what its rows are, not what the prober hoped for.

    The order is evidence first, shape second. A `records` row states its own
    kind, so it decides. Observation cells are judged by their values: one
    number anywhere makes the resource a measurement source, an all-empty
    sample stays one because a suppressed cell is still an observation, and a
    resource whose cells are all labels is a code list, a feature set or an
    entity record according to the dimensions it addresses them by.
    """

    kinds = registry.conn.execute(
        "SELECT kind, COUNT(*) AS n FROM records WHERE dataset_id = ? "
        "GROUP BY kind ORDER BY n DESC, kind",
        (dataset_id,),
    ).fetchall()
    if kinds:
        kind = kinds[0]["kind"]
        if kind == "entity" and _is_code_list(registry, dataset_id):
            return "lookup", "entity"
        mapped = _KIND_CAPABILITY.get(kind)
        if mapped is not None:
            return mapped

    rows = registry.conn.execute(
        "SELECT measure, value_json, dimensions_json FROM observations "
        "WHERE dataset_id = ? LIMIT ?",
        (dataset_id, _EVIDENCE_SAMPLE),
    ).fetchall()
    if not rows:
        return None

    import json as _json

    values: list[Any] = []
    measures: set[str] = set()
    dimensions: set[str] = set()
    for row in rows:
        raw = row["value_json"]
        try:
            values.append(_json.loads(raw) if raw is not None else None)
        except ValueError:
            values.append(raw)
        if row["measure"]:
            measures.add(str(row["measure"]).strip().casefold())
        try:
            parsed = _json.loads(row["dimensions_json"] or "{}")
        except ValueError:
            parsed = {}
        if isinstance(parsed, dict):
            dimensions.update(str(key).strip().casefold() for key in parsed)

    if any(_is_number(value) for value in values):
        return "observations", "observation"
    if all(_is_empty(value) for value in values):
        return "observations", "observation"
    if measures and measures <= _CODE_MEASURES:
        return "lookup", None
    if dimensions and dimensions <= _CODE_LIST_DIMENSIONS:
        return "lookup", None
    if dimensions & _GEOMETRY_DIMENSIONS:
        return "features", "feature"
    return "entities", "entity"


def record_evidence(registry: Registry, dataset_id: str, result: Any) -> bool:
    """Write what a successful fetch demonstrated, if nothing has recorded it.

    Not every fetch branch records a capability, and the ones that do not leave
    a resource looking unfetchable after a fetch that worked.
    `_fetch_kikommuner` is one, so kikommuner:3419 held an observation and no
    capability; fhi's is another, so a pass that fetched 365 of 369 fhi tables
    left every one of them `verified_at NULL`. The counter said verified and
    the registry disagreed, and the registry is the record that matters.

    The evidence is the cells that came back, so the count travels with the
    record and nothing is written when none did. An existing verification is
    never overwritten, and merging keeps the rest of the row: `set_capability`
    replaces every column, so a partial write would erase the endpoint, the
    record kind and any subject addressing.

    In discovery mode there is no declared capability to confirm, so the one
    written is read off the rows the fetch stored -- see
    `demonstrated_capability`. This used to be hardcoded to `observations`,
    which is how a Cristin institution came to be a verified observation
    source.
    """

    returned = getattr(getattr(result, "counts", None), "listed", 0) or 0
    if returned <= 0:
        return False
    existing = registry.get_capability(dataset_id)
    if existing and existing["verified_at"]:
        return False
    if existing:
        merged = {key: existing[key] for key in existing.keys() if key != "dataset_id"}
    else:
        dataset = registry.get_dataset(dataset_id) or {}
        demonstrated = demonstrated_capability(registry, dataset_id)
        if demonstrated is None:
            # The fetch reported rows and none are stored under this dataset, so
            # there is nothing to read the capability off. Claiming one anyway is
            # how the hardcoded `observations` got written in the first place.
            return False
        capability, record_kind = demonstrated
        merged = {
            "capability": capability,
            "record_kind": record_kind,
            "endpoint": dataset.get("access_path"),
        }
    merged["verified_at"] = utc_now()
    merged["verified_sample_count"] = returned
    registry.set_capability(dataset_id, merged)
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
            if record_evidence(registry, dataset_id, result):
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
                    if record_evidence(registry, dataset_id, result):
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
