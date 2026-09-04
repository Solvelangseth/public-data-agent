# Brief: the connector lane

You are working on the crawl and connector side of this project. Another Claude Code
session owns the query side. This file is the shared understanding. Read it before
touching anything, and treat it as more current than `context.md`, which predates the
change of direction described below.

## What the product is

An MCP server that answers questions about Norwegian public data with **accurate,
citable data** — company records, demographics, buildings, geography, transport,
environment, everything. Someone asks a question through Claude, the MCP finds the right
data and returns it with provenance.

**The v1 goal is finding the correct data.** Not analysis, not joins, not feature
engineering. If retrieval does not work, nothing built on top of it matters. Analysis
comes later and must not shape decisions now.

## What is actually true right now

Measured, not estimated:

| | |
|---|---|
| datasets in registry | 13,281 |
| of those, able to return a number | 4,160 |
| observations stored | 596,543 |
| connector files in `sources/` | **186** |
| sources actually harvested | **3** (datanorge, ssbtable, fhi) |
| tests | 1,836 passing |

The gap between 186 and 3 is the entire job. Connectors for company registry, geospatial,
transport, environment, marine, research and government data were all written and never
promoted to the point where they return real data.

## The finding that set the strategy

Every one of the 9,121 Data.norge catalogue records was classified by what its access
path can actually yield. **Zero return a number.**

```
9,121 catalogue records
  └ 8,739 have distributions (49,577 total)
      └ mostly geospatial imagery — 6,311 GeoTIFF, 4,397 TIFF, 4,309 JPEG, 1,962 LiDAR
      └ 1,073 have any tabular format
          └ 239 have an API-shaped URL
              ├ 133 raw CSVs on GitHub
              ├ 156 ArcGIS portals for two individual municipalities
              └   0 that can return a cell
```

So: **do not grow the metadata-only catalogue.** More dataset cards that describe data
without holding any is not progress. The existing 9,121 are frozen — they stay for
benchmark ground truth and as a map of which domains have gaps, and they are not to be
extended.

Growth comes from promoting connectors that return real data.

## Non-negotiable rules

These are the trust boundary. Everything else is negotiable; these are not.

- **Never invent a value, id, period, licence, dimension or key.** Every number must
  trace to something actually fetched, with the request URL and retrieval time stored.
- **Licences stay `null` when unknown.** Do not guess, do not default to "open".
- **Fetch only through a registered connector.** A catalogue landing page is not an API.
  If you cannot verify a payload returns real data, classify it `unverified`, not
  `observations`. Claiming reach you do not have is worse than having none.
- **Never weaken a test to make something pass.** If a test blocks you, either the code
  is wrong or the test encodes something you have not understood yet. Find out which.
- **Respect rate limits.** FHI rate-limits at 2 requests/second and returns HTTP 429
  under load — a naive 4-worker crawl looked like 123 broken tables and was not. Use
  `HttpClient(limiter=RateLimiter(...))`, never raw `urllib` in a loop.

## The data model — ready, use it

Landed in commit `5dcc24d`. Every stored row used to be an **observation**:
`(measure, value, dimensions)`. That fits a statistical cell and nothing else, which is
why the original FHI connector stored *table ids* as observation values — there was no
other shape on offer. A company, a building and a parliamentary decision are not
measures of anything.

There are now two halves. Write both for every connector you promote.

### 1. The resource index — what a source can return and what is inside it

This is the v1 priority. A question reaches a resource through this index, not through
its title. A question about building costs missed twelve fetchable building-cost tables
because search could only read their names.

```python
registry.set_capability(dataset_id, {
    "capability": "observations",       # entities | features | documents
                                        # lookup | unverified | none
    "record_kind": "observation",
    "endpoint": "https://.../data",     # what returns data, not a landing page
    "request_method": "POST",
    "period_start": "2000", "period_end": "2025",
    "source_modified_at": "...",        # publisher's timestamp, for refresh crawls
    "verified_at": "...",               # requires verified_sample_count
    "verified_sample_count": 12,
})

registry.set_resource_shape(dataset_id, fields=[
    {"field_code": "Region", "field_label": "region", "field_role": "key",
     "values": [{"value_code": "0301", "value_label": "Oslo"}, ...]},
    {"field_code": "Tid", "field_role": "period", "values": [...]},
], keys=[
    {"scheme": "klass:131", "field_code": "Region", "coverage_count": 356},
])
```

`field_role` is `key | period | measure | attribute | geometry`, so a caller can find the
period field without guessing at its name. `scheme` is a published identifier system —
`klass:1168`, `klass:131`, `brreg:orgnr`, `matrikkel:bygningsnummer`. Record every scheme
a resource speaks; that is what makes two resources relatable later, and it costs nothing
now.

`verified_at` is refused without `verified_sample_count`. A capability is a claim from
records actually seen, never from a URL pattern — that is what `unverified` is for.

Two queries fall out that used to need a crawl:

```python
registry.datasets_containing_value("0301")     # which resources contain this code
registry.datasets_with_key("brreg:orgnr")      # which resources speak this scheme
```

### 2. The record store — one spine, four kinds

```python
registry.upsert_record({
    "id": ...,
    "dataset_id": ...,
    "kind": "observation",              # entity | feature | document
    "series": "fetch:<table>",          # which projection wrote this
    "subject_scheme": "brreg:orgnr",    # what the record is about
    "subject_code": "923609016",
    "subject_label": "EQUINOR ASA",
    "period": "2025",
    "measure": ..., "value": ...,       # observations only; null otherwise
    "suppressed": ":",                  # publisher's withheld marker, if any
    "attributes": {...},                # dimensions, columns or properties
    "geometry": {...},                  # features only
    "retrieved_at": ..., "request_url": ..., "http_status": ...,
    "publisher_name": ..., "license": None,
}, run_id)
```

**Identity is deliberately wide** — subject, period, measure and attributes all
participate. Keyed on less, a resource that splits a subject several ways overwrites
itself and reports success; that is how a join once reported 7,200 rows and stored 36.
When you build an `id`, include everything that makes two records different.

A suppression marker goes in `suppressed`, never in the value. `value_num` stays null for
anything non-numeric, so a later average cannot count a censored record as data.

`datasets` and `observations` are untouched and still in use. The 596,543 stored
observations migrate later as a separate, deliberate change — do not migrate them as a
side effect of your work.

## Ownership

| | you | the query session |
|---|---|---|
| owns | `sources/`, harvest, the endpoint/shape index | search, fetch dispatch, joins, MCP tools |
| writes to | crawl tables | query tables |
| never writes to | query tables | crawl tables |

Same repository. Work on a branch, open a PR, and **never merge red** — the suite is the
only thing standing between two sessions without shared context and a silent regression.

## Definition of done for promoting one connector

The FHI job is the worked example (commits `6ef054d`, `42d91aa`). It took about a day.
A connector is done when all of these hold:

1. **Listing reaches the level that holds data.** FHI originally listed 13 registers,
   each addressed by a URL returning a list of table ids — one level too shallow, so
   nothing was fetchable. It now lists 369 tables.
2. **`classify_access_path` gives it a truthful capability** — `observations`, `lookup`,
   `unverified` or `none` — and distinguishes a data endpoint from a listing endpoint.
3. **A fetch adapter returns real payload data**, respecting whatever the API requires.
   Some APIs refuse an unfiltered dimension; that is a feature, not an obstacle.
4. **A too-large request is refused before it is sent**, naming what to narrow.
5. **An unsatisfiable request fails** rather than silently widening. A year range that
   matches nothing must error, never fall back to fetching everything.
6. **The resource index is filled** — capability, fields, field values and key schemes.
   A promoted connector whose shape is not recorded cannot be found by a question.
7. **Tests exist and pass**, using a fake HTTP client, with no network in the test suite.
8. **A live run is verified by eye.** Look at actual returned values before declaring it
   works. `tests/test_records.py` shows the store's contract.

## Three failures that have already cost us — do not repeat them

**A single green metric is not evidence a change is safe.** A change once returned the
retrieval benchmark to exactly its previous score while taking a common query from four
usable results to zero. It was only caught by having a second, independent measure.
Check at least two before calling anything safe.

**Real cells, correct provenance, wrong selection.** This is the recurring failure and it
always reports success. Examples: a join reported 7,200 rows and stored 36, because row
identity omitted the fields that made rows different, so each overwrote the last. A
publisher's suppression marker `:` was stored as if it were a number. A fetch scoped by
the wrong key returned 545,688 values for a two-year question. The provenance was
impeccable every time.

**A write that looks additive can be destructive.** Passing a different `series` tag when
re-writing the same cells did not add rows — it *relabelled* rows an earlier run had
written, and a read scoped to the original tag lost half its data. Before writing,
check whether the identity you are writing under already exists under a different label.

## What not to do

- Do not add Data.norge-style metadata records.
- Do not bulk-mine records. Storage is cheap but the value is not there yet. Fill the
  resource index exhaustively and store enough records to verify a connector works; mass
  ingestion is a later decision.
- Do not migrate the existing observations into `records`. That is a separate change.
- Do not do any work involving `offentligdata.no`.
- Do not print or commit `OPENAI_API_KEY`; `.env` and `.env.*` are gitignored.

## Where to start

Company registry (`brreg*`, 15 files) is the strongest first domain: Brønnøysund has a
documented open API, org numbers are as clean an identifier scheme as Klass codes are for
geography, and companies exercise the `entity` kind that statistics never did. Promote
one connector end to end against the definition of done above, then report back before
doing the other fourteen — the first one will surface whatever the model did not
anticipate, and it is cheaper to fix then than after fifteen.

Report findings honestly, including negative ones. A connector that cannot return data is
a useful result, and saying so early is worth more than a promoted source that turns out
to return nothing.
