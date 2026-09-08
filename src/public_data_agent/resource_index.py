"""Index what a resource contains, so a question can reach it by its contents.

Search reads a title and little else, which is why a question naming a place can
miss a table that holds that place's code and never says so in its name. This
module records a resource's shape -- its fields, the values they carry, the
identifier schemes they speak -- and searches over it.

Nothing here fetches data. It reads the metadata a source already publishes
about its own tables, and writes the resource_* tables through `Registry`.
"""

from __future__ import annotations

import re
from typing import Any

from public_data_agent.fetch import JsonHttp
from public_data_agent.http_util import HttpClient
from public_data_agent.registry import Registry, utc_now

# A field whose values look like these is a period, not an attribute. Naming the
# role means a caller can find the time field without guessing at its code,
# which differs by publisher ("Tid", "AAR", "year").
PERIOD_FIELD_CODES = frozenset({"tid", "aar", "år", "year", "periode", "time"})
PERIOD_VALUE = re.compile(r"^(1[6-9]|20)\d{2}([MKQUH]\d{1,2}|-\d{2})?$")

# Published identifier systems. A scheme is claimed only when a field's values
# are actually in the published code list -- never from the shape of the codes.
# Matching on shape alone tagged employer associations, transport types and
# livestock species as counties, because all three number themselves 01, 02, 03.
# A join on that key would match "01" to "01" and produce nonsense carrying
# perfect provenance.
KLASS_CLASSIFICATIONS = {
    "klass:104:fylke": 104,
    "klass:131:kommune": 131,
    "klass:103:bydel": 103,
}
# Below this share of a field's values, an overlap is coincidence. Small code
# lists overlap by accident more easily, so the floor is a share, not a count.
MIN_SCHEME_SHARE = 0.6
MIN_SCHEME_MATCHES = 3

# Values a caller could never usefully search for, and which would otherwise
# dominate the index: a table of monthly periods since 1978 carries 583 of them.
MAX_VALUES_PER_FIELD = 400

# Statistical tables carry decades of history, so a key must be checked against
# codes that were valid then as well as now: "01" was Østfold until the 2020
# county reform and still appears in thousands of tables.
KLASS_HISTORY_FROM = "1970-01-01"
KLASS_HISTORY_TO = "2030-01-01"

_CODE_CACHE: dict[str, dict[str, set[str]]] = {}


def klass_codes(scheme: str, *, http: JsonHttp | None = None) -> dict[str, set[str]]:
    """A published classification's codes and the names it gives them.

    The names matter as much as the codes. Historical county codes run 01-20,
    and so does every small category a statistician ever numbered, so code
    membership alone cannot tell a county from a livestock species. The name
    can: "01" is Østfold in one and Storfe in the other.

    Cached per process. A failure returns empty, and an empty list claims no
    scheme -- an unverifiable key is not a key.
    """

    if scheme in _CODE_CACHE:
        return _CODE_CACHE[scheme]
    classification = KLASS_CLASSIFICATIONS.get(scheme)
    if classification is None:
        return {}
    client = http or HttpClient(timeout=30.0, max_retries=2)
    try:
        body = client.get_json_response(
            f"https://data.ssb.no/api/klass/v1/classifications/{classification}/codes"
            f"?from={KLASS_HISTORY_FROM}&to={KLASS_HISTORY_TO}"
        ).body
        # A code carries several names across reforms -- 030101 is Gamle Oslo
        # now and was Bygdøy-Frogner before 2004 -- so every published name is
        # kept. Keeping one would reject a table that uses any of the others.
        codes: dict[str, set[str]] = {}
        for item in (body or {}).get("codes") or []:
            code = item.get("code")
            if not code:
                continue
            codes.setdefault(str(code), set()).add(str(item.get("name") or ""))
    except Exception:
        codes = {}
    _CODE_CACHE[scheme] = codes
    return codes


