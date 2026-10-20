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

# A publisher's way of writing "no value here". A cell that carries one is
# still an observation, so an empty sample must not be read as labels.
EMPTY_VALUES = frozenset({"", ":", "..", ".", "-", "none", "null", "na"})

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

# Norges Bank's SDMX flows print the security the row is about under `ISIN`.
NORGESBANK_ID_FIELDS = ("ISIN",)

# Enhetsregisteret addresses a code list by its code and prints the name under
# a separate key, so the cell value is the code over again. The change feeds
# address an update by the id the feed hands out.
BRREG_ID_FIELDS = ("kode", "nummer", "oppdateringsid", "id")
BRREG_LABEL_FIELDS = ("beskrivelse", "navn")

# A fish-farm environmental survey is addressed by its report id, and the site
# it surveyed is the name the connector already prints as the cell value.
ENVREPORT_ID_FIELDS = ("reportId", "reportid")

# What an OGC API Features item is addressed by. Havforskningsinstituttet's
# collections print `fid` on the 2025 advisory layers and `id` on the 2024 ones.
FEATURE_ID_FIELDS = ("fid", "id", "objectid", "gid")


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
    label_fields: tuple[str, ...] = (),
    prefix: str = "cristin",
    kind: str = "entity",
) -> list[dict[str, Any]]:
    """Map cells to entity records, one per member.

    The identifier becomes `subject_code`, which is the column a later join
    reads, and the name becomes `subject_label`. Where the connector had no
    name to print and fell back to the identifier itself -- Cristin's funding
    list does, and every Udir curriculum code does -- the record carries the
    code and no label, because inventing a name for it is the failure this
    whole change is about.

    `label_fields` is for the sources that print the code twice. Enhetsregisteret
    returns `{"kode": "AAFY", "beskrivelse": "Underenhet til ikke-naeringsdrivende"}`
    and the connector picks the code as the cell value, so left alone the record
    would be labelled with its own code and the name would sit in the
    attributes. Naming which key carries the name is a mapping, not an
    invention: the string is the publisher's either way.

    `kind` is the caller's to state, because the shape of a cell cannot see it:
    a spawning ground and a scooter model are written identically and one is a
    thing in a place. The geometry that would prove it is nested where these
    connectors do not copy it, so a feature record carries no `geometry_json`
    until the connector learns to read it.
    """

    records: list[dict[str, Any]] = []
    for index, (measure, value, dims) in enumerate(cells):
        # The connector already chose which printed field is the member's
        # identity when it picked the measure, and that choice outranks
        # whatever else the response happens to carry: Udir prints both `kode`
        # and a `id` UUID, and the curriculum is addressed by the code.
        label_field = next((field for field in label_fields if dims.get(field)), None)
        # A cell whose measure and value are the same string is naming
        # something, not measuring it: Norges Bank's auction calendar prints
        # the ISIN as both, and the ISIN is what the row is about.
        if value is not None and measure == str(value):
            id_field: str | None = None
            subject_code: str | None = str(value)
            subject_label = None
        elif measure in id_fields and value is not None:
            id_field = None
            subject_code = str(value)
            subject_label = None
        else:
            id_field = next((field for field in id_fields if dims.get(field)), None)
            subject_code = str(dims[id_field]) if id_field is not None else None
            subject_label = None if value is None else str(value)
        if label_field is not None:
            subject_label = str(dims[label_field])
        scheme = _scheme_for(
            id_field if id_field is not None else (measure if measure in id_fields else None),
            prefix=prefix,
            table_id=table_id,
        )
        attributes = {
            key: val
            for key, val in dims.items()
            if key != id_field and key != label_field
        }
        # Two members of one listing must not share an id. A member that printed
        # no identifier at all is keyed by its position in the response, which
        # is what the connector read it from.
        handle = subject_code if subject_code is not None else f"row{index}"
        records.append(
            {
                "id": f"{kind}:{dataset_id}:{scheme}:{handle}",
                "kind": kind,
                "subject_scheme": scheme,
                "subject_code": subject_code,
                "subject_label": subject_label,
                "attributes": attributes,
            }
        )
    return records


def is_number(value: Any) -> bool:
    """Whether a stored value is a measurement rather than a label.

    Numbers arrive as JSON strings often enough that type alone misreads them:
    Norges Bank publishes the key policy rate as `"4.25"`, and reading that as
    a label would file an interest-rate series as a list of things.
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


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip().casefold() in EMPTY_VALUES


def cells_are_labels(cells: list[tuple[str, Any, dict[str, str]]]) -> bool:
    """Whether a response measured nothing at all.

    The same question `demonstrated_capability` asks of stored rows, asked of a
    batch about to be stored, so a connector that can return either shape --
    Norges Bank returns both rate series and auction calendars -- routes each
    response to the table that fits it instead of being configured per dataset.

    One number anywhere makes the batch a measurement batch. An all-empty batch
    is one too, because a suppressed cell is still an observation. Only a batch
    that is entirely labels is not.
    """

    if not cells:
        return False
    values = [value for _measure, value, _dims in cells]
    if any(is_number(value) for value in values):
        return False
    return not all(is_empty(value) for value in values)
