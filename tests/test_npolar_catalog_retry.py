"""The NPI service list is asked again when a backend answers without ids.

Measured on 2026-09-21 over eight requests to the same URL: five printed five
services with `id` and `path`, two printed them with `path` but no `id`, and
one printed nothing. Dropping every entry of a stripped response left harvest
with "printed no services" on roughly a third of runs.
"""

from __future__ import annotations

import pytest

from public_data_agent.models import SourceError
from public_data_agent.sources.npolar import CATALOG_ATTEMPTS, NpolarSource

GOOD = {"feed": {"entries": [{"id": "language-api", "path": "/language"}]}}
# The stripped variant: the path is printed, the id is not.
STRIPPED = {"feed": {"entries": [{"path": "/language"}],
                     "list": {"self": "http://api.npolar.no/service/?fields-remove=id,_id"}}}
EMPTY: dict[str, dict[str, list[object]]] = {"feed": {"entries": []}}


class _Http:
    def __init__(self, bodies: list[object]) -> None:
        self.bodies, self.calls = bodies, 0

    def get_json(self, url: str) -> object:
        body = self.bodies[min(self.calls, len(self.bodies) - 1)]
        self.calls += 1
        return body


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("public_data_agent.sources.npolar.time.sleep", lambda _s: None)


def test_a_stripped_listing_is_asked_again() -> None:
    http = _Http([STRIPPED, GOOD])
    source = NpolarSource(http=http)
    refs = source.list_dataset_refs(limit=5)
    assert [r.source_native_id for r in refs] == ["language-api"]
    assert http.calls == 2


def test_an_empty_listing_is_asked_again() -> None:
    http = _Http([EMPTY, GOOD])
    assert len(NpolarSource(http=http).list_dataset_refs(limit=5)) == 1
    assert http.calls == 2


def test_a_run_of_stripped_listings_is_an_error_naming_the_shape() -> None:
    http = _Http([STRIPPED])
    with pytest.raises(SourceError, match="1 entries printed, 1 with a path, none with an id"):
        NpolarSource(http=http).list_dataset_refs(limit=5)
    assert http.calls == CATALOG_ATTEMPTS


def test_a_path_never_becomes_an_id() -> None:
    # Deriving an id from the printed path would land the same service twice.
    http = _Http([STRIPPED])
    with pytest.raises(SourceError):
        NpolarSource(http=http).list_dataset_refs(limit=5)
