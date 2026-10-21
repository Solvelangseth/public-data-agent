"""Addressing a resource that is not reachable by its access_path.

Two kinds of resource need this and only one was ever designed for:

    a register        one record by one id -- Enhetsregisteret, NVDB objects.
                      `subject_template` with `{subject}`. 1.1M subjects behind
                      a collection endpoint that is not a fetch.
    a pinned query    several parameters that only mean anything together.
                      MET Frost returns HTTP 400 unless sources, elements and
                      referencetime are all present; NVE HydAPI wants four.

`subject_url` was written for the first and nothing ever called it, so every
resource of either kind was unreachable through `fetch_observations`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.registry import Registry
from public_data_agent.resource_index import request_url, subject_url, template_placeholders

FROST_TEMPLATE = (
    "https://frost.met.no/observations/v0.jsonld"
    "?sources={sources}&elements={elements}&referencetime={referencetime}"
)
BRREG_TEMPLATE = "https://data.brreg.no/enhetsregisteret/api/enheter/{subject}"


def _registry(tmp_path: Path, dataset_id: str, capability: dict) -> Registry:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id=dataset_id, title=None, publisher_name=None,
        access_path="https://example.no/collection", license=None,
    )
    registry.set_capability(dataset_id, capability)
    return registry


def test_placeholders_are_read_in_the_order_the_template_asks() -> None:
    assert template_placeholders(FROST_TEMPLATE) == ["sources", "elements", "referencetime"]
    assert template_placeholders(BRREG_TEMPLATE) == ["subject"]
    assert template_placeholders("https://example.no/api") == []
    assert template_placeholders("{a}/{b}/{a}") == ["a", "b"], "named once, in first order"


def test_a_register_is_addressed_by_one_id(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "brreg:enheter", {
        "capability": "entities", "record_kind": "entity",
        "endpoint": "https://data.brreg.no/enhetsregisteret/api/enheter",
        "subject_template": BRREG_TEMPLATE, "subject_scheme": "brreg:orgnr",
    })
    assert subject_url(registry, "brreg:enheter", "912345678").endswith("/enheter/912345678")
    assert request_url(registry, "brreg:enheter", "912345678").endswith("/enheter/912345678")
    registry.close()


def test_a_pinned_query_is_addressed_by_the_combination(tmp_path: Path) -> None:
    """None of the three identifies anything alone, so none of them is a subject."""

    registry = _registry(tmp_path, "frost:obs", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://frost.met.no/observations/v0.jsonld",
        "subject_template": FROST_TEMPLATE,
    })
    url = request_url(registry, "frost:obs", {
        "sources": "SN18700",
        "elements": "air_temperature",
        "referencetime": "2026-10-01/2026-10-02",
    })
    assert "sources=SN18700" in url
    assert "elements=air_temperature" in url
    assert "referencetime=2026-10-01/2026-10-02" in url, "the range separator survives"
    registry.close()


def test_a_value_with_spaces_and_brackets_is_encoded(tmp_path: Path) -> None:
    """A Frost element is `sum(precipitation_amount P1D)`.

    Sent raw it is an invalid URL; the separators `/`, `:` and `,` must
    survive because the same publishers use them inside values.
    """

    registry = _registry(tmp_path, "frost:obs", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://frost.met.no/observations/v0.jsonld",
        "subject_template": FROST_TEMPLATE,
    })
    url = request_url(registry, "frost:obs", {
        "sources": "SN18700,SN50540",
        "elements": "sum(precipitation_amount P1D)",
        "referencetime": "2026-10-01T00:00:00Z/2026-10-02T00:00:00Z",
    })
    assert "sum%28precipitation_amount%20P1D%29" in url
    assert "sources=SN18700,SN50540" in url, "a comma list must not be escaped"
    assert "2026-10-01T00:00:00Z/2026-10-02T00:00:00Z" in url, "slash and colon survive"
    assert " " not in url and "(" not in url
    registry.close()


def test_a_missing_placeholder_is_named_rather_than_defaulted(tmp_path: Path) -> None:
    """Frost answers HTTP 400 to a literal `{elements}`, which is the good case."""

    registry = _registry(tmp_path, "frost:obs", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://frost.met.no/observations/v0.jsonld",
        "subject_template": FROST_TEMPLATE,
    })
    with pytest.raises(ValueError) as caught:
        request_url(registry, "frost:obs", {"sources": "SN18700"})
    message = str(caught.value)
    assert "elements" in message and "referencetime" in message
    assert "sources" in message, "the error states what the template asks for"
    registry.close()


def test_a_value_the_template_ignores_is_refused(tmp_path: Path) -> None:
    """Silently dropping it would look like a filter that was applied."""

    registry = _registry(tmp_path, "brreg:enheter", {
        "capability": "entities", "record_kind": "entity",
        "endpoint": "https://data.brreg.no/enhetsregisteret/api/enheter",
        "subject_template": BRREG_TEMPLATE, "subject_scheme": "brreg:orgnr",
    })
    with pytest.raises(ValueError, match="does not take"):
        request_url(registry, "brreg:enheter", {"subject": "912345678", "year": "2024"})
    registry.close()


def test_a_resource_with_no_template_is_refused(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "plain:thing", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://example.no/collection",
    })
    with pytest.raises(ValueError, match="no subject_template"):
        request_url(registry, "plain:thing", "anything")
    registry.close()


def test_an_empty_subject_is_not_the_whole_collection(tmp_path: Path) -> None:
    registry = _registry(tmp_path, "brreg:enheter", {
        "capability": "entities", "record_kind": "entity",
        "endpoint": "https://data.brreg.no/enhetsregisteret/api/enheter",
        "subject_template": BRREG_TEMPLATE, "subject_scheme": "brreg:orgnr",
    })
    with pytest.raises(ValueError, match="to address"):
        subject_url(registry, "brreg:enheter", "   ")
    registry.close()


# --- what the capability will and will not accept ---------------------------


def test_a_template_with_no_placeholder_is_refused(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(dataset_id="x:y", title=None, publisher_name=None,
                                     access_path="https://example.no/", license=None)
    with pytest.raises(ValueError, match="no placeholder"):
        registry.set_capability("x:y", {
            "capability": "observations", "record_kind": "observation",
            "endpoint": "https://example.no/", "subject_template": "https://example.no/fixed",
        })
    registry.close()


def test_a_subject_template_still_demands_a_scheme(tmp_path: Path) -> None:
    """An unnamed id cannot be validated or joined. That rule is unchanged."""

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(dataset_id="x:y", title=None, publisher_name=None,
                                     access_path="https://example.no/", license=None)
    with pytest.raises(ValueError, match="subject_scheme"):
        registry.set_capability("x:y", {
            "capability": "entities", "record_kind": "entity",
            "endpoint": "https://example.no/", "subject_template": BRREG_TEMPLATE,
        })
    registry.close()


def test_a_named_query_template_needs_no_subject_scheme(tmp_path: Path) -> None:
    """sources+elements+referencetime is a query, not a subject.

    Demanding a scheme for it would mean inventing a vocabulary for "a query".
    """

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(dataset_id="frost:obs", title=None, publisher_name=None,
                                     access_path="https://frost.met.no/", license=None)
    registry.set_capability("frost:obs", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://frost.met.no/observations/v0.jsonld",
        "subject_template": FROST_TEMPLATE,
    })
    assert registry.get_capability("frost:obs")["subject_template"] == FROST_TEMPLATE
    registry.close()


# --- the bug this mechanism nearly shipped with ------------------------------


def test_the_filled_url_reaches_the_connector_not_just_the_router(tmp_path: Path) -> None:
    """The first version rebound a local and left `dataset["access_path"]` alone.

    Every connector reads that key for itself, so routing would have used the
    filled URL and the fetch would have requested the collection -- which for
    Frost is an HTTP 400 and for Enhetsregisteret is 1.1M records.
    """

    from public_data_agent.fetch import fetch_observations
    from public_data_agent.http_util import JsonResponse

    requested: list[str] = []

    class Recorder:
        def get_json_response(self, url: str, *, headers=None):
            requested.append(url)
            return JsonResponse(status=200, url=url, body={
                "license": "https://creativecommons.org/licenses/by/3.0/no/",
                "data": [{
                    "sourceId": "SN18700:0",
                    "referenceTime": "2026-10-01T00:00:00.000Z",
                    "observations": [{
                        "elementId": "air_temperature", "value": 13.5, "unit": "degC",
                        "timeOffset": "PT0H", "timeResolution": "PT1H",
                        "timeSeriesId": 0, "performanceCategory": "C",
                        "exposureCategory": "1", "qualityCode": 0,
                    }],
                }],
            })

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id="frost:obs", title=None, publisher_name=None,
        # the collection endpoint, which Frost refuses
        access_path="https://frost.met.no/observations/v0.jsonld", license=None,
    )
    registry.set_capability("frost:obs", {
        "capability": "observations", "record_kind": "observation",
        "endpoint": "https://frost.met.no/observations/v0.jsonld",
        "subject_template": FROST_TEMPLATE,
    })
    result = fetch_observations(
        registry, "frost:obs", table_id="observations", http=Recorder(),
        subject={"sources": "SN18700", "elements": "air_temperature",
                 "referencetime": "2026-10-01/2026-10-02"},
    )
    assert requested, "nothing was requested at all"
    assert "sources=SN18700" in requested[0], (
        f"the connector requested {requested[0]!r}, not the filled template"
    )
    assert result.counts.listed == 1
    assert registry.observation_count() == 1
    registry.close()


def test_without_a_subject_the_access_path_is_used_unchanged(tmp_path: Path) -> None:
    """The mechanism must not change how the other 190 connectors behave."""

    from public_data_agent.fetch import fetch_observations
    from public_data_agent.http_util import JsonResponse

    requested: list[str] = []

    class Recorder:
        def get_json_response(self, url: str, *, headers=None):
            requested.append(url)
            return JsonResponse(status=200, url=url, body={"license": None, "data": []})

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id="frost:sources", title=None, publisher_name=None,
        access_path="https://frost.met.no/sources/v0.jsonld?types=SensorSystem", license=None,
    )
    with pytest.raises(Exception):
        fetch_observations(registry, "frost:sources", table_id="sources", http=Recorder())
    assert requested == ["https://frost.met.no/sources/v0.jsonld?types=SensorSystem"]
    registry.close()
