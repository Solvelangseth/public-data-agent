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

## shared-registry landing — 2026-09-09 — promoted connectors now findable

**Endpoint(s).** Landed only registered item endpoints into the shared
`data/registry.sqlite`: one `/api/enheter/{orgnr}`, one
`/api/underenheter/{orgnr}`, and every published item in the five small lookup
vocabularies. No `/lastned`, totalbestand, update-feed or other bulk endpoint was
called. The earlier live evidence in this log came from isolated temporary registries;
it proved connector behavior but did not make those resources available to the query
lane.

**Shape.** The shared registry now contains 463 Brreg datasets and 463 records:
1 main entity, 1 sub-unit, 44 organisation forms, 365 municipality/special codes,
27 role types, 21 role-group types and 4 representative types. Every one of those 463
datasets has a stored capability, at least one resource field, and its connector's
verified source-owned key. There are zero harvested datasets in this bounded landing
set without a record, capability or resource shape.

**Capability recorded.** The two organisation-number samples are `entities`; all 461
code-list concepts are `lookup`; every record kind is `entity` and each capability has
`verified_sample_count = 1`. MCP `inspect` now reports `indexed: true`, the endpoint,
fields, values and key for tested company, organisation-form and municipality datasets.
Normal search returns `brorgform:AS` for `Aksjeselskap`, and MCP fetch returns its live
`AS` / `Aksjeselskap` entity with HTTP 200 and stored provenance. These checks are
independent of the SQL completeness audit.

**Surprises.** Landing the whole small vocabulary set exposed three non-ASCII codes that
ASCII smoke samples missed. Organisation form `SÆR` arrived through a percent-encoded
self URL and was compared to the encoded path segment; role-type and role-group code
`FFØR` had not been encoded when constructing their public item URLs. Item path segments
are now percent-encoded on construction and decoded before comparing to the publisher's
printed code. Regression tests cover the exact live codes, and all three failed shared
items succeeded on retry. Full suite: 1,931 passed, 1 skipped and 1 live test deselected.

**Scope correction.** The two bulk entity mirrors and the proposed national roles and
operations work are deferred. They were not run or landed. V1 work returns to breadth:
auditing duplicate/metadata-only connectors and then the unanswered question list,
starting with a source that can return real luftfart passenger observations.

**Open question for the query side.** None.

## ssbtable:08507 — 2026-09-09 — luftfart passenger sample verified

**Endpoint(s).** Reused the official SSB PxWeb resource already present in the shared
registry: `POST https://data.ssb.no/api/v0/no/table/08507`. No new Avinor scraper was
needed. The table is *Lufttransport. Passasjerar, etter lufthamn, trafikktype og
innanlands-/utanlandsflyging*, covering `2009M01` through `2026M07` when checked.

**Bounded live proof.** Sent an explicit one-cell selection: `Lufthavn=ENGM` (Oslo
Gardermoen), `TrafikkType=000` (all commercial flights), `TrafikkFly=IU` (domestic and
international), `PassasjerType=AAT` (total passengers aboard at arrival and departure),
`ContentsCode=Passasjerer`, and `Tid=2026M07`. SSB returned HTTP 200 and exactly one
cell: 2,737,712 passengers. One observation with request URL, retrieval time and HTTP
status is now stored in the shared registry; no broad table query or historical import
was attempted.

**Shape and capability.** The indexed shape has six source-owned fields: one measure,
one monthly period and four attributes (airport, traffic type, domestic/international
flight, and passenger group). Capability remains `observations` with record kind
`observation` and method `POST`; `verified_at` and `verified_sample_count = 1` now reflect
the live record rather than metadata inspection alone.

**Surprises.** The resource was already registered and shaped but had zero observations,
so it looked complete from the catalog side without an end-to-end data proof. The exact
held-out query `luftfart passasjerer` also does not retrieve table 08507 in the first ten
results even after the sample is stored. The most likely cause is a language-form gap:
the official Norwegian title and labels use Nynorsk `passasjerar`, while the question
uses Bokmål `passasjerer`.

**Open question for the query side.** Add or evaluate Bokmål/Nynorsk lexical expansion
so `luftfart passasjerer` reaches `ssbtable:08507`. This is a retrieval concern; the
crawler-side source, live observation, capability and shape are now present.

