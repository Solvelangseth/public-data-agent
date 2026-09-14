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

## ldirmelk / datanorge melk CSVs — 2026-09-13 — promoted

**Endpoint(s).** Yearly CSVs already stored as Data.norge access paths, for example
`https://raw.githubusercontent.com/LandbruksdirektoratetGIT/opendata/refs/heads/main/datasets/leveransedata-melk/2025/dataset.csv`.
GitHub lists year directories 2013–2025 under `datasets/leveransedata-melk`. The
publisher's råvarestatistikk page describes the same series. No new catalogue
cards were ingested: the 13 year rows were already in the shared registry and
were classified `none` because nothing read the CSV.

**Shape.** `observation`. Printed columns are `orgnr`, `navn`, `komnr`,
`kumelk_liter`, `geitemelk_liter`. Default fetch stores the **national sums** of
the two litre columns for that year, not one row per farm (~6,000 farms, 268 KB
file). A farm extract requires `select={"organisasjonsnummer": [...]}` and is
capped at 20. Empty cells are skipped, not stored as zero. `brreg:orgnr` is
claimed only after the printed orgnr column passes mod-11; `komnr` stays an
attribute because the CSV prints no municipality names.

**Capability recorded.** `observations` on the 2025 Data.norge row
`datanorge:ab9ed61d-0e4a-38d8-8fe1-5f47a02b9433`. Live GET 2026-09-13: HTTP 200,
two cells inserted: `kumelk_liter` 1,528,922,792 and `geitemelk_liter`
17,649,873 for `år=2025`. That is 1,546.6 million litres delivered to dairies,
against the publisher's rounded 1,547 million litres (1,529 cow + 18 goat) in
the 2025 markedsrapport. Licence on the harvested card is NLOD 2.0. The CSV
itself prints none.

**Surprises.**
- SSB's table catalogue has no milk-production table. Livestock tables count
  dairy cows, not litres. The coverage hole was Landbruksdirektoratet, already
  catalogued, never connected.
- The publisher states the CSV excludes milk sent to local processing. The
  stored measures are dairy deliveries, not all production. That distinction
  belongs in the answer.
- Fetching every farm would have been a bulk import of a small file. The bound
  is still applied: national totals by default, one farm by orgnr, otherwise
  `SelectionTooLarge`.

**Open question for the query side.** `melkeproduksjon` may not rank the title
`Leveranser til meieri i landbruket 2025`. That is a retrieval issue; the
source, live cells, capability and shape are now present. Held-out labels h023
and h041 now name this dataset, moving them from excluded to scored.

Proof: `data/ldirmelk_source_proof.json`.

## naturvern:naturvern_omrade — 2026-09-13 — promoted

**Endpoint(s).** Layer 0 of the printed ArcGIS REST MapServer
`https://kart.miljodirektoratet.no/arcgis/rest/services/vern/MapServer/0`.
Query is `.../query?where=...&outFields=...&returnGeometry=false&resultRecordCount=N&f=json`.
The Geonorge dataset UUID is `5857ec0a-8d2c-4cd8-baa2-0dc54ae213b4`. The Atom
feed national GeoJSON zip (~61 MB) was not downloaded. The WMS
(`mdirgis:vern`) stays a map service, classified `none`.

**Shape.** `feature`. Subject scheme `naturbase:naturvernId` (printed
`VV00003155`). Label is printed `offisieltNavn`. Attributes include
`verneform`, `kommune` as `"Asker (3203)"`, IUCN class, faktaark URL, and
`SHAPE.STArea()` / `SHAPE.STLength()`. Geometry is omitted on purpose.
Publisher count for the layer is 3,512.

**Capability recorded.** `features`. Live ingest of the one layer, then a
bounded page of ten: HTTP 200, ten feature records stored, zero observations.
Sample: `VV00003155` Blåfjell naturreservat, Naturreservat, Asker (3203).
Default page is 10, hard cap 100; `select={"naturvernId": ["VV00003155"]}`
fetches one. Licence on this harvest is `null`; Geonorge states NLOD 2.0 for
the dataset this layer serves and that was not copied onto the ArcGIS JSON.

**Surprises.**
- The leftover `miljogis` connector matches the same host and would have
  stored MapServer *layer names* as observations. Fetch dispatch checks the
  area-layer URL first. Do not fetch the MapServer root as data.
- `kommune` is a name plus a four-digit code in one string. No Klass key is
  claimed from that.
- Search ranks the Data.norge metadata card first and `naturvern:naturvern_omrade`
  second. Lanes should put the REST layer in the fetchable list.

**Open question for the query side.** MCP `fetch` still requires `table`. A
naturvern fetch uses `select.naturvernId`, not a PxWeb table id. Same gap as
Brreg orgnr and NVDB object id.

Proof: `data/naturvern_source_proof.json`.

## miljogis MapServer catalog — 2026-09-13 — fetch disabled

**Endpoint(s).** `https://kart.miljodirektoratet.no/arcgis/rest/services/{name}/MapServer?f=json` lists layers. That JSON is a catalog, the same shape Vegvesen `package_show` was.

**What changed.** Fetch dispatch for these URLs is removed. `classify_access_path` is `none`. The old path stored each layer's `name` as an observation (`anadrome_vandringshinder_laks` as a measured value). Tests that pinned that are replaced by one asserting a catalog fetch writes no observations. Harvest of the 10 MapServer rows is unchanged. The vern **area layer** (`.../vern/MapServer/0`) is the data endpoint and is handled by `naturvern`.

**Open question for the query side.** Anadrome stretches and statlig-sikra
friluftsliv now have layer-query connectors. Other MapServer services (NiN,
anadrome barriers/stocks, `friluftsliv_kartlagt`) still need the same treatment
if those questions matter. Do not re-enable catalog fetch to fake coverage.
Do not bulk-load `friluftsliv_kartlagt` (~44k polygons).

## anadrom:anadrome_strekninger_lin — 2026-09-13 — promoted

**Endpoint(s).** Layer 4 of the printed ArcGIS REST MapServer
`https://kart.miljodirektoratet.no/arcgis/rest/services/anadrome_laksefisk/MapServer/4`.
Query is `.../query?where=...&outFields=...&returnGeometry=false&resultRecordCount=N&f=json`.
The Geonorge dataset UUID is `8e01b0fb-476b-4b7f-8c16-60fcfb2df508`. The MapServer
root stays a catalog, classified `none`. Other layers on the same service
(barriers, stocks, outlets) are not this register.

**Shape.** `feature`. Subject scheme `nve:vassdragsnummer` (printed
`vassdragsNR`, e.g. `234.Z`). Label is printed `elvenavn`. Attributes include
`nasjonaltLaksevassdrag` (Ja/Nei) and `lakseregURL`. Geometry is omitted on
purpose. Publisher count for the layer is 471; vassdragsNR is unique on that
set. The scheme is the printed NVE vassdragsnummer, the same id Lakseregisteret
puts in `visElv.aspx?id=`; it was not checked against a downloaded NVE list.
No Klass key is claimed.

**Capability recorded.** `features`. Live ingest of the one layer, then one
river by `vassdragsNR=234.Z` and a bounded page of ten: HTTP 200. Sample:
`234.Z` Tanaelva, nasjonalt laksevassdrag Ja. Default page is 10, hard cap 100;
`select={"vassdragsNR": ["234.Z"]}` fetches one; `elvenavn` and
`nasjonaltLaksevassdrag` are exact printed filters. Licence on this harvest is
`null`; Geonorge states NLOD 2.0 for the dataset this layer serves and that was
not copied onto the ArcGIS JSON.

**Surprises.**
- The leftover `miljogis` connector matches the same host and would have
  stored MapServer *layer names* as observations. Fetch dispatch checks the
  stretch-layer URL first. Do not fetch the MapServer root as data.
- `vassdragsNR` values look like `001.1Z` / `234.Z`. They are not kommune
  codes.

**Open question for the query side.** `friluftsliv_kartlagt` is ~44k polygons;
do not bulk-load it. Other leftover MapServers (NiN, barriers/stocks) still
need a layer-query connector if those questions matter.

Proof: `data/anadrom_source_proof.json`.

## friluft:friluftsliv_statlig_sikra — 2026-09-13 — promoted

**Endpoint(s).** Layer 0 of the printed ArcGIS REST MapServer
`https://kart.miljodirektoratet.no/arcgis/rest/services/friluftsliv_statlig_sikra/MapServer/0`.
Query is `.../query?where=...&outFields=...&returnGeometry=false&resultRecordCount=N&f=json`.
The Geonorge dataset UUID is `e08ad2cb-3262-4a78-bc58-2f3b5c5ccfd2`. The MapServer
root stays a catalog, classified `none`. `friluftsliv_kartlagt` (~44k polygons)
was not ingested.

**Shape.** `feature`. Subject scheme `naturbase:friluftId` (printed
`FS00000161`). Label is printed `omraadeNavn`. Attributes include
`omraadeVerdi`, `faktaark` (`https://faktaark.naturbase.no/?id=FS00000161`),
and `SHAPE.STArea()` / `SHAPE.STLength()`. Geometry is omitted on purpose.
Publisher count for the layer is 2,347.

