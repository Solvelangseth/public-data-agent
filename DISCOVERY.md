# The discovery lane

A brief for a second session. You own **finding doors that return rows**. The
registry lane owns deciding what to do with them. The two must not write to
the same file, and this document is the seam.

Read this whole file before running anything. It is short on purpose.

---

## The one hard rule

**Never write to `data/registry.sqlite`.** Not a row, not a capability, not a
harvest. In this worktree it is a *symlink to the other session's live 2.1 GB
database*, and `scripts/discover.py` opens it with `mode=ro` so it cannot.
Keep it that way: no `pda ingest`, no `pda fetch`, no `pda verify`, no script
that calls `Registry(...)` without `mode=ro`.

Everything you produce goes in `discovery/*.jsonl`, which is gitignored. The
registry lane reads that file and decides.

If you think you need to write to the registry, you have found a task that
belongs to the other lane. Write it down in the handover instead.

---

## Why this lane exists

The registry lists 17,505 datasets. Most of what it cannot read is not closed:

| | |
|---|---|
| datasets with no licence recorded | 8,416 |
| capability rows that are not readable | 78 (`catalogue` 28, `withdrawn` 32, `empty` 10, `restricted` 8) |
| sources never probed at all | 12 |
| datasets under a Norge digitalt licence, none ever fetched | 6,350 |

A large share of the unreadable ones are a **landing page, a service
descriptor or a capabilities document sitting where an endpoint should be**.
The data is public and reachable and one declared link away. Proven twice this
week: `vegvesen` looked like 23 blocked datasets and is 2 blocked and 21
landing pages; `havnedata` was marked `catalogue` and its collections return
features the moment you follow the `items` link the payload prints.

Your job is to find those links at scale and write down what is behind them.

---

## The tool

    scripts/discover.py

It fetches one URL at a polite rate, classifies what came back, follows the
doors the payload **declares**, and appends a JSON line per finding. It stores
nothing else and decides nothing.

It is pure standard library, so it runs under plain `python3`. **This worktree
has no `.venv` on purpose**: without it `pda` is not importable, so no command
here can write to the registry even by accident. Do not create one. If you
genuinely need a dependency, that is a sign the task belongs to the other
lane — write it in the handover instead.

    # everything the registry cannot read, one dataset per source+verdict
    python3 scripts/discover.py --unreadable --limit 200

    # one source, in depth
    python3 scripts/discover.py --source riksantikvaren --limit 30

    # one url, for a hunch
    python3 scripts/discover.py --url https://api.elhub.no/energy-data/v0

    # the seed list of sources not in the registry at all
    python3 scripts/discover.py --catalogues --probe

Useful flags: `--pause` (seconds between requests, default 1.0 — raise it,
never lower it below 0.5), `--probe` (also try well-known paths nobody linked
to), `--out` (which JSONL to append to; use one per batch).

### Verdicts

| verdict | means |
|---|---|
| `rows` | **the prize.** Members with published fields. |
| `rows-truncated` | JSON larger than the read cap. Still a win; the count was read from the prefix. |
| `catalogue` | the service describing itself — layers, collections, field definitions. Follow it. |
| `openapi` | an API document. Its paths are doors. |
| `empty` | answers correctly, holds nothing. Not a failure, not a win. |
| `restricted` | 401/403. Real data, needs a credential — hand to the registry lane, see `ACCESS.md`. |
| `withdrawn` | 404. |
| `unreachable` / `unclear` | the request failed, or the shape is unrecognised. Read the evidence before believing it. |

### `how`, and why it matters

Every line records how the URL was arrived at:

- `declared:*` — the payload named this link (`ogc-items`, `arcgis-layer`,
  `openapi-path`, `link`). Following it is **reading**.
- `probed:*` — a well-known path nobody linked to. This is a **guess**.

Never present a `probed:` hit as though the publisher documented it. The
distinction is the difference between this project and a scraper.

---

## The job queue, in priority order

Work top down. Append to `discovery/candidates.jsonl` and keep the handover
updated as you go.

1. **`--unreadable` across every source.** ~200 rows at `--pause 1.0` is under
   an hour. This is the broad sweep and it is where the volume is.
2. **The 28 `catalogue` rows**: fiskerigis, arcticsdi, havnedata, gribfiles,
   aviationforecast. `havnedata` is already proven — do the rest.
3. **The 12 never-probed sources**: nvemap (63 datasets), ssbver 39, sodir 39,
   nbcodelist 37, hoydegis 35, mdirwms 30, riksantikvaren 29, ngu 28,
   npitema 27, npiintern 24, nbprov 24, nbdsd 24. Several are WMS by name and
   will be the wrong door; say so rather than forcing a verdict.