## fdirpx:A06002a — 2026-09-10 — farmed salmon production source verified

**Endpoint(s).** Added a bounded Fiskeridirektoratet PxWeb connector. The official
catalogue is `https://statistikkbanken.fiskeridir.no/PxWeb/api/v1/no/Fiskeridirektoratet/A_Akvakultur/A_06_Salg`;
it prints table `A06002a.px`, whose direct metadata/data endpoint is
`https://statistikkbanken.fiskeridir.no/PxWeb/api/v1/no/Fiskeridirektoratet/A_Akvakultur/A_06_Salg/A06002a.px`.
The publisher's explanatory page is the official *Akvakulturstatistikk: laks,
regnbueørret og ørret* page. The connector promotes only this table for now instead
of creating thirteen metadata-only neighbours.

**Shape.** The publisher prints three dimensions: `År` (1994–2025), `Art` (Laks,
Regnbueørret, Ørret), and `Statistikkvariabel` (Kvantum (tonn), Verdi (1000 kroner)).
The shared resource index records all 32 year values and both measures. Licence remains
null because the PxWeb table metadata does not print a per-table licence URI; the
publisher's general NLOD page is retained as a landing/reference link, not silently
claimed as a field from the table payload.

**Bounded live proof.** Queried exactly one cell with `År=2025`, `Art=Laks`, and
`Statistikkvariabel=Kvantum (tonn)`. The official endpoint returned HTTP 200 and
`1,754,557` tonnes. That observation, its POST URL, retrieval time and status are now
in the shared registry. Capability is `observations`, record kind `observation`, with
`verified_sample_count = 1`; no historical or company-level import was attempted.

**Implementation note.** This is a normal PxWeb table, but its API is hosted under
Fiskeridirektoratet rather than SSB. Fetch dispatch, capability classification and
resource-shape indexing now recognise the exact `/PxWeb/api/v1/no/Fiskeridirektoratet/`
path. Focused connector/fetch/index tests pass.

**Open question for the query side.** The held-out wording `oppdrettslaks produksjon`
may need compound expansion (`oppdrettslaks` → `oppdrett` + `laks`) to rank this table;
the source title uses the publisher's precise `Matfisk. Salg av laks` wording. That
retrieval issue is recorded rather than solved in the crawler lane.

The harvested metadata now also carries the publisher-defined category terms
`Akvakultur`, `Salg`, `Matfisk`, and `Produksjon`; this adds source vocabulary without
renaming the official table or inventing a measure.

## source reconnaissance — 2026-09-10 — future crawl paths saved

This is a link inventory only. No archive or bulk download was started while the
external storage decision is pending.

**Naturvernområder (Miljødirektoratet/Geonorge).** The registered Data.norge row is
`datanorge:0f231dc0-84be-3765-a4e1-bc0c761788f3`, metadata UUID
`5857ec0a-8d2c-4cd8-baa2-0dc54ae213b4`. The publisher's live Atom feed is
`https://pgisnedlasting.blob.core.windows.net/data/atom/datasett/vern.xml` and was
updated `2026-09-10T06:01:40`; it prints national data links including
`.../vern/GEOJSON/4326/vern_0000_norge_4326_GEOJSON.zip`,
`.../vern/GML/25833/vern_0000_norge_25833_GML.zip`, and FileGDB variants for EPSG:4326,
25832 and 25833. The feed also prints county/regional ZIP paths. The GeoJSON national
ZIP is about 61 MB and was deliberately not downloaded. The Geonorge metadata and
frontend `/Metadata/.../GeoJSON` routes returned HTML, not features; the Atom feed is
the machine-readable discovery path to use later. NLOD 2.0 is printed by the catalog.

**Permitteringer / driftsinnskrenkninger (NAV).** The registered landing page is
`https://www.nav.no/no/NAV+og+samfunn/Statistikk/Arbeidssokere+og+stillinger+-+statistikk/Forhandsinnmeldte+driftsinnskrenkninger`
and the corresponding catalog title is *Statistikk forhåndsinnmeldte driftsinnskrenkninger*.
The current registry row has no machine-readable distribution or verified capability;
the page is therefore recorded as a lead, not promoted. Next crawl should inspect the
page's printed CSV/JSON/download links and NAV's official public API/catalogue before
writing any rows.