**Capability recorded.** `features`. Live ingest of the one layer, then one
area by `friluftId=FS00000161` and a bounded page of ten: HTTP 200. Sample:
`FS00000161` Kystad. Default page is 10, hard cap 100;
`select={"friluftId": ["FS00000161"]}` fetches one. Licence on this harvest is
`null`; Geonorge states NLOD 2.0 for the dataset this layer serves and that was
not copied onto the ArcGIS JSON.

**Surprises.**
- Same leftover `miljogis` catalog trap as vern and anadrom. Dispatch checks
  the area-layer URL first.
- `kommune` is not a field on this layer. No Klass key is claimed.

**Open question for the query side.** None.

Proof: `data/friluft_source_proof.json`.

## stortinget:dagensrepresentanter — 2026-09-13 — promoted

**Endpoint(s).** `GET https://data.stortinget.no/eksport/dagensrepresentanter?format=json`.
The collection is already harvested as `stortinget:dagensrepresentanter`. Other
`/eksport/` lists (periods, sessions, parties) still use the generic Stortinget
observation decoder and were not changed.

**Shape.** `entity`. Subject scheme `stortinget:representant_id` (printed `id`,
e.g. `MARNIL`). Label is printed `fornavn` + `etternavn`. Nested `parti` and
`fylke` are flattened to `parti.id` / `parti.navn` and `fylke.id` /
`fylke.navn`. Committee arrays are skipped. Microsoft `/Date(...)/` timestamps
are stored as printed. Licence is `null`.

**Capability recorded.** `entities`. Live GET 2026-09-13: HTTP 200, **168**
member records inserted, zero observation rows. Sample: `MARNIL` Marius Arion
Nilsen, FrP, Aust-Agder. `select={"id": ["MARNIL"]}` fetches one; an unknown id
is refused. The published roster is the complete current Stortinget, not a
historical dump.

**Surprises.**
- The generic Stortinget fetch would have stored each name as an observation
  (`measure=navn`). Dispatch checks this URL first.
- Search for `stortingsrepresentanter` still ranks SSB election tables first;
  the harvested title is the printed operation id `dagensrepresentanter`.

**Open question for the query side.** None for this register. Session
questions are now documents; see `stsporre:2025-2026`.

Proof: `data/strepresent_source_proof.json`.

## stsporre:2025-2026 — 2026-09-13 — promoted (documents)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/sporretimesporsmal?sesjonid=2025-2026&format=json`.
The session is already harvested as `stsporre:2025-2026`. Other leftover
`/eksport/` lists (saker, interpellasjoner, møter) still use the generic
title-as-observation decoder and were not changed.

**Shape.** `document`. Subject scheme `stortinget:sporsmal_id` (printed `id`,
e.g. `124284`). Label is printed `tittel`. Nested `sporsmal_fra` is flattened
to `sporsmal_fra.id` / `fornavn` / `etternavn` / `parti.id`. `emne_liste` is
skipped. Microsoft `/Date(...)/` timestamps are stored as printed. Licence
is `null`. Publisher count for session 2025-2026 is 524.

**Capability recorded.** `documents`. Live GET 2026-09-13: HTTP 200, one
question by `select={"id": ["124284"]}` then a page of ten. Zero observation
rows. Sample: `124284` from STIA (Stig Atle Abrahamsen) to
helse- og omsorgsministeren. Default page is 10, hard cap 100; an unknown id
is refused. The 524 questions were not all ingested. The API has no
per-question URL; the session collection is fetched and filtered.

**Surprises.**
- The previous fetch stored each `tittel` as an observation (`measure=tittel`).
  Dispatch now writes documents. `cells_from_stsporre` still copies titles for
  unit tests and is unused by fetch.
- Harvested title is the session id `2025-2026`, not "spørretimespørsmål".

**Open question for the query side.** Other leftover Stortinget collections
(`stsaker`, interpellasjoner) would still store titles as observations if
fetched.

Proof: `data/stsporre_documents_proof.json`.

## stsaker:2025-2026 — 2026-09-13 — promoted (documents)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/saker?sesjonid=2025-2026&format=json`.
The session is already harvested as `stsaker:2025-2026`. Other leftover lists
(`stskrift`, møter) still use the title-as-observation decoder and were not
changed.

**Shape.** `document`. Subject scheme `stortinget:sak_id` (printed `id`, e.g.
`200391`). Label is printed `tittel` (else `korttittel`). Nested `komite` is
flattened to `komite.id` / `komite.navn`. `emne_liste` and
`forslagstiller_liste` are skipped. Licence is `null`. Publisher count for
session 2025-2026 is 665.

**Capability recorded.** `documents`. Live GET 2026-09-13: HTTP 200, one case
by `select={"id": ["200391"]}`. Zero observation rows. Sample: `200391`
Dokument 8:288 S (2025–2026), representantforslag on wheelchair access to air
travel. Default page is 10, hard cap 100; an unknown id is refused. The 665
cases were not all ingested. The API has no per-case URL; the session
collection is fetched and filtered.

**Surprises.**
- The previous fetch stored each `korttittel` as an observation. Dispatch now
  writes documents. `cells_from_stsaker` still copies titles for unit tests
  and is unused by fetch.
- The publisher's JSON for this case prints `?å sikre` where å belongs; that
  character is stored as printed.

**Open question for the query side.** None for this register. Written
questions are now documents; see `stskrift:2025-2026`.

Proof: `data/stsaker_documents_proof.json`.

## stskrift:2025-2026 — 2026-09-13 — promoted (documents)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/skriftligesporsmal?sesjonid=2025-2026&format=json`.
The session is already harvested as `stskrift:2025-2026`. Other leftover
lists (`stmoter`, interpellasjoner) still use the title-as-observation
decoder and were not changed.

**Shape.** `document`. Subject scheme `stortinget:sporsmal_id` (printed `id`,
e.g. `127161`). Same id space as spørretimespørsmål. Label is printed
`tittel`. Nested `sporsmal_fra` is flattened to `sporsmal_fra.id` /
`fornavn` / `etternavn` / `parti.id`. `emne_liste` is skipped. Licence is
`null`. Publisher count for session 2025-2026 is 3,657.

**Capability recorded.** `documents`. Live GET 2026-09-13: HTTP 200, one
question by `select={"id": ["127161"]}` then a page of ten. Zero observation
rows. Sample: `127161` from TMV (Trygve Slagsvold Vedum) to
landbruks- og matministeren. Default page is 10, hard cap 100; an unknown id
is refused. The 3,657 written questions were not all ingested. The API has no
per-question URL; the session collection is fetched and filtered.

**Surprises.**
- The previous fetch stored each `tittel` as an observation. Dispatch now
  writes documents. `cells_from_stskrift` still copies titles for unit tests
  and is unused by fetch.
- This collection is much larger than spørretimespørsmål (3,657 vs 524). The
  bound matters.

**Open question for the query side.** `stmoter` is now documents; see
`stmoter:2025-2026`. Interpellasjoner/høringer have leftover comments in
`stskrift` but no registered source.

Proof: `data/stskrift_documents_proof.json`.

## stmoter:2025-2026 — 2026-09-13 — promoted (documents)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/moter?sesjonid=2025-2026&format=json`.
The session is already harvested as `stmoter:2025-2026`. Leftover lookup lists
(`stpartier`, `stkomiteer`, `stperioder`) still use the name-as-observation
decoder and were not changed.

**Shape.** `document`. Subject scheme `stortinget:mote_id` (printed `id`, e.g.
`11513`). Label is printed `referat_id` (else `merknad`). There is no title
field. Licence is `null`. Publisher count for session 2025-2026 is 155.

**Capability recorded.** `documents`. Live GET 2026-09-13: HTTP 200, one
meeting by `select={"id": ["11513"]}`. Zero observation rows. Sample:
`11513` referat `refs-202526-10-01`, merknad `-PACE. Strasbourg`. Default
page is 10, hard cap 100; an unknown id is refused. The 155 meetings were
not all ingested.

**Surprises.**
- The previous fetch stored each `referat_id` as an observation. Dispatch now
  writes documents. `cells_from_stmoter` still copies referat ids for unit
  tests and is unused by fetch.

**Open question for the query side.** `stpartier` is now a lookup list; see
`stpartier:2025-2026`. `stkomiteer` / `stperioder` still store names as
observations. Interpellasjoner have no registered source.

Proof: `data/stmoter_documents_proof.json`.

## stpartier:2025-2026 — 2026-09-13 — promoted (lookup)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/partier?sesjonid=2025-2026&format=json`.
The session is already harvested as `stpartier:2025-2026`.

**Shape.** `entity` with capability `lookup`. Subject scheme
`stortinget:parti_id` (printed `id`, e.g. `FrP`). Label is printed `navn`.
`representert_parti` is stored as printed. Licence is `null`. Publisher
count for session 2025-2026 is 9.

**Capability recorded.** `lookup`. Live GET 2026-09-13: HTTP 200, one party
by `select={"id": ["FrP"]}` then the complete session list of nine. Zero
observation rows. Sample: `FrP` Fremskrittspartiet, representert. An unknown
id is refused. Nine is the whole published roster for the session, not a
bulk dump.

**Surprises.**
- The previous fetch stored each `navn` as an observation (`measure=navn`).
  Dispatch now writes lookup entities. `cells_from_stpartier` still copies
  names for unit tests and is unused by fetch.
