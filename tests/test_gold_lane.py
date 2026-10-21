"""Every gold answer has to be in the lane the question is scored in.

`lookup` is deliberately not retrievable: a code list supplies join keys, it
does not answer a question. That exclusion is only safe while no gold answer
carries it, and this session moved 571 datasets into `lookup` by re-reading
their stored rows. One of them landing on a gold answer would take that
question out of the fetchable lane, and recall would drop with nothing in the
ranking having changed -- the hardest kind of regression to attribute.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from public_data_agent.fetch import classify_access_path, is_retrievable
from public_data_agent.registry import Registry

REGISTRY = Path("data/registry.sqlite")
GOLD_SETS = (
    Path("data/fetchable_gold.json"),
    Path("data/heldout_gold.json"),
    Path("data/coverage_gold.json"),
)


def _expected_ids(path: Path) -> set[str]:
    """The ids a gold file says answer its questions.

    Read from the `expected` lists only. The files also carry long `_notes`
    describing how the labels were made, and those mention dataset ids in
    prose; scraping every colon-separated token out of the file picks those up
    as answers.
    """

    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("questions", []) if isinstance(data, dict) else data
    ids: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict):
            for item in entry.get("expected", []) or []:
                if isinstance(item, str):
                    ids.add(item)
    return ids


def test_no_gold_answer_sits_outside_the_retrievable_lane() -> None:
    if not REGISTRY.exists():
        pytest.skip("no local registry.sqlite; the lane rule is unit-tested elsewhere")
    registry = Registry(REGISTRY)
    try:
        excluded: list[tuple[str, str]] = []
        checked = 0
        for path in GOLD_SETS:
            if not path.exists():
                continue
            for dataset_id in sorted(_expected_ids(path)):
                row = registry.get_dataset(dataset_id)
                if row is None:
                    continue
                checked += 1
                # The same precedence the ranking uses: what a fetch recorded
                # beats what the URL looks like.
                recorded = (registry.get_capability(dataset_id) or {}).get("capability")
                capability = recorded or classify_access_path(row.get("access_path"))["kind"]
                if not is_retrievable(capability):
                    excluded.append((dataset_id, capability))
        assert checked > 100, f"only {checked} gold ids resolved; the gold files moved"
        assert excluded == [], (
            "gold answers are no longer in the fetchable lane: "
            + ", ".join(f"{dataset_id} is {capability}" for dataset_id, capability in excluded)
        )
    finally:
        registry.close()


def test_no_capability_row_is_unverified_without_saying_why() -> None:
    """"Unverified" on its own is not a finding, it is an absence of one.

    Rows carry no verification and never will: the resource is withdrawn, it
    is a service catalogue, it is empty, it is behind authorisation, or its
    host does not exist. Each of those is a decided answer with the reason
    recorded. A row that is merely unverified means nobody has looked, and
    this is what keeps that distinction from quietly refilling.

    It works. Adding `unreachable` for the 82 datasets on a host that returns
    NXDOMAIN failed this test until the verdict was registered here, which is
    the point: a new way of saying "nothing came back" has to be declared as
    a decided answer, not slipped in beside them.
    """

    if not REGISTRY.exists():
        pytest.skip("no local registry.sqlite; the vocabulary is unit-tested elsewhere")
    registry = Registry(REGISTRY)
    try:
        decided = {"withdrawn", "catalogue", "empty", "restricted", "unreachable"}
        rows = registry.conn.execute(
            "SELECT dataset_id, capability, notes FROM resource_capability "
            "WHERE verified_at IS NULL"
        ).fetchall()
        undecided = [row["dataset_id"] for row in rows if row["capability"] not in decided]
        silent = [row["dataset_id"] for row in rows if not row["notes"]]
        assert undecided == [], (
            f"{len(undecided)} capability rows are unverified with no verdict: "
            + ", ".join(undecided[:10])
        )
        assert silent == [], (
            f"{len(silent)} rows carry a verdict with no reason recorded: "
            + ", ".join(silent[:10])
        )
    finally:
        registry.close()


def test_no_observations_dataset_stores_only_labels() -> None:
    """The whole of P1, in one assertion.

    11,374 stored cells held a label rather than a measurement, and every one
    of them sat in a dataset the registry called an observation source: a
    Cristin institution's name, an Entur scooter model, 7,127 occupation
    titles. They are records now. This is what stops the next connector
    quietly refilling the table, because nothing else would notice -- a count
    over `observations` reads the same either way.

    Two datasets hold a minority of label cells and are expected to: Norges
    Bank publishes a settlement date as an observation value, which is an SDMX
    attribute in the wrong place. That is written up in GAPS.md and is a
    different repair from this one, so the test is about datasets that measure
    nothing at all.
    """

    if not REGISTRY.exists():
        pytest.skip("no local registry.sqlite; the storage rules are unit-tested elsewhere")
    from public_data_agent.entity_records import is_empty, is_number

    registry = Registry(REGISTRY)
    try:
        import json as _json

        rows = registry.conn.execute(
            "SELECT o.dataset_id, o.value_json FROM observations o "
            "JOIN resource_capability rc ON rc.dataset_id = o.dataset_id "
            "WHERE rc.capability = 'observations'"
        ).fetchall()
        stored: dict[str, int] = {}
        labelled: dict[str, int] = {}
        for row in rows:
            raw = row["value_json"]
            try:
                value = _json.loads(raw) if raw is not None else None
            except ValueError:
                value = raw
            stored[row["dataset_id"]] = stored.get(row["dataset_id"], 0) + 1
            if not is_number(value) and not is_empty(value):
                labelled[row["dataset_id"]] = labelled.get(row["dataset_id"], 0) + 1
        assert stored, "no observation cells at all; the query or the registry changed"
        all_labels = sorted(d for d, n in stored.items() if labelled.get(d, 0) == n)
        assert all_labels == [], (
            f"{len(all_labels)} dataset(s) are called observation sources and store "
            "no measurement: " + ", ".join(all_labels[:10])
        )
    finally:
        registry.close()