**Fiskeridirektoratet statistics-bank root.** The official landing page is
`https://www.fiskeridir.no/statistikk-tall-og-analyse/statistikkbanken`; its PX-Web UI
is `https://statistikkbanken.fiskeridir.no/PxWeb/pxweb/no/Fiskeridirektoratet/` and
its API root is
`https://statistikkbanken.fiskeridir.no/PxWeb/api/v1/no/Fiskeridirektoratet/`.
The API lists `A_Akvakultur` and `F_Fiskeri` folders; the first promoted table uses
the exact `A_Akvakultur/A_06_Salg/A06002a.px` path above. This root is retained as the
discovery path for subsequent bounded tables, not as a reason to ingest every table.

**Dead-end check.** Direct Geonorge metadata format routes for the nature UUID were
tested and returned an HTML application shell (HTTP 200), so they are not data endpoints.
The attempt is written down to prevent retrying those routes as if they were GeoJSON.

**NAV follow-up check (2026-09-10).** The catalog URL above now redirects and ends at
NAV HTTP 404, with no CSV/JSON/XLSX link in the returned page. Treat that Data.norge
landing path as stale until NAV publishes a replacement; do not build a connector
against the dead URL. The failed check is retained here so it is not retried blindly.

## ssbtable:11787 — 2026-09-10 — household water consumption sample verified

**Endpoint.** Reused the indexed official SSB KOSTRA PxWeb table
`https://data.ssb.no/api/v0/no/table/11787`, *Vannforsyning og beredskap. Kommunalt
drikkevann*. Its shape has 32 measures, 891 municipality/region values and years
2015–2025. The relevant source-owned measure is
`KOSVREGesthushfo0000` — “Estimert gjennomsnittlig husholdningsforbruk per tilknyttet
innbygger per døgn”.

**Bounded live proof.** Selected exactly `KOKkommuneregion0000=0301` (Oslo - Oslove),
`Tid=2025`, and that measure. SSB returned HTTP 200 and `149` litres per person per
day. One observation and provenance are now in the shared registry; capability is
`observations` with `verified_sample_count = 1`. No municipality-wide or historical
pull was attempted.

**Retrieval note.** The held-out wording “vannforbruk per husholdning” is now supported
by a current numeric cell, although the published measure is technically per connected
resident rather than per household. Query-side ranking should use the table's indexed
measure label and explain that distinction in an answer.

## ssbtable:08264 — 2026-09-10 — industry profitability indicator verified

**Endpoint.** Reused the official SSB PxWeb table
`https://data.ssb.no/api/v0/no/table/08264`, *Konjunkturbarometer. Tendenser*. The
indexed shape publishes ten measures, including source-owned `ContentsCode=Lonnsomhet`,
with industrial group `PKoder=P105` (Industri), adjustment `Justering=S` (seasonally
adjusted), reference period `ReferansePeriode=01` (actual change from the previous
quarter), series `SerieType=01` (diffusion index), and periods through `2026K2`.

**Bounded live proof.** That exact six-dimensional selection returned HTTP 200 and
`45.7`. One observation and provenance are now shared. Capability is `observations`,
record kind `observation`, and `verified_sample_count = 1`; no company-level accounts
or broad time series were imported.

**Interpretation boundary.** This answers “lønnsomhet i industrien” as SSB's survey-based
diffusion index, not a kroner-based profit margin. The distinction and the source-owned
dimensions are retained so the query lane can explain it instead of presenting the
indicator as accounting profit.

## nvdb:* — 2026-09-10 — 423 road object registers catalogued, none imported

**Endpoint(s).** `GET https://nvdbapiles.atlas.vegvesen.no/vegobjekttyper` lists every
road object type Statens vegvesen publishes. Objects of a type come from
`GET .../vegobjekter/{type}`, one object from `.../vegobjekter/{type}/{id}`, and a
type's size from `.../vegobjekter/{type}/statistikk`. NVDB throttles anonymous callers
harder, so the connector sends `X-Client`. The v3 host answers 400 on the same request;
v4 at `nvdbapiles.atlas.vegvesen.no` is the one that works.

