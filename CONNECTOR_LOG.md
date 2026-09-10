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
