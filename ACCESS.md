# Sources that need a credential, a registration or an email

Written 2026-10-21 from the registry and from live probes, not from memory.
Every claim has a row or a response code behind it, and the few things I could
not verify are marked as such rather than guessed at.

The registry's rule is that a resource is `restricted` when a probe got HTTP
401 or 403: the data is real, the connector is right, and what is missing is
authorisation. That is deliberately distinct from `withdrawn` (gone), `empty`
(answers and holds nothing) and `catalogue` (the service describing itself).

**Priority, if you only do one:** BarentsWatch, because you already have the
access and the endpoint is confirmed live. NVDB second. Datafangst last — it
is a submission API and probably worth nothing to this project.

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

## 2. BarentsWatch — you already have the access, and it is usable

I had this wrong in the previous version of this file, on two counts.

The registry holds **one** BarentsWatch dataset and it is the wrong kind:
`bwgis:bw_ows` → `geo.barentswatch.no/geoserver/bw/ows?…GetCapabilities`,
which answers 200 **without any credential** and is a WMS capabilities
document. This project refuses those (a map service returns imagery, not
numbers) and it correctly has no capability row. So nothing in the registry
uses a BarentsWatch credential today.

But the authenticated API is real and I confirmed it this session. I had
previously tested `www.barentswatch.no/api/v1/…` and got 404 and concluded
nothing. The base path is `/bwapi/`, and with it:

    GET https://www.barentswatch.no/bwapi/v1/geodata/fishhealth/locality/2024/1
    → HTTP 401, WWW-Authenticate: Bearer

A 401 with a Bearer challenge is the endpoint saying *you have the right door,
show a token*. Same for the wave forecast. That is a per-locality weekly time
series of fish health — exactly the shape this registry answers questions
from, and the single best thing on this page.

**The whole flow, verified against the publisher's docs:**

1. Register a client at <https://www.barentswatch.no/minside/> — create a
   user, log in, self-register a client. Choose **API-client** (not
   AIS-client) for fish health; the choice decides your scope. If your
   existing access is an AIS-client you will need a second client for `api`.
2. Exchange it for a token:

       curl -X POST https://id.barentswatch.no/connect/token \
         -H "Content-Type: application/x-www-form-urlencoded" \
         -d "grant_type=client_credentials&client_id=YOUR_ID&client_secret=YOUR_SECRET&scope=api"

   Note the client id looks like `you@example.com:myclient` — it contains `@`
   and `:` and must be URL-encoded if your client does not do it for you.
   Tokens last 3600 seconds, so a connector has to refresh.
3. Call with `Authorization: Bearer <access_token>`.

Docs: <https://developer.barentswatch.no/docs/appreg/> ·
OpenAPI browser: <https://www.barentswatch.no/bwapi/openapi/index.html>
(authorise there with the public `bwopenapi` client to explore without a
secret) · Python examples including `fiskehelse_weeksummary.py`:
<https://github.com/barentswatch/barentswatch-api-examples>
Contact: post@barentswatch.no

**What I need from you:** the client id and secret in `.env` as
`BARENTSWATCH_CLIENT_ID` and `BARENTSWATCH_CLIENT_SECRET`, and whether the
client you already made is an API-client or an AIS-client. Nothing goes into
the registry; it is handled the way the OpenAI key is. Then the connector is a
small job: token cache, one path template, locality rows keyed by locality
number and week.

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