**Why this source.** The registry was heavy on statistics and thin on things. NVDB is
bridges, tunnels, guardrails, kerbs, signs — and each object carries geometry, typed
attributes, and the fylke and kommune it sits in, so it joins the same Klass vocabulary
the statistics do.

**Shape.** The type listing already carries each type's `egenskapstyper`, so the whole
catalogue including every attribute schema is **one request** rather than 424. Attribute
names are stored as harvested keywords and the publisher's categories as themes, because
neither is in a one-word title like "Bru". The abstract type is skipped: it holds no
objects, and cataloguing it would promise records that do not exist.

**Bounded live proof.** Six types spread across the catalogue — bridge (60), tunnel
(581), guardrail (5), sign (96), type 9 and fence (7) — were each queried for exactly
one object with `antall=1`. All six returned an object with geometry; bridge 272296863
came back with 18 typed attributes (`Byggverkstype = Hvelvbru (562)`, `Lengde = 23.0`,
`Eier = Fylkeskommune`) and a `LINESTRING Z`. **No road objects were imported.** The six
proof objects were inspected and not stored.

**Two strengths of claim, kept apart.** `subject_count` is the publisher's own number
from `/statistikk`, read for every type: 414 succeeded, 9 failed and were left null
rather than estimated. 29,152 bridges, 245,616 guardrails, 29,658,377 objects across all
423 registers. The capability — `features`, addressed by `NVDB vegobjekt-id` through a
`subject_template` — carries `verified_at` and `verified_sample_count` **only** on the
six proved types; the other 417 carry the capability with those fields null and a note
saying the class was verified on six sampled types and not on this one.

**Licence is null.** NVDB prints no licence field on an object type. Statens vegvesen's
CKAN portal at `dataut.vegvesen.no` states NLOD for *its* 85 datasets; that is a claim
about those datasets, not about this API, and copying it across would be inventing a
licence.

**Displacement checked, not assumed.** 423 new fetchable resources can push correct
answers out of the top five. Held-out recall@5 holds at 0.892 with MRR 0.760, and
`pda benchmark` at 0.8923 / 0.9385.

**Open question for the query side.** `bruer i Norge` does not retrieve `nvdb:60`, whose
title is the singular `Bru`. `tunneler` and `rekkverk langs vegen` do retrieve their
types. This is the Norwegian inflection gap, recorded rather than solved here.

**Other sources probed, and what they answered.** `dataut.vegvesen.no` is a CKAN
instance with 85 datasets carrying real NLOD licences and `end_point_url` fields — a
good next connector. Norges Bank's SDMX API answers without credentials. MET Frost and
NVE HydAPI both return 401 and need registered keys. Guessed PxWeb hosts for NAV, Udir,
Landbruksdirektoratet, Husbanken, Helsedirektoratet, Miljødirektoratet and Vegvesen all
404 or fail DNS: guessing URLs is the wrong method, and mining `access_path` and
distribution URLs already in the registry is what found NVDB and CKAN.

## nvdb:* — 2026-09-10 — fetch wired, bounded by construction

**What changed.** `classify_access_path` now recognises both NVDB shapes, and
`fetch_observations` dispatches them to `_fetch_nvdb`. Road objects land in `records`
with kind `feature` and subject scheme `NVDB vegobjekt-id`, alongside observations and
entities on the same provenance spine.

**"Fetch this type" cannot mean "fetch all of it".** Type 5 holds 245,616 guardrails.
A collection request returns a bounded page — ten by default, a hundred at most — and
asking for more raises `SelectionTooLarge` with the limit rather than truncating
quietly. `select` accepts `kommune` and `fylke` as **numeric Klass codes**; a place
name is refused, because NVDB would accept the parameter and match nothing, which reads
as "there are no bridges in Oslo".

