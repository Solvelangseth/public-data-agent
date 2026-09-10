"""The NVDB object type catalogue.

What is worth pinning: an abstract type is not a retrievable resource, licence
stays null because NVDB prints none, and the attribute schema that arrives with
the listing is kept rather than refetched.
"""

from __future__ import annotations

from public_data_agent.mapping import map_harvested_record
from public_data_agent.sources.nvdb import NvdbSource

LISTING = [
    {
        "id": 60,
        "navn": "Bru",
        "kortnavn": "bru",
        "beskrivelse": "Byggverk uten overliggende fylling som fører vegen over en fri åpning.",
        "objektliste_dato": "2026-02-11",
        "abstrakt_type": False,
        "egenskapstyper": [
            {"id": 9182, "navn": "Byggverkstype"},
            {"id": 1263, "navn": "Brukategori"},
            {"navn": ""},
        ],
        "kategorier": [{"id": 38, "navn": "Alle"}],
    },
    {"id": 999, "navn": "Abstrakt", "abstrakt_type": True, "egenskapstyper": []},
    {"navn": "no id at all"},
]


class ScriptedHttp:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.headers: list[dict | None] = []

    def get_json(self, url, headers=None):
        self.urls.append(url)
        self.headers.append(headers)
        return LISTING


def test_the_whole_catalogue_is_one_request() -> None:
    http = ScriptedHttp()
    refs = NvdbSource(http=http).list_dataset_refs()
    assert len(http.urls) == 1
    # NVDB throttles anonymous callers harder, so the client identifies itself.
    assert (http.headers[0] or {}).get("X-Client")
    assert [ref.source_native_id for ref in refs] == ["60"]


def test_an_abstract_type_is_not_catalogued() -> None:
    # An abstract type holds no objects, so listing it as retrievable would
    # promise records that do not exist.
    refs = NvdbSource(http=ScriptedHttp()).list_dataset_refs()
    assert "999" not in [ref.source_native_id for ref in refs]


def test_the_schema_arrives_with_the_listing(tmp_path=None) -> None:
    source = NvdbSource(http=ScriptedHttp())
    ref = source.list_dataset_refs()[0]
    record = source.fetch_dataset(ref)
    # 424 types would otherwise cost 424 extra requests for the same fields.
    assert record.payload["variables"] == ["Byggverkstype", "Brukategori"]


def test_mapped_row_points_at_the_object_endpoint_and_claims_no_licence() -> None:
    source = NvdbSource(http=ScriptedHttp())
    record = source.fetch_dataset(source.list_dataset_refs()[0])
    mapped = map_harvested_record(record)
    assert mapped.access_path == "https://nvdbapiles.atlas.vegvesen.no/vegobjekter/60"
    assert mapped.publisher_name == "Statens vegvesen"
    # NVDB prints no licence field. The NLOD on Statens vegvesen's CKAN portal
    # is a claim about those datasets, not about this API.
    assert mapped.license is None


def test_an_unlisted_type_is_an_error_not_an_invention() -> None:
    source = NvdbSource(http=ScriptedHttp())
    source.list_dataset_refs()
    from public_data_agent.models import DatasetRef

    try:
        source.fetch_dataset(DatasetRef(source_native_uri="x", source_native_id="12345"))
    except KeyError:
        return
    raise AssertionError("fetching an unlisted type should raise, not fabricate a record")
