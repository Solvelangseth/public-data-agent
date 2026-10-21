# Sources that need a credential, a registration or an email

Written 2026-10-21 from the registry and from live probes, not from memory.
Every claim has a row or a response code behind it, and the few things I could
not verify are marked as such rather than guessed at.

The registry's rule is that a resource is `restricted` when a probe got HTTP
401 or 403: the data is real, the connector is right, and what is missing is
authorisation. That is deliberately distinct from `withdrawn` (gone), `empty`
(answers and holds nothing) and `catalogue` (the service describing itself).

**Nothing on this page is waiting on a registration any more**, except the
NVDB object types in section 1. BarentsWatch is done: both clients work and
the fish-health API is open, so section 2 is now a connector job, not an
access problem. Datafangst never — it is a submission API and has nothing for
a read-only registry.

---

## 1. NVDB — Statens vegvesen · 8 road object types · needs a login

Eight object types answer `HTTP 401 {"title":"Krever innlogging"}`. These are
the `uoffisiell` load-class types and the historical one, which NVDB serves
but not anonymously.

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
Statens vegvesen's own authentication page names exactly this set as its
examples of sensitive types, so the registry's list and theirs agree.

**Two separate things are required, and they are easy to confuse.**

1. `X-Client`, a free-text identifier for the calling application, has been
   mandatory on *every* NVDB API Les V4 request since 5 January 2026. Without
   it you get `HTTP 400 "X-Client må være satt når du kaller API Les V4"`,
   which is not an authorisation failure. It is for logging, needs no
   registration, and the connector in this repo already sends it — a probe I
   wrote by hand did not, which is how I first mis-read this.
2. `Authorization: Bearer <token>`, which is the actual credential, and which
   only these eight types need.

**How to get the token.** Two routes:

- *By hand, for a one-off check:* open <https://nvdbapiles.atlas.vegvesen.no>,
  log in with the button top right (external users go through ID-porten with
  two-factor), then click **Kopier token**. Send it as
  `Authorization: Bearer <token>`.
- *For a service, which is what this project needs:*
  `POST https://nvdbapiles.atlas.vegvesen.no/auth/api/v1/auth/autentiser`
  with a JSON body of `brukernavn`, `passord` and
  `brukertype: "TJENESTEBRUKER"`. The response carries `access_token` and
  `refresh_token`; renew at `/auth/api/v1/auth/refresh`. Statens vegvesen say
  this endpoint will eventually be service-users-only and then replaced by
  Maskinporten, so treat it as the current route, not a permanent one.

**The part I could not find a link for.** Logging in is not the same as being
granted these eight types. The docs say access is granted "gjennom systemet
tilgangskontrolltjenesten til NVDB" and give no form or address. The route to
ask is the NVDB contact form:
<https://www.vegvesen.no/fag/teknologi/nasjonal-vegdatabank/kontakt-nvdb/>
Ask for a *tjenestebruker* with access to the sensitive load-class object
types, and say what you are building.

Docs: <https://nvdb-docs.atlas.vegvesen.no/nvdbapil/v4/Autentisering/>

**Where it would go in the code:** the connector reads no credential today.
Adding one means an env var and a header, and the capability rows flip from
`restricted` back to unverified so the next probe can earn a real verification.

**Worth it?** Eight object types of unofficial load classes. Honest answer:
low value for the registry, and only worth asking for if you want the road
network complete.

---

## 2. BarentsWatch — both credentials work · nothing left to request

**Settled 2026-10-21.** Two clients are registered on one account and both are
live. Re-check either with `scripts/check_barentswatch.py`, which stores
nothing and prints no secret.

| client | scope | in `.env` as | opens |
|---|---|---|---|
| `…:Platform` | `ais` | `BARENTSWATCH_CLIENT_ID` / `_SECRET` | live and historic AIS |
| `…:fiske_helse_klient` | `api` | `BARENTSWATCH_API_CLIENT_ID` / `_SECRET` | everything under `/bwapi/` |

BarentsWatch issues **one scope per client** and the two are not
interchangeable — each pair is refused by the other's scope with
`invalid_scope`. That is why two clients, not one.

### What the `api` scope returns