- Capability is `lookup`, not `entities`: this is a code list used as a join
  key on representatives and questions, the same role Brreg orgform plays.

**Open question for the query side.** `stkomiteer` is now a lookup list; see
`stkomiteer:2025-2026`. `stperioder` still stores names as observations.

Proof: `data/stpartier_lookup_proof.json`.

## stkomiteer:2025-2026 — 2026-09-13 — promoted (lookup)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/komiteer?sesjonid=2025-2026&format=json`.
The session is already harvested as `stkomiteer:2025-2026`.

**Shape.** `entity` with capability `lookup`. Subject scheme
`stortinget:komite_id` (printed `id`, e.g. `ARBSOS`). Label is printed
`navn`. Licence is `null`. Publisher count for session 2025-2026 is 18.

**Capability recorded.** `lookup`. Live GET 2026-09-13: HTTP 200, one
committee by `select={"id": ["ARBSOS"]}` then the complete session list of
18. Zero observation rows. Sample: `ARBSOS` Arbeids- og sosialkomiteen. An
unknown id is refused. Eighteen is the whole published list for the session.

**Surprises.**
- The previous fetch stored each `navn` as an observation. Dispatch now
  writes lookup entities. `cells_from_stkomiteer` still copies names for
  unit tests and is unused by fetch.
- The session list includes special committees whose printed names mention
  earlier sessions (e.g. `KOR`, `EOS`). Those names are stored as printed.

**Open question for the query side.** `stortinget:stortingsperioder` is a
lookup list. `stperioder:*` representatives are now person entities; see
`stperioder:2025-2029`.

Proof: `data/stkomiteer_lookup_proof.json`.

## stortinget:stortingsperioder — 2026-09-14 — promoted (lookup)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/stortingsperioder?format=json`.
Already harvested as `stortinget:stortingsperioder`. This is the 21-member
period catalog, not `stperioder:*` (historical representatives per period).

**Shape.** `entity` with capability `lookup`. Subject scheme
`stortinget:periode_id` (printed `id`, e.g. `2025-2029`). Label is the printed
id. `fra` / `til` are stored as the publisher's `/Date(...)/` strings.
`innevaerende_stortingsperiode` is a nested object and was not copied as a
second subject. Licence is `null`. Publisher count is 21.

**Capability recorded.** `lookup`. Live GET 2026-09-14: HTTP 200, 21 period
records inserted, zero observation rows. Sample: `2025-2029`, `2021-2025`.
`select={"id": ["2025-2029"]}` fetches one; an unknown id is refused.

**Surprises.**
- The previous fetch stored each period `id` as an observation. Dispatch now
  writes lookup entities. `cells_from_stortinget` still copies ids for other
  leftover `/eksport/` lists and for unit tests.
- `stperioder:2025-2029` is a different resource: ~169 historical members for
  that period. It still uses the name-as-observation decoder.

**Open question for the query side.** None for this register. Period
representatives are now person entities; see `stperioder:2025-2029`.

Proof: `data/stperioder_lookup_proof.json`.

## stperioder:2025-2029 — 2026-09-14 — promoted (entities)

**Endpoint(s).** `GET https://data.stortinget.no/eksport/representanter?stortingsperiodeid=2025-2029&format=json`.
The period is already harvested as `stperioder:2025-2029`. Other periods
were not fetched. This is not `stortinget:stortingsperioder` (the 21-period
catalog).

**Shape.** `entity`. Subject scheme `stortinget:representant_id` (printed
`id`, e.g. `MARNIL`) — the same scheme as `dagensrepresentanter`. Label is
printed `fornavn` + `etternavn`. Nested `parti` and `fylke` are flattened.
Licence is `null`. Publisher count for 2025-2029 is 169.

**Capability recorded.** `entities`. Live GET 2026-09-14: HTTP 200, one
member by `select={"id": ["MARNIL"]}` then a page of ten. Zero observation
rows. Sample: `MARNIL` Marius Arion Nilsen, FrP, Aust-Agder. Default page is
10, hard cap 100; an unknown id is refused. The 169 members were not all
ingested. Other harvested periods were not fetched.

**Surprises.**
- The previous fetch stored each `fornavn` as an observation. Dispatch now
  writes person entities, reusing `entity_from_representant`.
  `cells_from_stperioder` still copies names for unit tests and is unused
  by fetch.
- Live id for Abid Raja in this period is `ABIR`, not the older `AR` used
  in the harvest-era fixture.

**Open question for the query side.** The leftover untemplated `/eksport/`
lists are now lookups; see the following entry. Interpellasjoner have no
registered source. Generic `_fetch_stortinget` still decodes unknown
`/eksport/` paths as observations.

Proof: `data/stperioder_representanter_proof.json`.

## stortinget leftover /eksport/ catalogs — 2026-09-14 — promoted (lookup)

**Endpoint(s).** Untemplated collection GETs already harvested as `stortinget:*`:
`sesjoner` (43), `emner` (27), `fylker` (19), `allepartier` (23),
`allekomiteer` (60), `saksganger` (50). Same `format=json` query the
documentation prints.

**Shape.** `entity` with capability `lookup`. Subject schemes
`stortinget:sesjon_id`, `emne_id`, `fylke_id`, `parti_id`, `komite_id`,
`saksgang_id`. Label is printed `navn` except sessions, which use printed
`id`. Nested arrays (`underemne_liste`, `saksgang_steg_liste`) are skipped.
Licence is `null`.

**Capability recorded.** `lookup` on all six. Live GET 2026-09-14: HTTP 200,
complete published lists, zero observation rows. Samples: session `2028-2029`;
emne `4` Energi; fylke `AA` Aust-Agder; party `A` Arbeiderpartiet; committee
`ARBSOS` Arbeids- og sosialkomiteen; saksgang `PRPLOV` Lovforslag fra
Regjeringen. `select={"id": [...]}` fetches one; unknown ids are refused.

**Surprises.**
- The generic Stortinget fetch stored each `navn`/`id` as an observation.
  These six catalogs now share one lookup decoder. `cells_from_stortinget`
  remains for unit tests and for any future untemplated path not in the map.
- `allepartier` / `allekomiteer` share subject schemes with the session
  `stpartier` / `stkomiteer` lists. Record ids stay dataset-scoped.
- `sesjoner` is also the harvest listing URL for leftover session sources.
  Classifying it as lookup is correct for `stortinget:sesjoner`.

**Open question for the query side.** Interpellasjoner have no registered
source. Generic `_fetch_stortinget` still decodes unknown `/eksport/` paths
as observations.

Proof: `data/stortinget_lookup_proof.json`.

## mattilsynet:hobby_preparater — 2026-09-14 — promoted (entities)

**Endpoint(s).** `GET https://api.plantevernmidler.mattilsynet.io/hobby_preparater`.
Already harvested. OpenAPI lists other collections on the same host
(`godkjente_kjemiske_mikrobiologiske_preparater`, 268 products). Those were
not fetched. Templated `/preparat/{id}` paths were never harvested.

**Shape.** `entity`. Subject scheme `mattilsynet:preparat_id` (printed `id`,
e.g. `4572`). Label is printed `navn`. Nested lists (`virksommeStoffer`,
`importoerer`) are skipped. Licence is the harvested OpenAPI NLOD 2.0 URL
(`https://data.norge.no/nlod/no/2.0`). Publisher count for hobby products is
54.

**Capability recorded.** `entities`. Live GET 2026-09-14: HTTP 200, one
product by `select={"id": ["4572"]}` then a page of ten. Zero observation
rows. Sample: `4572` ANDERcontrol, registreringsnummer `2024.2`, status
Godkjent, form Rovmidd. Default page is 10, hard cap 100; an unknown id is
refused. The 54 hobby products were not all ingested.

**Surprises.**
- The previous fetch stored each `navn` as an observation. Dispatch now
  writes product entities. `cells_from_mattilsynet` still copies names for
  unit tests and is unused by fetch.
- Live OpenAPI has no `/preparater` collection (HTTP 404). The test fixture
  still names that leftover path; harvest skips it if the spec no longer
  prints it.
- Leftover WMS (`--source mattilsyn`) is a different host and was not
  changed. WMS/WFS stays imagery, not products.

**Open question for the query side.** Other plantevern collections on this
host share the same decoder if fetched — do not bulk the 268 professional
products. Udir NSR small catalogs are now lookups; see the following entry.

Proof: `data/mattilsynet_preparater_proof.json`.

## udir NSR small catalogs — 2026-09-14 — promoted (lookup)

**Endpoint(s).** Already harvested NSR collection GETs:
`https://data-nsr.udir.no/fylker` (36), `/skoletyper` (16), `/nacekoder` (14),
`/relasjonstyper` (4). Licence on the harvested rows is NLOD 2.0 from the
OpenAPI `info.license.url`.

**Shape.** `entity` with capability `lookup`. Subject schemes `udir:fylkesnr`
(printed `Fylkesnr`), `udir:skoletype` (`Id`), `udir:nacekode` (`Kode`),
`udir:relasjonstype` (`Id`). Label is printed `Navn`. Nested objects are
skipped. Members with an empty code are skipped.

**Capability recorded.** `lookup` on all four. Live GET 2026-09-14: HTTP 200,
complete published lists, zero observation rows. Samples: fylke `42` Agder;
skoletype `1` Grunnskole; nacekode `85.201` Ordinær grunnskoleundervisning;
relasjonstype `1` Eierstruktur.

