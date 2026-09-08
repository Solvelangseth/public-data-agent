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

## brkommuner — 2026-09-08 — promoted

**Endpoint(s).** `GET https://data.brreg.no/enhetsregisteret/api/kommuner` is a
paginated collection; its printed `next` links lead through 19 pages. `GET
https://data.brreg.no/enhetsregisteret/api/kommuner/{nummer}` returns one municipality
concept. Pagination now follows only HTTPS next links on the exact Brreg collection
path, rejects loops/off-origin links, and stops at a 10,000-item safety ceiling.

**Shape.** `entity` used as a `lookup`. The printed `nummer` is the subject under
`brreg:kommunenummer`, `navn` is the label, and any future extra fields are attributes.
This deliberately does not claim `klass:131`: Brreg currently includes special code
`0999 UTENLANDS` and historical-looking `0301 OSLO`, so equivalence to particular Klass
versions must be validated rather than inferred from four digits.

**Capability recorded.** `lookup`, record kind `entity`. A full fresh live catalogue
walk returned and harvested all 365 printed municipalities with no failures. A live item
fetch then stored `brkommuner:1101` as code `1101`, label `EIGERSUND`, HTTP 200, one
verified resource key and zero observation rows. Mismatched selections and mismatched
successful item responses are refused before writes.

**Surprises.** The previous connector read only the first page and defaulted to ten
items, silently turning a 365-member source into a ten-member catalogue. It also stored
the municipality name as if it were a measurement. Both behaviors looked successful in
the old observation-only tests. This is the first promoted connector where exhaustive
listing, not a sample, exposed the actual source coverage.

**Open question for the query side.** `brreg:kommunenummer` is the safe source-native
scheme. A separate validated correspondence should relate its code/name pairs to the
correct historical/current `klass:131` versions; do not make them globally identical by
code alone.

## brrolletype — 2026-09-08 — promoted

**Endpoint(s).** `GET
https://data.brreg.no/enhetsregisteret/api/roller/rolletyper` returns the complete
27-member role-type vocabulary. Its live member `self` links currently point at
`/autorisert-api/...` and return HTTP 401 without Maskinporten, but the official API
documentation prints the public `/api/roller/rolletyper/{kode}` item form; that public
path returns HTTP 200. The connector already derived precisely that documented path
from the collection origin plus each printed code and never follows the unusable
authorized link.

**Shape.** `entity` used as a `lookup`. `kode` is the subject under
`brreg:rolletype`, `beskrivelse` is the label, and additional properties remain
attributes. This vocabulary is the interpretation key for role records such as `DAGL`
(Daglig leder), `LEDE` and `MEDL`.

**Capability recorded.** `lookup`, record kind `entity`. A fresh live run harvested all
27 collection members, then fetched the public `brrolletype:DAGL` item: HTTP 200, one
entity inserted, one verified `brreg:rolletype` key and zero observation rows.

**Surprises.** The publisher's live collection self-links cross from the public API to
the protected API even though equivalent public item endpoints work and are printed in
the official documentation. Blind HAL traversal would turn a fully public vocabulary
into 27 authentication failures. The old adapter also misrepresented each role label as
a measurement.

**Open question for the query side.** None.

## crawl-storage — 2026-09-08 — guarded, provisioning pending

**Finding.** The working filesystem has only 2.3 GiB free and is 99% full. No
external volume is mounted, and no `rclone`, AWS CLI or Restic client is installed.
The live Brreg main-unit CSV gzip alone is about 147 MiB, but the active SQLite copy
also needs room for expanded rows and transaction state; raw-file size is therefore
not a sufficient capacity estimate.

**Implementation.** Complete Brreg snapshots now check the publisher's printed
`Content-Length` before starting a manifest or download. The minimum combines the
compressed object plus 512 MiB raw headroom with an intentionally conservative
12-times compressed-size estimate plus 1 GiB database headroom. Requirements are
combined when `--db` and `--storage-dir` share a filesystem. Unknown file size or
insufficient capacity fails before any bytes are downloaded. A live preflight on this
machine correctly refused the main-unit snapshot: it estimated 3.4 GiB minimum free
and found 2.3 GiB. The implementation and exact deployment layout are documented in
`docs/CRAWL_STORAGE.md`. Unit coverage proves both low-capacity and missing-length
refusals happen before a download or raw manifest is started. Full suite: 1,929 passed,
1 skipped and 1 live test deselected.

