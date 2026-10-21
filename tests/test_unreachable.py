"""A host that does not exist is its own verdict.

Geonorge advertises 82 datasets as OGC:OAPIF on `pycsw.nina.no`, which returns
NXDOMAIN from three resolvers while `nina.no` resolves. Until that was
recorded they were the second-largest group of queryable APIs in the registry
and 25% of the queryable-api tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from public_data_agent.fetch import (
    CAPABILITY_RESTRICTED,
    CAPABILITY_UNREACHABLE,
    CAPABILITY_WITHDRAWN,
    RETRIEVABLE_CAPABILITIES,
    is_retrievable,
)
from public_data_agent.registry import Registry


def test_unreachable_is_not_retrievable() -> None:
    assert not is_retrievable(CAPABILITY_UNREACHABLE)
    assert CAPABILITY_UNREACHABLE not in RETRIEVABLE_CAPABILITIES


def test_unreachable_is_distinct_from_withdrawn_and_restricted() -> None:
    """Each one says something different about why nothing came back.

    `withdrawn` answered 404, so a server considered the request and declined
    it. `restricted` is served to someone. `unreachable` has no server: the
    catalogue's entry is wrong and no connector can fix it.
    """

    assert len({CAPABILITY_UNREACHABLE, CAPABILITY_WITHDRAWN, CAPABILITY_RESTRICTED}) == 3


def test_a_verdict_can_be_recorded_without_a_sample_count(tmp_path: Path) -> None:
    """Nothing was fetched, so there is nothing to count.

    `verified_at` without `verified_sample_count` is refused elsewhere, and
    this verdict must not pretend to either.
    """

    registry = Registry(tmp_path / "registry.sqlite")
    registry.ensure_dataset_identity(
        dataset_id="nina:x", title=None, publisher_name=None,
        access_path="https://kartkatalog.geonorge.no/metadata/uuid/abc", license=None,
    )
    registry.set_capability("nina:x", {
        "capability": CAPABILITY_UNREACHABLE,
        "endpoint": "https://pycsw.nina.no/geoapi/collections/abc",
        "request_method": "GET",
        "notes": "pycsw.nina.no returns NXDOMAIN (local resolver, 1.1.1.1, 8.8.8.8)",
    })
    capability = registry.get_capability("nina:x")
    assert capability["capability"] == CAPABILITY_UNREACHABLE
    assert capability["verified_at"] is None
    assert capability["verified_sample_count"] is None
    assert "NXDOMAIN" in capability["notes"], "the reason travels with the verdict"
    registry.close()


def test_the_marker_refuses_to_act_on_a_host_that_resolves() -> None:
    """A DNS failure can be local and temporary, so the script re-checks.

    Writing 82 verdicts from a claim in a docstring is the failure this guards
    against.
    """

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mark_unreachable", Path("scripts/mark_unreachable.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.resolves("localhost") is True
    assert module.resolves("this-host-does-not-exist.invalid") is False