**Surprises.**
- The previous fetch stored each `Navn` as an observation. Dispatch now
  writes lookup entities. `cells_from_udir` remains for `enheter` /
  `kommuner` (1,179 kommuner including closed) until those get a bounded
  entity fetch.
- Fylkesnr `42` is Agder in this register. No Klass key is claimed from the
  number alone.

**Open question for the query side.** `udir:enheter` (schools) and
`udir:kommuner` (1,179) still use the name-as-observation decoder. Do not
dump them. NBR small vocabs are now lookups; see the following entry.

Proof: `data/udir_lookup_proof.json`.

## nbr small catalogs — 2026-09-14 — promoted (lookup)

**Endpoint(s).** Already harvested NBR collection GETs:
`https://data-nbr.udir.no/v3/barnehagekategorier` (10), `/maalformer` (3
printed, 2 stored), `/naeringskoder` (1), `/organisasjonsformer` (46 printed,
45 stored), `/utgaattyper` (7), `/relasjonstyper` (6). Licence on the
harvested rows is NLOD from the OpenAPI `info.license.url`
(`https://data.norge.no/nlod/no`). `enheter` was not fetched.

**Shape.** `entity` with capability `lookup`. Subject schemes
`nbr:barnehagekategori` (printed `Id`), `nbr:maalform` (`Id`),
`nbr:naeringskode` (`Kode`), `nbr:organisasjonsform` (`Id`),
`nbr:utgaattype` (`Id`), `nbr:relasjonstype` (`Id`). Label is printed
`Navn`. Nested objects are skipped. Members with an empty printed code are
skipped.

**Capability recorded.** `lookup` on all six. Live GET 2026-09-14: HTTP 200,
complete published lists, zero observation rows. Samples: kategori `18`
Offentlig barnehage; maalform `B` Bokmål; næringskode `85.100`
Førskoleundervisning og drift av barnehager; orgform `AS` Aksjeselskap;
utgåttype `S` Slettet; relasjonstype `6` Eierstruktur.

**Surprises.**
- The previous fetch stored each `Navn` as an observation. Dispatch now
  writes lookup entities. `cells_from_nbr` remains for `enheter` until that
  gets a bounded entity fetch.
- `maalformer` prints `Id=""` / Navn Udefinert. That row is skipped, not
  stored under a blank key. Bokmål and Nynorsk remain.
- `organisasjonsformer` prints an empty-Id "Ingen enhetstype"; skipped.
  `barnehagekategorier` Id `0` "Ingen verdi" is a printed code and is stored.

**Open question for the query side.** `nbr:enheter` still uses the
name-as-observation decoder. Do not dump it. NOR/NPR/NFR small catalogs are
now lookups; see the following entry.

Proof: `data/nbr_lookup_proof.json`.

## NOR/NPR/NFR small catalogs — 2026-09-14 — promoted (lookup)

**Endpoint(s).** Already harvested collection GETs on
`data-nor.udir.no/v4`, `data-npr.udir.no/v4`, `data-nfr.udir.no/v4`.
`enheter` / `endretetter` were not fetched.

**Shape.** `entity` with capability `lookup`. Codes from printed `Id` or
`Kode`, labels from printed `Navn`. Empty ids skipped. Payloads may be a
bare array or a `*Liste` wrapper.

**Capability recorded.** `lookup`. Live GET 2026-09-14, zero observation
rows. NOR: maalformer 2 (`B` Bokmål), organisasjonsformer 45, relasjonstyper
5, utgaattyper 7. NPR: maalformer 2, naeringskoder 1 (`85.691`),
organisasjonsformer 45, relasjonstyper 6, utgaattyper 7. NFR: maalformer 2,
naeringskoder 1 (`88.910`), organisasjonsformer 45, relasjonstyper 5,
utgaattyper 7, skolefritidsordningskategorier 3 (`0` Ingen verdi).

**Surprises.**
- Same leftover name-as-observation decoder as NBR. `cells_from_nor` /
  `npr` / `nfr` remain for `enheter`.
- NOR/NPR/NFR organisasjonsformer share printed codes (e.g. `ADOS`) but
  record ids stay dataset-scoped.

**Open question for the query side.** Unit registers (`nor:enheter`,
`npr:enheter`, `nfr:enheter`, `nbr:enheter`, `udir:enheter`) still store
names as observations. Do not dump them. NXR fylke/bydel catalogs are now
lookups; see the following entry. `nxr:kommunedata` (1,781 historical
municipalities) was not fetched.

Proof: `data/nor_npr_nfr_lookup_proof.json`.

## nxr fylkedata / bydeldata — 2026-09-14 — promoted (lookup)

**Endpoint(s).** Already harvested collection GETs:
`https://data-nxr-fellestjeneste.udir.no/api/v2/fylkedata` (69),
`/api/v2/bydeldata` (83). Licence is harvested NLOD
(`https://data.norge.no/nlod/no`). `kommunedata` (1,781) and `*med*`
query-filter paths were not fetched as catalogs.

**Shape.** `entity` with capability `lookup`. Subject schemes
`nxr:fylkedataid` (printed `FylkeDataId`) and `nxr:bydeldataid`
(`BydelDataId`). Labels are printed `Fylkesnavn` / `Bydelnavn`. Nested
lists and coordinate objects are skipped. Historical `Fylkesnummer`
repeats across versions, so it is an attribute, not the key. No Klass
key is claimed from the number.

**Capability recorded.** `lookup`. Live GET 2026-09-14: HTTP 200, complete
published lists, zero observation rows. Samples: `FYLKE_01_1900_01_01`
Smaalenenes amt; `BYDEL_030101_2002_01_01` Bygdøy-Frogner.

**Surprises.**
- The previous fetch stored each `Fylkesnavn` as an observation. Dispatch
  now writes lookup entities. `cells_from_nxr` remains for `kommunedata`.
- Current Finnmark is `FYLKE_56_2024_01_01` / Fylkesnummer `56`. That is
  not Klass 30 (current fylke codes).

**Open question for the query side.** `nxr:kommunedata` is 1,781 historical
municipalities; do not dump it. Udir-family unit registers still store
names as observations.

Proof: `data/nxr_lookup_proof.json`.

## leftover WMS/WFS GetCapabilities — 2026-09-14 — fetch disabled

**Endpoint(s).** Harvested leftover map services whose `access_path` contains
`/wms`, `/wfs`, `/ows`, `/geoserver/`, `service=wms`, or `service=wfs`
(vegwms, mdirwms, ldirwms, fdirwms, hiwms, nibiowms, nguwms, kvwms, rawms,
kystwms). Classify already reported `none` for those URLs.

**What changed.** `fetch_observations` now refuses those paths **before**
leftover WMS dispatchers can run. Fetching GetCapabilities stored each
layer/`FeatureType` `Name` as an observation. Tests that pinned that are
replaced by one asserting a map-service fetch writes no observations.
`cells_from_*wms` parsers remain for unit tests. Harvest of leftover WMS
rows is unchanged.

**Open question for the query side.** A real WFS GetFeature by id is still
the way to get features from these services, the same pattern as
`naturvern`. Do not re-enable GetCapabilities fetch to fake coverage.

Proof: `data/wms_fetch_disabled_proof.json`.

## elcert:GetSummaryValuesPerQuarter — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.nve.no/web/ElCert/GetSummaryValuesPerQuarter`.
Already harvested. The documentation also lists `GetApplications` (914 plant
names) and `GetSummaryValues` (HTTP 404 without year/month). Those were not
fetched here. Licence is `null`; the docs print none.

**Shape.** `observation`. Measures are the printed `Values` keys
`IMaalet` and `IOvergangsordningen`. Dimensions are printed `Year` and
`Quarter`. Publisher count is 59 quarters (2012-1 through 2026-3).

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200,
`select={"Year": ["2026"], "Quarter": ["3"]}` stored two cells:
`IMaalet` 1094.9400000000023 and `IOvergangsordningen` 150.5109999999986
(JSON numbers as printed). Unknown Year/Quarter is refused.

**Surprises.**
- The leftover decoder would have skipped nested `Values` and treated
  `Year` as a name. Dispatch now reads the printed `Values` object.
- `GetApplications` still stores `KraftverksNavn` if fetched. Do not dump
  914 plants. `GetSummaryValues` without year/month stays 404; no year is
  invented.

**Open question for the query side.** Plant applications could become
entities addressed by a printed plant id, bounded, not a 914-name dump.

Proof: `data/elcert_quarter_proof.json`.

## statnett:Frequency_BySecond — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://driftsdata.statnett.no/RestApi/Frequency/BySecond`.
Already harvested. `Frequency_ByMinute` without parameters returns an empty
`Measurements` array and was not fetched. `PhysicalFlow_GetData` prints
unlabeled number lists and was not promoted. Licence is `null`.

