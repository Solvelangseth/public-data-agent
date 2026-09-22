"""`pda status` says how many datasets have no vector.

A question is ranked by embedding alone, so a dataset without one cannot be
found by a question. Harvesting adds rows without vectors; on 2026-09-21,
1,702 of 15,446 rows had none, including every answer to four gold questions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from public_data_agent.cli import EMBEDDING_MODEL, _status
from public_data_agent.embeddings import pack
from public_data_agent.registry import Registry


def _dataset(registry: Registry, dataset_id: str) -> None:
    registry.ensure_observation_dataset(
        dataset_id=dataset_id, title=dataset_id, publisher_name="t",
        access_path=None, license=None,
    )


def test_counts_datasets_without_a_vector_for_that_model(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    try:
        for dataset_id in ("fixture:a", "fixture:b", "fixture:c"):
            _dataset(registry, dataset_id)
        registry.upsert_embedding(
            dataset_id="fixture:a", model=EMBEDDING_MODEL, vector=pack([1.0, 0.0]), dim=2, text_hash="h",
        )
        # A vector under another model does not make a row findable by this one.
        registry.upsert_embedding(
            dataset_id="fixture:b", model="other-model", vector=pack([1.0, 0.0]), dim=2, text_hash="h",
        )
        assert registry.count_without_embedding(EMBEDDING_MODEL) == 2
        assert registry.count_without_embedding("other-model") == 2
    finally:
        registry.close()


def test_status_reports_the_count(tmp_path: Path, capsys) -> None:
    db = tmp_path / "registry.sqlite"
    registry = Registry(db)
    try:
        _dataset(registry, "fixture:a")
    finally:
        registry.close()

    assert _status(argparse.Namespace(db=db)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["without_embedding"] == {EMBEDDING_MODEL: 1}
