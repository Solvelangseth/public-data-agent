"""Stable contracts shared by planners, executors, and interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Status = Literal["completed", "not_fetched", "failed"]


@dataclass(frozen=True)
class Provenance:
    dataset_id: str
    title: str | None = None
    publisher: str | None = None
    license: str | None = None
    access_path: str | None = None
    request_url: str | None = None
    periods: tuple[str, ...] = ()
    dimensions: dict[str, str] = field(default_factory=dict)
    why: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "title": self.title,
            "publisher": self.publisher,
            "license": self.license,
            "access_path": self.access_path,
            "request_url": self.request_url,
            "periods": list(self.periods),
            "dimensions": dict(self.dimensions),
            "why": self.why,
        }


@dataclass
class ToolResult:
    status: Status
    values: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[Provenance] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def numbers_retrieved(self) -> bool:
        return any(
            isinstance(value.get("value"), (int, float))
            and not isinstance(value.get("value"), bool)
            for value in self.values
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "values": self.values,
            "provenance": [item.to_dict() for item in self.provenance],
            "warnings": self.warnings,
            "error": self.error,
            "numbers_retrieved": self.numbers_retrieved,
        }


@dataclass(frozen=True)
class Artifact:
    kind: str
    path: str
    media_type: str
    rows: int | None = None
    columns: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "media_type": self.media_type,
            "rows": self.rows,
            "columns": list(self.columns),
            "lineage": list(self.lineage),
        }