**Shape.** `observation`. Measure is the printed key `Measurements` (Hz).
Each cell's `StartPointUTC` is the printed envelope start plus `i *
PeriodTickMs` from the printed period, the same reconstruction json-stat
uses from a printed index. `PeriodTickMs` is stored as a dimension.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 61
cells (the publisher's default window). Sample: 50.002 Hz at
StartPointUTC 1789357277000.0, PeriodTickMs 1000. More than 100 samples
is refused, not truncated. An empty Measurements array is an error.

**Surprises.**
- The leftover decoder required a JSON array of objects with `elspotId`.
  Frequency is an envelope object plus a float array. Dispatch now reads
  that envelope.
- `ByMinute` with no query is empty; no time range was invented to fill it.
- `GetApplications` still has no unique printed plant id (850 unique names
  of 914). Do not dump it as entities keyed by name.

**Open question for the query side.** `PhysicalFlow_GetData` still has
unlabeled floats. Do not invent series names. Elcert plants need a printed
id the collection does not provide.

Proof: `data/statnett_frequency_proof.json`.

## nve:HentOffentligDataSisteUke — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke`.
Already harvested. `HentOffentligData` is the 1995–present weekly dump
(14877 rows live). `HentOffentligDataMinMaxMedian` is 477 twenty-year
extrema rows. `HentOmråder` is nested area names. Those were not fetched.
Licence is `null`.

**Shape.** `observation`. Measures are the printed float keys
`fyllingsgrad`, `kapasitet_TWh`, `fylling_TWh`,
`fyllingsgrad_forrige_uke`, and `endring_fyllingsgrad`. Dimensions are
printed `omrType`, `omrnr`, `iso_aar`, `iso_uke`, and `dato_Id`.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200,
9 area rows, 45 cells. Sample: EL omrnr 1 fyllingsgrad 0.72504455 and
NO omrnr 0 fyllingsgrad 0.6360544 (fylling_TWh 55.615055 of kapasitet_TWh
87.43758) for iso_uke 36 / dato_Id 2026-09-06. More than 100 cells is
refused, not truncated. The full dump, MinMaxMedian, and area catalog
classify `none` and fetch is refused.

**Surprises.**
- Classify had left every Magasinstatistikk URL `unverified` even though
  the leftover decoder already copied printed float keys. Last-week is
  now `observations`; the dump is not.
- Other floats on the same row become dimensions of each measure. That is
  the existing leftover decoder, not a new invention.

**Open question for the query side.** `HentOmråder` could become lookup
entities addressed by printed `omrType`+`omrnr`. A bounded `iso_aar`/
`iso_uke` select on the full dump is a later slice, not a 14877-row load.

Proof: `data/nve_siste_uke_proof.json`.

## stormflo:national.json — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://stormflo-konsekvens.kartverket.no/public/api/v1/national.json`.
Already harvested. `alle_kommuner.json` is 232 municipalities / 38934 cells
live and was not fetched. Templated `{kommune}.json` was never ingested.
Licence is the printed OpenAPI URL `https://www.apache.org/licenses/LICENSE-2.0.html`.

**Shape.** `observation`. Measures are the printed integer keys
`offentlige_bygg`, `privat_naering`, `private_bygninger`, `bygning_total`,
`samfunnskritiske_bygg`, `annenbygning`, `veilengde_privat`,
`veilengde_offentlig`, `veilengde_total`, `bebyggelse`, `natur`,
`offentlige_anlegg`, `primarnaering`, `areal_total`. Dimensions are printed
scenario `code` (`1000ymax`, `200ymax`, `20ymax`, `highendwl`, `mhw`) and
`year` (`2025`, `2100`, `2150` where printed).

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 168
cells. Sample: `offentlige_bygg` 2118 (`1000ymax` 2025), 582 (`mhw` 2025),
4597 (`1000ymax` 2100). More than 200 cells is refused, not truncated.
`alle_kommuner.json` classifies `none` and fetch is refused.

**Surprises.**
- The leftover decoder already copied printed integers. Classify had left
  both URLs `unverified`, so a fetch of `alle_kommuner.json` would have
  stored 38934 cells.
- `Frequency_BySecondWithXy` prints unlabeled `[time, Hz]` pairs. Do not
  invent axis names; it was not promoted.

**Open question for the query side.** A single kommune is a templated path
the ingest skipped. A bounded fetch by printed kommunenummer is a later
slice, not the 232-row dump.

Proof: `data/stormflo_national_proof.json`.

## ssbv2:13760 — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.ssb.no/api/pxwebapi/v2/tables/13760/data?lang=no&outputFormat=json-stat2`.
Already harvested with nine neighbour v2 data hrefs. The tables catalog
`/api/pxwebapi/v2/tables` lists table ids and was not fetched. Licence is
`null`; the v2 message prints none.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Arbeidsstyrken (1000 personer)` on the default slice). Dimensions
are printed `Justering`, `Tid`, and `Alder`. The default slice is the
publisher's (`size` [4, 1, 1, 3], Tid `2026M07`); no period is invented.

**Capability recorded.** `observations` for printed `/tables/{id}/data`
hrefs. Live GET 2026-09-14: HTTP 200, 12 cells. Sample: Arbeidsstyrken
3067 (Trend, 2026M07, 15-74 år). More than 100 cells is refused, not
truncated. The tables catalog classifies `none` and fetch is refused.

**Surprises.**
- The leftover decoder already used `cells_from_jsonstat_coded`. Classify
  had left every v2 URL `unverified`, including the catalog that would
  store table labels as cells.
- Some default-slice values are json-stat `null` (seasonally adjusted
  3-month average). They are stored as printed, not filled.

**Open question for the query side.** A v2 table whose publisher default
exceeds 100 cells needs a printed dimension select, the same as PxWeb v0.
The nine harvested neighbour data hrefs classify `observations` the same
way; they were not dumped this slice.

Proof: `data/ssbv2_13760_proof.json`.

## norgesbank:IR — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.norges-bank.no/api/data/IR?format=sdmx-json&lastNObservations=5`.
Already harvested with 23 neighbour SDMX dataflows. `CBC_CALENDAR` prints
ISINs as both measure and value and was not fetched. `MONEY_MARKET`
answers lastN=1 with ~34906 cells and was not fetched. Licence is `null`;
the SDMX message prints none.

**Shape.** `observation`. Measure is the printed SDMX structure name
(`Styringsrente`). Dimensions are printed `FREQ`, `INSTRUMENT_TYPE`,
`TENOR`, `UNIT_MEASURE`, and `TIME_PERIOD`. Values are the first printed
observation array element, copied as printed (strings such as `"0.08"`).
No period is invented.

**Capability recorded.** `observations` for leftover SDMX dataflows whose
decoder copies printed observation values: IR, EXR, SHORT_RATES,
ANN_KPRA, GOVT_GENERIC_RATES, GOVT_IRS, GOVT_ZEROCOUPON,
FINANCIAL_INDICATORS. Live GET 2026-09-14: HTTP 200, 45 cells. Sample:
Styringsrente `"0.08"` (Annual, Key policy rate, Policy rate, Rate, 2021),
`"1.33"` (2022). More than 2000 cells is refused, not truncated. lastN is
capped at 100 (default 5). Calendars and wide dumps stay `unverified`.

**Surprises.**
- The leftover decoder already copied printed SDMX observation values.
  Classify had left every `/api/data/{id}` URL `unverified`, so MCP search
  would not offer a flow as observations until a live fetch wrote
  `resource_capability`.
- `CBC_CALENDAR` lastN=5 stores 70 cells whose measure and value are both
  the printed ISIN. That is not a measure; it stays unverified.
- Indexing a calendar still writes `unverified`. Indexing must not promote
  a shape-only read to observations.

**Open question for the query side.** A wide flow (MONEY_MARKET,
LIQUIDITY_FORECAST) still needs a printed series-key select. URL classify
does not claim those. Neighbour observation flows classify the same way;
they were not dumped this slice.

Proof: `data/norgesbank_ir_proof.json`.

## norgesbank:SETTLEMENT_STATISTICS — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.norges-bank.no/api/data/SETTLEMENT_STATISTICS?format=sdmx-json&lastNObservations=5`.
Already harvested. Neighbour leftover SDMX flows that also copy printed
numeric cells at lastN=5: `GOVT_KEYFIGURES` (846), `SEC` (900),
`LIQUIDITY_STATISTICS` (195), `REGNET` (415), `CBC_TRANSACTIONS` (304),
`ANN_FX_SPU` (5). They classify the same way and were not dumped this
slice. `CBC_CALENDAR`, `MONEY_MARKET`, `FAUCTION`, `LIQUIDITY_FORECAST`,
and `ANN_TEST` stay unverified. Licence is `null`.

**Shape.** `observation`. Measure is the printed SDMX structure name
(`Statistikk fra oppgjørssystemet`). Dimensions are printed `UNIT_MEASURE`,
`FREQ`, and `TIME_PERIOD`. Values are the first printed observation array
element, copied as printed (strings such as `"463"`). No period is invented.

**Capability recorded.** `observations` for the leftover SDMX dataflows
whose default lastN=5 stays under the 2000-cell ceiling. Live GET
2026-09-14: HTTP 200, 90 cells. Sample: `"463"` (Unutilised borrowing
facility in billions (NOK), Business, 2026-09-11). More than 2000 cells
is refused, not truncated.

**Surprises.**
- lastN=1 on `GOVT_KEYFIGURES` already returns 846 cells; lastN=5 is the
  same 846, so the extra periods are empty rather than a wider dump.
