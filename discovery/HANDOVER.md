# Discovery handover — started 2026-10-21

The registry lane reads this file. Keep it current; the JSONL is not committed.

## Doors that return rows

| source | url | how | evidence | worth a connector because |
|---|---|---|---|---|
| havnedata | `ogcapitest.kartverket.no/rest/services/havnedata3_0/collections/{id}/items?f=json&limit=5` | declared:ogc-items | 7 of 9 collections return features, 18 published properties on the first | the source is marked `catalogue` in the registry and is not: the items link was always there |
| elhub | `api.elhub.no/energy-data/v0/price-areas` | seed | JSON:API, 5 price areas (NO1–NO5), no credential | Elhub has **0 datasets** in the registry and permits commercial reuse under CC-BY-4.0 |
| arcticsdi | `geodata.npolar.no/arcgis/rest/services/ArcticSDI/ArcticSDI_NO_JAN/MapServer/{1..12}/query?where=1=1&outFields=*&returnGeometry=false&f=json` | declared:arcgis-layer | 8 of 8 non-group layers return features with published fields — GeographicalNames 29 (Category, FID, Name), TerrainContours 86 (Elev, FID), GlacierContours 81, Coastline 21, LocalRoads 11, plus Airports, PopulatedPlaces, Sea | also marked `catalogue` in the registry, and 28 layer-definition rows were deleted from it as metadata. The layers themselves were always queryable |

## Dead, with the proof

| source | url | verdict | evidence |
|---|---|---|---|
| havnedata | `…/collections/fartsrestriksjoner/items` | unclear | HTTP 500, consistently |

## Needs a credential

(none found yet by this lane; `ACCESS.md` holds the four that are known)

## Open questions for the registry lane

- `havnedata` and `arcticsdi` are both proven readable and both are recorded
  as `catalogue`. Does the registry lane want those connectors now, or after
  Frost and HydAPI? Between them that is ~20 queryable layers/collections.
- `arcticsdi` matters beyond itself: it is the first proof that the 28
  `catalogue` rows are a routing problem and not a dead end. Worth re-running
  `--unreadable` over the other four catalogue sources before deciding
  anything about them.

## Two things the tool learned the hard way, kept so nobody re-learns them

- **ArcGIS group layers cannot be queried.** They declare it by printing
  `subLayerIds`, so the tool skips them. Layer 0 of a MapServer is usually the
  group.
- **`resultRecordCount` breaks older ArcGIS servers.** Every ArcticSDI layer
  answered `"Pagination is not supported."` until the parameter came off, which
  made a perfectly readable service look entirely broken. The tool no longer
  sends it; size is handled by the read cap and the `rows-truncated` verdict.
- **ArcGIS puts fields under `attributes`, not `properties`.** GeoJSON uses
  `properties`; reading only that reported every ArcticSDI layer as "0
  properties", which reads like an empty service and would have had a reader
  skip eight queryable layers. The classifier now tries both and names the
  first few fields.
- **ArcGIS reports failure in a 200 body.** `{"error": {...}}` is now the
  `service-error` verdict carrying the server's own message, because
  "unclear" hid the reason and the reason was actionable both times.

## Notes

- Five of the six `SEED_CATALOGUES` URLs in `discover.py` are unverified
  guesses and do not resolve: Vannmiljø unreachable, Mattilsynet lakselus 404,
  Kulturminnesøk 404, Artsdatabanken 403, Doffin 403. Only Elhub was right.
  Replacing them from each publisher's developer pages is job one.
