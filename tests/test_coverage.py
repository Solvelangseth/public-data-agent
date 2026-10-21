"""Which places a dataset covers, and what can be ordered from it.

The Geonorge download service publishes both per dataset. The cases here are
the ones that decide whether the table is joinable or noise.
"""

from __future__ import annotations

from pathlib import Path

import json
import pytest

from public_data_agent.registry import Registry

DECLARED_BY = "https://nedlasting.geonorge.no/api/codelists/area/{uuid}"
WHEN = "2026-10-21T18:00:00+00:00"


def _registry(tmp_path: Path, *, dataset_id: str = "x:y", title: str = "FKB-Lufthavn") -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id=dataset_id, title=title, publisher_name=None,
        access_path="https://kartkatalog.geonorge.no/metadata/uuid/abc", license=None,
    )
    registry.set_distribution(dataset_id, {
        "tier": "bulk-download", "best_url": "https://nedlasting.geonorge.no/api/capabilities/",
        "access_constraint": "Åpne data",
        "resolved_from": "kartkatalog", "resolved_at": WHEN,
    })
    return registry


def test_a_grid_cell_is_not_a_place(tmp_path: Path) -> None:
    """A raster dataset offers up to 1,335 areas named 0001..1335.

    They join to nothing and would be most of the rows in the table.
    """

    registry = _registry(tmp_path)
    written = registry.set_coverage("x:y", [
        {"type": "kommune", "code": "1820", "name": "Alstahaug"},
        {"type": "celle", "code": "0001", "name": "0001"},
        {"type": "celle", "code": "0002", "name": "0002"},
        {"type": "landsdekkende", "code": "0000", "name": "Hele landet"},
    ], declared_by=DECLARED_BY, resolved_at=WHEN)
    assert written == 1
    rows = registry.conn.execute("SELECT area_type FROM dataset_coverage").fetchall()
    assert [row["area_type"] for row in rows] == ["kommune"]
    registry.close()


def test_nationwide_is_a_flag_not_a_place(tmp_path: Path) -> None:
    """"The whole country" is not something to join a kommune query against."""

    registry = _registry(tmp_path)
    registry.set_download_options("x:y", {"formats": ["FGDB", "SOSI"], "nationwide": True})
    registry.set_coverage("x:y", [{"type": "landsdekkende", "code": "0000", "name": "Hele landet"}],
                          declared_by=DECLARED_BY, resolved_at=WHEN)
    assert registry.conn.execute("SELECT COUNT(*) FROM dataset_coverage").fetchone()[0] == 0
    assert registry.get_distribution("x:y")["nationwide"] == 1
    registry.close()


def test_the_question_the_catalogue_cannot_answer(tmp_path: Path) -> None:
    """Which datasets cover Alstahaug, and in what format."""

    registry = _registry(tmp_path)
    registry.set_download_options("x:y", {"formats": ["GML", "SOSI", "FGDB"],
                                          "projections": ["25833"]})
    registry.set_coverage("x:y", [
        {"type": "kommune", "code": "1820", "name": "Alstahaug"},
        {"type": "kommune", "code": "5403", "name": "Alta (gammel)"},
        {"type": "fylke", "code": "18", "name": "Nordland"},
    ], declared_by=DECLARED_BY, resolved_at=WHEN)
    hits = registry.datasets_covering("1820")
    assert [h["title"] for h in hits] == ["FKB-Lufthavn"]
    assert hits[0]["tier"] == "bulk-download"
    assert json.loads(hits[0]["download_formats_json"]) == ["GML", "SOSI", "FGDB"]
    assert hits[0]["access_constraint"] == "Åpne data"
    assert registry.datasets_covering("9999") == []
    assert [h["title"] for h in registry.datasets_covering("18", area_type="fylke")] == ["FKB-Lufthavn"]
    registry.close()


def test_a_re_resolution_replaces_rather_than_accumulates(tmp_path: Path) -> None:
    """A dataset that now covers fewer kommuner must not keep the old ones."""

    registry = _registry(tmp_path)
    registry.set_coverage("x:y", [
        {"type": "kommune", "code": "1820", "name": "Alstahaug"},
        {"type": "kommune", "code": "1871", "name": "Andøy"},
    ], declared_by=DECLARED_BY, resolved_at=WHEN)
    assert registry.conn.execute("SELECT COUNT(*) FROM dataset_coverage").fetchone()[0] == 2
    registry.set_coverage("x:y", [{"type": "kommune", "code": "1820", "name": "Alstahaug"}],
                          declared_by=DECLARED_BY, resolved_at="2026-11-01T00:00:00+00:00")
    codes = [r["area_code"] for r in registry.conn.execute(
        "SELECT area_code FROM dataset_coverage")]
    assert codes == ["1820"], "Andøy should be gone, not kept"
    registry.close()


def test_a_code_with_a_leading_zero_survives(tmp_path: Path) -> None:
    """Oslo is kommune 0301 in the old numbering and fylke 03 in the new.

    Stored as a number either would become 301 and 3 and stop joining.
    """

    registry = _registry(tmp_path)
    registry.set_coverage("x:y", [
        {"type": "kommune", "code": "0301", "name": "Oslo"},
        {"type": "fylke", "code": "03", "name": "Oslo"},
    ], declared_by=DECLARED_BY, resolved_at=WHEN)
    rows = {r["area_type"]: r["area_code"] for r in registry.conn.execute(
        "SELECT area_type, area_code FROM dataset_coverage")}
    assert rows == {"kommune": "0301", "fylke": "03"}
    registry.close()


def test_download_options_need_a_resolved_distribution(tmp_path: Path) -> None:
    """Details of a distribution must not create one nobody resolved."""

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(dataset_id="z:w", title=None, publisher_name=None,
                                     access_path="https://e.no/", license=None)
    with pytest.raises(ValueError, match="no distributions row"):
        registry.set_download_options("z:w", {"formats": ["CSV"]})
    registry.close()


def test_a_required_role_is_recorded_where_it_can_be_seen(tmp_path: Path) -> None:
    """It is how the Norge digitalt gate shows up in the download API.

    ACCESS.md found the same restriction from the licence side; this is the
    publisher saying it in the place a fetch would hit.
    """

    registry = _registry(tmp_path, dataset_id="fkb:x", title="FKB-Lufthavn hist")
    registry.set_download_options("fkb:x", {
        "formats": ["GML", "SOSI", "FGDB"], "required_role": "nd.fkb",
    })
    assert registry.get_distribution("fkb:x")["required_role"] == "nd.fkb"
    registry.close()