4. **The five sources the registry lists but cannot read**, in this order
   because of what each is worth:
   - **Mattilsynet lakselus** — weekly counts and treatments per fish farm
     from autumn 2023. It joins BarentsWatch's `localityNo` directly, which
     makes it worth more than its size. 12 datasets listed, 1 readable.
   - **Elhub** — the only genuinely new one, **0 datasets in the registry**.
     `https://api.elhub.no/energy-data/v0/price-areas` returns 5 price areas
     as JSON:API with no credential. Find the consumption and production
     paths from there. CC-BY-4.0 with commercial reuse permitted, which
     matters: see `ACCESS.md` section 8.
   - **Vannmiljø (Miljødirektoratet)** — 89 datasets across `miljodir`,
     `miljogis`, `mdirgis`, `mdirwms`, **0 readable**. ArcGIS REST, so the
     `declared:arcgis-layer` path should work.
   - **Riksantikvaren** — 30 datasets, never probed.
   - **Artskart** — 4 datasets. `preflight.py` already reported this source
     **withdrawn**; confirm or overturn that, then stop.
5. **Doffin** — tenders. The registry holds only the buyer register
   (100 records). Find whether a public API exists before anyone writes a
   scraper.

### The seed list is mostly guesses

`SEED_CATALOGUES` in `discover.py` holds six URLs. **Only the Elhub one is
verified**; the rest were written from a description and five of six do not
resolve (two 404, two 401/403, one unreachable). Replacing them with real base
URLs found from each publisher's own developer pages is a good first task, and
the result is a code change worth committing.

---

## What you do *not* do

- No writes to the registry. Stated twice on purpose.
- **No connectors.** Finding the door is this lane; walking through it and
  storing rows is the other. A connector written here will conflict.
- **No scraping HTML** where a data service exists. If a table on a page comes
  from a JSON endpoint, find the endpoint. If it genuinely does not, write
  that down and stop — whether to scrape is the user's call, not yours.
- **No rate-limit pushing.** `--pause 1.0` minimum, and if a host returns 429
  or 503, stop asking it today and note it.
- **No inventing.** Not a URL pattern you have not seen answer, not a licence,
  not a join key. A guess goes in the file labelled `probed:` or does not go
  in at all.

---

## Handing back

Keep `discovery/HANDOVER.md` current. It is the only thing the registry lane
is guaranteed to read:

```markdown
# Discovery handover — <date>

## Doors that return rows
| source | url | how | evidence | worth a connector because |
|---|---|---|---|---|

## Dead, with the proof
| source | url | verdict | evidence |

## Needs a credential
(source, url, what the 401 said — then it belongs in ACCESS.md)

## Open questions for the registry lane
```

Commit the handover and any code changes on your own branch. Leave the JSONL
uncommitted — it is gitignored, it is large, and the handover is the summary
that matters.

A finding is worth a row in the handover when it says something a reader could
act on. "`riksantikvaren` is a WMS and returns imagery" is worth a row.
"HTTP 500" is not, unless it is consistent.

---

## The standard this project holds

Taken from `GAPS.md`, and they are not negotiable here either:

- **Verify before claiming.** A count that becomes a claim gets checked first.
  A `%NC%` LIKE pattern once reported 1,643 non-commercial datasets; the real
  number is 51, because SQLite's LIKE is case-insensitive and matched the word
  "li**nc**ence". Check what a pattern actually matched.
- **One sample is one sample.** `preflight.py` samples one dataset per source.
  Reading its verdict as the source's turned "2 of 23 blocked" into "23
  blocked" in a document someone would have acted on.
- **Say when you were wrong, in the commit message.** This repo's history does
  that and it is why the history is useful.

---

## Appendix: the machine is nearly out of disk

As of 2026-10-21 the data volume is at 100% capacity — about 1 GiB free of
228 GiB. Two consequences for this lane:

- `tests/test_brreg_sync.py` has a deliberate guard requiring 1.5 GiB free and
  9 of its 15 tests fail on that guard alone. That is the guard working, not a
  regression. The rest of the suite is green: **2,274 passed, 1 skipped**.
- **Do not download anything.** No bulk files, no snapshots, no caches. This
  lane probes and writes JSON lines; keep it that way. If a candidate can only
  be assessed by downloading it, say so in the handover and stop.

`discovery/*.jsonl` is gitignored but it still occupies disk. A full
`--unreadable` sweep is a few MB, which is fine; delete old batches when done.
