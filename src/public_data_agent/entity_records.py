"""Turn Cristin's printed members into the entity records they are.

Every Cristin endpoint returns a thing: an institution, a person, a project, a
result, a biobank, a unit. The connectors stored each as an observation cell
whose measure was the name field and whose value was the name --
`institution_name = "AOF Haugaland"` -- which made a name card compete in the
lane whose job is answering numeric questions, and made 1,413 name cards count
as published measurements.

The conversion reads the cells the connectors already build rather than the
payload, so what is copied and what is skipped stays exactly as each source
decided; only the shape it lands in changes.
"""

from __future__ import annotations

from typing import Any

# The identifier a Cristin member is addressed by, most specific first. `code`
# is last because a member that has both prints the Cristin id as its handle
# and `code` as a classification value.
CRISTIN_ID_FIELDS = (
    "cristin_institution_id",
    "cristin_unit_id",
    "cristin_person_id",
    "cristin_project_id",
    "cristin_result_id",
    "cristin_biobank_id",
    "cristin_funding_id",
    "code",
)


# What Entur addresses a GBFS member by. The free-floating scooter feeds print
# a vehicle type per model, so the type id is the handle, not the station.
ENTUR_ID_FIELDS = ("vehicle_type_id", "station_id", "bike_id", "region_id")

# Udir's curriculum vocabularies print `kode` as the member's whole identity.
GREP_ID_FIELDS = ("kode", "id", "uri")


def _scheme_for(id_field: str | None, *, prefix: str, table_id: str) -> str:
    """The vocabulary a subject code belongs to.

    Named after what the id identifies, so `cristin_person_id` becomes
    `cristin:person` and `vehicle_type_id` becomes `entur:vehicle_type`. An
    identifier that names nothing in particular -- Udir's bare `kode` -- keeps
    the endpoint that published it instead.
    """

    if id_field and id_field.endswith("_id"):
        thing = id_field[: -len("_id")]
        if thing.startswith(f"{prefix}_"):
            thing = thing[len(prefix) + 1 :]
        if thing:
            return f"{prefix}:{thing}"
    return f"{prefix}:{table_id}"


def records_from_cells(
    cells: list[tuple[str, Any, dict[str, str]]],
    *,
    dataset_id: str,
    table_id: str,
    id_fields: tuple[str, ...] = CRISTIN_ID_FIELDS,
    prefix: str = "cristin",
) -> list[dict[str, Any]]:
    """Map cells to entity records, one per member.

    The identifier becomes `subject_code`, which is the column a later join
    reads, and the name becomes `subject_label`. Where the connector had no
    name to print and fell back to the identifier itself -- Cristin's funding
    list does, and every Udir curriculum code does -- the record carries the
    code and no label, because inventing a name for it is the failure this
    whole change is about.
    """

    records: list[dict[str, Any]] = []
    for index, (measure, value, dims) in enumerate(cells):
        # The connector already chose which printed field is the member's
        # identity when it picked the measure, and that choice outranks
        # whatever else the response happens to carry: Udir prints both `kode`
        # and a `id` UUID, and the curriculum is addressed by the code.
        if measure in id_fields and value is not None:
            id_field: str | None = None
            subject_code: str | None = str(value)
            subject_label = None
        else:
            id_field = next((field for field in id_fields if dims.get(field)), None)
            subject_code = str(dims[id_field]) if id_field is not None else None
            subject_label = None if value is None else str(value)
        scheme = _scheme_for(
            id_field if id_field is not None else (measure if measure in id_fields else None),
            prefix=prefix,
            table_id=table_id,
        )
        attributes = {key: val for key, val in dims.items() if key != id_field}
        # Two members of one listing must not share an id. A member that printed
        # no identifier at all is keyed by its position in the response, which
        # is what the connector read it from.
        handle = subject_code if subject_code is not None else f"row{index}"
        records.append(
            {
                "id": f"entity:{dataset_id}:{scheme}:{handle}",
                "kind": "entity",
                "subject_scheme": scheme,
                "subject_code": subject_code,
                "subject_label": subject_label,
                "attributes": attributes,
            }
        )
    return records
