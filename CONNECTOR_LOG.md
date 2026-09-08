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

## brunder — 2026-09-08 — promoted

**Endpoint(s).** `GET https://data.brreg.no/enhetsregisteret/api/underenheter`
lists printed `_embedded.underenheter` members and their item links. `GET
https://data.brreg.no/enhetsregisteret/api/underenheter/{organisasjonsnummer}`
returns one data-bearing sub-unit. The collection and `/lastned` paths are
classified `none` as fetch targets and refused before send; a fetch must name one
sub-unit organisation number.

**Shape.** `entity`. The printed sub-unit `organisasjonsnummer` and `navn` become
the subject code and label. `overordnetEnhet` retains the parent organisation
number, and organisation form, industry and structured location fields are copied
as attributes. Structured scalar leaves such as
`beliggenhetsadresse.kommunenummer` are present in the resource index. The claimed
subject scheme is `brreg:orgnr`; the parent code is searchable as an attribute but
is not claimed as a second resource key.

**Capability recorded.** `entities`. A fresh live collection-to-item run on
2026-09-08 listed and fetched `brunder:933489272` (`- ZOTKO .NO`): HTTP 200, one
entity inserted, zero observations, `verified_sample_count = 1`, request URL
stored, parent `933365573` retained, and licence `null`. The full offline suite
passed after the live run.

**Surprises.** The earlier connector stored `navn` as an observation and silently
dropped the structured address; it now uses the entity store and shared lossless
attribute reader. Both the subject and parent values pass mod-11. The subject is
also verified by a successful item GET whose printed organisation number must
equal the requested number. Invalid-check-digit item URLs are not classified as
entities. Oversized, mismatched and unsupported selections are rejected before
the fake HTTP client sees a request. The source was originally developed on the
listed `cursor/brunder-*` branches and already incorporated into trunk as the
legacy adapter, so no branch was duplicated. No rate-limit response was seen with
the registered 2 requests/second client.

**Open question for the query side.** A sub-unit speaks `brreg:orgnr` in two
semantically different fields: its subject `organisasjonsnummer` and its parent
`overordnetEnhet`. `resource_keys` stores only one field per scheme per dataset.
For now the subject wins and the parent remains an indexed attribute. Does query
dispatch need an explicit field-level relationship representation for the parent?

## brreg-mirror — 2026-09-08 — implemented, full live import pending

**Endpoint(s).** `HEAD` and `GET
https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv` provide the complete
main-unit CSV gzip. The corresponding under-unit file is
`/api/underenheter/lastned/csv`. Incremental notices come from
`/api/oppdateringer/enheter` and `/api/oppdateringer/underenheter`; their printed
item links are fetched to replace the whole changed entity. Brreg's official API
documentation explicitly describes this complete-copy workflow, says the files are
produced nightly around 05:00, recommends streaming them, and exposes `etag` and
`last-modified`. It licenses this API under NLOD 2.0.

**Live source verification.** On 2026-09-08 the main-unit JSON gzip reported
210,027,337 bytes, its CSV gzip 154,541,019 bytes, and the under-unit JSON gzip about
88.5 MB. The live CSV printed the expected `organisasjonsnummer`, `navn`, dotted
organisation-form/address fields and real entity rows. The update endpoint printed
ascending integer `oppdateringsid`, timestamp, organisation number, change type and an
item link. A range request was ignored by the server, so `--limit` limits ingestion
only; it does not avoid downloading the complete compressed file.

**Shape.** Two canonical `entity` datasets, `brenheter:all` and `brunder:all`, one
stable row per validated `brreg:orgnr`. Snapshot CSV fields and item JSON fields are
projected into one case-folded dotted attribute namespace so an incremental refetch
does not introduce a second schema. Unambiguous booleans and numbers are restored,
while leading-zero codes remain strings. The resource index is replaced from the
actual CSV header and claims only the validated organisation-number key.

**Continuous-copy behavior.** `pda mirror-brreg enheter snapshot` (and
`underenheter`) streams exact gzip bytes to a `.part` file, verifies content length,
hashes SHA-256, atomically renames it, parses with the standard quoted CSV reader and
stores ETag/Last-Modified/path/hash in `raw_snapshots` plus `crawl_checkpoints`. Equal
ETags skip the download. A corrupt replacement rolls back every record change. A
successful complete replacement tombstones rows absent from the new total inventory.
`pda mirror-brreg enheter updates` starts 24 hours before a new snapshot timestamp, as
a conservative implementation of Brreg's overlap recommendation, then persists
`updateid + 1` progress. Each page and its cursor commit together. `Ny`, `Endring` and
`Ukjent` refetch the complete printed item; `Sletting`, `Fjernet`, and an item that has
already become HTTP 404 remove the live row and retain deletion provenance. The same
commands exist for under-units. Requests use the registered two-per-second limiter.

**Database changes.** Additive crawl-owned tables hold checkpoints, raw-snapshot
manifests and tombstones; large source files remain outside SQLite. The generic record
upsert now notices changes to labels, geometry and suppression markers, not only value
and attributes. Existing dataset and observation tables are unchanged.

**Verification.** Snapshot replacement, ETag conditioning, exact-byte hashing,
partial-download cleanup, schema projection, mod-11 rejection, rollback, tombstones,
item mismatch, overlap query, monotonic cursor and CLI output are covered offline. Full
suite: 1,925 passed, 1 skipped, 1 live test deselected. A complete live file has not yet
been committed into a production registry, so this entry does not claim a national
record count.

**Open question for the query side.** None. The next crawler-side operation is one
full `enheter` snapshot, followed immediately by updates, then the same sequence for
`underenheter`; production storage location and retention policy should be set before
those multi-hundred-megabyte files are scheduled indefinitely.

## brorgform — 2026-09-08 — promoted

**Endpoint(s).** `GET
https://data.brreg.no/enhetsregisteret/api/organisasjonsformer` lists the complete
published vocabulary and printed item links. `GET
https://data.brreg.no/enhetsregisteret/api/organisasjonsformer/{kode}` returns one
data-bearing concept. The collection currently prints 44 concepts.

**Shape.** `entity` used as a `lookup`, not an observation. `kode` is the subject under
the source-owned `brreg:organisasjonsform` scheme and `beskrivelse` is its label. Any
future additional printed properties remain attributes. The resource index records the
actual `kode` and label plus one verified key.

**Capability recorded.** `lookup`, with record kind `entity`. A fresh live run fetched
`brorgform:AS` from its printed item URL: HTTP 200, one record inserted as code `AS`,
label `Aksjeselskap`, `verified_sample_count = 1`, and zero observation rows. The
connector refuses a requested code that differs from the harvested item before sending,
and rejects a successful response that prints another code before writing.

**Surprises.** The old adapter represented `Aksjeselskap` as a measured value named
`beskrivelse`; this is a classification concept, so that shape was false even though
the payload and provenance were real. The API does expose stable per-code item URLs even
though the service overview emphasizes the collection. The harvested dataset still has
a null licence because the item payload does not print one; the separate official API
documentation states NLOD 2.0, but that provenance has not yet been wired into this
legacy metadata adapter.

**Open question for the query side.** None.
