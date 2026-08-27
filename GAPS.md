# Known gaps

Living log of gaps we already measured. Each row cites an artifact. This file does not fix them.

Discovery MVP (milestones 1 through 6) is on `main` at merge `51610b1f04b9a658e41d239b3aa76e7910ace460`. Theme stays out of the scorer. Token-overlap weights stay title 10, keyword 5, description 2.

## Upstream harvest

- **Named variables are absent.** Live enrich wrote `fields=0` on every row. No harvested Resource Service payload stored `variables`, `variableList`, or `variable_list`. We do not invent measure lists. Source: `data/enrich_proof.json` `live_enrich.nonempty.fields=0` and `missing.fields=9120`. Also `decisions.tsv` 2026-08-26T21:50:16Z and 2026-08-26T21:57:46Z.

- **Spatial is missing on most rows.** 8243 of 9120 datasets (90.38%) have no stored `spatial`. Source: `data/harvest_stats.json` `missing_fields.missing.spatial`.

- **Publisher is missing on 322 rows (3.53%).** Source: `data/harvest_stats.json` `missing_fields.missing.publisher`.

- **License is missing on 585 rows (6.41%).** Source: `data/harvest_stats.json` `missing_fields.missing.license`.

- **Modified is missing on 7204 rows (78.99%).** This is the dataset `modified` field, not the SPARQL catalog-record timestamp. Source: `data/harvest_stats.json` `missing_fields.missing.modified`.

The harvest file is the 9120-row Data.norge run in `data/harvest_stats.json` (`produced_at` 2026-08-26T21:26:38Z).

- **Harvested payloads print no unused PxWeb table URLs.** `pda scan-table-urls` on 9121 payloads found `new_stored=0`. No `data.ssb.no/api/v0/.../table/<id>` or `statbank/api/v1/.../*.px` string that is not already `access_path`. 07459 is not printed. Source: `data/table_url_scan_proof.json`.

## Search and coverage

- **Indirect Recall@5 stays 0.33.** After AND-decompose, `indirect.recall_at_5` is still 0.333 (9 questions). Theme-only strings live on gold `theme` fields. Theme is not a retrieval field and is not in `FIELD_WEIGHTS`. Source: `data/benchmark_compare.json` `after.by_kind.indirect`. Also `decisions.tsv` 2026-08-26T22:14:10Z.

- **Coverage confidence can be 1.0 while the gold id is missing.** Coverage is "a retrieved row stores this token", not "we found the expected dataset".
  - q036 `Health`. Gold id `datanorge:0d45b3e6-467a-3b5e-bab2-2672002fd13e` (stored theme `Health`). Recall@5 0. Confidence 1.0 because other hits store `health`. Source: `data/coverage_proof.json` examples q036. Gold reason in `data/benchmark_questions.json` q036.
  - q056 `AtB`. Gold id `datanorge:bd93f99e-6844-3b37-b386-eab994595180` (stored `publisher_name` `AtB`). Recall@5 0. Confidence 1.0 because another hit stores `atb`. Source: `data/coverage_proof.json` examples q056. Gold reason in `data/benchmark_questions.json` q056.

- **Theme-only single tokens skip follow-up.** q040 `ECON` and q042 `AGRI` have confidence 0 and empty ranked lists. Follow-up did not run because the missing requirement is the same query. Theme was not added to the scorer. Source: `data/coverage_proof.json` notes, and `data/benchmark_results.json` q040 and q042.

- **Hard single-token publisher miss.** q056 `AtB` is one token. Publisher_name can satisfy a requirement only on the multi-requirement path. A one-token query still uses title, keyword, and description overlap. Source: `data/coverage_proof.json` examples q056. Also `decisions.tsv` 2026-08-26T22:14:10Z and 2026-08-26T22:20:00Z.

## What this file is not

This file does not add theme to the scorer. It does not rewrite ranking. It does not invent gold ids or observation values. Milestone 7 (data retrieval) is a separate change.

## Later source probes

- **Norsk Polarinstitutt OGC Features is still absent.** `https://geodata.npolar.no/ogc/features/v1/collections` was not used. The working printed catalog is `https://api.npolar.no/service/?q=*&format=json` (5 service paths). A GET of `/service` without `q=*` returns `count=51` and zero entries. We do not invent the missing 46. Source: live GET 2026-08-27T14:33:41Z and `data/npolar_source_proof.json` discarded list.

- **Sikt DataverseNO OpenAPI is not the walk.** `https://dataverse.no/openapi` is HTTP 200 YAML for the generic Dataverse 6.6 software API (414 paths, 134 untemplated, mostly `/admin`). The working printed catalog is `https://dataverse.no/api/dataverses/:root/contents` (31 members; 18 titled dataverses). Root datasets print no title. We do not invent aliases or licenses. Source: live GET 2026-08-27T15:00:41Z and `data/sikt_source_proof.json` discarded list.