| endpoint | result |
|---|---|
| `/bwapi/v1/geodata/fishhealth/locality/{year}/{week}` | 1,745 localities in 2024 w1, 1,749 in w20, of which 579 report a lice count |
| `/bwapi/v1/geodata/fishhealth/locality/{localityNo}/{year}/{week}` | one locality's detail: `aquaCultureRegister`, `escapes`, `ilaPdCase`, ILA/PD protection and surveillance zones, export restriction areas |
| `/bwapi/v1/geodata/fishhealth/localities` | 2,712 register rows: `localityNo`, `name`, `municipality`, `municipalityNo`, `aquaCultureRegistryVersion` |
| `/bwapi/v1/geodata/waveforecast/available?modelname=…&fairwayid=…` | `forecasts`, `maxwave`, `modelrundatetime` |

A weekly member looks like this, and it is worth reading closely because it
decides how the connector stores it:

    localityNo 14746   name Aarsand   municipality Bindal   municipalityNo 1811
    lat 65.045867   lon 12.156933   localityWeekId 1682665
    avgAdultFemaleLice None
    hasReportedLice / hasSalmonoids / isFallow / isOnLand / hasIla / hasPd
    hasMechanicalRemoval / hasSubstanceTreatments / hasCleanerfishDeployed

So each row carries one real measure, `avgAdultFemaleLice` — adult female
lice per fish, the number the whole regulatory regime turns on — plus a set
of booleans that are facts about the locality that week, a coordinate, and
`municipalityNo`, which is a **published** join key to every kommune-level
dataset already in the registry. `avgAdultFemaleLice` is null wherever
`hasReportedLice` is false, which is most of them; a fallow site reports
nothing, and that is not a gap to fill.

There is no OpenAPI document under `/bwapi/` at any of the obvious paths
(`openapi/v1/openapi.json`, `swagger/v1/swagger.json`, `openapi/index.json`
all 404), so the endpoint list above was found by probing and is not
exhaustive. The browser at <https://www.barentswatch.no/bwapi/openapi/index.html>
is the publisher's own list.

### The token flow, for both clients

    curl -X POST https://id.barentswatch.no/connect/token \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "grant_type=client_credentials&client_id=YOUR_ID&client_secret=YOUR_SECRET&scope=api"

Client ids look like `you@example.com:clientname` and must be URL-encoded if
the library does not do it. Tokens last 3600 seconds, so a connector caches
and refreshes. Call with `Authorization: Bearer <access_token>`.

### Two traps, both met today

- **The secret is chosen by whoever registers the client, and the field is
  masked.** Not generated, not shown once — a password box. I had this
  backwards for two rounds and said so; the correction is recorded here
  rather than quietly fixed.
- **`invalid_client` and `invalid_scope` are different answers.**
  `invalid_client` means the id and secret are not a recognised pair;
  `invalid_scope` means the pair is real and registered for the other scope;
  an HTTP 401 from an endpoint means a valid token reaching outside its
  scope. The first one took three attempts here because the client *name*
  had been pasted into the secret field, and the server says nothing about
  which half is wrong.

### What the registry holds today, which is the wrong thing

`bwgis:bw_ows` → `geo.barentswatch.no/geoserver/bw/ows?…GetCapabilities`,
which answers 200 **without any credential** and is a WMS capabilities
document. This project refuses those — a map service returns imagery, not
numbers — and it correctly has no capability row. An earlier version of this
file concluded from a 404 on `www.barentswatch.no/api/v1/…` that the
authenticated path could not be verified. The base path is `/bwapi/`, not
`/api/`.

Docs: <https://developer.barentswatch.no/docs/appreg/> ·
live AIS <https://developer.barentswatch.no/docs/AIS/live-ais-api/> ·
historic AIS <https://developer.barentswatch.no/docs/AIS/historic-ais-api/> ·
Python examples <https://github.com/barentswatch/barentswatch-api-examples> ·
post@barentswatch.no

### Build order

Fish health first: weekly rows per locality, one measure, a published join
key, and years of history addressed by `{year}/{week}`. That is the shape the
retrieval stack is tuned for.

