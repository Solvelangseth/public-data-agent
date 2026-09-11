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
