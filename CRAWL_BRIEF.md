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

## The data model is being rewritten — do not design around the current one

Today every stored record is an **observation**: `(measure, value, dimensions)`. That
fits statistics and nothing else. It does not fit a company record, a building
footprint, or a parliamentary decision.

There is already damage from this: the original FHI connector stored *table ids* as
observation values, because observation was the only shape on offer.

The query-side session is designing a wider model — roughly observations, entities and
features over one shared provenance spine (id, source, retrieved_at, request_url,
licence). **Wait for that schema before mass-promoting connectors.** In the meantime,
work on connectors whose data genuinely is statistical, or on mapping endpoints without
storing yet.

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
6. **Tests exist and pass**, using a fake HTTP client, with no network in the test suite.
7. **A live run is verified by eye.** Look at actual returned values before declaring it
   works.

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
- Do not bulk-mine cells. Storage is cheap but the value is not there yet; map endpoints
  and shapes first. Cell mining is a later decision.
- Do not do any work involving `offentligdata.no`.
- Do not print or commit `OPENAI_API_KEY`; `.env` and `.env.*` are gitignored.

## Where to start

Pick a domain with many unpromoted connectors and a real API — company registry
(`brreg*`, 15 files) is the strongest candidate, since Brønnøysund has a documented open
API and org numbers are a join key as clean as the Klass codes are for geography. Map
what each connector can actually reach, and report back what shape the data comes in, so
the model being designed on the query side accommodates it.

Report findings honestly, including negative ones. A connector that cannot return data is
a useful result, and saying so early is worth more than a promoted source that turns out
to return nothing.