AIS second, and it is a different kind of thing — 4,337 live positions and
475 track points over 24 hours, each with `mmsi`, `msgtime` and a coordinate,
addressed by a vessel id the asker has to already know, with 14 days of
history. Worth having, not what this registry is good at answering.

---

## 3. Statens vegvesen `vegvesen` · 2 of 23 restricted, not 23 — correction

The previous version of this file said all 23 datasets in this source sit on
the datafangst API. That was wrong, and it was wrong in a way worth recording:
`scripts/preflight.py` samples **one** dataset per source, and I extrapolated
its verdict across the source. Probing one URL per distinct host gives 13
different hosts and a different picture:

| result | datasets |
|---|---|
| HTTP 401 | `datafangst-api`, `kjoretoyopplysninger-med-eierinformasjon` |
| HTTP 200 but a landing or docs page | datex (6), nvdb-les, nvdbskriv, hcreg (2), ferjepriser, ecoc, dataut |
| HTTP 404 / unresolvable host | `endre-leasingtaker`, `ferjedatabank`, `eierskifte`, `innsending-kjoreseddel` |
| HTTP 200 JSON | `tn-its-eksport-api` |

So the credential story here is only two rows:

- **`vegvesen:datafangst-api`** — "Autorisering feilet. Vennligst inkluder et
  gyldig token." Datafangst 2.0 is the API for *registering* road data, and
  the token is personal and not to be shared. Service page:
  <https://dataut.vegvesen.no/en/dataservice/datafangst-api> · support
  datafangst-support@vegvesen.no. **Do not bother.** A submission API has
  nothing for a read-only registry.
- **`vegvesen:kjoretoyopplysninger-med-eierinformasjon`** — vehicle data
  *with owner information*. That is personal data about named people. Not
  something to request for a public-data registry.

The useful finding in this source is not a credential at all: the 6 DATEX
traffic/weather/travel-time datasets and `tn-its-eksport-api` are open, and
the registry only holds their landing pages. Those are real observations
behind the wrong URL — a connector job, filed under P1.9/P3.6 in `GAPS.md`,
and worth more than every credential on this page except BarentsWatch.

General Statens vegvesen API access guide:
<https://www.vegvesen.no/fag/teknologi/apne-data/slik-far-du-tilgang-til-et-api/>

---

## 4. Geonorge — distributions you request by email

Of 55 sampled datasets behind `kartkatalog.geonorge.no/metadata/uuid/…`, one
came back with `DistributionProtocol: GEONORGE:OFFLINE` — a distribution
obtained by contacting the publisher, not over HTTP.

Extrapolating 1 in 55 across 7,425 datasets gives an order of magnitude of
roughly a hundred, which is a guess and labelled as one. (See section 3 for
what extrapolating from a sample did to me once already.) Enumerating them
exactly means one request per UUID against
`kartkatalog.geonorge.no/api/getdata/{uuid}` — about two hours at a polite
rate, and it would also fill in the licences (`GAPS.md`, P6.4).

**Not worth chasing before the licences are.** An offline distribution cannot
be fetched by any agent, so each one is a document to request by hand.

---

## 5. Not credential problems, recorded here so they are not mistaken for one

- **10 NVDB types are `empty`** — they answer correctly and hold no objects.
  No credential would change that; they may hold objects next month.
- **28 datasets are `catalogue`** — fiskerigis, arcticsdi, havnedata,
  gribfiles, aviationforecast. The URL is reachable and it is the wrong door:
  the service describes itself. What they need is a connector that asks for a
  layer or a collection's items, not a login.
- **32 are `withdrawn`** — 30 SSB tables and one FHI table the publisher has
  removed, plus one NVDB type. Nothing to register for.
- **Landing pages instead of endpoints** — most of the `vegvesen` source, see
  section 3. The same shape as `catalogue`: reachable, wrong door, no login
  involved.
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

`scripts/preflight.py --unprobed` samples one dataset per source and stores
nothing, so it is safe to point at a source nobody has looked at. It reports
`restricted` for a 401 or 403, which is how `vegvesen` was found.

**Read its output as one dataset's verdict, not the source's.** Section 3 is
what happens otherwise. Use `--source X` and widen by host before believing a
count. Run it before `probe_unverified.py`, which fetches and stores for real.