def load_classifications(*, http: JsonHttp | None = None) -> dict[str, dict[str, set[str]]]:
    """Every published code list the indexer can verify a key against."""

    return {
        scheme: klass_codes(scheme, http=http)
        for scheme in KLASS_CLASSIFICATIONS
        if klass_codes(scheme, http=http)
    }


def _names_agree(label: str, published: set[str] | str) -> bool:
    """Whether a field's label for a code is a name the classification gives it.

    Publishers decorate names -- "Oslo (fylke)", "Østfold (-2019)", "Bydel
    Grünerløkka" -- so containment either way counts, but an empty label never
    does. Any of a code's published names is enough, since a table may use the
    name from whichever era its data covers.
    """

    a = (label or "").casefold().strip()
    if not a:
        return False
    names = {published} if isinstance(published, str) else published
    for name in names:
        b = (name or "").casefold().strip()
        if b and (a == b or b in a or a in b):
            return True
    return False


def field_role(code: str, values: list[tuple[str, str]],
               catalogues: dict[str, dict[str, set[str]]] | None = None) -> str:
    """Say how a field may be used: key, period, measure, attribute."""

    lowered = code.casefold()
    if lowered in PERIOD_FIELD_CODES:
        return "period"
    if values and all(PERIOD_VALUE.match(value) for value, _ in values[:12]):
        return "period"
    if lowered in {"contentscode", "measure_type", "statistikkvariabel"}:
        return "measure"
    if _schemes_for(values, catalogues):
        return "key"
    return "attribute"


def _schemes_for(
    values: list[tuple[str, str]],
    catalogues: dict[str, dict[str, set[str]]] | None = None,
) -> list[dict[str, Any]]:
    """Which published classifications a field's values actually belong to.

    A value counts only when its code is in the classification *and* the field's
    label for that code is the name the classification gives it. Codes alone are
    not enough: historical county codes and the numbering of any small category
    are both 01, 02, 03.

    With no code lists to check against, nothing is claimed. A key that cannot
    be verified against what the publisher published is a guess, and a guessed
    join key is worse than none.
    """

    if not catalogues or not values:
        return []
    distinct = {code: label for code, label in values if code}
    if not distinct:
        return []
    found: list[dict[str, Any]] = []
    for scheme, known in catalogues.items():
        if not known:
            continue
        agreed = [
            code
            for code, label in distinct.items()
            if code in known and _names_agree(label, known[code])
        ]
        if len(agreed) >= MIN_SCHEME_MATCHES and len(agreed) >= len(distinct) * MIN_SCHEME_SHARE:
            found.append({"scheme": scheme, "coverage_count": len(agreed)})
    return found


