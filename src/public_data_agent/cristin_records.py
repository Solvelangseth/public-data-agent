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
ID_FIELDS = (
    "cristin_institution_id",
    "cristin_unit_id",
    "cristin_person_id",
    "cristin_project_id",
    "cristin_result_id",
    "cristin_biobank_id",
    "cristin_funding_id",
    "code",
)


def _scheme_for(id_field: str | None, table_id: str) -> str:
    """The vocabulary a subject code belongs to.

    Named after what the id identifies, so `cristin_person_id` becomes
    `cristin:person` and a code list keeps the endpoint that published it.
    """

    if id_field and id_field.startswith("cristin_") and id_field.endswith("_id"):
        return "cristin:" + id_field[len("cristin_") : -len("_id")]
    return f"cristin:{table_id}"


def records_from_cells(
    cells: list[tuple[str, Any, dict[str, str]]],
    *,
    dataset_id: str,
    table_id: str,
) -> list[dict[str, Any]]:
    """Map Cristin cells to entity records, one per member.

    The identifier becomes `subject_code`, which is the column a later join
    reads, and the name becomes `subject_label`. Where the connector had no
    name to print and fell back to the identifier itself -- Cristin's funding
    list does -- the record carries the code and no label, because inventing a
    name for it is the failure this whole change is about.
    """

    records: list[dict[str, Any]] = []
    for index, (measure, value, dims) in enumerate(cells):
        id_field = next((field for field in ID_FIELDS if dims.get(field)), None)
        if id_field is not None:
            subject_code: str | None = str(dims[id_field])
            subject_label = None if value is None else str(value)
        elif measure in ID_FIELDS and value is not None:
            subject_code = str(value)
            subject_label = None
        else:
            subject_code = None
            subject_label = None if value is None else str(value)
        scheme = _scheme_for(id_field or (measure if measure in ID_FIELDS else None), table_id)
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