- `CBC_TRANSACTIONS` keeps ISIN as a dimension, not a measure. The
  calendar (`CBC_CALENDAR`) still prints ISINs as both and stays unverified.

**Open question for the query side.** Wide flows still need a printed
series-key select. `LENDINGSURVEY` 404s as before.

Proof: `data/norgesbank_settlement_proof.json`.

## omregning:search — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.fiskeridir.no/conversion-factor-api/api/v1/conversionfactors/search?fish=0102`.
Already harvested. The OpenAPI prints optional query `fish`. Unfiltered
search is 1950 rows and was not fetched. Templated `{id}` and required
`codes?type=` were never ingested. Licence is `null`.

**Shape.** `observation`. Measure is the printed key `factor`. Dimensions
are printed `fish`, `condition`, `preservation`, `validityPeriodStart`,
and `validityPeriodEnd`. Nested objects are not copied.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 1
cell. Sample: factor `1` for fish `0102`, condition `110`, preservation
`99`. Unfiltered search is refused. Unknown `fish` that returns no row is
an error. More than 100 cells is refused, not truncated.

**Surprises.**
- The leftover decoder preferred `fish` as the measure and stored factor
  as a dimension. Fetch now copies the printed numeric `factor`.
- `airquality:values` is a parameter catalog; `airquality:met` 400s
  without a station. `tidalwater:available` is an XML catalog. Those were
  not promoted. No station or lat/lon was invented.

**Open question for the query side.** A fish-code lookup could be the
required `codes?type=` path, as lookup entities, not this search dump.

Proof: `data/omregning_factor_proof.json`.

## kystverket:api/ais/realtime/vessels-by-type — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://kystdatahuset.no/ws/api/ais/realtime/vessels-by-type`.
Already harvested. County lists, location catalogs, and realtime GeoJSON
were not fetched. Licence is harvested NLOD
(`https://data.norge.no/nlod/en/1.0`).

**Shape.** `observation`. Measure is the printed key `number_of_ships`.
Dimension is printed `ship_type`. Nested objects are not copied.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 43
cells. Sample: Cargo `1186`, Fishing `2092`, Passenger `478`. More than
100 cells is refused, not truncated. Other Kystdatahuset catalogs
classify `none` and fetch is refused.

**Surprises.**
- The leftover decoder preferred `ship_type` as the measure and stored
  the count as a dimension. Fetch now copies the printed numeric
  `number_of_ships`.
- Counts move with the last-minute AIS window; they are copied as printed.
- `utdanning:tidsserie` prints `antall_ansatte` / `antall_aarsverk` but
  hydra lists 4171 rows; `endring_arbeidsmarked` is 2.3 million. Those
  were not dumped. `GOVT_PRIMARY_MARKET` lastN=5 is 7648 cells and stays
  unverified.

**Open question for the query side.** County lists could become lookup
entities addressed by printed `countyno`. Do not dump location/all or
realtime GeoJSON.

Proof: `data/kystverket_vessels_proof.json`.

## utdanning:tidsserie — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.utdanning.no/arbeidsmarkedskart/tidsserie?kommune=0301&page=1&itemsPerPage=100`.
Already harvested. OpenAPI prints optional `kommune` plus default
`page=1` and `itemsPerPage=100`. Unfiltered hydra is 4171 rows and was
not fetched. `endring_arbeidsmarked` is millions of rows and was not
fetched. Licence is `null`.

**Shape.** `observation`. Measures are the printed keys `antall_ansatte`
and `antall_aarsverk`. Dimensions are printed `dato`, `kommunenr`,
`kommunenavn`, `fylkenr`, `fylkenavn`, `region`, and `id`.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200,
11 hydra members, 22 cells. Sample: Oslo (`0301`) `antall_ansatte`
756403 (2025-10-14) and 777452 (2026-08-14). Unfiltered tidsserie is
refused. A hydra page shorter than `hydra:totalItems` is refused, not
truncated. Stedsvelger and other name catalogs classify `none`.

**Surprises.**
- The leftover decoder preferred `fylkenavn` / `tittel` as the measure.
  Tidsserie now copies the printed numeric employee counts.
- Bare `?kommune=0301` timed out; the printed OpenAPI defaults
  `page=1&itemsPerPage=100` with `kommune` returned in seconds.

**Open question for the query side.** `stedsvelger` could become lookup
entities addressed by printed `fylkenr`. Do not dump
`endring_arbeidsmarked`.

Proof: `data/utdanning_tidsserie_proof.json`.

## oslo:OK-BEF008.px — 2026-09-14 — promoted (observations)

**Endpoint(s).** `POST https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/Befolkning/Folkemengde/OK-BEF008.px`
with printed year `2025`. Already harvested leftover PxWeb tables.
Neighbour leftover Oslo tables classify the same way and were not dumped.
Licence is `null`.

**Shape.** `observation`. Measures are the printed json-stat labels
`Folkemengden i alt (antall personer)` and `Årlig endring (antall
personer)`. Dimensions are printed `geografisk område` and `år`.

**Capability recorded.** `observations`. Live POST 2026-09-14: HTTP 200, 4
cells for year 2025. Sample: Oslo (Kristiania og Aker) i alt
`Folkemengden i alt` `724290`, `Årlig endring` `6580`. The full
1801–2026 table was not fetched. Unknown years still error through
PxWeb time_codes.

**Surprises.**
- Classify already reported `observations` from the PxWeb URL; fetch had
  never written `resource_capability` or stored cells.
- Default leftover PxWeb query without a year would cover 1801–2026.
  This slice named printed `2025`.

**Open question for the query side.** Leftover Oslo tables share the SSB
PxWeb POST path. Neighbour leftover tables (BEF001–BEF010) classify the
same way; they were not dumped this slice.

Proof: `data/oslo_bef008_proof.json`.

## ssbv2:14483 — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.ssb.no/api/pxwebapi/v2/tables/14483/data?lang=no&outputFormat=json-stat2`.
Already harvested leftover v2 data href. Neighbour leftover data hrefs
classify the same way and were not dumped. Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Arbeidsstyrken (1000 personer)` on the default slice). Dimensions
are printed `Justering`, `Tid`, and `Alder`. The default slice is the
publisher's; no period is invented.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 21
cells. Sample: Arbeidsstyrken 3062 (Trend, 2026K2, 15-74 år). More than
100 cells is refused, not truncated.

**Surprises.**
- Same leftover decoder and classify as `ssbv2:13760`. This slice is
  another leftover harvested data href that had no stored cells.
- Some default-slice values can be json-stat `null`; they stay printed.

**Open question for the query side.** Remaining leftover v2 data hrefs
(`13618`, `13619`, `05110`, …) classify the same way; they were not
dumped this slice.

Proof: `data/ssbv2_14483_proof.json`.

## elcert:GetSummaryValues — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.nve.no/web/ElCert/GetSummaryValues?year=2025&month=1`.
Already harvested. Without Year/Month the publisher returns HTTP 404.
`GetApplications` (914 plant names) was not fetched. Licence is `null`.

**Shape.** `observation`. Measures are the printed keys `IMaalet` and
`IOvergangsordningen`. Dimensions are printed `Year` and `Month`.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 2
cells. Sample: IMaalet 1585.5099999999948 and IOvergangsordningen
175.48300000000017 for Year 2025 Month 1 (JSON numbers as printed).
Missing Year/Month is refused before the 404. GetApplications classifies
`none` and fetch is refused.

**Surprises.**
- The leftover decoder would have stored `KraftverksNavn` if
  GetApplications were fetched. That path is now refused.
- Query keys `year`/`month` (lowercase) are what the live API accepts;
  `Year`/`Month` also worked. Select uses Year/Month like the quarterly
  endpoint.

**Open question for the query side.** GetApplications still has no unique
printed plant id. Do not dump 914 names.

Proof: `data/elcert_summary_proof.json`.

