#!/usr/bin/env python3
"""Build data/benchmark_questions.json from the live registry.

Every expected id is looked up. Every reason is checked against a stored field.
This script refuses to write a question it cannot source.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from public_data_agent.benchmark import validate_questions
from public_data_agent.registry import Registry
from public_data_agent.search import keywords_from_payload

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "registry.sqlite"
DEFAULT_OUT = ROOT / "data" / "benchmark_questions.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"no registry at {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    questions = [_build(conn, spec) for spec in SPECS]
    payload = {
        "version": 1,
        "sourced_from": str(args.db),
        "sourced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule": (
            "Every expected dataset_id exists in the registry. "
            "Every reason cites a stored title, publisher_name, keyword, theme, or description."
        ),
        "kinds": {
            "simple": "query uses a distinctive stored title token",
            "synonym": "query uses a stored keyword that is not the title string",
            "indirect": "query uses a stored theme or description phrase, not the title",
            "multi": "query has two stored-field requirements",
            "hard": "publisher-only or a stored synonym that our title-token search may miss",
        },
        "questions": questions,
    }
    registry = Registry(args.db)
    try:
        validate_questions(registry, payload)
    finally:
        registry.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(questions)} questions to {args.out}")
    return 0


def _build(conn: sqlite3.Connection, spec: dict) -> dict:
    rows = _lookup(conn, spec)
    if not rows:
        raise SystemExit(f"{spec['id']}: no registry row for {spec}")
    expected = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        reason_specs = spec.get("per_id_reasons", {}).get(row["id"], spec.get("reasons"))
        if not reason_specs:
            raise SystemExit(f"{spec['id']}: no reasons for {row['id']}")
        reasons = []
        for reason in reason_specs:
            stored = _stored_value(row, payload, reason)
            if not stored:
                raise SystemExit(f"{spec['id']}: {reason} empty on {row['id']}")
            reasons.append({"field": reason["field"], "stored": stored})
        expected.append({"dataset_id": row["id"], "reasons": reasons})
    return {
        "id": spec["id"],
        "kind": spec["kind"],
        "query": spec["query"],
        "expected": expected,
        "requirements": spec["requirements"],
    }


def _lookup(conn: sqlite3.Connection, spec: dict) -> list[sqlite3.Row]:
    if "dataset_id" in spec:
        row = conn.execute(
            """
            SELECT d.id, d.title, d.publisher_name, d.description, p.payload_json
            FROM datasets d
            JOIN harvested_payloads p ON p.dataset_id = d.id
            WHERE d.id = ?
            """,
            (spec["dataset_id"],),
        ).fetchone()
        return [row] if row else []
    if "title_exact" in spec:
        return list(
            conn.execute(
                """
                SELECT d.id, d.title, d.publisher_name, d.description, p.payload_json
                FROM datasets d
                JOIN harvested_payloads p ON p.dataset_id = d.id
                WHERE d.title = ?
                """,
                (spec["title_exact"],),
            )
        )
    if "ids" in spec:
        found = []
        for dataset_id in spec["ids"]:
            row = conn.execute(
                """
                SELECT d.id, d.title, d.publisher_name, d.description, p.payload_json
                FROM datasets d
                JOIN harvested_payloads p ON p.dataset_id = d.id
                WHERE d.id = ?
                """,
                (dataset_id,),
            ).fetchone()
            if row is None:
                raise SystemExit(f"{spec['id']}: missing {dataset_id}")
            found.append(row)
        return found
    raise SystemExit(f"{spec['id']}: lookup key missing")


def _stored_value(row: sqlite3.Row, payload: dict, reason: dict) -> str | None:
    field = reason["field"]
    if field == "title":
        return row["title"]
    if field == "publisher_name":
        return row["publisher_name"]
    if field == "description":
        text = row["description"] or ""
        needle = reason["contains"]
        return needle if needle.casefold() in text.casefold() else None
    if field == "keyword":
        needle = reason["contains"]
        for item in keywords_from_payload(payload):
            if needle.casefold() == item.casefold() or needle.casefold() in item.casefold():
                return item
        return None
    if field == "theme":
        needle = reason["contains"]
        for item in _theme_labels(payload):
            if needle.casefold() == item.casefold():
                return item
        return None
    return None


def _theme_labels(payload: dict) -> list[str]:
    labels: list[str] = []
    for key in ("theme", "losTheme"):
        value = payload.get(key)
        items = value if isinstance(value, list) else [value] if value else []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("prefLabel")
            if isinstance(title, dict):
                labels.extend(str(part) for part in title.values() if part)
            elif isinstance(title, str):
                labels.append(title)
            code = item.get("code")
            if isinstance(code, str):
                labels.append(code)
    return labels


# Each spec names a live row. Queries are words taken from that stored field.
SPECS = [
    {
        "id": "q001",
        "kind": "simple",
        "query": "abortregisteret",
        "title_exact": "Register over svangerskapsavbrudd (Abortregisteret)",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "abortregisteret", "kind": "token", "field": "title", "token": "abortregisteret"}],
    },
    {
        "id": "q002",
        "kind": "simple",
        "query": "familievernkontorenes dokumentasjonssystem",
        "title_exact": "Familievernkontorenes dokumentasjonssystem",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "familievernkontorenes", "kind": "token", "field": "title", "token": "familievernkontorenes"},
            {"id": "dokumentasjonssystem", "kind": "token", "field": "title", "token": "dokumentasjonssystem"},
        ],
    },
    {
        "id": "q003",
        "kind": "simple",
        "query": "ilandstigningslokaliteter svalbard",
        "title_exact": "Ilandstigningslokaliteter Svalbard",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "ilandstigningslokaliteter", "kind": "token", "field": "title", "token": "ilandstigningslokaliteter"},
            {"id": "svalbard", "kind": "token", "field": "title", "token": "svalbard"},
        ],
    },
    {
        "id": "q004",
        "kind": "simple",
        "query": "nntrans",
        "title_exact": "Høydetransformasjonsmodell (NNTrans)",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "nntrans", "kind": "token", "field": "title", "token": "nntrans"}],
    },
    {
        "id": "q005",
        "kind": "simple",
        "query": "arealrepresentativ naturovervåking",
        "title_exact": "Arealrepresentativ naturovervåking (ANO)",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "arealrepresentativ", "kind": "token", "field": "title", "token": "arealrepresentativ"},
            {"id": "naturovervåking", "kind": "token", "field": "title", "token": "naturovervåking"},
        ],
    },
    {
        "id": "q006",
        "kind": "simple",
        "query": "blomkålkorallskog",
        "title_exact": "Sårbare marine bunndyr - observasjonsdata Blomkålkorallskog",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "blomkålkorallskog", "kind": "token", "field": "title", "token": "blomkålkorallskog"}],
    },
    {
        "id": "q007",
        "kind": "simple",
        "query": "tilleggstollavgiftssatser",
        "title_exact": "Nåværende og fremtidige tilleggstollavgiftssatser / Current and future increased customs duty for imports",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "tilleggstollavgiftssatser", "kind": "token", "field": "title", "token": "tilleggstollavgiftssatser"}],
    },
    {
        "id": "q008",
        "kind": "simple",
        "query": "flydata avinor",
        "title_exact": "Flydata fra Avinor",
        "reasons": [{"field": "title"}, {"field": "publisher_name"}],
        "requirements": [
            {"id": "flydata", "kind": "token", "field": "title", "token": "flydata"},
            {"id": "avinor", "kind": "token", "field": "title", "token": "avinor"},
        ],
    },
    {
        "id": "q009",
        "kind": "simple",
        "query": "gjeldsregisteret",
        "title_exact": "Gjeldsregisteret",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "gjeldsregisteret", "kind": "token", "field": "title", "token": "gjeldsregisteret"}],
    },
    {
        "id": "q010",
        "kind": "simple",
        "query": "radnett radioaktivitet",
        "title_exact": "Radnett - overvåking av radioaktivitet",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "radnett", "kind": "token", "field": "title", "token": "radnett"},
            {"id": "radioaktivitet", "kind": "token", "field": "title", "token": "radioaktivitet"},
        ],
    },
    {
        "id": "q011",
        "kind": "simple",
        "query": "kirkebygg",
        "title_exact": "Kirkebygg i Norge",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "kirkebygg", "kind": "token", "field": "title", "token": "kirkebygg"}],
    },
    {
        "id": "q012",
        "kind": "simple",
        "query": "badevannstemperaturer horten",
        "title_exact": "Badevannstemperaturer Horten",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "badevannstemperaturer", "kind": "token", "field": "title", "token": "badevannstemperaturer"},
            {"id": "horten", "kind": "token", "field": "title", "token": "horten"},
        ],
    },
    {
        "id": "q013",
        "kind": "simple",
        "query": "kulturminner hadsel",
        "title_exact": "Kulturminner i Hadsel kommune",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "kulturminner", "kind": "token", "field": "title", "token": "kulturminner"},
            {"id": "hadsel", "kind": "token", "field": "title", "token": "hadsel"},
        ],
    },
    {
        "id": "q014",
        "kind": "simple",
        "query": "skyteanlegg dfs",
        "title_exact": "Skyteanlegg DFS",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "skyteanlegg", "kind": "token", "field": "title", "token": "skyteanlegg"},
            {"id": "dfs", "kind": "token", "field": "title", "token": "dfs"},
        ],
    },
    {
        "id": "q015",
        "kind": "simple",
        "query": "forsvarets helseregister",
        "title_exact": "Forsvarets helseregister",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "forsvarets", "kind": "token", "field": "title", "token": "forsvarets"},
            {"id": "helseregister", "kind": "token", "field": "title", "token": "helseregister"},
        ],
    },
    {
        "id": "q016",
        "kind": "simple",
        "query": "husbankens statistikkbank",
        "title_exact": "Husbankens statistikkbank",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "husbankens", "kind": "token", "field": "title", "token": "husbankens"},
            {"id": "statistikkbank", "kind": "token", "field": "title", "token": "statistikkbank"},
        ],
    },
    {
        "id": "q017",
        "kind": "simple",
        "query": "kulturnav",
        "title_exact": "KulturNav",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "kulturnav", "kind": "token", "field": "title", "token": "kulturnav"}],
    },
    {
        "id": "q018",
        "kind": "simple",
        "query": "anleggsregisteret",
        "title_exact": "Anleggsregisteret",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "anleggsregisteret", "kind": "token", "field": "title", "token": "anleggsregisteret"}],
    },
    {
        "id": "q019",
        "kind": "simple",
        "query": "bivirkningsregisteret",
        "title_exact": "Bivirkningsregisteret",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "bivirkningsregisteret", "kind": "token", "field": "title", "token": "bivirkningsregisteret"}],
    },
    {
        "id": "q020",
        "kind": "simple",
        "query": "kreftregisteret",
        "title_exact": "Kreftregisteret",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "kreftregisteret", "kind": "token", "field": "title", "token": "kreftregisteret"}],
    },
    {
        "id": "q021",
        "kind": "simple",
        "query": "medisinsk fødselsregister",
        "title_exact": "Medisinsk Fødselsregister",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "medisinsk", "kind": "token", "field": "title", "token": "medisinsk"},
            {"id": "fødselsregister", "kind": "token", "field": "title", "token": "fødselsregister"},
        ],
    },
    {
        "id": "q022",
        "kind": "simple",
        "query": "nowac",
        "title_exact": "The Norwegian Women and Cancer study (NOWAC)",
        "reasons": [{"field": "title"}],
        "requirements": [{"id": "nowac", "kind": "token", "field": "title", "token": "nowac"}],
    },
    {
        "id": "q023",
        "kind": "simple",
        "query": "strandsonekartlegging jølstravassdraget",
        "title_exact": "Strandsonekartlegging Jølstravassdraget 2026",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "strandsonekartlegging", "kind": "token", "field": "title", "token": "strandsonekartlegging"},
            {"id": "jølstravassdraget", "kind": "token", "field": "title", "token": "jølstravassdraget"},
        ],
    },
    {
        "id": "q024",
        "kind": "simple",
        "query": "landbrukseiendommer landbruksregisteret",
        "title_exact": "Landbrukseiendommer i Landbruksregisteret",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "landbrukseiendommer", "kind": "token", "field": "title", "token": "landbrukseiendommer"},
            {"id": "landbruksregisteret", "kind": "token", "field": "title", "token": "landbruksregisteret"},
        ],
    },
    {
        "id": "q025",
        "kind": "synonym",
        "query": "oljeindustri",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "keyword", "contains": "oljeindustri"}],
        "requirements": [{"id": "oljeindustri", "kind": "token", "field": "keyword", "token": "oljeindustri"}],
    },
    {
        "id": "q026",
        "kind": "synonym",
        "query": "gruveindustri",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "keyword", "contains": "gruveindustri"}],
        "requirements": [{"id": "gruveindustri", "kind": "token", "field": "keyword", "token": "gruveindustri"}],
    },
    {
        "id": "q027",
        "kind": "synonym",
        "query": "petroliumsindustri",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "keyword", "contains": "petroliumsindustri"}],
        "requirements": [{"id": "petroliumsindustri", "kind": "token", "field": "keyword", "token": "petroliumsindustri"}],
    },
    {
        "id": "q028",
        "kind": "synonym",
        "query": "datahotell",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "keyword", "contains": "datahotell"}],
        "requirements": [{"id": "datahotell", "kind": "token", "field": "keyword", "token": "datahotell"}],
    },
    {
        "id": "q029",
        "kind": "synonym",
        "query": "produksjonstilskudd",
        "dataset_id": "datanorge:239fb895-061c-3b8a-a752-6f939db02fed",
        "reasons": [{"field": "keyword", "contains": "produksjonstilskudd"}],
        "requirements": [{"id": "produksjonstilskudd", "kind": "token", "field": "keyword", "token": "produksjonstilskudd"}],
    },
    {
        "id": "q030",
        "kind": "synonym",
        "query": "doffin",
        "dataset_id": "datanorge:a77b0408-85f9-3e12-8a66-8d500b492e9d",
        "reasons": [{"field": "keyword", "contains": "Doffin"}],
        "requirements": [{"id": "doffin", "kind": "token", "field": "keyword", "token": "doffin"}],
    },
    {
        "id": "q031",
        "kind": "synonym",
        "query": "quickclay",
        "dataset_id": "datanorge:af4e4e83-7c26-3b89-bc9b-58739083758d",
        "reasons": [{"field": "keyword", "contains": "quickclay"}],
        "requirements": [{"id": "quickclay", "kind": "token", "field": "keyword", "token": "quickclay"}],
    },
    {
        "id": "q032",
        "kind": "synonym",
        "query": "rockfall",
        "dataset_id": "datanorge:abdfbcc5-8c3c-3bf1-a13a-09672723ffda",
        "reasons": [{"field": "keyword", "contains": "rockfall"}],
        "requirements": [{"id": "rockfall", "kind": "token", "field": "keyword", "token": "rockfall"}],
    },
    {
        "id": "q033",
        "kind": "synonym",
        "query": "oljevernberedskap",
        "dataset_id": "datanorge:29be745f-5da2-3ef7-b1a8-560a338f54ec",
        "reasons": [{"field": "keyword", "contains": "Oljevernberedskap"}],
        "requirements": [{"id": "oljevernberedskap", "kind": "token", "field": "keyword", "token": "oljevernberedskap"}],
    },
    {
        "id": "q034",
        "kind": "synonym",
        "query": "grunnforurensning",
        "dataset_id": "datanorge:fbd6e4e4-4d30-3bb7-9d3f-f3660462fe59",
        "reasons": [{"field": "keyword", "contains": "grunnforurensning"}],
        "requirements": [{"id": "grunnforurensning", "kind": "token", "field": "keyword", "token": "grunnforurensning"}],
    },
    {
        "id": "q035",
        "kind": "synonym",
        "query": "energy cooperatives",
        "dataset_id": "datanorge:0d56ad96-5a51-32d6-93a1-ef5305ab5751",
        "reasons": [{"field": "keyword", "contains": "energy cooperatives"}],
        "requirements": [
            {"id": "energy", "kind": "token", "field": "keyword", "token": "energy"},
            {"id": "cooperatives", "kind": "token", "field": "keyword", "token": "cooperatives"},
        ],
    },
    {
        "id": "q036",
        "kind": "indirect",
        "query": "Health",
        "dataset_id": "datanorge:0d45b3e6-467a-3b5e-bab2-2672002fd13e",
        "reasons": [{"field": "theme", "contains": "Health"}],
        "requirements": [{"id": "health", "kind": "token", "field": "theme", "token": "health"}],
    },
    {
        "id": "q037",
        "kind": "indirect",
        "query": "Helse",
        "dataset_id": "datanorge:0d45b3e6-467a-3b5e-bab2-2672002fd13e",
        "reasons": [{"field": "theme", "contains": "Helse"}],
        "requirements": [{"id": "helse", "kind": "token", "field": "theme", "token": "helse"}],
    },
    {
        "id": "q038",
        "kind": "indirect",
        "query": "offentlig sektor",
        "dataset_id": "datanorge:0d45b3e6-467a-3b5e-bab2-2672002fd13e",
        "reasons": [{"field": "keyword", "contains": "offentlig sektor"}],
        "requirements": [
            {"id": "offentlig", "kind": "token", "field": "keyword", "token": "offentlig"},
            {"id": "sektor", "kind": "token", "field": "keyword", "token": "sektor"},
        ],
    },
    {
        "id": "q039",
        "kind": "indirect",
        "query": "Energy",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "theme", "contains": "Energy"}],
        "requirements": [{"id": "energy", "kind": "token", "field": "theme", "token": "energy"}],
    },
    {
        "id": "q040",
        "kind": "indirect",
        "query": "ECON",
        "dataset_id": "datanorge:607f3e76-2bfe-3570-b359-492d6ed57b5c",
        "reasons": [{"field": "theme", "contains": "ECON"}],
        "requirements": [{"id": "econ", "kind": "token", "field": "theme", "token": "econ"}],
    },
    {
        "id": "q041",
        "kind": "indirect",
        "query": "Public procurement",
        "dataset_id": "datanorge:a77b0408-85f9-3e12-8a66-8d500b492e9d",
        "reasons": [{"field": "theme", "contains": "Public procurement"}],
        "requirements": [
            {"id": "public", "kind": "token", "field": "theme", "token": "public"},
            {"id": "procurement", "kind": "token", "field": "theme", "token": "procurement"},
        ],
    },
    {
        "id": "q042",
        "kind": "indirect",
        "query": "AGRI",
        "dataset_id": "datanorge:239fb895-061c-3b8a-a752-6f939db02fed",
        "reasons": [{"field": "theme", "contains": "AGRI"}],
        "requirements": [{"id": "agri", "kind": "token", "field": "theme", "token": "agri"}],
    },
    {
        "id": "q043",
        "kind": "indirect",
        "query": "family history of cancer",
        "dataset_id": "datanorge:8e77e6bf-a4fa-38ec-83c9-605f8e0b8324",
        "reasons": [{"field": "keyword", "contains": "FAMILY HISTORY OF CANCER"}],
        "requirements": [
            {"id": "family", "kind": "token", "field": "keyword", "token": "family"},
            {"id": "cancer", "kind": "token", "field": "keyword", "token": "cancer"},
        ],
    },
    {
        "id": "q044",
        "kind": "indirect",
        "query": "citizen energy",
        "dataset_id": "datanorge:0d56ad96-5a51-32d6-93a1-ef5305ab5751",
        "reasons": [{"field": "keyword", "contains": "citizen energy"}],
        "requirements": [
            {"id": "citizen", "kind": "token", "field": "keyword", "token": "citizen"},
            {"id": "energy", "kind": "token", "field": "keyword", "token": "energy"},
        ],
    },
    {
        "id": "q045",
        "kind": "multi",
        "query": "forurensning oslo",
        "ids": [
            "datanorge:a290a2d1-b5eb-3747-8e00-5bca67b89c90",
            "datanorge:4a6016f8-3a64-38e6-8bdc-8a05168e0989",
            "datanorge:f5d0ed23-0c50-3caf-9e63-7da9cfb80481",
        ],
        "per_id_reasons": {
            "datanorge:a290a2d1-b5eb-3747-8e00-5bca67b89c90": [
                {"field": "keyword", "contains": "forurensning"},
                {"field": "keyword", "contains": "oslo"},
            ],
            "datanorge:4a6016f8-3a64-38e6-8bdc-8a05168e0989": [
                {"field": "keyword", "contains": "forurensning"},
                {"field": "description", "contains": "oslo"},
            ],
            "datanorge:f5d0ed23-0c50-3caf-9e63-7da9cfb80481": [
                {"field": "description", "contains": "forurensning"},
                {"field": "description", "contains": "oslo"},
            ],
        },
        "requirements": [
            {"id": "forurensning", "kind": "token", "token": "forurensning"},
            {"id": "oslo", "kind": "token", "token": "oslo"},
        ],
    },
    {
        "id": "q046",
        "kind": "multi",
        "query": "akutt forurensning",
        "ids": [
            "datanorge:29be745f-5da2-3ef7-b1a8-560a338f54ec",
            "datanorge:a2c06b68-72c6-3675-ae4d-4f5695dba13d",
        ],
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "akutt", "kind": "token", "field": "title", "token": "akutt"},
            {"id": "forurensning", "kind": "token", "field": "title", "token": "forurensning"},
        ],
    },
    {
        "id": "q047",
        "kind": "multi",
        "query": "elvebunnkartlegging hellelandselva",
        "ids": [
            "datanorge:bd2df436-c9b3-35a2-aa78-eb7bf840a1d9",
            "datanorge:1c1d1c95-c75b-3f76-ab41-c9e2931634db",
        ],
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "elvebunnkartlegging", "kind": "token", "field": "title", "token": "elvebunnkartlegging"},
            {"id": "hellelandselva", "kind": "token", "field": "title", "token": "hellelandselva"},
        ],
    },
    {
        "id": "q048",
        "kind": "multi",
        "query": "hardbunnskorallskog observasjonsdata",
        "title_exact": "Sårbare marine bunndyr - observasjonsdata Hardbunnskorallskog",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "hardbunnskorallskog", "kind": "token", "field": "title", "token": "hardbunnskorallskog"},
            {"id": "observasjonsdata", "kind": "token", "field": "title", "token": "observasjonsdata"},
        ],
    },
    {
        "id": "q049",
        "kind": "multi",
        "query": "vannforsyningssystem innrapportering",
        "title_exact": "Vannverk - vannforsyningssystem_innrapportering",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "vannforsyningssystem", "kind": "token", "field": "title", "token": "vannforsyningssystem"},
            {"id": "innrapportering", "kind": "token", "field": "title", "token": "innrapportering"},
        ],
    },
    {
        "id": "q050",
        "kind": "multi",
        "query": "saltvannssjøbunn punktobservasjoner",
        "title_exact": "NiN grunntyper og hovedtyper av saltvannssjøbunn, punktobservasjoner",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "saltvannssjøbunn", "kind": "token", "field": "title", "token": "saltvannssjøbunn"},
            {"id": "punktobservasjoner", "kind": "token", "field": "title", "token": "punktobservasjoner"},
        ],
    },
    {
        "id": "q051",
        "kind": "multi",
        "query": "operasjonelle akvakulturrettigheter",
        "title_exact": "Offentlig API for operasjonelle akvakulturrettigheter",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "operasjonelle", "kind": "token", "field": "title", "token": "operasjonelle"},
            {"id": "akvakulturrettigheter", "kind": "token", "field": "title", "token": "akvakulturrettigheter"},
        ],
    },
    {
        "id": "q052",
        "kind": "multi",
        "query": "bølgevarsel punkt",
        "title_exact": "Bølgevarsel - punkt",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "bølgevarsel", "kind": "token", "field": "title", "token": "bølgevarsel"},
            {"id": "punkt", "kind": "token", "field": "title", "token": "punkt"},
        ],
    },
    {
        "id": "q053",
        "kind": "multi",
        "query": "sanntidsdata buss sør-trøndelag",
        "title_exact": "Sanntidsdata - Buss i Sør-Trøndelag",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "sanntidsdata", "kind": "token", "field": "title", "token": "sanntidsdata"},
            {"id": "buss", "kind": "token", "field": "title", "token": "buss"},
        ],
    },
    {
        "id": "q054",
        "kind": "multi",
        "query": "trafikkdata bane nor",
        "title_exact": "Trafikkdata fra Bane NOR",
        "reasons": [{"field": "title"}],
        "requirements": [
            {"id": "trafikkdata", "kind": "token", "field": "title", "token": "trafikkdata"},
            {"id": "bane", "kind": "token", "field": "title", "token": "bane"},
        ],
    },
    {
        "id": "q055",
        "kind": "hard",
        "query": "AVINOR AS",
        "title_exact": "Flydata fra Avinor",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "avinor", "kind": "token", "field": "publisher_name", "token": "avinor"}],
    },
    {
        "id": "q056",
        "kind": "hard",
        "query": "AtB",
        "title_exact": "Sanntidsdata - Buss i Sør-Trøndelag",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "atb", "kind": "token", "field": "publisher_name", "token": "atb"}],
    },
    {
        "id": "q057",
        "kind": "hard",
        "query": "Gjeldsregisteret as",
        "title_exact": "Gjeldsregisteret",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "gjeldsregisteret", "kind": "token", "field": "publisher_name", "token": "gjeldsregisteret"}],
    },
    {
        "id": "q058",
        "kind": "hard",
        "query": "Barentswatch",
        "title_exact": "Bølgevarsel - punkt",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "barentswatch", "kind": "token", "field": "publisher_name", "token": "barentswatch"}],
    },
    {
        "id": "q059",
        "kind": "hard",
        "query": "Geonorge",
        "title_exact": 'Ruteinndelinger ("velg fra kartblad")',
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "geonorge", "kind": "token", "field": "publisher_name", "token": "geonorge"}],
    },
    {
        "id": "q060",
        "kind": "hard",
        "query": "INDRE ØSTFOLD KOMMUNE",
        "title_exact": "Nød- og vakttelefoner",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "østfold", "kind": "token", "field": "publisher_name", "token": "østfold"}],
    },
    {
        "id": "q061",
        "kind": "hard",
        "query": "HØGSKOLEN I BERGEN",
        "title_exact": "Tidligere eksamensoppgaver fra Høgskolen i Bergen",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "høgskolen", "kind": "token", "field": "publisher_name", "token": "høgskolen"}],
    },
    {
        "id": "q062",
        "kind": "hard",
        "query": "Det frivillige Skyttervesen",
        "title_exact": "Skyteanlegg DFS",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "skyttervesen", "kind": "token", "field": "publisher_name", "token": "skyttervesen"}],
    },
    {
        "id": "q063",
        "kind": "hard",
        "query": "Forsvaret",
        "title_exact": "Forsvarets helseregister",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "forsvaret", "kind": "token", "field": "publisher_name", "token": "forsvaret"}],
    },
    {
        "id": "q064",
        "kind": "hard",
        "query": "KULTURIT ANS",
        "title_exact": "KulturNav",
        "reasons": [{"field": "publisher_name"}],
        "requirements": [{"id": "kulturit", "kind": "token", "field": "publisher_name", "token": "kulturit"}],
    },
    {
        "id": "q065",
        "kind": "hard",
        "query": "Soil",
        "dataset_id": "datanorge:fbd6e4e4-4d30-3bb7-9d3f-f3660462fe59",
        "reasons": [{"field": "keyword", "contains": "Soil"}],
        "requirements": [{"id": "soil", "kind": "token", "field": "keyword", "token": "soil"}],
    },
]


if __name__ == "__main__":
    raise SystemExit(main())