**Storage decision.** Use both layers for different jobs: an encrypted APFS external
SSD for the live SQLite database and crawl staging, and a private EU-jurisdiction
S3-compatible object bucket for immutable compressed publisher bytes and off-site
recovery. Do not put SQLite or its WAL in object storage. Cloudflare R2 is the simplest
initial bucket candidate because its official service is S3-compatible, offers an EU
jurisdiction and currently lists standard storage at USD 0.015/GB-month with free
Internet egress. Provider selection remains configuration so R2, AWS S3 or Backblaze
B2 can be changed without changing connector logic.

**Open question for the crawler owner.** Provision and mount a suitably sized external
SSD before the two national Brreg mirrors are run. A 2 TB SSD is a workable minimum;
4 TB gives more useful runway for geospatial sources. Cloud credentials are not needed
to validate the first import, but an EU bucket should be created before unattended
retention begins.

## brrollegruppe — 2026-09-08 — promoted

**Endpoint(s).** `GET
https://data.brreg.no/enhetsregisteret/api/roller/rollegruppetyper` returns the complete
21-member role-group-type vocabulary. As with role types, its live member `self` links
point at protected `/autorisert-api/...` paths. The connector derives the public
`/api/roller/rollegruppetyper/{kode}` path from the collection origin and printed code;
the live `DAGL` item returned HTTP 200. Brreg's official API documentation lists the
collection endpoint and explicitly defines `rollegruppetype` as a code list/enum.

**Shape.** `entity` used as a `lookup`. `kode` is the subject under the source-owned
`brreg:rollegruppetype` scheme, `beskrivelse` is its label, and any future additional
properties remain attributes. This is intentionally distinct from `brreg:rolletype`:
the two vocabularies can print the same code, including `DAGL`, without being declared
globally equivalent.

**Capability recorded.** `lookup`, record kind `entity`. A fresh live run harvested
all 21 collection members with no failures, then fetched `brrollegruppe:DAGL` from the
public item URL: HTTP 200, one entity inserted, code `DAGL`, label `Daglig leder`, one
verified resource key and zero observation rows. Full suite: 1,930 passed, 1 skipped
and 1 live test deselected.

**Surprises.** The old adapter represented the label as an observation, capped a
default harvest at ten even though the complete list has 21 members, and did not add a
resource shape or capability. The limit is now only a 100-member safety ceiling. A
successful item response whose printed code differs from the requested path is rejected
before a record or capability is written; an unsatisfiable selection is rejected before
the HTTP request.

**Open question for the query side.** None.

## brrepresent — 2026-09-08 — promoted

**Endpoint(s).** `GET
https://data.brreg.no/enhetsregisteret/api/roller/representanter` returns the complete
four-member representative vocabulary: `A-AK`, `AREP`, `B-AK` and `C-AK`. Member
`self` links point at protected `/autorisert-api/...` paths, while the equivalent
public `/api/roller/representanter/{kode}` paths work; a live fetch of `A-AK` returned
HTTP 200. Brreg's official API documentation lists the collection and defines
`representant` as a code list/enum describing whom someone represents on a board.

**Shape.** `entity` used as a `lookup`. The printed `kode` is the subject under
`brreg:representant`, `beskrivelse` is its label, and future additional properties
remain attributes. It is a vocabulary used to interpret role records, not a numeric
observation.

**Capability recorded.** `lookup`, record kind `entity`. A fresh live run harvested
all four collection members with no failures, then fetched `brrepresent:A-AK` from the
public item URL: HTTP 200, one entity inserted, label `Representant for A-aksjonærene`,
one verified resource key and zero observation rows. Full suite: 1,931 passed, 1
skipped and 1 live test deselected.