**Bounded live proof.** One bridge by id: object 272296863, `Byggverkstype = Hvelvbru
(562)`, `Eier = Fylkeskommune`, `lengde = 22.95`, kommune `3105`, fylke `31`, with a
`LINESTRING Z`. Then three bridges in Oslo via `select={"kommune": ["0301"], "antall":
["3"]}` — 272296875, 272296888, 272296891, kommune `301`. Four feature records stored
in total, each with its request URL, HTTP status and retrieval time. Capability for
`nvdb:60` now carries `verified_at` and `verified_sample_count = 3`; the other 422 types
still say the class was verified and they were not.

**Why the kommune code matters.** It is a Klass code, the same vocabulary the SSB tables
use, so a road object is joinable to a statistic about the same municipality. That is the
thing NVDB adds that a map tile does not.

**An empty response is an error, not an answer.** A request that returns no objects
raises and stores nothing. Reporting success with zero records would read as "there are
none", which is a claim about the world rather than about the request.

**Storage.** Still pointers: 423 registers addressing 29,658,377 objects, and 4 objects
actually stored. Held-out recall@5 holds at 0.892 / MRR 0.759, `pda benchmark` 0.8923.

## Klass mirror deleted — 2026-09-10

`data/klass/versions/` (170 MB, 837 version payloads) is removed. The vocabulary it was
harvested for measured no change in retrieval and the reasoning is in GAPS.md. The
derived aliases stay in `term_aliases` (5,869 rows, tiny) and `scripts/harvest_klass.py`
rebuilds the mirror in about twelve minutes; `data/klass/classifications.json` is kept
because the harvester reuses it and it saves 151 requests on a rebuild.

## norgesbank:* — 2026-09-11 — harvested, bounded, and verified

**The connector already existed.** `sources/norgesbank.py`, the fetch dispatch and
`tests/test_norgesbank_source.py` were all committed and working; the source had simply
never been run, so the registry held no financial or monetary data. I did not check that
before starting, and wrote a second connector for a source that already had one — see
the note at the end.

**Harvested.** 24 dataflows, with the publisher's Norwegian names because the API prints
both: `Valutakurser`, `Styringsrente`, `Nøkkeltall for statsgjelden`, `Pengemarkedsdata`.
The source caps itself at 10 by default and says so in its ingest reason, so `--limit 50`
was used rather than changing someone else's deliberate default.

**Two bounds, because one was not enough.** The fetch requested `access_path` as listed,
which for `EXR` is every currency pair for its whole history. Adding SDMX's
`lastNObservations` (default 5, capped at 100) bounds periods per series — and that alone
is not a bound. `MONEY_MARKET` answered a **one-period** request with **34,906 cells**,
`FAUCTION` with 11,941, `LIQUIDITY_FORECAST` with 5,053, because those flows hold tens of
thousands of *series*. A request can be bounded in one dimension and unbounded in the
other. A 2,000-cell ceiling now refuses the response before anything is stored, naming
the series key as the way to narrow.

I found that out by writing 58,687 rows and 65 MB into the registry first. They are
deleted, the cap is in place, and re-verification stores 2,141 cells across 18 flows.

**Verified, and honestly partial.** A dataflow classifies as `unverified` from its URL,
which is correct and keeps it out of the fetchable lane. `scripts/verify_norgesbank.py`
discharges that with one period per flow: 18 proved and now carry `observations` with
`verified_at`, a sample count and an SDMX `subject_template`; 5 are refused as too wide
and stay `unverified`, which is the true statement — no bounded read of them has been
demonstrated yet; 1 (`LENDINGSURVEY`) 404s and is left alone. The five that are too wide
need series-key addressing to become readable, which is the next step.

`valutakurser` now returns `norgesbank:EXR`, `styringsrenten` returns
`norgesbank:ANN_KPRA`, `rentebytteavtaler` returns `norgesbank:GOVT_IRS`. Held-out holds
at 0.897 / 0.749 and `pda benchmark` at 0.8923 / 0.9385.

**A mistake worth recording.** I wrote `src/public_data_agent/sources/norgesbank.py` with
`cat >` without checking whether the file existed, and destroyed a committed connector
that was better than the one I was writing. It was restored from git and my duplicate
reverted. Check what exists before building; `cat >` on a path you have not read is a
destructive write.

## norgesbank:* — 2026-09-11 — the five wide flows, readable one series at a time