def shape_from_pxweb(
    meta: dict[str, Any], catalogues: dict[str, dict[str, set[str]]] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read an SSB PxWeb table's published metadata into fields and key schemes."""

    fields: list[dict[str, Any]] = []
    keys: list[dict[str, Any]] = []
    for variable in meta.get("variables") or []:
        code = str(variable.get("code") or "")
        if not code:
            continue
        values = list(
            zip(
                [str(v) for v in variable.get("values") or []],
                [str(t) for t in variable.get("valueTexts") or []],
            )
        )
        role = field_role(code, values, catalogues)
        kept = values if len(values) <= MAX_VALUES_PER_FIELD else values[:MAX_VALUES_PER_FIELD]
        fields.append(
            {
                "field_code": code,
                "field_label": variable.get("text"),
                "field_role": role,
                # The count is of everything published, not of what was kept, so
                # a truncated field does not read as a smaller one.
                "value_count": len(values),
                "values": [{"value_code": c, "value_label": t} for c, t in kept],
            }
        )
        for found in _schemes_for(values, catalogues):
            keys.append({**found, "field_code": code})
    return fields, keys


def shape_from_fhi(
    dimensions: list[dict[str, Any]], catalogues: dict[str, dict[str, set[str]]] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read an FHI table's dimension metadata into fields and key schemes."""

    from public_data_agent.sources.fhi import flatten_categories

    fields: list[dict[str, Any]] = []
    keys: list[dict[str, Any]] = []
    for dim in dimensions:
        code = str(dim.get("code") or "")
        if not code:
            continue
        values = flatten_categories(dim.get("categories"))
        role = field_role(code, values, catalogues)
        kept = values[:MAX_VALUES_PER_FIELD]
        fields.append(
            {
                "field_code": code,
                "field_label": dim.get("label"),
                "field_role": role,
                "value_count": len(values),
                "values": [{"value_code": c, "value_label": t} for c, t in kept],
            }
        )
        for found in _schemes_for(values, catalogues):
            keys.append({**found, "field_code": code})
    return fields, keys


def period_span(fields: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Earliest and latest period a resource publishes, from its period field."""

    for field in fields:
        if field.get("field_role") != "period":
            continue
        codes = sorted(v["value_code"] for v in field.get("values") or [])
        if codes:
            return codes[0], codes[-1]
    return None, None


def index_dataset(
    registry: Registry,
    dataset_id: str,
    *,
    http: JsonHttp | None = None,
    catalogues: dict[str, dict[str, set[str]]] | None = None,
) -> dict[str, Any]:
    """Record what one dataset contains, from the metadata its source publishes.

    Only the shape is read. A capability is written as `unverified` unless a
    fetch has already proved the resource returns records, because a shape says
    what a resource claims to hold, not that asking for it works.
    """

    from public_data_agent.fetch import _is_ssb_table_url, classify_access_path
    from public_data_agent.sources.brenheter import is_brenheter_url, shape_from_brenheter
    from public_data_agent.sources.brunder import is_brunder_url, shape_from_brunder
    from public_data_agent.sources.brorgform import is_brorgform_url, shape_from_brorgform
    from public_data_agent.sources.brkommuner import is_brkommuner_url, shape_from_brkommuner
    from public_data_agent.sources.fhi import is_fhi_table_url, printed_table_data_url, split_table_url

    dataset = registry.get_dataset(dataset_id)
    if dataset is None:
        raise ValueError(f"unknown dataset {dataset_id}")
    access_path = dataset.get("access_path") or ""
    client = http or HttpClient(timeout=60.0, max_retries=3)
    if catalogues is None:
        catalogues = load_classifications()

    if is_fhi_table_url(access_path):
        source_id, table_id = split_table_url(access_path)
        base = printed_table_data_url(source_id, table_id)
        meta = client.get_json_response(f"{base}/dimension?includeValues=true")
        fields, keys = shape_from_fhi((meta.body or {}).get("dimensions") or [], catalogues)
        endpoint, method = f"{base}/data", "POST"
        record_kind = "observation"
    elif _is_ssb_table_url(access_path):
        meta = client.get_json_response(access_path.rstrip("/"))
        fields, keys = shape_from_pxweb(meta.body or {}, catalogues)
        endpoint, method = access_path.rstrip("/"), "POST"
        record_kind = "observation"
    elif is_brenheter_url(access_path):
        # Shape comes from the printed enhet itself. Capability stays whatever
        # classify says unless a fetch already verified a sample.
        meta = client.get_json_response(access_path)
        fields, keys = shape_from_brenheter(meta.body or {})
        endpoint, method = access_path, "GET"
        record_kind = "entity"
    elif is_brunder_url(access_path):
        meta = client.get_json_response(access_path)
        fields, keys = shape_from_brunder(meta.body or {})
        endpoint, method = access_path, "GET"
        record_kind = "entity"
    elif is_brorgform_url(access_path):
        meta = client.get_json_response(access_path)
        fields, keys = shape_from_brorgform(meta.body or {})
        endpoint, method = access_path, "GET"
        record_kind = "entity"
    elif is_brkommuner_url(access_path):
        meta = client.get_json_response(access_path)
        fields, keys = shape_from_brkommuner(meta.body or {})
        endpoint, method = access_path, "GET"
        record_kind = "entity"
    else:
        raise ValueError(f"no metadata reader for {dataset_id} ({access_path or 'no access_path'})")

    written = registry.set_resource_shape(dataset_id, fields, keys=keys)
    start, end = period_span(fields)
    existing = registry.get_capability(dataset_id) or {}
    capability = classify_access_path(access_path)["kind"]
    registry.set_capability(
        dataset_id,
        {
            "capability": capability,
            "record_kind": record_kind,
            "endpoint": endpoint,
            "request_method": method,
            "period_start": start,
            "period_end": end,
            # A shape does not prove a fetch works, so a verification already
            # earned is carried forward and never invented here.
            "verified_at": existing.get("verified_at"),
            "verified_sample_count": existing.get("verified_sample_count"),
            "notes": f"shape read {utc_now()}",
        },
    )
    return {"dataset_id": dataset_id, **written, "period": (start, end)}


# What a match on each part of the index is worth. A value label is the
# strongest signal -- a table that publishes a value called "Grünerløkka" is
# about Grünerløkka whatever its title says. A field label is weaker: every
# regional table has a field called "region".
VALUE_LABEL_WEIGHT = 6
VALUE_CODE_WEIGHT = 8
FIELD_LABEL_WEIGHT = 2

# A value carried by most resources says nothing about any of them. Every table
# with geography lists all 892 municipalities, so "strøm" matching Lillestrøm
# made election statistics an answer about electricity. A term appearing in more
# than this share of indexed resources is treated as a stopword of the index.
MAX_TERM_SHARE = 0.15
# A share only means something once there is a population to take a share of.
# In an index of three resources, a term in one of them is 33% and obviously
# informative; discarding it would make a small index answer nothing.
MIN_TOTAL_FOR_SHARE = 20
# Matching one value of a field that lists eight hundred industries says the
# resource *covers* that industry, not that it is *about* it. A table whose
# measure field has three values and one of them matches is about the thing.
# Coverage is a filter and belongs in `datasets_containing_value`; this is
# relevance, so a match in a narrow field counts for much more than in a wide
# one.
FIELD_BREADTH_FLOOR = 0.05
# And among the rest, a rarer term is stronger evidence than a common one.
import math as _math


class ResourceHit:
    __slots__ = ("dataset_id", "title", "capability", "score", "why", "matched")

    def __init__(self, dataset_id, title, capability, score, why, matched) -> None:
        self.dataset_id = dataset_id
        self.title = title
        self.capability = capability
        self.score = score
        self.why = why
        self.matched: list[str] = matched

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ResourceHit({self.dataset_id!r}, score={self.score})"


def search_resources(
    registry: Registry,
    query: str,
    *,
    limit: int = 10,
    capability: str | None = "observations",
    covers_period: str | None = None,
) -> list[ResourceHit]:
    """Find resources by what they contain rather than by what they are called.

    A question naming a place misses a table that holds that place's code and
    never mentions it in its title. This matches query tokens against the
    values and field labels a resource publishes, and can require that the
    resource actually covers the period being asked about.

    Returned alongside, never instead of, title search: the two find different
    things and the catalogue lane is scored on titles.
    """

    from public_data_agent.search import tokenize

    total = registry.conn.execute(
        "SELECT COUNT(DISTINCT dataset_id) FROM resource_fields"
    ).fetchone()[0]
    if not total:
        return []
    tokens = set(tokenize(query))
    # Codes are not words. "030102" survives tokenisation as a token, but so
    # would a year, so raw whitespace splitting is what finds an exact code.
    raw = {part.strip(".,;:()").casefold() for part in query.split() if part.strip(".,;:()")}
    if not tokens and not raw:
        return []

    scores: dict[str, int] = {}
    why: dict[str, list[str]] = {}
    matched: dict[str, set[str]] = {}

    def credit(dataset_id: str, points: int, reason: str, token: str) -> None:
        scores[dataset_id] = scores.get(dataset_id, 0) + points
        if reason not in why.setdefault(dataset_id, []):
            why[dataset_id].append(reason)
        matched.setdefault(dataset_id, set()).add(token)

    for code in raw:
        rows = registry.datasets_containing_value(code, limit=400)
        weight = _selectivity(len({r["dataset_id"] for r in rows}), total)
        if weight is None:
            continue
        for row in rows:
            credit(row["dataset_id"], int(VALUE_CODE_WEIGHT * weight),
                   f"publishes code {code} in {row['field_code']}", code)

    for token in tokens:
        matches = [
            row
            for row in registry.conn.execute(
                "SELECT dataset_id, field_code, value_label FROM resource_field_values "
                "WHERE value_label IS NOT NULL AND lower(value_label) LIKE ? LIMIT 3000",
                (f"%{token}%",),
            )
            # A token must be a word in the label, not a fragment of one:
            # "strøm" inside "Lillestrøm" is a different subject entirely.
            if _word_in(token, row["value_label"])
        ]
        weight = _selectivity(len({r["dataset_id"] for r in matches}), total)
        if weight is not None:
            breadth = _field_breadth(registry, matches)
            for row in matches:
                narrowness = breadth.get((row["dataset_id"], row["field_code"]), 1.0)
                points = int(round(VALUE_LABEL_WEIGHT * weight * narrowness))
                if points <= 0:
                    continue
                credit(row["dataset_id"], points,
                       f"publishes a value named {row['value_label']}", token)
        for row in registry.conn.execute(
            "SELECT dataset_id, field_code, field_label FROM resource_fields "
            "WHERE field_label IS NOT NULL AND lower(field_label) LIKE ? LIMIT 400",
            (f"%{token}%",),
        ):
            if _word_in(token, row["field_label"]):
                credit(row["dataset_id"], FIELD_LABEL_WEIGHT,
                       f"has a field named {row['field_label']}", token)

    if not scores:
        return []

    placeholders = ",".join("?" * len(scores))
    rows = {
        row["id"]: row
        for row in registry.conn.execute(
            f"SELECT d.id, d.title, rc.capability, rc.period_start, rc.period_end "
            f"FROM datasets d LEFT JOIN resource_capability rc ON rc.dataset_id = d.id "
            f"WHERE d.id IN ({placeholders})",
            list(scores),
        )
    }

    hits: list[ResourceHit] = []
    for dataset_id, score in scores.items():
        row = rows.get(dataset_id)
        if row is None:
            continue
        if capability is not None and row["capability"] != capability:
            continue
        if covers_period is not None and not _covers(row, covers_period):
            continue
        hits.append(
            ResourceHit(
                dataset_id=dataset_id,
                title=row["title"],
                capability=row["capability"],
                score=score,
                why="; ".join(why[dataset_id][:3]),
                matched=sorted(matched[dataset_id]),
            )
        )
    # More distinct query terms covered beats a higher score from one term
    # repeated, so a resource matching the whole question outranks one matching
    # a single word many times.
    hits.sort(key=lambda hit: (-len(hit.matched), -hit.score, hit.dataset_id))
    return hits[:limit]


def _field_breadth(registry: Registry, matches: list[Any]) -> dict[tuple[str, str], float]:
    """How much a match in each field is worth, given how many values it holds.

    One of three values is a statement about the resource; one of eight hundred
    is a line item. The floor keeps a wide field from counting for nothing,
    since covering the thing asked about is still weak evidence.
    """

    pairs = {(row["dataset_id"], row["field_code"]) for row in matches}
    if not pairs:
        return {}
    out: dict[tuple[str, str], float] = {}
    for dataset_id, field_code in pairs:
        row = registry.conn.execute(
            "SELECT value_count FROM resource_fields WHERE dataset_id = ? AND field_code = ?",
            (dataset_id, field_code),
        ).fetchone()
        count = (row["value_count"] if row else None) or 1
        out[(dataset_id, field_code)] = max(FIELD_BREADTH_FLOOR, min(1.0, 8.0 / count))
    return out


_WORD = re.compile(r"[0-9a-zæøåäöéèü]+", re.IGNORECASE)


def _word_in(token: str, label: str | None) -> bool:
    """Whether a token is a whole word of a label, not a fragment inside one."""

    if not label:
        return False
    return token.casefold() in {w.casefold() for w in _WORD.findall(label)}


def _selectivity(carrying: int, total: int) -> float | None:
    """How much a term's presence is worth, or None if it is worth nothing.

    A term most resources carry cannot distinguish between them. Among the rest,
    rarer is stronger, which is what stops a table that lists every industry
    from answering every question that names one.
    """

    if carrying <= 0 or total <= 0:
        return None
    if total < MIN_TOTAL_FOR_SHARE:
        return 1.0
    if carrying > total * MAX_TERM_SHARE:
        return None
    return _math.log(total / carrying) / _math.log(total) + 0.2


def _covers(row: Any, period: str) -> bool:
    """Whether a resource's published span contains a period.

    A resource with no recorded span is kept: absence of a period field is not
    evidence that it fails to cover the question.
    """

    start, end = row["period_start"], row["period_end"]
    if not start or not end:
        return True
    return str(start)[:4] <= str(period)[:4] <= str(end)[:4]


# Norwegian statistical titles name the subject first and the breakdown after
# "etter": "Lønn, sysselsetting og produktivitet, etter næring". 72% of the SSB
# titles in the registry follow it. The distinction matters because a table
# *split by* employment is not a table *about* employment, and a query naming
# employment was reaching e-commerce statistics broken down that way.
SUBJECT_SEPARATORS = (", etter ", ", fordelt på ", ", etter,")


def split_title(title: str | None) -> tuple[str, str]:
    """Return a title's (subject, breakdown) halves.

    A title with no separator is all subject: absence of a breakdown clause is
    not evidence that the whole title is one.
    """

    text = title or ""
    for separator in SUBJECT_SEPARATORS:
        if separator in text:
            head, tail = text.split(separator, 1)
            return head, tail
    return text, ""


def matches_subject(query: str, title: str | None) -> bool | None:
    """Whether the query's words reach the title's subject rather than only its
    breakdown.

    Returns None when the query shares no word with either half, so a candidate
    matched on something other than its title -- a description, an embedding --
    is neither credited nor punished for it.
    """

    from public_data_agent.search import tokenize

    subject, breakdown = split_title(title)
    wanted = set(tokenize(query))
    if not wanted:
        return None
    in_subject = wanted & set(tokenize(subject))
    in_breakdown = wanted & set(tokenize(breakdown))
    if not in_subject and not in_breakdown:
        return None
    return bool(in_subject)


def demote_breakdown_only(
    registry: Registry, ranked: list[str], query: str, *, depth: int = 20
) -> list[str]:
    """Move candidates that match only a title's breakdown below those that
    match its subject.

    Only demotes. An earlier version also promoted subject matches above
    candidates the retriever had ranked on something other than a title -- a
    description, an embedding -- and pushed correct answers down from rank one,
    costing more in ranking quality than the demotion won in recall. Everything
    that is not a breakdown-only match keeps its original order.

    Applied to the head of a ranking only, so nothing far down can be promoted.
    """

    head, tail = ranked[:depth], ranked[depth:]
    kept: list[str] = []
    breakdown_only: list[str] = []
    for dataset_id in head:
        title = (registry.get_dataset(dataset_id) or {}).get("title")
        if matches_subject(query, title) is False:
            breakdown_only.append(dataset_id)
        else:
            kept.append(dataset_id)
    return [*kept, *breakdown_only, *tail]


def covering(
    registry: Registry, query: str, *, limit: int = 4000
) -> tuple[set[str], list[str]] | None:
    """Resources that contain a value the query names.

    This is a filter, not a ranking. "Hvor mange bor det i Bergen" is answered
    by a population table that covers Bergen; the Bergen half says *which*
    resources are eligible and the rest of the question says which is relevant.
    Scoring them together fails both ways -- a term that most resources carry
    cannot rank them, and dropping it as a stopword discards the constraint.

    Returns the eligible ids and the terms that constrained them, or None when
    the query names nothing the index recognises, which is not a constraint of
    "nothing".
    """

    from public_data_agent.search import STOP_TOKENS, tokenize

    words = [w for w in tokenize(query) if len(w) >= 4 and w not in STOP_TOKENS]
    if not words:
        return None
    eligible: set[str] | None = None
    used: list[str] = []
    for word in words:
        rows = registry.conn.execute(
            "SELECT DISTINCT dataset_id FROM resource_field_values "
            "WHERE lower(value_label) = ? LIMIT ?",
            (word, limit),
        ).fetchall()
        found = {r["dataset_id"] for r in rows}
        if not found:
            continue
        used.append(word)
        # Each recognised term narrows further: a question naming two places
        # wants what covers both.
        eligible = found if eligible is None else (eligible & found)
        if not eligible:
            return None
    if eligible is None:
        return None
    return eligible, used


def rank_within_coverage(
    registry: Registry, ranked: list[str], query: str, *, keep: int = 200
) -> list[str]:
    """Lift the candidates that cover what the query names, keeping their order.

    Only reorders. A resource the ranking already placed well is not demoted
    for lacking a value the index may simply not have recorded yet, since the
    index is incomplete and absence there is not evidence of absence.
    """

    result = covering(registry, query)
    if result is None:
        return ranked
    eligible, _ = result
    if not eligible:
        return ranked
    head = [d for d in ranked[:keep] if d in eligible]
    rest = [d for d in ranked[:keep] if d not in eligible]
    return [*head, *rest, *ranked[keep:]]


# How many of a field's values to show. A planner needs enough to recognise the
# shape and write a valid selection; the exact count is reported alongside so a
# sample is never mistaken for the whole list.
SAMPLE_VALUES = 12


def resource_shape(registry: Registry, dataset_id: str) -> dict[str, Any]:
    """What a resource holds and how to ask it for something.

    Read from the index rather than the network, and available for a resource
    nothing has ever fetched -- which is the point. Dimension names are
    source-defined and cannot be guessed from a title, so without this a caller
    planning a fetch invents a filter that matches no rows.
    """

    capability = registry.get_capability(dataset_id) or {}
    fields: list[dict[str, Any]] = []
    for field in registry.resource_fields(dataset_id):
        code = field["field_code"]
        rows = registry.conn.execute(
            "SELECT value_code, value_label FROM resource_field_values "
            "WHERE dataset_id = ? AND field_code = ? ORDER BY value_code",
            (dataset_id, code),
        ).fetchall()
        stored = [{"code": r["value_code"], "label": r["value_label"]} for r in rows]
        # For a period the ends are what a caller needs; for anything else the
        # first few show the shape.
        sample = (
            [stored[0], stored[-1]]
            if field["field_role"] == "period" and len(stored) > 2
            else stored[:SAMPLE_VALUES]
        )
        fields.append(
            {
                "code": code,
                "label": field["field_label"],
                "role": field["field_role"],
                "value_count": field["value_count"],
                "values": sample,
                "values_shown": len(sample),
            }
        )
    keys = [
        {
            "scheme": row["scheme"],
            "field_code": row["field_code"],
            "coverage_count": row["coverage_count"],
        }
        for row in registry.conn.execute(
            "SELECT scheme, field_code, coverage_count FROM resource_keys WHERE dataset_id = ?",
            (dataset_id,),
        )
    ]
    if not fields and not capability:
        return {"indexed": False, "reason": "this resource's shape has not been recorded"}
    return {
        "indexed": True,
        "capability": capability.get("capability"),
        "record_kind": capability.get("record_kind"),
        "endpoint": capability.get("endpoint"),
        "request_method": capability.get("request_method"),
        "period": {
            "start": capability.get("period_start"),
            "end": capability.get("period_end"),
        },
        "verified_at": capability.get("verified_at"),
        "verified_sample_count": capability.get("verified_sample_count"),
        "fields": fields,
        "keys": keys,
        "values_note": (
            "`values` is a sample; `value_count` is how many the source publishes. "
            "A value absent from the sample is not absent from the resource."
        ),
    }