## ssbv2:13618 — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.ssb.no/api/pxwebapi/v2/tables/13618/data?lang=no&outputFormat=json-stat2`.
Already harvested leftover v2 data href. Neighbour leftover data hrefs
classify the same way and were not dumped. Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Personer (1000 personer)` on the default slice). Dimensions are
printed `Alder`, `Kjonn`, and `Tid`. The default slice is the
publisher's; no period is invented.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 15
cells. Sample: Personer 4170 (15-74 år, Begge kjønn, 2025). More than
100 cells is refused, not truncated.

**Surprises.**
- Same leftover decoder and classify as `ssbv2:13760` / `14483`. This
  leftover harvested data href had no stored cells.
- Title prints arbeidsstyrkestatus; the default slice's ContentsCode
  label is `Personer (1000 personer)`.

**Open question for the query side.** Remaining leftover v2 data hrefs
(`13619`, `05110`, …) classify the same way; they were not dumped this
slice.

Proof: `data/ssbv2_13618_proof.json`.

## ssbv2:13619 — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.ssb.no/api/pxwebapi/v2/tables/13619/data?lang=no&outputFormat=json-stat2`.
Already harvested leftover v2 data href. Neighbour leftover data hrefs
classify the same way and were not dumped. Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Personer (1000 personer)` on the default slice). Dimensions are
printed `Alder`, `Kjonn`, and `Tid`. The default slice is the
publisher's; no period is invented.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 15
cells. Sample: Personer 4186 (15-74 år, Begge kjønn, 2026K2). More than
100 cells is refused, not truncated.

**Surprises.**
- Same leftover decoder as `13618`. Quarterly default slice (`2026K2`)
  against `13618`'s annual `2025`.
- Neighbour leftover v2 hrefs (`05110`, …) classify the same way; they
  were not dumped this slice.

**Open question for the query side.** Remaining leftover v2 data hrefs
still need a live default-slice check against the 100-cell cap.

Proof: `data/ssbv2_13619_proof.json`.

## ssbv2:05110 — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://data.ssb.no/api/pxwebapi/v2/tables/05110/data?lang=no&outputFormat=json-stat2`.
Already harvested leftover v2 data href. Neighbour leftover data hrefs
classify the same way and were not dumped. Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Personer (1 000 personer)` on the default slice). Dimensions are
printed `Alder`, `ArbStyrkStatus`, and `Tid`. The default slice is the
publisher's; no period is invented.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 30
cells. Sample: Personer 4186 (15-74 år, Personer i alt, 2026K2). More
than 100 cells is refused, not truncated.

**Surprises.**
- Same leftover decoder. Default slice is labour-force status, not
  `Kjonn` as on `13618`/`13619`.
- Remaining leftover v2 hrefs (`14714`, `14715`, `05111`, `14077`,
  `14090`) classify the same way; they were not dumped this slice.

**Open question for the query side.** Check the 100-cell cap on remaining
leftover v2 default slices before storing.

Proof: `data/ssbv2_05110_proof.json`.

## vannkraft:GetHydroPowerPlantsInOperation — 2026-09-14 — blocked (none)

**Endpoint(s).** `GET https://api.nve.no/web/Powerplant/GetHydroPowerPlantsInOperation`.
Already harvested with `GetHydroPowerPlants`. Live collection is 1863
plants. Licence is `null`.

**Shape.** Not observations. The leftover decoder copies printed `Navn`.
Plants print unique `VannKraftverkID` and numeric `MaksYtelse`,
`MidProd_91_20`, `BruttoFallhoyde_M`. Those were not stored here.

**Capability recorded.** `none`. Fetch is refused before HTTP so leftover
`Navn` cells are not written. Classify is `none` for both harvested
paths.

**Surprises.**
- 1863 unique `VannKraftverkID`; 1798 unique `Navn` (names are not a
  key).
- There is no printed single-plant GET in the untemplated docs list.

**Open question for the query side.** A later slice can fetch one printed
`VannKraftverkID` as an entity, or its printed `MaksYtelse` as
observations, without dumping 1863 names. `vindkraft` leftover `Navn` is
the same pattern.

Proof: `data/vannkraft_fetch_disabled_proof.json`.

## leftover ssbv2 remaining default slices — 2026-09-14 — promoted (observations)

**Endpoint(s).** GET json-stat2 data hrefs already harvested:
`14714` (9), `14715` (9), `05111` (24), `14077` (15), `14090` (20).
Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat ContentsCode
label (`Personer (1 000 personer)`). Dimensions are printed `Alder`,
`Tid`, and either `Kjonn` or `UtdStatus`. Publisher default slices; no
period is invented.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200
for each. Samples: `14714` Personer 1673 (Menn, 20-64 år, 2026K2);
`14715` 1729 (Menn, 20-66 år, 2025); `05111` 2330 (Menn, 15-89 år,
2025); `14077` 3513 (Ikke under utdanning, 15-74 år, 2026K2); `14090`
1021 (Verken under utdanning eller nyutdannet, 40-54 år, 2025). More
than 100 cells is refused.

**Surprises.** Default slices differ by table (`Kjonn` vs `UtdStatus`).
Harvested leftover v2 data hrefs are now all stored.

**Open question for the query side.** None of these leftover v2 hrefs
remain unstored.

Proofs: `data/ssbv2_14714_proof.json`, `data/ssbv2_14715_proof.json`,
`data/ssbv2_05111_proof.json`, `data/ssbv2_14077_proof.json`,
`data/ssbv2_14090_proof.json`.

## vindkraft:GetWindPowerPlantsInOperation — 2026-09-14 — blocked (none)

**Endpoint(s).** `GET https://api.nve.no/web/WindPowerplant/GetWindPowerPlantsInOperation`.
Already harvested with `GetWindPowerPlants`. Live collection is 65
plants. Licence is `null`.

**Shape.** Not observations. The leftover decoder copies printed `Navn`.
Plants print unique `VindkraftAnleggId` and numeric
`InstallertEffekt_MW`, `NormalAArsproduksjon_GWh`. Those were not stored
here.

**Capability recorded.** `none`. Fetch is refused before HTTP so leftover
`Navn` cells are not written. Classify is `none` for both harvested
paths.

**Surprises.**
- 65 unique `VindkraftAnleggId` and 65 unique `Navn`.
- Same leftover name-as-observation decoder as vannkraft.

**Open question for the query side.** A later slice can fetch one printed
`VindkraftAnleggId` as an entity, or its printed `InstallertEffekt_MW`
as observations, without dumping 65 names.

Proof: `data/vindkraft_fetch_disabled_proof.json`.

## oslo:OK-BEF010.px — 2026-09-14 — promoted (observations)

**Endpoint(s).** `POST https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/Befolkning/Fødte, døde og forventet levealder/OK-BEF010.px`
with printed year `2025`. Already harvested leftover PxWeb.
Neighbour leftover Oslo tables classify the same way and were not dumped.
Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat table label
`BEF010: Antall fødte barn etter bosted (GO), 2017-2025`. Dimensions are
printed `bosted` and `år`.

**Capability recorded.** `observations`. Live POST 2026-09-14: HTTP 200,
335 cells for year 2025 (one per printed GO bosted). Sample: Grønland 1
`30`, Grønland 2 `23`. Full 2017–2025 was not fetched.

**Surprises.**
- Classify already reported `observations`. Fetch had never stored cells.
- Year 2025 still expands to every printed GO. That is 335 cells, over
  the leftover JSON 100-cell cap, but one printed year rather than nine.
  There is no Oslo-i-alt row on this table.

**Open question for the query side.** A later slice can name one printed
`bosted` if 335 GO cells is too wide. Neighbour leftover Oslo tables
(BEF001–BEF007, BEF025) classify the same way; they were not dumped.

Proof: `data/oslo_bef010_proof.json`.

## oslo:OK-BEF005.px — 2026-09-14 — promoted (observations)

**Endpoint(s).** `POST https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/Befolkning/Folkemengde/OK-BEF005.px`
with printed year `2025`. Already harvested leftover PxWeb. Neighbour
leftover Oslo tables classify the same way and were not dumped. Licence
is `null`.

**Shape.** `observation`. Measure is the printed json-stat table label
`BEF005`. Dimensions are printed `bosted`, `aldersgruppe`,
`statistikkvariabel`, and `år`.

**Capability recorded.** `observations`. Live POST 2026-09-14: HTTP 200,
336 cells for year 2025 (16 bosted × 21 aldersgruppe). Sample: Oslo i
alt, Alder i alt `722326`; Bydel Gamle Oslo, Alder i alt `64565`. Full
2017–2026 was not fetched.

**Surprises.**
- Year 2025 still expands to every printed bydel and age group (336
  cells). `BEF001` year 2025 would be ~6038 cells and was not fetched.
- `statistikkvariabel` prints `antall`; the stored measure is the table
  label `BEF005`.

**Open question for the query side.** A later slice can name one printed
`bosted` if 336 cells is too wide. Neighbour leftover Oslo tables
(BEF002/003/006/007/025) are wider and were not dumped.

Proof: `data/oslo_bef005_proof.json`.

## aqua:licenses-overview — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.fiskeridir.no/pub-aqua/api/v1/licenses-overview?license-nr=A-A-0001`.
Already harvested. OpenAPI prints optional `license-nr` and default
`range` `0-9`. Unfiltered overview is a truncated page of the register
and was not fetched. Licence is the printed OpenAPI URL
`https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data`.

**Shape.** `observation`. Measures are the printed `capacity` keys
`current` and `accumulated`. Dimensions include printed `licenseNr`,
`unit`, `type`, and `legalEntityName`. Nested objects besides `capacity`
are not copied.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 2
cells. Sample: current `1.0` and accumulated `1.0` (unit `TN`, type
`MTK`) for license-nr `A-A-0001` (NMBU). Unfiltered overview is refused.
Area, site, and fish-code catalogs classify `none`.

**Surprises.**
- The leftover decoder copies `name` / `defaultName` and skips nested
  `capacity`. Overview now reads the printed numeric capacity keys.
- Default `range=0-9` returns 10 licenses without saying it is a page.

**Open question for the query side.** Sites and licenses collections are
registers. Address one printed `licenseNr` or `siteNr`; do not dump
names.

Proof: `data/aqua_overview_proof.json`.

## hoydedata:datakilder — 2026-09-14 — promoted (lookup)

**Endpoint(s).** `GET https://ws.geonorge.no/hoydedata/v1/datakilder` and
`GET https://ws.geonorge.no/hoydedata/v1/terrengtyper`. Already harvested.
`/punkt` needs coordinates and was not fetched. Licence is `null`.

**Shape.** `lookup` entities. `datakilder` keyed by printed `datakilde`
under `hoydedata:datakilde`. `terrengtyper` keyed by printed `terreng`
under `hoydedata:terreng`. Empty terreng skipped. Nested objects not copied.