**The problem.** Five dataflows answered even a one-period request with more cells than
the 2,000-cell ceiling allows — `MONEY_MARKET` 34,906, `FAUCTION` 11,941,
`LIQUIDITY_FORECAST` 5,053, `GOVT_PRIMARY_MARKET` 2,529, `GOVT_SECONDARY_MARKET` 2,117 —
so they were refused and stayed `unverified`. That was honest, but it left real data with
no bounded way in.

**Dimensions first, from `detail=serieskeysonly`.** That request lists the codes that
occur and no observations, so a flow too wide to read still describes itself cheaply:
`MONEY_MARKET`'s 35,354 series fit in 1.7 MB and show why the flow is wide — 12
dimensions, one of them `COLL_ISIN` with 1,046 values. `index_dataset` now has a Norges
Bank branch that records these as the resource's shape.

**Order had to become data.** An SDMX key is positional (`B.USD.NOK.SP` is
FREQ.BASE_CUR.QUOTE_CUR.TENOR), and `resource_fields` read back alphabetically, losing the
only thing that says which code goes where. It gained a `position` column, added by
migration and NULL for named-field sources, which keep their alphabetical order.
`resource_shape`, and therefore MCP `inspect`, now shows each field's position.

**Narrowing by dimension, not by hand-written key.** `select={"FX_CURRENCY": ["USD"]}`
builds the key in recorded order, with empty slots as wildcards and `+` for several
values. Two things are refused before anything is sent, because the API answers both
with a bare 400 or 404:
- a code the flow doesn't use, when the stored code list is complete (a list truncated at
  400 values, like `COLL_ISIN`'s, cannot refuse anything);
- a code containing a character a key can't carry. `GOVT_PRIMARY_MARKET`'s `COUPON` codes
  are all like `0.00000000` — the dot is the key separator — and its `INSTR` codes are like
  `NTB 03/2004`. Wildcarding both works, and that is what the refusal says to do.

The 404 that started this was mine: I wrote an 11-position key for a 12-dimension flow.
Counting positions from the recorded shape is exactly the check that would have caught it.

**Proven live.** `scripts/verify_norgesbank.py` now indexes each flow and then reads it
whole, or narrows to the first real series the flow lists. Result: **18 read whole, 5
proved by narrowing, 1 failed** (`LENDINGSURVEY` 404s, as before). `MONEY_MARKET` narrowed
on all 12 dimensions to 1 cell; `GOVT_PRIMARY_MARKET` on 6 of 8, with `COUPON` and `INSTR`
wildcarded. All five now carry `observations` with a verified sample. Storage grew by
exactly five observations.

Through the MCP tool rather than the fetcher directly: `tool_fetch` on `EXR` with
`BASE_CUR=USD` sent `.../EXR/.USD..` and returned three USD/NOK rates, including 9.2999 for
2026-09-11. `tool_fetch` on `MONEY_MARKET` unnarrowed refuses with all 12 real dimensions
and their widths, and stores nothing.

**Two bugs this found in existing code.**
- *Re-indexing downgraded a verified resource.* `index_dataset` carried `verified_at`
  forward but rewrote the capability from the URL, and `set_capability` replaces the whole
  row. Indexing a proven Norges Bank flow would have written `unverified` over
  `observations` and erased its subject template. It now carries a verified capability
  forward whole.
- *The too-wide error pointed at a field the fetcher refuses.* The MCP tool tells a caller
  to narrow by "the dimensions listed above", and my first cell cap listed one made-up
  dimension, `series`. Following the error's own instructions failed. It now lists the
  flow's real dimensions.

**Unchanged.** Held-out 0.897 / 0.749, `pda benchmark` 0.8923 / 0.9385.

**Open.**
- The MCP too-wide suggestion also says "or use from_year/to_year to shorten time". The
  Norges Bank fetcher ignores those; width here is series count, not time. The message is
  shared with SSB, where it is correct, so it was left as it is.
- `pengemarked` does not retrieve `MONEY_MARKET` (`Pengemarkedsdata`). The query is the
  head of a longer title compound — the prefilter keeps the row by prefix and the exact
  scorer then drops it. The compound splitter handles the opposite case, not this one.
