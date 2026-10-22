"""A 404 from a download service is not one fact, and a 200 is not presence.

The download service answers 404 for 45 of the 689 datasets whose catalogue
record points at it. Three different things are behind that, and all three are
decided answers rather than failures -- a Datasettserie with no distribution
of its own, a publisher who declares the distribution offline, and a dataset
the service simply has no entry for.

The second assertion here is the one that matters. `codelists/format/{uuid}`
and `codelists/area/{uuid}` answer `200 []` for a uuid the service has never
heard of, including `00000000-0000-0000-0000-000000000000`. Treating that as
"the service knows the dataset and it offers nothing" would publish a positive
claim sourced from an empty list, for every one of the ten.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from public_data_agent.registry import Registry

spec = importlib.util.spec_from_file_location(
    "resolve_download_capabilities", Path("scripts/resolve_download_capabilities.py")
)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)

SERVICE = "https://nedlasting.geonorge.no/api/capabilities/"
UUID = "94bc96ae-cb2c-43f4-91d5-951534120fcc"


def _answers(monkeypatch, replies: dict[str, object]) -> list[str]:
    """Serve canned bodies and record every URL the resolver asks for."""

    asked: list[str] = []

    def fake_get(url: str, cap: int = 0) -> tuple[int, object]:
        asked.append(url)
        for prefix, body in replies.items():
            if url.startswith(prefix):
                return (404, None) if body is None else (200, body)
        return (404, None)

    monkeypatch.setattr(resolver, "_get", fake_get)
    monkeypatch.setattr(resolver.time, "sleep", lambda _seconds: None)
    return asked


def test_a_series_parent_is_skipped_not_recorded_as_a_failure(monkeypatch) -> None:
    _answers(monkeypatch, {
        SERVICE: None,
        resolver.CATALOGUE: {"HierarchyLevel": "series", "Type": "series"},
    })
    entry = resolver.resolve("d", UUID, SERVICE, pause=0.0)
    assert "error" not in entry
    assert entry["skipped"].startswith("series:")


def test_an_offline_distribution_is_its_own_verdict(monkeypatch) -> None:
    _answers(monkeypatch, {
        SERVICE: None,
        resolver.CATALOGUE: {
            "HierarchyLevel": "dataset",
            "DistributionProtocol": "GEONORGE:OFFLINE",
        },
    })
    entry = resolver.resolve("d", UUID, SERVICE, pause=0.0)
    assert "error" not in entry
    assert entry["skipped"].startswith("offline:")


def test_the_codelists_are_never_asked_because_their_200_means_nothing(
    monkeypatch,
) -> None:
    """The regression this file exists for.

    A fallback to `codelists/format` and `codelists/area` on a 404 looks right
    -- both return 200 -- and would have recorded "no formats, covers nowhere"
    for ten datasets, because those routes return an empty list for any uuid
    at all. The resolver must ask the catalogue instead, and must not read a
    codelist it did not reach through a capabilities response.
    """

    asked = _answers(monkeypatch, {
        SERVICE: None,
        resolver.CATALOGUE: {
            "HierarchyLevel": "dataset",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "DistributionFormats": [{"Name": "GML", "Version": "3.2.1"}],
        },
        # Present and answering, exactly as the live service does.
        "https://nedlasting.geonorge.no/api/codelists/": [],
    })
    entry = resolver.resolve("d", UUID, SERVICE, pause=0.0)
    assert not any("codelists" in url for url in asked), asked
    assert "formats" not in entry, "an empty codelist must not become a format list"
    assert "areas" not in entry and "nationwide" not in entry
    assert entry["unregistered_download"].startswith("declares GEONORGE:DOWNLOAD")
    assert entry["catalogue_formats"] == ["GML 3.2.1"]


def test_an_unregistered_download_keeps_the_view_service_it_declares(
    monkeypatch,
) -> None:
    """8 of the 9 view services on these records answer WFS with real features.

    Recorded, not probed: the resolver's job is to say what the publisher
    declares, and a GeoServer layer published as WMS is a candidate, not a
    verdict.
    """

    _answers(monkeypatch, {
        SERVICE: None,
        resolver.CATALOGUE: {
            "HierarchyLevel": "dataset",
            "DistributionProtocol": "GEONORGE:DOWNLOAD",
            "ServiceDistributionProtocolForDataset": "OGC:WMS",
            "ServiceDistributionNameForDataset": "mareano_biologi:hornkorall_radicipes",
            "ServiceDistributionUrlForDataset": (
                "https://kart.hi.no/mareano/mareano_biologi/hornkorall_radicipes/ows"
                "?request=GetCapabilities&service=WMS"
            ),
        },
    })
    entry = resolver.resolve("d", UUID, SERVICE, pause=0.0)
    assert entry["view_service"]["protocol"] == "OGC:WMS"
    assert entry["view_service"]["layer"] == "mareano_biologi:hornkorall_radicipes"
    assert entry["view_service"]["url"].startswith("https://kart.hi.no/")


def test_a_non_404_failure_is_still_a_failure(monkeypatch) -> None:
    """Only a 404 gets the catalogue question.

    A 500 or a timeout means the service was reached and did not answer, and
    the catalogue cannot speak for it. Asking anyway would turn an outage into
    a decided verdict about the dataset.
    """

    asked = _answers(monkeypatch, {resolver.CATALOGUE: {"HierarchyLevel": "dataset"}})

    def fails(url: str, cap: int = 0) -> tuple[int, object]:
        asked.append(url)
        return (500, None)

    monkeypatch.setattr(resolver, "_get", fails)
    entry = resolver.resolve("d", UUID, SERVICE, pause=0.0)
    assert entry["error"] == "capabilities HTTP 500"
    assert not any(url.startswith(resolver.CATALOGUE) for url in asked)


@pytest.mark.parametrize(
    "entry",
    [
        {"dataset_id": "x:y", "skipped": "series: a parent record grouping versions"},
        {"dataset_id": "x:y", "skipped": "offline: the publisher declares it not online"},
        {"dataset_id": "x:y", "unregistered_download": "declares GEONORGE:DOWNLOAD"},
    ],
)
def test_the_apply_step_writes_nothing_for_a_decided_non_answer(
    entry: dict, tmp_path: Path, monkeypatch, capsys
) -> None:
    """A decided non-answer must not reach `set_download_options`.

    These rows carry no formats, no projections and no areas, and the writer
    defaults each of those to an empty list. Letting them through records
    "offers nothing, covers nowhere" as the publisher's statement, when the
    publisher never made one -- and overwrites what the previous run found.
    """

    spec_apply = importlib.util.spec_from_file_location(
        "apply_download_capabilities", Path("scripts/apply_download_capabilities.py")
    )
    applier = importlib.util.module_from_spec(spec_apply)
    spec_apply.loader.exec_module(applier)

    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    registry.ensure_dataset_identity(
        dataset_id="x:y", title="Hornkoraller - Radicipes", publisher_name=None,
        access_path="https://kartkatalog.geonorge.no/metadata/uuid/abc", license=None,
    )
    registry.set_distribution("x:y", {
        "tier": "bulk-download",
        "best_url": "https://nedlasting.geonorge.no/api/capabilities/",
        "resolved_from": "kartkatalog",
        "resolved_at": "2026-10-22T10:00:00+00:00",
    })
    # What a successful earlier run would have left behind.
    registry.set_download_options("x:y", {"formats": ["GML"], "projections": ["25833"]})
    registry.close()

    jsonl = tmp_path / "entries.jsonl"
    jsonl.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["apply", "--db", str(db), "--jsonl", str(jsonl), "--apply"],
    )
    assert applier.main() == 0
    capsys.readouterr()

    registry = Registry(db)
    try:
        row = registry.get_distribution("x:y")
        assert json.loads(row["download_formats_json"]) == ["GML"], (
            "a decided non-answer overwrote the formats an earlier run resolved"
        )
        assert json.loads(row["download_projections_json"]) == ["25833"]
        assert registry.conn.execute(
            "SELECT COUNT(*) FROM dataset_coverage WHERE dataset_id = 'x:y'"
        ).fetchone()[0] == 0
    finally:
        registry.close()
