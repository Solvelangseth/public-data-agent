# Connector log

Written by the connector lane, read by the query lane. One entry per connector
attempted, whether or not it worked, newest at the bottom. The format is in
`CRAWL_BRIEF.md`.

A connector that cannot return data is a result worth writing down: it stops the same
one being attempted twice, and a domain full of dead endpoints is a finding about the
domain.

---

## fhi — 2026-09-04 — promoted

Written by the query lane as the worked example. Commits `6ef054d`, `42d91aa`.

**Endpoints.** `https://statistikk-data.fhi.no/api/open/v1`
`/Common/source` lists 13 registers · `/{register}/Table` lists that register's tables ·
`/{register}/Table/{id}/dimension?includeValues=true` gives the shape ·
`POST /{register}/Table/{id}/data` returns json-stat2.

**Shape.** `observation`. 369 tables; 119 of them (all in the `nokkel` register) carry a
`GEO` dimension. Geography is printed as Klass codes — 36 of the 42 codes in Klass 1168
appear verbatim — so the rows share a vocabulary with SSB.

**Capability recorded.** `observations`, verified against real returned cells on a live
run. A register's `/Table` listing URL is *not* data: it returns table ids, and the
original connector stored those as observation values.

**Surprises.**
- json-stat2 permits `category.index` as an object *or* an array. SSB emits the object,
  FHI the array. Our decoder handled only the object, so a conforming payload looked
  unsupported. Fixed for both decoders in `6ef054d`.
- Every dimension must be filtered explicitly or the API returns 400. This is a feature:
  an accidental whole-table pull is impossible and the error names the dimension you
  missed.
- `GEO` nests bydel under kommune under fylke, so the category tree has to be walked.
- Labels differ from Klass where the codes agree (`Bydel Grünerløkka` against
  `Grünerløkka`). Join on codes; names would silently match nothing.
- `:` means a withheld cell, not a number. It now goes in `records.suppressed`.
- Rate limit is ~2 requests/second. Four unthrottled workers produced 123 HTTP 429s that
  looked exactly like 123 broken tables.

**Open question for the query side.** None.

## brenheter — 2026-09-08 — promoted

**Endpoint(s).** `GET https://data.brreg.no/enhetsregisteret/api/enheter` lists
printed `_embedded.enheter` members and their printed `_links.self.href` values.
`GET https://data.brreg.no/enhetsregisteret/api/enheter/{organisasjonsnummer}`
returns one data-bearing company entity. The collection and `/lastned` paths are
not single-entity fetches and are refused before send; callers must narrow to one
organisation number.

**Shape.** `entity`. The subject is the printed `organisasjonsnummer`, the label is
the printed `navn`, and every other printed property is an attribute. Scalar and
published code/description fields remain flat; addresses, historical names,
activities, purpose and capital stay as JSON after recursively removing HAL
`_links`. Their scalar leaves are indexed with dotted field codes, for example
`forretningsadresse.kommunenummer` and `kapital.belop`. The only claimed scheme is
`brreg:orgnr` on `organisasjonsnummer`. Address municipality numbers are indexed as
attributes but are not claimed as a Klass key from a single code.

**Capability recorded.** `entities`. A fresh live run on 2026-09-08 fetched
`brenheter:923609016` (`EQUINOR ASA`) from the item endpoint: HTTP 200, one entity
record inserted, zero observation rows, `verified_sample_count = 1`, request URL
stored, and licence `null`. The full offline suite passed after the live check.

**Surprises.** The end-to-end entity promotion already existed in commit `96f35e2`
but had not been reported in this log. Reading the live response exposed that the
adapter dropped non-code objects and arrays even though the record store accepts
JSON; company addresses, historical names, activities and capital were therefore
missing from both the record and resource index. The connector now retains them
and indexes their leaves. Organisation-number verification uses both checks the
brief calls for: the nine-digit value must pass mod-11, then the item GET must
succeed and print the same organisation number that was requested. A different
valid number in a successful response is rejected before any record or capability
is written. No rate-limit response was encountered while using the existing
2 requests/second limiter.

**Open question for the query side.** None.