**Surprises.** The old adapter turned the description into a measured value and had no
resource shape or verified capability. It also used a ten-item default cap; the complete
collection is only four, but the source now uses the same explicit 100-code safety
ceiling as the adjacent vocabularies. Mismatched successful responses and impossible
selections are rejected before they can write records or make unnecessary requests.

**Open question for the query side.** None.

## brroller — 2026-09-08 — duplicate discovery connector, fetch disabled

**Endpoint(s).** This source reads the official OpenAPI document and selects three
unparameterized paths under `/api/roller/`: `representanter`, `rollegruppetyper` and
`rolletyper`. Those are exactly the three vocabularies now represented canonically by
`brrepresent`, `brrollegruppe` and `brrolletype`. The actual company-role endpoint is
`/api/enheter/{organisasjonsnummer}/roller`; because it requires a path parameter, this
source deliberately excludes it. `/api/roller/totalbestand` is also deliberately
excluded.

**Shape.** `none` for this connector. Its three selected endpoints contain lookup
concepts, but storing their descriptions again under `brroller:*` would create duplicate
identities and the old adapter incorrectly wrote them as observations. This source does
not return a company's roles despite its name.

**Capability recorded.** Fetch dispatch now refuses these discovery collections before
making an HTTP request and directs callers to the three canonical per-code lookup
sources. Access-path classification returns `none` with the duplicate/non-company-role
reason. No observations or records are written. Full suite: 1,931 passed, 1 skipped and
1 live test deselected.

**Surprises.** The old test looked convincingly data-bearing because the endpoint
returned real labels under `_embedded`; what it proved was only that a code list could
be misrepresented as measurements a second time. A future company-role connector must
be keyed from a validated organisation number and model the returned role groups and
participants explicitly; `brroller` is not that connector and should not be scheduled.

**Open question for the query side.** None.

## brroles-totalbestand — 2026-09-08 — contract verified, implementation pending storage

**Endpoint(s).** `GET`/`HEAD
https://data.brreg.no/enhetsregisteret/api/roller/totalbestand` serves the public
national role inventory as gzip-compressed JSON. On 2026-09-08 it reported ETag
`2641cfe3f2ed281ae040e8ee37698e3d`, last-modified 04:03 CEST and 129,790,836
compressed bytes. The stream begins with a top-level JSON array containing one object
per printed `organisasjonsnummer`, its printed company and self links, and nested
`rollegrupper`. `GET /api/oppdateringer/roller` is the continuous feed; the official
contract exposes `afterTime`, then monotonic `afterId`, and each CloudEvent prints the
organisation number plus the company-role source URL to refetch.

**Shape decision.** Store one `document` record per validated company organisation
number, with `brreg:orgnr` as the subject and the complete role groups as nested
attributes. This preserves the published relationship without inventing a person ID.
The public payload prints a person's name and birth date but no stable public person
identifier; combining those fields into a synthetic identity would violate the schema
trust boundary. A role participant that is itself an organisation does print a real
organisation number and can retain that relation in attributes.

**Pipeline plan.** Stream and hash the exact gzip to immutable raw storage, then parse
the top-level JSON array incrementally rather than loading the national file in memory.
Checkpoint the ETag, last-modified timestamp and hash. Apply update pages and their
`afterId + 1` cursor atomically; refetch the complete printed company-role URL for each
event, and retain a tombstone if it becomes 404. This is the same snapshot-plus-event
contract already implemented for entities, with JSON-array parsing and document records
instead of CSV entities.

**Privacy boundary.** Only the unauthenticated public endpoint is in scope. Brreg also
offers a Maskinporten-protected totalbestand containing national identity numbers; that
endpoint is neither required nor authorized and must not be called or stored. The public
birth-date fields still deserve access controls and a documented retention purpose even
though Brreg publishes them openly.

**Blocked operation.** The working disk remains 99% full with 2.3 GiB free. The stream
format was verified by decompressing only its first bytes through a pipe; no snapshot
was saved. Implementing and testing the streaming adapter can continue locally, but its
first complete live proof should use the external SSD so raw bytes, SQLite expansion and
rollback space share a capacity-safe volume.

**Open question for the crawler owner.** Mount the external SSD and provide its volume
path before the full roles snapshot proof is run.
