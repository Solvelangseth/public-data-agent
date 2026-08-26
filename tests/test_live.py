from __future__ import annotations

import os

import pytest

from public_data_agent.harvest import harvest
from public_data_agent.registry import Registry
from public_data_agent.sources.datanorge import DataNorgeSource

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.environ.get("PDA_ALLOW_LIVE") != "1", reason="live harvest is opt-in")
def test_live_smoke_two_datasets(tmp_path) -> None:
    """Hits production. Not collected in CI (pytest -m 'not live')."""

    registry = Registry(tmp_path / "registry.sqlite")
    counts = harvest(registry, DataNorgeSource(), limit=2)
    assert counts.failed == 0
    assert counts.inserted == 2
    assert registry.dataset_count() == 2
    registry.close()