**Capability recorded.** `lookup`. Live GET 2026-09-14: datakilder HTTP 200,
5 entities (`dtm1` Digital terrengmodell med 1 meters oppløsning.).
terrengtyper HTTP 200, 23 entities (`ÅpentOmråde`). Punkt classifies
`none` and fetch is refused.

**Surprises.**
- The leftover decoder stored `datakilde` as an observation measure.
  These are catalogs, not height cells.
- Live terrengtyper prints 24 rows including one null `terreng`; that
  row is skipped, not stored under a blank key.

**Open question for the query side.** A later slice can GET `/punkt` with
printed coordinates from a question. Do not invent lat/lon.

Proof: `data/hoydedata_lookup_proof.json`.

## oslo:OK-BEF004.px — 2026-09-14 — promoted (observations)

**Endpoint(s).** `POST https://statistikkbanken.oslo.kommune.no/statbank/api/v1/no/db1/Befolkning/Folkemengde/OK-BEF004.px`
with printed year `2019` (last printed time label). Already harvested
leftover PxWeb. Neighbour leftover Oslo wide tables classify the same
way and were not dumped. Licence is `null`.

**Shape.** `observation`. Measure is the printed json-stat table label
`Folkemengden etter administrativ bydel og alder 2008-2019`. Dimensions
are printed `År`, `Geografi`, `Aldersgrupper`, and `Måltall`
(`Personer`). json-stat does not mark `Måltall` as metric.

**Capability recorded.** `observations`. Live POST 2026-09-14: HTTP 200,
320 cells for year 2019 (16 Geografi × 20 Aldersgrupper). Sample: Oslo
i alt, Alder i alt `678730`; Bydel Gamle Oslo, Alder i alt `55739`.
Full 2008–2019 (3840 cells) was not fetched.

**Surprises.**
- Year codes are `0`–`11`; `from_year=2019` matches the printed label
  `2019` and selects code `11`.
- Same leftover measure-as-table-label as BEF005 (`statistikkvariabel`
  / `Måltall` stay dimensions).

**Open question for the query side.** A later slice can name one printed
`Geografi` if 320 cells is too wide. Leftover Oslo `BEF001`/`BEF002`/
`BEF003`/`BEF006`/`BEF007`/`BEF025` stay wide and should not be dumped.
`statnett:ElspotPowerSituation_GetPowerSituations` prints
`powerSituation` strings (`Normal`), not numeric cells.

Proof: `data/oslo_bef004_proof.json`.

## vindkraft:GetWindPowerPlants — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://api.nve.no/web/WindPowerplant/GetWindPowerPlants`
with select `VindkraftAnleggId=20` (Bessakerfjellet). Already harvested.
Unfiltered collection is 72 plants / 404 float cells and was not stored.
`GetWindPowerPlantsInOperation` (65 names) stays refused. Licence is
`null`.

**Shape.** `observation`. Measures are printed JSON float keys
`InstallertEffekt_MW`, `NormalAArsproduksjon_GWh`,
`GjsnittGeneratorytelse`, `GjsnittNavhoeyde`, `GjsnittRotordiameter`,
and `EnergiPerSveiptAreal`. Other scalars stay dimensions. Nested
`Turbiner` is not copied. Integer ids are not measures.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200, 6
cells. Sample: InstallertEffekt_MW `57.5` and NormalAArsproduksjon_GWh
`152.9` for VindkraftAnleggId `20` (Åfjord). Unfiltered fetch is refused
before HTTP. InOperation classifies `none`.

**Surprises.**
- Documentation prints `/GetWindPowerPlants/{id}`, but a live GET of
  `/GetWindPowerPlants/20` returns the same 72-plant catalog as the
  collection. The request URL is therefore the collection; rows are
  filtered to the printed id after GET.
- `HovedEierOrgNr` is a printed nine-digit string. It is stored as a
  dimension, not claimed as `brreg:orgnr`.

**Open question for the query side.** Do not GET the vannkraft collection
(1863 plants) to filter one id. `statnett:ElspotPowerSituation_GetPowerSituations`
prints `powerSituation` strings (`Normal`), not numeric cells.

Proof: `data/vindkraft_plant_proof.json`.

## nve:HentOmråder — 2026-09-14 — promoted (lookup)

**Endpoint(s).** `GET https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOmråder`.
Already harvested. Last-week cells stay `observations`. The weekly dump
and MinMaxMedian stay refused. Licence is `null`.

**Shape.** `lookup` entities under `nve:magasin_omrade`. Key is printed
`omrType` and `omrnr` joined with `:`. Label is printed `navn`. Nested
`land` / `elspot` / `vassdrag` arrays are unwrapped. Empty keys skipped.

**Capability recorded.** `lookup`. Live GET 2026-09-14: HTTP 200, 10
entities. Sample: `NO:0` Norge, `EL:1` NO 1, `VASS:1` VASS1. Codes
EL:1–5, NO:0, VASS:1–4. Fylkesnummer is not claimed.

**Surprises.**
- Live payload is a one-element JSON array wrapping the three groups.
  A bare object is also accepted.
- Leftover decoder would have stored nested `navn` as observation
  measures.

**Open question for the query side.** Last-week `fyllingsgrad` cells
already use printed `omrType`/`omrnr` as dimensions. This catalog is the
label side of that key.

Proof: `data/nve_omrader_proof.json`.

## nve:HentOffentligDataMinMaxMedian — 2026-09-14 — promoted (observations)

**Endpoint(s).** `GET https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataMinMaxMedian`
with select `iso_uke=1` (printed). Already harvested. Unfiltered extrema
are 477 rows / 2862 cells and were not stored. The 1995–present weekly
dump stays refused. Licence is `null`.

**Shape.** `observation`. Measures are the printed float keys
`minFyllingsgrad`, `minFyllingTWH`, `medianFyllingsGrad`,
`medianFylling_TWH`, `maxFyllingsgrad`, and `maxFyllingTWH`. Dimensions
are printed `omrType`, `omrnr`, and `iso_uke`. Other floats on the same
row stay dimensions of each measure.

**Capability recorded.** `observations`. Live GET 2026-09-14: HTTP 200,
54 cells for iso_uke 1 (9 areas × 6 measures). Sample: EL omrnr 1
minFyllingsgrad `0.4569424`; NO omrnr 0 minFyllingsgrad `0.4268934`.
Unfiltered fetch is refused before HTTP. One area all weeks is 318 cells
and stays over the 100-cell cap.

**Surprises.**
- OpenAPI prints no query filter. The request is the collection GET;
  rows are filtered to the printed `iso_uke` after GET.
- `iso_uke` runs 1–53. Week 1 is the first printed week, not invented.

**Open question for the query side.** A later slice can name printed
`omrType`+`omrnr` together with `iso_uke` if 54 cells is too wide.
`statnett:Frequency_ByMinute` still returns an empty Measurements array
without a time range; do not invent `from`/`to`.

Proof: `data/nve_minmax_proof.json`.

## baf:Fylker — 2026-09-14 — promoted (lookup)

**Endpoint(s).** `GET https://www.barnehagefakta.no/api/Fylker`.
Already harvested. `Location` is every kindergarten and was not fetched.
Licence is `null`.

**Shape.** `lookup` entities under `baf:fylkesnummer`. Key is printed
`fylkesnummer`. Label is printed `fylkesnavn`. Nested `kommuner` arrays
are not copied.

**Capability recorded.** `lookup`. Live GET 2026-09-14: HTTP 200, 16
entities. Sample: `03` Oslo, `42` Agder, `21` Svalbard. Location
classifies `none` and fetch is refused.

**Surprises.**
- The leftover decoder stored `fylkesnavn` as an observation measure.
- Printed names include Sámi forms (`Nordland - Nordlánnda`).
- Klass fylkesnummer is not claimed; these are BAF's printed codes.

**Open question for the query side.** Nested kommuner could become lookup
entities addressed by printed `kommunenummer`, not a kindergarten dump.

Proof: `data/baf_fylker_proof.json`.

## aqua:fish-codes — 2026-09-14 — promoted (lookup)

**Endpoint(s).** `GET https://api.fiskeridir.no/pub-aqua/api/v1/fish-codes`.
Already harvested. License/site dumps were not fetched. Licence is the
printed OpenAPI URL
`https://www.fiskeridir.no/Tall-og-analyse/Lisens-for-bruk-av-Fiskeridirektoratets-data`.

**Shape.** `lookup` entities under `aqua:fish-code`. Key is printed
`code`. Label is printed `nbNoName` (else `latinName`). Other scalars
stay attributes. Nested objects are not copied.

**Capability recorded.** `lookup`. Live GET 2026-09-14: HTTP 200, 540
entities. Sample: `010901` Abbor (`Perca fluviatilis`, FAO `FPE`).
Sites/licenses/entities catalogs classify `none`.

**Surprises.**
- The leftover decoder stored `nbNoName` as an observation measure.
- 540 unique printed codes; duplicates would have been skipped.

**Open question for the query side.** `aqua:intentions` is 10 printed
purpose ids. `kystverket` counties is 17 printed `countyno`.
`miljodir:Public_GetUnitList` is 114 printed `UnitID`.

Proof: `data/aqua_fish_codes_proof.json`.


