- `index_dataset` still has no caller outside tests and this script.

## vegvesen:* — 2026-09-11 — Dataportalen's 23 data services, pointed at the services

**The connector already existed and had never been run.** `sources/vegvesen.py` and its
tests were committed, capped at 10 packages, and the registry held no `vegvesen:` rows.
Reading it before running it turned up two things worth more than the harvest.

**It pointed at the catalogue, not the data.** Every record's `access_path` and
distribution was CKAN's `package_show` action, which returns metadata. And `fetch.py`
dispatched that URL to `cells_from_vegvesen`, which stored each *resource description*
as an observation — measure `name`, value `"Åpne data via NVDB api"`. Two tests pinned
exactly that. The dispatch, `_fetch_vegvesen` and `cells_from_vegvesen` are removed, and
the two tests are replaced by one asserting the opposite: a `package_show` URL classifies
as `none`, and fetching a stored catalogue record writes no observations. Replacing those
tests corrects a pinned violation of the rule that observations are data values; it is
not a weakening. Nothing to clean up — the old path had never been run, so it had written
nothing.

**Most of the portal was already catalogued, and one field says which part.** Of its 85
packages, 62 are already in the registry through data.norge, matched by CKAN package id,
with no licence disagreements; CKAN would have added a missing licence to only 3. Harvesting
all 85 would have put 62 second copies into search. The split is exact on the package's own
`type`: all 62 covered packages are `dataset`, all 23 uncovered ones are `dataservice`, with
no exceptions. data.norge harvests Vegvesen's datasets and not its data services. So the
source now lists `package_search` with `fq=type:dataservice` — and checks the printed type
itself, in case the filter is ignored — which is also one request rather than 86.

**Pointed at the services.** Distributions are the printed `end_point_url` then any printed
resources; landing pages are the printed `uri` (a live `/dataservice/<uuid>` page) and `url`
(a live publisher page, on 8). Formats stay in the stored package rather than being mapped,
because the portal prints values like `ukjent`.

**Access rights recorded, because an open portal is not all open data.** The printed EU
access-right URI now fills `access_rights` / `access_rights_uri`: 13 `PUBLIC`, 5 `RESTRICTED`
(NVDB Skriv, Datafangst, vehicle data with owner details, eCOC, driving-log submission), and
5 printing nothing — parking-permit registers, change of ownership, change of lessee, vehicle
technical data — which stay unknown rather than open. `api_requirements` prints what look
like encrypted blobs and is not interpreted.

**Harvested.** 23 of 23 inserted, none failed, none pointing at `package_show`. Licences: 10
NLOD, 2 CC-BY 4.0, 11 not stated and left null. All 23 land in the descriptive lane: no
connector reads these services yet, and several are write or restricted APIs that should
never be one. `ferjedatabank`'s printed endpoint is `/api/Login`, so it is credentialed in
practice whatever its access right says.

**Overlap that remains, checked by endpoint rather than assumed.** One service shares an
endpoint with a data.norge record: `nvdb-les` and "Nasjonal vegdatabank (NVDB)", both at
`nvdbapiles.atlas.vegvesen.no` — which the 423 `nvdb:*` registers also address. Kept, as the
publisher's own entry for its API. Three data.norge records surface beside new services on the
same subject — `Trafikkmeldinger`, `Værdata`, `Webkamera` — and are different resources: all
three point at the DATEX2 *specification* repository on `git.vegvesen.no`, while the new
records point at the live endpoints.

**Open.** `reisetider på veg` does not reach `vegvesen:reisetider-*`; `reisetider` alone does.
Every query word is a hard requirement and `veg` is not in those titles — existing search
behaviour, not a connector defect.

**What an agent now gets.** `tool_fetch` on `vegvesen:datex` returns
`unsupported_access_path` — "numbers were not retrieved" — naming the live DATEX endpoint,
and writes no observations. The same record would previously have been fetched through
`package_show` and returned resource descriptions as numbers.

**Displacement checked.** 23 new records can push answers down. Held-out holds at 0.897 /
0.749 and `pda benchmark` at 0.8923 / 0.9385. 1988 tests.
