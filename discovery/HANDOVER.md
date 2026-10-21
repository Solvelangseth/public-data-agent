# Discovery handover — started 2026-10-21

The registry lane reads this file. Keep it current; the JSONL is not committed.

## Doors that return rows

| source | url | how | evidence | worth a connector because |
|---|---|---|---|---|
| havnedata | `ogcapitest.kartverket.no/rest/services/havnedata3_0/collections/{id}/items?f=json&limit=5` | declared:ogc-items | 7 of 9 collections return features, 18 published properties on the first | the source is marked `catalogue` in the registry and is not: the items link was always there |
| elhub | `api.elhub.no/energy-data/v0/price-areas` | seed | JSON:API, 5 price areas (NO1–NO5), no credential | Elhub has **0 datasets** in the registry and permits commercial reuse under CC-BY-4.0 |

## Dead, with the proof

| source | url | verdict | evidence |
|---|---|---|---|
| havnedata | `…/collections/fartsrestriksjoner/items` | unclear | HTTP 500, consistently |

## Needs a credential

(none found yet by this lane; `ACCESS.md` holds the four that are known)

## Open questions for the registry lane

- `havnedata` is proven readable. Does the registry lane want the connector
  now, or after Frost and HydAPI? It is 9 collections, one of them broken.

## Notes

- Five of the six `SEED_CATALOGUES` URLs in `discover.py` are unverified
  guesses and do not resolve: Vannmiljø unreachable, Mattilsynet lakselus 404,
  Kulturminnesøk 404, Artsdatabanken 403, Doffin 403. Only Elhub was right.
  Replacing them from each publisher's developer pages is job one.
