# Sources that need a credential, a registration or an email

Written 2026-10-21 from the registry, not from memory. Every claim here has a
row behind it, and the few things I could not verify are marked as such rather
than guessed at.

The registry's rule is that a resource is `restricted` when a probe got HTTP
401 or 403: the data is real, the connector is right, and what is missing is
authorisation. That is deliberately distinct from `withdrawn` (gone), `empty`
(answers and holds nothing) and `catalogue` (the service describing itself).

---

## 1. NVDB — Statens vegvesen · 8 road object types · blocked today

Eight object types answer HTTP 401. These are the `uoffisiell` load-class
types and the historical one, which NVDB serves but not anonymously.

| dataset | object type |
|---|---|
| `nvdb:871` | Historisk_Bruksklasse |
| `nvdb:890` | Bruksklasse, modulvogntog, uoffisiell |
| `nvdb:892` | Bruksklasse, 12/65 mobilkran m.m., uoffisiell |
| `nvdb:894` | Bruksklasse, 12/100-vegnett, uoffisiell |
| `nvdb:895` | VegROS |
| `nvdb:901` | Bruksklasse, tømmertransport, uoffisiell |
| `nvdb:903` | Bruksklasse, spesialtransport, uoffisiell |
| `nvdb:905` | Bruksklasse, normaltransport, uoffisiell |

All eight are on one host: `nvdbapiles.atlas.vegvesen.no/vegobjekter/{id}`.

**What is needed:** whatever credential Statens vegvesen issues for the
authenticated part of NVDB API LES. I have not confirmed which scheme it uses
or where to apply, so that is the thing to check.

**Where it would go:** the connector reads no credential today. Adding one
means an env var and a header, and the capability rows flip from `restricted`
back to unverified so the next probe can earn a real verification.

---

## 2. BarentsWatch — you said you already have access

The registry holds **one** BarentsWatch dataset and it is the wrong kind.

- `bwgis:bw_ows` → `geo.barentswatch.no/geoserver/bw/ows?SERVICE=WMS&REQUEST=GetCapabilities`
  — answers HTTP 200 **without any credential**, and is a WMS
  GetCapabilities document. This project refuses those: a map service returns
  imagery, not numbers, and `_MAP_SERVICE_MARKS` blocks the fetch. It has no
  capability row, correctly.
- `datanorge:9a7b4816-…` "Offentlige data via BarentsWatch" → points at a
  Geonorge **metadata page**, not an endpoint.

So nothing in the registry currently uses a BarentsWatch credential, and the
one thing that is wired up does not need one.

**If your access is to the authenticated BarentsWatch API** — the fish-health,
AIS or wave data served over HTTPS with a token — then it is worth a
connector, because those are per-locality time series and that is exactly the
shape this registry answers questions from. I could not verify the current
path: `www.barentswatch.no/api/v1/geodata/fishhealth/locality/2024/1` answers
404 unauthenticated, which tells us nothing about the authenticated route.

**What I need from you to build it:** the base URL your access is for, and
whether the token is a static key or an OAuth client-credentials pair. I will
read it from an env var and never write it into the registry, the same way the
OpenAI key is handled.

---

## 3. Geonorge — distributions you request by email

Of 55 sampled datasets behind `kartkatalog.geonorge.no/metadata/uuid/…`, one
came back with `DistributionProtocol: GEONORGE:OFFLINE` — a distribution
obtained by contacting the publisher, not over HTTP.

Extrapolating from 1 in 55 across 7,425 datasets gives an order of magnitude
of roughly a hundred, which is a guess and labelled as one. Enumerating them
exactly means one request per UUID against
`kartkatalog.geonorge.no/api/getdata/{uuid}` — about two hours at a polite
rate, and it would also fill in the licences (see `GAPS.md`, P6.4).

**Not worth chasing before the licences are.** An offline distribution cannot
be fetched by any agent, so each one is a document to request by hand.

---

## 4. Not credential problems, recorded here so they are not mistaken for one

- **10 NVDB types are `empty`** — they answer correctly and hold no objects.
  No credential would change that; they may hold objects next month.
- **28 datasets are `catalogue`** — fiskerigis, arcticsdi, havnedata,
  gribfiles, aviationforecast. The URL is reachable and it is the wrong door:
  the service describes itself. What they need is a connector that asks for a
  layer or a collection's items, not a login.
- **32 are `withdrawn`** — 30 SSB tables and one FHI table the publisher has
  removed, plus one NVDB type. Nothing to register for.
- **12 sources have no capability row at all on any dataset** — nvemap 63,
  ssbver 39, sodir 39, nbcodelist 37, hoydegis 35, mdirwms 30, riksantikvaren
  29, ngu 28, npitema 27, npiintern 24, nbprov 24, nbdsd 24. These have never
  been probed, so whether any of them needs a credential is unknown. Several
  are WMS by their names, which would make them the same wrong-door case as
  the catalogues above.

---

## How to re-check this file

    .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/registry.sqlite'); \
      [print(r) for r in c.execute(\"select dataset_id, endpoint from resource_capability \
      where capability='restricted'\")]"

`scripts/probe_unverified.py --source <name>` re-probes a source and records
`restricted` from a 401 or 403 on its own, so this list keeps itself current
as new sources are probed.
