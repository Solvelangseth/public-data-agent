# Lead book — Norwegian open-data platform

Living file. Owner: Commercial Scout. Reports to Chief of staff, not Sølve.
No email, call, or outbound post from this file. Contacts are only what the org prints.

Product sold: registry of Norwegian public datasets (Data.norge first ingest, sources replaceable), natural-language search, first fetch of actual rows. Later analysis. LLM for intent and explanation. Deterministic retrieval. Provenance (source, publisher, license, access path) on every hit.
Repo: https://github.com/Solvelangseth/public-data-agent

Status 27 Aug 2026, 10:30 Europe/Oslo: 28 sourced leads. Mix: 9 municipalities, 5 energy, 3 health, 3 consultancies, 2 media, 2 property/infra, 2 research, 2 NGOs. Wave-2 (13) added same day: FHI, Helsedirektoratet, Helse Sør-Øst RHF, Statnett, Eviny, Hafslund, Tensio, Lnett, Fredrikstad, Sandnes, Bodø, Kristiansand, Lillestrøm. Contacts only as listed. No invented emails. No outreach.

How to read a lead: why they would pay is tied to a named programme, not "they use data." Service shape is always search → fetch → later analysis. If a field says none published, do not invent one.

Sources below were opened 2026-08-27 from official pages and the named press/programme documents. Brønnøysund pages use Enhetsregisteret lookups at `data.brreg.no/enhetsregisteret/oppslag/enheter/{orgnr}`.

---

## 1. Oslo kommune — DIG + Klimaetaten + Oslostatistikken

**Why they would pay.** Digitaliseringsetaten (DIG) was established 1 January 2026 as the city's combined digital-development and IT agency, with an explicit mandate that includes better use of data across the municipality and "deling av data". Klimaetaten owns follow-up of *Klimastrategi for Oslo 2020–2030* (95 percent emission cut by 2030) and produces the faglig grunnlag for the climate budget. Oslostatistikken / Statistikkbanken is the city's official fact base for planning, debate, evaluation and research. Those three programmes need datasets that do not all live on Oslo's own pages: Miljødirektoratet municipal GHG inventory, SSB, traffic, building, energy, and other agencies. Paying is for finding and fetching those rows with provenance, not for another municipal portal.

**Concrete use case.** A Klimaetaten analyst preparing the climate-budget appendix needs the latest municipal GHG inventory, local traffic/toll counts, and building-energy series. Search in natural language across the national registry; fetch the actual PxWeb / API rows; later analysis compares Oslo's local series with the national inventory (CICERO and others have already documented that the national inventory does not always reflect local measures).

**Search → fetch → later analysis.**
- Search: "klimagassutslipp Oslo kommune veitrafikk annen mobil forbrenning" plus publisher filters (Miljødirektoratet, SSB, Oslo kommune).
- Fetch: first observation rows from Statistikkbanken PxWeb and from national catalogue access paths, with license and publisher on every hit.
- Later analysis: join local traffic/energy series to the national inventory time series; explain residuals; do not invent values.

**Public contact (only published).**
- Digitaliseringsetaten postmottak: postmottak@dig.oslo.kommune.no
- Telephone (city switchboard, printed on DIG and Klimaetaten pages): 21802180 / 21 80 21 80
- Etatsdirektør, printed on the DIG etat page: torstein.harildstad@dig.oslo.kommune.no
- Pressekontakt, printed on the DIG etat page: therese.bergwitz-larsen@dig.oslo.kommune.no
- Oslostatistikken: oslostatistikken@byr.oslo.kommune.no (printed on Statistikkbanken and on oslo.kommune.no/statistikk/kontakt-oss/)
- Klimaetaten postmottak: postmottak@kli.oslo.kommune.no
- Municipality org: 958935420 (OSLO KOMMUNE). DIG prints a separate subunit org 935 346 312; Klimaetaten prints 876 819 902 for invoicing. Use 958935420 for the municipality.

**Key facts.**
- DIG: ~320 staff; merges digital/IT environments from Oslo Origo and UKE; etablert 1. januar 2026; data sharing and information security are stated responsibilities.
- Klimaetaten: created 1 July 2016; under Byrådsavdeling for miljø og samferdsel; climate budget, klimatilpasning, Klima- og energifondet, Næring for Klima, C40 Clean Construction.
- Oslostatistikken: Statistikkbanken is PxWeb (same family as SSB); API guidance is published; contact for demografi, tjenesteproduksjon, bolig, arbeids- og næringsliv is oslostatistikken@byr.oslo.kommune.no.

**Deepen (27 Aug 2026).** DIG Tildelingsbrev 2026 (21.01.2026, ref. 25/5336) assigns a 2026 datadeling task (målbilde/veikart, dataprodukter, frist 01.07.2026) and prints an estimated 45,5 mill. kroner saving on a named PC-ownership klimabudsjett measure (klimaoslo.no: sentralisere eierskap og forvaltning of kommunens PC-er / IKT-utstyr; DIG named with OKF). Do not claim the 817 699 / 75 000 cells as kroner; they lack a unit line.

**Sources opened 2026-08-27.**
- https://www.oslo.kommune.no/etater-foretak-og-ombud/digitaliseringsetaten/
- https://www.oslo.kommune.no/etater-foretak-og-ombud/klimaetaten/
- https://www.oslo.kommune.no/statistikk/
- https://www.oslo.kommune.no/statistikk/kontakt-oss/
- https://statistikkbanken.oslo.kommune.no/
- https://statistikkbanken.oslo.kommune.no/statbank/pxweb/no/db1/
- https://www.oslo.kommune.no/get-file/1396749/7975dfc27e88db851f1c640a0c31cdf4210f344a6ba008df468e9fe0d87d119c
- https://www.klimaoslo.no/klimabudsjett/klimabudsjettet/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/958935420

---

## 2. Bergen kommune — Seksjon for digital transformasjon konsern

**Why they would pay.** Seksjon for digital transformasjon konsern (Byrådsavdeling for finans) holds corporate fagmyndighet for digitalisering: it sets standards and requirements for all byrådsavdelinger and etater. Bergen's digitaliseringsstrategi says the municipality will use digitalisering, automatisering and KI to deliver services in new ways; Ansattservice is the operational data-forvaltning environment. The seksjon's published innspill to the national digitaliseringsstrategi comes from this unit. They would pay to discover and fetch national and other-municipality datasets into that corporate data work — not to replace their own platform build.

**Concrete use case.** The seksjon needs a named dataset from Kartverket, SSB or another agency for a municipal service or KI use-case, cannot find the access path and license in one place, and must fetch a first slice of rows with provenance before Ansattservice or a fagetat builds on it.

**Search → fetch → later analysis.**
- Search: natural-language questions over the national registry (geodata, KOSTRA, health, climate) with publisher and license on each hit.
- Fetch: first rows / API sample from the access path the catalogue records.
- Later analysis: compare Bergen's own series with peer large cities (Oslo, Trondheim, Stavanger) on the same definitions.

**Public contact (only published).**
- Seksjon inbox, printed on the seksjon contact page and on Bergen's national-strategy innspill: Digitalisering.Innovasjon@bergen.kommune.no
- Municipal hovedpostmottak: hovedpostmottak@bergen.kommune.no
- Switchboard: 55 56 55 56 / 55565556
- Org: 964338531
- The seksjon contact page lists named staff with municipal emails. Those are printed there; this book uses the seksjon inbox and hovedpostmottak only. No invented address.

**Key facts.**
- Seksjonssjef printed on the contact page: Kenneth Eidsvåg Oppedal.
- Seksjonen belongs to Byrådsavdeling for finans; Rådhusgaten 10; Postboks 7700, 5020 Bergen.
- Corporate digital authority vs operational dataforvaltning at Ansattservice is described in municipal budget/revision text.

**Sources opened 2026-08-27.**
- https://www.bergen.kommune.no/omkommunen/avdelinger/seksjon-for-digital-transformasjon-konsern
- https://www.bergen.kommune.no/omkommunen/avdelinger/seksjon-for-digital-transformasjon-konsern/kontakt
- https://www.bergen.kommune.no/omkommunen/kontakt-oss/kontakt-bergen-kommune
- https://www.bergen.kommune.no/omkommunen/avdelinger/byradsavdeling-for-finans/om-oss
- https://www.regjeringen.no/globalassets/departementene/kdd/aif/ny-digitaliseringsstrategi-innspill-fra-bergen-kommune.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/964338531

---

## 3. Trondheim kommune — Trondheim Åpne Data + Klimaløftene

**Why they would pay.** *Klimaløftene* (kommunedelplan for energi og klima) was adopted by bystyret in April 2024. The plan supports Paris and the SDGs; four cross-cutting goals include phasing out fossil energy. The city has a 2030 climate-neutrality target: at least 80 percent cut, then compensate the rest. Klimabarometeret is the published monitoring tool (2024 figures: ~29 percent cut since 2009, from ~600 000 to ~430 000 t CO2e). Trondheim Åpne Data exists as a portal, but the climate topic on that portal listed 0 datasets when opened. The gap is finding and fetching energy, transport, building and national inventory rows from *other* publishers so Klimaløftene / Klimabarometer can be evidence-based. They already have a portal; they do not have cross-catalogue search + row fetch.

**Concrete use case.** A Klimaløftene officer needs municipal energy-use and transport-emission series that are not on data.trondheim.kommune.no, plus the Miljødirektoratet municipal inventory used in Klimabarometer, fetched as rows with license and access path.

**Search → fetch → later analysis.**
- Search: "klimagassutslipp Trondheim energibruk transport" across the national registry; do not assume the city portal is complete.
- Fetch: first rows from the publisher's access path (often PxWeb or a national API).
- Later analysis: feed Klimabarometer indicators; compare with Oslo/Bergen/Stavanger on the same national series.

**Public contact (only published).**
- General municipal inbox printed on the Norwegian contact page (updated 29 May 2026): trondheim-kommune.postmottak@trondheim.kommune.no
- Older printed municipal inbox still used on official letterheads: tk.postmottak@trondheim.kommune.no
- Switchboard: 72 54 00 00 (printed; weekday 08.00–15.30)
- No dedicated Åpne Data or Klimaløftene unit inbox published on the pages opened. Do not invent one.
- Org: 942110464

**Key facts.**
- Open-data portal: https://data.trondheim.kommune.no/ (topics include miljø, befolkning; climate topic can be empty while Klimabarometer lives on the kommune site).
- Klimaløftene page asks contacts to mark the subject "Klimaløftene"; it does not print a separate unit inbox on the pages opened.
- Employee names and personal emails were removed from the municipal site to reduce misuse (stated on kontaktinformasjon).

**Sources opened 2026-08-27.**
- https://www.trondheim.kommune.no/kontaktinformasjon/
- https://www.trondheim.kommune.no/english/category/contact/
- https://www.trondheim.kommune.no/tema/klima-miljo-og-naring/miljo/klimaplan-klimaloftene/
- https://www.trondheim.kommune.no/tema/klima-miljo-og-naring/miljo/klimaplan/Klimabarometer/
- https://data.trondheim.kommune.no/
- https://data.trondheim.kommune.no/topics
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/942110464

---

## 4. Stavanger kommune — opencom.no since 2016, strategy through 2029

**Why they would pay.** Stavanger has run opencom.no since 2016 (first regional open-data portal in Norway, printed on the municipal åpne-data page). Digitaliseringsstrategien is the overordnet styringsdokument; it is vedtatt through 31 December 2029. Goal 2 is to strengthen the position as a data-driven organisation; goal 3 says the municipality shall actively tilrettelegge for deling og bruk av offentlige data. They already publish and have a datasjø (Bouvet, from 2019; Fyrlyktprisen 2023). They would pay to *discover and fetch other agencies' and other municipalities' datasets* into that lake and into opencom — the printed 2019 AI-strategy innspill already said a problem is that people who look for Stavanger data do not know where to find it, and the inverse is also true: Stavanger cannot see the rest of the national catalogue as one search-then-fetch path.

**Concrete use case.** The open-data / datasjø team wants a Kartverket or SSB series that matches an opencom dataset (population by delområde, plan layers) so a regional product can be published under NLOD with both sources named.

**Search → fetch → later analysis.**
- Search: national registry for the matching publisher + theme; return license (NLOD vs other) and access path.
- Fetch: first rows or API sample; do not scrape opencom as if it were the product.
- Later analysis: join Stavanger opencom / datasjø tables to national series; keep provenance on every hit.

**Public contact (only published).**
- opendata@stavanger.kommune.no — printed on opencom.no (front page and about) as the address for dataset wishes and contact, and as Vedlikeholdes av on the Regnsensordata dataset.
- Staff-ID sk5028338@stavanger.kommune.no is printed next to opendata@ on that dataset (Forfatter: Espen S. Oftedal). Not a new outreach inbox.
- No separate switchboard printed on the open-data pages opened.
- Org: 964965226

**Key facts.**
- License instruction printed on opencom.no: Norsk lisens for offentlige data (NLOD) + source name Opencom.no.
- Digitaliseringsstrategi vedtatt 06.12.2022, valid to 31.12.2029; five goals including data-driven organisation and sharing of public data.
- Årets publisist 2020 (Digdir); datasjø established 2019 with Bouvet.

**Deepen (27 Aug 2026).** Live first-party dataset https://opencom.no/nb_NO/dataset/regnsensordata «Regnsensordata»: last updated 27 Aug 2026 02:01 CEST (page stamp 27. august 2026, 00:01 UTC+00:00), daily NLOD CSV/ZIP (plus JSON and other listed formats). Daily files dated 2026-08-26 were on the page when opened.

**Sources opened 2026-08-27.**
- https://opencom.no/
- https://opencom.no/about
- https://opencom.no/nb_NO/dataset/regnsensordata
- https://www.stavanger.kommune.no/om-stavanger-kommune/apne-data/
- https://www.stavanger.kommune.no/samfunnsutvikling/planer/strategier/digitaliseringsstrategien/
- https://www.stavanger.kommune.no/nyheter/stavanger-kommune-mottok-pris-for-deling-av-apne-data/
- https://www.bouvet.no/bouvet-deler/stavanger-kommune-vinner-av-fyrlyktprisen-2023
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/964965226

---

## 5. Statsbygg — BIM/SIMBA + multi-portal site data

**Why they would pay.** Statsbygg requires BIM on all projects and publishes SIMBA (machine-checkable BIM requirements; SIMBA 2.1 in force for new projects from 1 July 2022; current pages at simba.statsbygg.no). Site and project work also depends on data that does *not* live in SIMBA: Kartverket, municipal plans, energy, environment, transport, and other agencies' portals. The product is search → fetch of those layers with provenance, then later analysis against BIM/site models — not another BIM manual.

**Concrete use case.** A project or virksomhetsarkitektur team needs flood, energy-label, cadastral or municipal-plan layers for a Statsbygg site, finds them split across GeoNorge, municipal portals and Data.norge, and needs a first fetch of the actual features/rows plus license and publisher before anyone joins them to a SIMBA model.

**Search → fetch → later analysis.**
- Search: natural language over the national registry and recorded access paths (Kartverket, NVE, municipalities, Enova/SSB as published).
- Fetch: first rows / features from the stated access path.
- Later analysis: overlay on the site/BIM context; keep source, publisher, license, access path on every hit.

**Public contact (only published).**
- postmottak@statsbygg.no
- BIM shared inbox, printed on the BIM page and on retired SIMBA pages: bim@statsbygg.no
- Elisabeth Heier, leder for Seksjon for virksomhetsarkitektur, printed on https://www.statsbygg.no/bim: elisabeth.heier@statsbygg.no, tlf. 410 00 707. BIM questions are directed to bim@statsbygg.no.
- Org: 971278374

**Key facts.**
- Current kravsett is SIMBA 2.1 (veiledning 2022-07-01, rettelse 2025-01-08). PDF: https://prod-backend.simapp01.statsbygg.clh.no/documents/kravene/SIMBA2-1_Veiledning_NO_Rettet_2025-01-08_2025-01-08-110119_arje.pdf. IFC4, machine validation, discipline/phase requirement sets; guidance PDF lists www.statsbygg.no/bim and bim@statsbygg.no.
- Old Google Sites SIMBA pages were unpublished 2025-03-05; current entry is simba.statsbygg.no.

**Deepen (27 Aug 2026).** tungt.no 19 Mar 2026 write-up of årsrapport 2025 prints 13,6 mrd investments. Mark that as second-hand because the statsbygg.no article fetch failed.

**Sources opened 2026-08-27.**
- https://www.statsbygg.no/bim
- https://www.statsbygg.no/nyheter/statsbyggs-bim-krav-i-ny-drakt
- https://simba.statsbygg.no
- https://prod-backend.simapp01.statsbygg.clh.no/documents/kravene/SIMBA2-1_Veiledning_NO_Rettet_2025-01-08_2025-01-08-110119_arje.pdf
- https://sites.google.com/view/simba-bim-krav/hjem
- https://www.tungt.no/article/view/1217557/statsbygg_2025_436_millioner_i_resultat_investerte_136_milliarder
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/971278374

---

## 6. Statens vegvesen — Dataportalen / NVDB exist; gap is other agencies' layers

**Why they would pay.** SVV already publishes Dataportalen (dataut.vegvesen.no) and NVDB (API Les, Vegkart, ~400 object types, tens of millions of objects). That is their own stack. The discovery gap is *other agencies' layers* that sit next to the road: municipal plans, NVE flood/slide, Kartverket, SSB transport, coastal and rail datasets. They would pay to search those publishers and fetch first rows with provenance, not to replace NVDB.

**Concrete use case.** An NVDB / Dataportalen product owner needs a municipal or NVE layer that users keep asking for alongside NVDB objects, finds it only after portal-hopping, and needs a licensed fetch path into a later overlay.

**Search → fetch → later analysis.**
- Search: registry query excluding or de-prioritising SVV's own already-known NVDB records; surface other publishers.
- Fetch: first rows from the other agency's access path.
- Later analysis: overlay on Vegkart / NVDB geometry.

**Public contact (only published).**
- firmapost@vegvesen.no — printed as "E-postadresse" on Faktura-, post- og besøksadresser.
- Switchboard printed on https://www.vegvesen.no/en/about-us/contact-us/give-us-a-call/: +47 22 07 30 00. NVDB portal metadata also prints nvdb@vegvesen.no as maintainer on the NVDB dataset page. Do not invent extra inboxes.
- Org: 971032081 (also printed as EHF invoice address).

**Key facts.**
- Dataportalen: datasets and APIs, harvested toward the national catalogue; NVDB Skriv/Les; Trafikk informasjon API.
- NVDB contact forms live at vegvesen.no/fag/teknologi/nasjonal-vegdatabank/kontakt-nvdb/ (themed forms, not a second invented inbox).
- Post: Postboks 1010 Nordre Ål, 2605 Lillehammer.

**Sources opened 2026-08-27.**
- https://dataut.vegvesen.no/
- https://dataut.vegvesen.no/dataset/nasjonal-vegdatabank
- https://www.vegvesen.no/om-oss/kontakt-oss/
- https://www.vegvesen.no/en/about-us/contact-us/give-us-a-call/
- https://www.vegvesen.no/om-oss/kontakt-oss/faktura--post--og-besoksadresser/
- https://www.vegvesen.no/fag/teknologi/nasjonal-vegdatabank/kontakt-nvdb/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/971032081

---

## 7. NIBR / OsloMet — 2026 Sosial klimasårbarhet, 218 beredskapsplaner

**Why they would pay.** NIBR (By- og regionforskningsinstituttet at OsloMet) delivered *Sosial klimasårbarhet* (2026) for Røde Kors. The study includes a document analysis of overordnede beredskapsplaner in 218 municipalities (N=218), a deeper plan sample in 55 municipalities, interviews with DSB, NVE and three statsforvaltere, and cases in Gjerdrum, Nesseby and Nordre Follo. OsloMet news (19 Aug 2026) reports that few municipalities link climate and social vulnerability directly in beredskap, and that no municipality has systematic responsibility for nabolagsberedskap. That programme is paid research that must find, fetch and later analyse municipal plans plus climate, demographic and service datasets. A registry search + row fetch with provenance is the missing middle between "PDF on a kommune site" and NIBR's analysis.

**Concrete use case.** Repeat or extend the 218-plan corpus: search for each municipality's current overordnet beredskapsplan and related ROS / climate-adaptation datasets, fetch the files or tables, later analyse mentions of sårbare grupper vs climate — without inventing contacts at 218 municipalities.

**Search → fetch → later analysis.**
- Search: municipality name + "beredskapsplan" / "ROS" / climate-adaptation datasets in the national registry and recorded access paths.
- Fetch: first document or table rows; record publisher, license, access path.
- Later analysis: the NIBR coding (sårbare grupper, frivillige, climate link); deterministic counts, not model-invented figures.

**Public contact (only published).**
- post-nibr@oslomet.no — printed on the 2026 report title page.
- OsloMet / NIBR telephone printed on oslomet.no/om/nibr and on the report: 67 23 50 00
- OsloMet org: 997058925
- No separate NIBR org printed as a distinct Enhetsregisteret hovedenhet on the pages opened.

**Key facts.**
- Report publisher block: By- og regionforskningsinstituttet NIBR, OsloMet, Postboks 4 St. Olavs plass, 0130 Oslo.
- Related project page: Analyse av klimasårbarheit i Noreg (27.01.2026–31.07.2029, Røde Kors, prosjekt 204293).
- NIBR page currently flags the Sosial klimasårbarhet launch.

**Sources opened 2026-08-27.**
- https://www.oslomet.no/om/nibr
- https://www.oslomet.no/no/forskning/forskningsnyheter/er-du-klar-til-a-redde-naboen-hvis-krisen-rammer
- https://www.oslomet.no/forskning/forskningsprosjekter/analyse-klimasarbarhet-norge
- https://www.rodekors.no/globalassets/_rapporter/klima/2026_nibr_sosial-klimasarbarhet_rapport.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/997058925

---

## 8. CICERO Senter for klimaforskning STI — city GHG inventory practice

**Why they would pay.** CICERO is a research foundation (~100 staff) with a government-origin mandate to develop the knowledge base for climate policy. It has a published practice on *kommunefordelt klimagassregnskap* and local data sources: the 2020 assignment for Oslo Klimaetaten, *Lokale datakilder på klima*, mapped sectors (veitrafikk, annen mobil forbrenning, energiforsyning) and said the national municipal inventory has large improvement potential and does not always reflect local measures. Oslo's Climate Budget 2026 appendix still cites CICERO/Sweco mapping of tax-exempt diesel in Oslo vs the national allocation. CICERO would pay (as oppdrag or as research infrastructure) to search and fetch the candidate local and national series with provenance, then later analyse inventory residuals — that is their existing method, productised.

**Concrete use case.** Update the Oslo (or another city) local-data map: search for traffic, machinery, energy-supply and port datasets; fetch rows; later compare with Miljødirektoratet's municipal inventory.

**Search → fetch → later analysis.**
- Search: sector terms + municipality + publisher (Miljødirektoratet, SSB, SVV, municipality, port).
- Fetch: first rows from each access path; keep license.
- Later analysis: inventory vs local activity data; document method, do not guess tonnes.

**Public contact (only published).**
- post@cicero.oslo.no — printed on cicero.oslo.no/om-oss ("Generelle henvendelser") and on the 2020 notat.
- Press telephone printed on om-oss: +47 40 00 46 70. The 2020 notat also prints 22 00 47 00. Do not invent a third inbox.
- Org: 971274190

**Key facts.**
- Location: Forskningsparken, Oslo; independent stiftelse; IPCC AR6 contributors among staff.
- Om-oss does not print a personal sales inbox.

**Sources opened 2026-08-27.**
- https://cicero.oslo.no/no/om-oss
- https://cicero.oslo.no/no/prosjekter/bistand-til-arbeid-med-lokale-datakilder-pa-klima
- https://www.klimaoslo.no/wp-content/uploads/sites/2/2024/01/CICERO_Lokale-datakilder-pa-klima.pdf
- https://www.klimaoslo.no/wp-content/uploads/sites/2/2026/01/Appendix-to-the-Climate-Budget-2026.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/971274190

---

## 9. Transparency International Norge — OGP procurement commitment

**Why they would pay.** TI Norge is a named partner on Commitment 1 of Norway's OGP action plan 2023–2027 / handlingsplan 5: improve availability and quality of quantitative public-procurement data (Doffin announcements, accounts/supplier information, climate- and environment-friendly procurement, DFØ anskaffelsesundersøkelse). TI's 2025 election recommendations ask for easy access to who buys what, from whom, at what price, for what public purpose, and cite the OGP procurement-openness commitment. They would pay to search and fetch those procurement and accounts datasets as they actually exist (Doffin, DFØ, municipal accounts), then later analyse coverage gaps — not for a new TI portal.

**Concrete use case.** Check whether a municipality or agency's procurement and spend datasets are findable and fetchable with license and access path, against the OGP commitment text.

**Search → fetch → later analysis.**
- Search: "offentlige anskaffelser" / Doffin / spend / klima-anskaffelser by publisher.
- Fetch: first rows or machine files from the recorded access path.
- Later analysis: which commitment data types are actually retrievable; provenance on every hit.

**Public contact (only published on https://www.transparency.no/om-oss/ansatte).**
- Guro Slettemark, generalsekretær: slettemark@transparency.no, +47 908 74 626
- Tor Dølvik, spesialrådgiver: dolvik@transparency.no, +47 913 42894
- Johanne Meisingset Lund, rådgiver: lund@transparency.no, +47 97 96 13 11
- Sara Eline Grønvold, spesialrådgiver: gronvold@transparency.no, +47 938 09 282
- Org: 981958659
- No other inbox invented. Dølvik's page text notes prior OGP-råd membership.

**Key facts.**
- OGP IRM review lists Transparency International Norge next to NFD, DFØ and DFD on Commitment 1.
- TI 5 July 2025 party letter: "Større åpenhet om offentlige anskaffelser" with OGP reference.

**Sources opened 2026-08-27.**
- https://www.transparency.no/om-oss/ansatte
- https://www.transparency.no/publikasjonerverkty/fem-anbefalinger-fra-transparency-international-norge-mot-stortingsvalget-2025-9sfm5
- https://www.regjeringen.no/no/dokumenter/noregs-handlingsplan-5-open-government-partnership-ogp-2024-2027/id3030567/
- https://www.opengovpartnership.org/wp-content/uploads/2024/12/Norway_Action-Plan-Review_2023-2027_NO.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/981958659

---

## 10. WWF Verdens naturfond — Naturkampen 2025 plan + nature layers

**Why they would pay.** WWF and Sabima commissioned Norkart's 2025 *Analyse av planlagt utbyggingsareal i Norge* for Naturkampen 2025: digital municipal areal- and reguleringsplaner from GeoNorge (March–April 2024), 2 559 km² undeveloped area set aside for housing, cabins and næring (hytte 1 182, næring 844, bolig 523), overlap with naturskog, myr, INON, villrein, IBA, floodplains, strandsone. WWF's own page *Naturen vi planlegger å miste* describes the innsynsløsning (web map) with those plan layers plus nature/friluftsliv overlays (second Norkart report 2026 for DNT). Naturkampen 2025 uses 32 indicators / five categories; Norkart supplied 10 indicators on WWF/Sabima assignment. WWF would pay to search and fetch the underlying plan and nature datasets as they are updated, then later refresh overlays — the programme is plan+nature layers, not a generic "they care about nature."

**Concrete use case.** Annual refresh: find current municipal plan datasets and Miljødirektoratet / SSB / NINA layers used in the 32 indicators; fetch; later recompute planned-build overlap.

**Search → fetch → later analysis.**
- Search: municipal plan datasets, nature-type and KOSTRA nature indicators, GeoNorge access paths.
- Fetch: first features/rows; record license (often NLOD) and publisher.
- Later analysis: overlap of plan formål with nature layers; municipality ranking inputs.

**Public contact (only published).**
- post@wwf.no — "Generelle henvendelser" on https://www.wwf.no/om-wwf/kontakt-og-ansatte
- Telephone: 22 03 65 00 (09–15)
- Org: 952330071
- The same page prints giverservice@wwf.no and brigitte.grov@wwf.no for giver / GS+styre (not press). Do not invent a Naturkampen inbox.

**Key facts.**
- Naturkampen is built by Sabima + Kantega; WWF is a published partner and co-commissioner of the plan-area analysis.
- Norkart customer page names "Sabima og Verdens naturfond (WWF)" and Naturkampen 2025.

**Sources opened 2026-08-27.**
- https://www.wwf.no/om-wwf/kontakt-og-ansatte
- https://www.wwf.no/nyheter/naturen-vi-kan-miste-se-hva-som-er-planlagt-nedbygd-i-din-kommune
- https://naturkampen.sabima.no/
- https://www.sabima.no/naturkampen-2025-et-demokrativerktoy-for-naturen/
- https://www.sabima.no/naturkampen-vurderingskriterier-2025/
- https://www.sabima.no/kart-over-planlagt-utbygd-natur-i-norge/
- https://www.norkart.no/tjenester/prosjekt/analyse-av-planlagt-utbyggingsareal-i-norge
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/952330071

---

## 11. Bouvet Norge AS — Kartverket 2026 rammeavtale, Stavanger datasjø, Faktavarehus 2.0

**Why they would pay.** Bouvet is a delivery partner on three published data-platform programmes: (1) Kartverket rammeavtale signed 26 June 2026 with Bekk and Bouvet Norge AS, inntil åtte år, systemutvikling / rådgivning / produktutvikling / transformasjon, against Kartverket's printed 2026 statsbudsjett grant of 477 million kroner over five years for nasjonale fellesløsninger (no Bouvet contract price on that page); (2) Stavanger datasjø (from 2019; Fyrlyktprisen 2023) for analysis, efficiency and open-data sharing; (3) Sokkeldirektoratet Faktavarehus 2.0, a modern data platform for continental-shelf data, Stavanger team + Geodata. Those programmes already collect, structure and share data. Bouvet would pay or resell a search → fetch → later-analysis layer that sits on a national registry (not only the client's lake) so delivery teams can find other agencies' datasets and pull first rows with provenance.

**Concrete use case.** A Kartverket or Stavanger delivery team needs a dataset from another publisher to land in the lake / national infrastructure; search the registry; fetch a sample; later engineer the pipeline.

**Search → fetch → later analysis.**
- Search: client question in natural language over the national registry.
- Fetch: first rows + license + access path into the lake or notebook.
- Later analysis: client-side; this product does not replace Bouvet's engineering.

**Public contact (only published).**
- info@bouvet.no (printed on office pages, e.g. Oslo).
- Named Ledelsen emails printed on https://www.bouvet.no/om-bouvet/ledelsen:
  - per.tronsli@bouvet.no (daglig leder)
  - steffen.garder@bouvet.no
  - lisbeth.viker@bouvet.no
  - jorgen.kaasa@bouvet.no — also printed on the Kartverket 26 June 2026 announcement with tlf. 97 69 28 70
  - anne.hasselgreen@bouvet.no
  - renate.kristiansen@bouvet.no
  - bjarte.gudmundsen@bouvet.no
  - helene.tonnessen@bouvet.no
  - anders.lennartzon@bouvet.no
  - knut.dischington@bouvet.no
  - trude.hole@bouvet.no
  - rune.fagermoen@bouvet.no
  - henriette.hoyer@bouvet.no
  - simen.sommerfeldt@bouvet.no
  - tone.hesterskog@bouvet.no
  - eirik.vefsnmo@bouvet.no
  - owe.nielsen@bouvet.no
  - remi.ovstebo@bouvet.no (Dataforvaltning og analyse)
- Org: 996756246
- Do not invent project-team inboxes.

**Key facts.**
- Kartverket news 26 June 2026: Per Gunnar Tronsli (Bouvet) and Frithjof Ugelstad Frederiksen (Bekk) quoted; Jørgen Kaasa listed as Bouvet region contact on that page.
- Faktavarehus 2.0: Kjetil Molaug, Thao Ha, Bjarte Gudmundsen named in Bouvet/CW coverage.
- Bekk is a close peer on the Kartverket agreement; Bekk is skipped as a *lead* (see skipped notes), not as a fact about Bouvet.

**Deepen (27 Aug 2026).** Kartverket 26 June 2026 announcement of Bekk/Bouvet contracts prints a 2026 statsbudsjett grant of 477 million kroner over five years for nasjonale fellesløsninger. No Bouvet contract price on that page. Practice page still says 200 konsulenter; Oslo job ad 25 Aug 2026 says 50 Oslo / about 250 across Bouvet.

**Sources opened 2026-08-27.**
- https://www.bouvet.no/om-bouvet/ledelsen
- https://www.bouvet.no/om-bouvet/vare-kontorer/oslo
- https://www.bouvet.no/bouvet-deler/stavanger-kommune-vinner-av-fyrlyktprisen-2023
- https://www.bouvet.no/vi-jobber-med/Tjenester/tjeneste-plattform-innsikt-og-analyse
- https://www.bouvet.no/bli-en-av-oss/ledige-stillinger/arkitekter-radgivere-og-utviklere-for-moderne-data-og-analyseplattformer-708
- https://kartverket.no/om-kartverket/nyheter/alle/2026/juni/nasjonalt-loft-gir-ny-it-avtale
- https://www.cw.no/bekk-bouvet-digitalisering/kartverket-velger-bouvet-som-utviklingsleverandor/2455702
- https://www.cw.no/bouvet-datavarehus-it-bransjen/sokkeldirektoratet-velger-bouvet/2462734
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/996756246

---

## 12. Sopra Steria AS — offentlig sektor + digitaliseringsstrategi innspill on sharing public data

**Why they would pay.** Sopra Steria Norge publishes a dedicated offentlig-sektor practice and told the government, in its innspill to the national digitaliseringsstrategi, that "Norge må bli bedre på å dele og gjenbruke offentlige data på tvers av virksomheter" and recommended a shared data platform, once-only, and better reuse. That is a named position, not "they do consulting." They would pay to put search → fetch → later analysis under that recommendation when they staff public-sector programmes: find the datasets across agencies, fetch first rows with provenance, analyse later in the client engagement.

**Concrete use case.** A public-sector delivery (municipality, directorate, helse, transport) needs datasets from other enterprises for a "once only" or felles-dataplattform story; the team uses the registry instead of manual portal-hopping.

**Search → fetch → later analysis.**
- Search: client question over the national registry; publisher + license on each hit.
- Fetch: first rows from the access path.
- Later analysis: client architecture / gevinst; this product stays deterministic on retrieval.

**Public contact (only published).**
- firmapost.no@soprasteria.com — printed on https://www.soprasteria.no/kontakt-oss/oslo with telephone 22 57 56 00 and org 910 909 088.
- No personal emails printed on that contact block. Do not invent any.
- Org: 910909088

**Key facts.**
- Offentlig practice page: https://www.soprasteria.no/dette-kan-vi/bransjer/offentlig
- Innspill PDF: felles dataplattform, once-only, Digitalarkivet / eInnsyn / Altinn as existing building blocks, better cross-enterprise reuse of public data.
- Ledelsen page lists role titles and phone numbers; it does not print personal emails in the opened view. Do not invent them.

**Sources opened 2026-08-27.**
- https://www.soprasteria.no/kontakt-oss/oslo
- https://www.soprasteria.no/dette-kan-vi/bransjer/offentlig
- https://www.regjeringen.no/globalassets/departementene/kdd/aif/innspill-til-ny-nasjonal-digitaliseringsstrategi_-sopra-steria.pdf
- https://www.regjeringen.no/no/tema/statlig-forvaltning/it-politikk/ny-nasjonal-digitaliseringsstrategi/innspill-til-ny-nasjonal-digitaliseringsstrategi/id2982896/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/910909088

---

## 13. Knowit AS — OpenEPI + Kartverket dataplattform

**Why they would pay.** Knowit is the published technology partner for OpenEPI (Open Earth Platform Initiative, Norad): an open, multi-cloud, API-first platform for climate/nature data (feasibility + PoC through 2023–2024; report published 23 June 2025; platform described as active through 2025). Separately, Knowit's Kartverket case describes a common dataplattform (collection, handling, sharing), hybrid GCP/Anthos, pipelines, catalogue and analysis; Knowit says 40+ people on the account across strategy and operations. Those programmes are about making data findable and fetchable. Knowit would pay to attach a Norwegian-registry search → fetch → later-analysis capability to OpenEPI-style or Kartverket-style platforms, or to use it in delivery.

**Concrete use case.** An OpenEPI or Kartverket data-platform team needs a Norwegian public dataset (weather, geodata, environment) resolved to a licensed access path and a first row fetch before it is landed as a product.

**Search → fetch → later analysis.**
- Search: natural language over the Norwegian registry (and recorded access paths).
- Fetch: first rows; provenance required.
- Later analysis: land in OpenEPI / Kartverket platform; do not replace those platforms.

**Public contact (only published).**
- No generic inbox printed on https://www.knowit.no/kontakt/ (page prints 02486 / +47 22 92 66 66 only).
- Oslo office page: Amund Brandsrud, virksomhetsleder Knowit Solutions — amund.brandsrud@knowit.no
- Oslo office page: Sigrid Stana Fasmer, Knowit Solutions Data & Tech AS — sigrid.stana.fasmer@knowit.no
- Org (Knowit AS): 997725646
- Do not invent a generic info@ for Knowit AS.

**Key facts.**
- OpenEPI: Knowit case at knowit.no/kundecaser/open-earth-platform-initiative-openepi/; project site openepi.io.
- Kartverket case: knowit.no/kundecaser/kartverket-digital-transformasjon/
- Knowit Solutions AS org 815 837 932 is printed on the Oslo contact page as a subunit; the lead entity in this book is Knowit AS 997725646.

**Sources opened 2026-08-27.**
- https://www.knowit.no/kontakt/
- https://www.knowit.no/kontakt/oslo/
- https://www.knowit.no/kundecaser/open-earth-platform-initiative-openepi/
- https://www.knowit.no/kundecaser/kartverket-digital-transformasjon/
- https://openepi.io/
- https://openepi.io/about
- https://www.openepi.io/articles/openepi-feasibility-study-and-proof-of-concept-now-published
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/997725646

---

## 14. Norsk rikskringkasting AS — NRKbeta + Samarbeidsdesken

**Why they would pay.** NRKbeta is NRK's technology/method desk (tips, SecureDrop, method writing). Samarbeidsdesken is a named programme (from late 2023) with LLA and SUJO: a small development desk that builds unique datasets and research packages so local papers can do data-driven journalism (Ukrainian refugees, suicide prevention, Mattilsynet restaurant controls, naturskade, etc.). NRK's own mediemangfold page describes research, unique datasets, workshops and a contact for the project. They would pay to search the national registry and fetch first rows with provenance as the start of a research package — later analysis stays editorial.

**Concrete use case.** Samarbeidsdesken starts a package on municipal climate, beredskap or spending: search for the relevant public datasets, fetch rows, later local papers localise the story.

**Search → fetch → later analysis.**
- Search: the package question over the national registry; every hit carries publisher, license, access path.
- Fetch: first rows / machine files.
- Later analysis: editorial (NRK / LLA); this product does not publish the story.

**Public contact (only published).**
- info@nrk.no — NRK Publikumsservice, printed on https://nrkbeta.no/kontakt/ (telephone 23 04 70 00)
- nrkbeta@nrk.no — printed on the same NRKbeta contact page for editorial matters that do not fit a comment field
- pressevakt@nrk.no — printed on https://info.nrk.no/presse/pressekontakter/
- NRK mediemangfold page also prints Christian Lura, prosjektleder Samarbeidsdesken: christian.lura@nrk.no
- Org: 976390512

**Key facts.**
- Samarbeidsdesken: Media City Bergen; LLA coverage at lla.no; desk site samarbeidsdesken.no.
- NRKbeta editor printed: Marius Arnesen, tel. 982 30 516; ansvarlig redaktør Vibeke Fürst Haugen.

**Sources opened 2026-08-27.**
- https://nrkbeta.no/kontakt/
- https://info.nrk.no/presse/pressekontakter/
- https://info.nrk.no/nrks-bidrag-til-mediemangfoldet/
- https://lla.no/nyheter/samarbeidsdesken-godt-i-gang-og-ny-medlemsrekord-i-lla/
- https://lla.no/samarbeidsdesken/stor-interesse-for-samarbeidsdeskens-nyeste-prosjekt/
- https://samarbeidsdesken.no/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/976390512

---

## 15. Aftenposten AS — data desk; tips page asks for data

**Why they would pay.** Journalisten 1 July 2026 (notice 677965) reports Kajsa Garmann Lønrusten (Faktisk.no) and Jonas Blich Bakken (DN) hired as data journalists; leader Eirik Wallem Fossan; Journalisten then writes that the desk is six data journalists, working with two creative leads and an illustrator, on datagraving, analysis, OSINT and KI-supported method. Desk size «seks» is Journalisten only; do not claim aftenposten.no prints six. The tips page asks for tips that can be backed with facts and prints a tips inbox and tipstelefon. GitHub org "Aftenposten - datajournalistikk" prints mm@aftenposten.no and hosts story data repos. They would pay to search Norwegian public datasets and fetch first rows with provenance as the start of a desk story — later analysis is editorial.

**Concrete use case.** Desk story on municipal spending, climate, property or demographics: search the registry, fetch the rows, later analyse and visualise; publish with source/license.

**Search → fetch → later analysis.**
- Search: reporter question over the national registry.
- Fetch: first rows; provenance mandatory for publication.
- Later analysis: Aftenposten data desk; this product does not write the article.

**Public contact (only published).**
- tips@aftenposten.no — printed on https://www.aftenposten.no/tips
- Tipstelefon: 02286 — printed on the same page
- mm@aftenposten.no — printed as the GitHub org email on https://github.com/Aftenposten
- eirik.wallem.fossan@aftenposten.no — in the HTML of https://www.aftenposten.no/av/eirik-wallem-fossan (mailto «Send e-post»). Not invented.
- Org: 890412882
- Do not invent reporter inboxes beyond what those pages print.

**Key facts.**
- Tips page: relevant tips, preferably with facts; debatt@aftenposten.no is for opinions, not this book.
- GitHub public repos include story datasets (e.g. toppbyråkrater, barnehage, covid departures, valg).
- E24 and Kommunal Rapport are weaker than Aftenposten's published data desk (see skipped). Journalisten is the source for «seks»; aftenposten.no does not print that count on the pages opened.

**Deepen (27 Aug 2026).** Author page: «Jeg leder et team med datajournalister og visuelle journalister». Named story: https://www.aftenposten.no/norge/i/oAk8j0/slik-blir-kvikkleiren-livsfarlig-sjekk-skredfaren-der-du-bor.

**Sources opened 2026-08-27.**
- https://www.aftenposten.no/tips
- https://www.aftenposten.no/av/eirik-wallem-fossan
- https://www.aftenposten.no/norge/i/oAk8j0/slik-blir-kvikkleiren-livsfarlig-sjekk-skredfaren-der-du-bor
- https://www.journalisten.no/notice/677965
- https://github.com/Aftenposten
- https://www.kampanje.com/medier/aftenposten-satser-mer-pa-datajournalistikk/1013592
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/890412882

---

## 16. Folkehelseinstituttet (FHI) — Folkehelserapporten + FIDA/KoSy

**Why they would pay.** Folkehelserapporten describes helsetilstanden in Norway from helseregistre, helseundersøkelser, rapporter and forskningspublikasjoner. The *Befolkningen i Norge* chapter prints SSB as the default source unless another is named. FIDA (Folkehelseinstituttets integrerte data- og analysetjenester) is an FHI+KS infrastructure, financed through Digdir's medfinansieringsordning, for mottak, lagring, sammenstilling, analyse and deling of statistikkprodukter. KoSy (Kommunens sykdomsoversikt) is the first published FIDA product (launched September 2025): dagsaktuell statistikk for kommuneoverleger from MSIS, MSIS labdatabase, NorSySS and SYSVAK. Those programmes already own FHI registers. They would pay to find and fetch SSB/KOSTRA and other agencies' municipal series that sit *next to* those registers — befolkning, levekår, kommunehelse — with provenance, not for another FHI portal.

**Concrete use case.** A Folkehelserapporten / FIDA analyst needs the latest SSB befolkning and KOSTRA helse- og omsorg tables for a municipality, fetched as rows with license and access path, before later joining them to FHI register series used in the report or in FIDA products.

**Search → fetch → later analysis.**
- Search: municipality + "befolkning" / "KOSTRA helse omsorg" with publisher filters (SSB, Helsedirektoratet, kommune); do not assume FHI registers cover those tables.
- Fetch: first PxWeb / API rows from the recorded access path; keep license and publisher.
- Later analysis: join to Folkehelserapporten / FIDA series; deterministic residuals, not invented rates.

**Public contact (only published / listed).**
- folkehelseinstituttet@fhi.no — printed as sentralbord e-post on the åpningstider/kontakt page
- Telephone: 21 07 70 00
- Org: 983744516
- Do not invent a Folkehelserapporten or FIDA inbox.

**Key facts.**
- Postboks 222 Skøyen, 0213 Oslo; EHF 0192:983744516.
- Folkehelserapporten is a living nettutgave (temautgave 2026: De viktigste folkehelseutfordringene). Ansvarlig redaktør printed: direktør Guri Rørtveit.
- FIDA user groups printed on Helsedirektoratet's e-helse veikart: kommune and fylkeskommune. KoSy is restricted to kommuneoverleger for the named smitte/vaksine series.

**Sources opened 2026-08-27.**
- https://www.fhi.no/om/fhi/apningstider-ansattoversikt-adresser-til-folkehelseinstituttet/
- https://www.fhi.no/he/fr/folkehelserapporten/om-rapporten/om-folkehelserapporten/
- https://www.fhi.no/he/fr/folkehelserapporten/samfunn/befolkningen/
- https://www.fhi.no/hd/kommunens-sykdomsoversikt--kosy/
- https://www.helsedirektoratet.no/digitalisering-og-e-helse/veikart-for-nasjonal-e-helsestrategi/folkehelseinstituttet
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983744516

---

## 17. Helsedirektoratet — Folkehelseprofiler §24 + SAMDATA

**Why they would pay.** Folkehelseloven §24 assigns Helsedirektoratet to understøtte kommuner and fylkeskommuner by making statistics available for their oversikt over helsetilstand and påvirkningsfaktorer. That grunnlag is published as Folkehelseprofiler, oppvekstprofiler and statistikkbanken Folkehelsestatistikk (data from sentrale registre and other municipal-level sources). SAMDATA kommune hunts IPLOS, KOSTRA and KUHR for kommunal helse- og omsorgsvariasjon; SAMDATA spesialisthelsetjenesten hunts NPR for ressursinnsats and tjenestebruk. The discovery gap is finding and fetching the FHI / SSB / KOSTRA / NPR series as they actually exist across those publishers — not another profile PDF.

**Concrete use case.** A Folkehelseprofil or SAMDATA analyst needs a municipal KOSTRA or NPR series that is not already in this year's profile pack, resolved to a licensed access path and a first row fetch before later indicator work.

**Search → fetch → later analysis.**
- Search: municipality / HF + "KOSTRA" / "NPR" / folkehelseindikator with publisher (SSB, FHI, Helsedirektoratet, NPR).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed Folkehelsestatistikk or SAMDATA indicators; do not invent rates.

**Public contact (only published / listed).**
- postmottak@helsedir.no
- Telephone: 47 47 20 20 (printed (+47) 47 47 20 20)
- Org: 983544622
- Do not invent a Folkehelseprofil or SAMDATA inbox.

**Key facts.**
- Folkehelseprofiler: four-page annual report per kommune, fylke and bydeler in Oslo, Bergen, Stavanger and Trondheim.
- Oppvekstprofiler developed with AVdir, Bufdir, FHI, IMDi, KS, Udir and Helsedirektoratet.
- SAMDATA spesialisthelsetjenesten: no annual report after 2021; statistics pages remain the published path. Direktoratet for e-helse and Helsedirektoratet are slått sammen (printed on kontakt-oss).

**Sources opened 2026-08-27.**
- https://www.helsedirektoratet.no/om-oss/kontakt-oss
- https://www.helsedirektoratet.no/forebygging-diagnose-og-behandling/forebygging-og-levevaner/folkehelsestatistikk-og-profiler/om-folkehelse-og-oppvekstprofilene
- https://www.helsedirektoratet.no/veiledere/oppfolging-av-personer-med-store-og-sammensatte-behov/metoder-og-verktoy-for-systematisk-kvalitetsforbedring-for-helhetlige-og-koordinerte-tjenester/det-ma-benyttes-tilgjengelige-styringsdata-fra-ulike-datakilder-til-kvalitetsforbedring-og-tjenesteutvikling
- https://www.helsedirektoratet.no/rapporter/samdata-spesialisthelsetjenesten
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983544622

---

## 18. Helse Sør-Øst RHF — Klinisk dashboard (NPR / FHI / Kreftregisteret)

**Why they would pay.** Klinisk dashboard was built in HSØ after a 2023 konsernrevisjon found boards and leaders focused more on økonomi/HR than on klinisk kvalitet. HSØ launched it as a styringsverktøy with data from Norsk pasientregister (NPR), Folkehelseinstituttet (FHI) and Kreftregisteret, to identify uønsket variasjon in kvalitet, pasientsikkerhet and ressursbruk against the regional «sørge-for-ansvar». From 1 July 2025 SKDE publishes the interregional version nationally. HSØ still owns 11 helseforetak and still consumes those three publishers plus adjacent public series. They would pay to search and fetch NPR / FHI / Kreftregisteret and neighbouring agency tables with provenance — not to replace SKDE's dashboard.

**Concrete use case.** An HSØ analyst preparing a quality brief for one of the 11 HF needs the latest NPR styringsdata, FHI definitions and Kreftregisteret 5-års overlevelse series, fetched as rows with license and access path before later overlay on the dashboard indicators.

**Search → fetch → later analysis.**
- Search: "NPR styringsdata" / kreft overlevelse / pasientsikkerhet + publisher (FHI, Kreftregisteret, Helsedirektoratet).
- Fetch: first rows from the recorded access path (FHI publishes aggregated NPR files for RHF styring).
- Later analysis: compare HF / sykehusområde against national rates; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- postmottak@helse-sorost.no
- Telephone: 62 58 55 00
- Org: 991324968
- Do not invent a dashboard or SKDE inbox for HSØ.

**Key facts.**
- Hovedkontor Parkgata 36, Hamar; Postboks 404, 2303 Hamar; open 08.00–16.00.
- Named on the 10 July 2025 news page: prosjektdirektør Ole Tjomsland and senioranalytiker Christian Thoresen developed and forvaltet the dashboard content.
- SKDE page: dashboard uses NPR-SOM / NPR-AvtaleSOM; 5-års relativ overlevelse from Kreftregisteret; NPR definitions from FHI.

**Sources opened 2026-08-27.**
- https://www.helse-sorost.no/om-oss/kontakt-oss
- https://www.helse-sorost.no/nyheter/styringsverktoy-for-kvalitet-er-tilgjengelig-nasjonalt/
- https://www.skde.no/vare-oppdrag/interregionalt-klinisk-dashbord/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/991324968

---

## 19. Statnett SF — SUP 2025 + 10 områdeplaner + Omstillingsplan 2026

**Why they would pay.** Systemutviklingsplan 2025 (published 3 Nov 2025) is Statnett's overordnet plan for transmisjonsnett, markedsløsninger and systemdrift (150–200 mrd kroner over the next ten years in nett and digitalisering). Ten geografiske områdeplaner, updated in dialog with regionale nettselskap, are a printed building block of SUP. Omstillingsplan 2026 (published February 2026) is the sustainability plan toward 2050 (klima, natur, mennesker, styring). Those programmes need forbruksprognoser, industri, produksjon, fornyelse and nature/climate layers that do *not* all live on statnett.no: NVE, SSB, municipalities, Miljødirektoratet. They would pay to search and fetch those rows with provenance, then later analyse against SUP / områdeplan assumptions — not another Statnett portal.

**Concrete use case.** An områdeplan team needs municipal plan, SSB nærings/befolkning and NVE/Miljødirektoratet nature layers for one of the ten areas, fetched as rows/features with license before later overlay on the målnett.

**Search → fetch → later analysis.**
- Search: area name + "arealplan" / "forbruk" / "naturtype" with publisher (NVE, SSB, kommune, Miljødirektoratet).
- Fetch: first rows / features from the recorded access path.
- Later analysis: feed områdeplan behov and Omstillingsplan nature/climate follow-up; keep provenance.

**Public contact (only published / listed).**
- firmapost@statnett.no — printed on the Oslo hovedkontor block
- Telephone: 23 90 30 00
- Org: 962986633
- Do not invent a SUP or områdeplan inbox.

**Key facts.**
- Hovedkontor: Nydalen allé 33, 0484 Oslo; PB 4904 Nydalen, 0423 Oslo.
- SUP 2025 is the second edition (after 2023); områdeplaner established 2022, normally updated every other year.
- Omstillingsplan 2026: implementering into processes and finansiell planlegging in 2026.

**Sources opened 2026-08-27.**
- https://www.statnett.no/om-statnett/kontakt-oss/
- https://www.statnett.no/om-statnett/nyheter-og-pressemeldinger/nyhetsarkiv-2025/systemutviklingsplan-2025/
- https://www.statnett.no/planer-for-stromnettet/omradeplaner/
- https://www.statnett.no/om-statnett/barekraft/omstillingsplan/
- https://www.statnett.no/globalassets/om-statnett/barekraft/statnetts-omstillingsplan.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/962986633

---

## 20. Eviny AS — 100-på-10 / PIA / dataflyt

**Why they would pay.** Konsernstrategi *100 på 10* (defined 2024) says Eviny will invest over the next ten years what it built over the previous hundred: 2,5 TWh ny fornybar energi, 30 percent more effekt, double regional nettkapasitet. The published dataflyt/dataanalyse page says good decisions need sanntidsdata on kraftmarkedet, kraftpriser, sensordata and værprognoser; Digital sjef Trond Stokken is printed there. PIA (Plattform for Innsikt og Analyse) is named on Bouvet's Eviny case as the lake where sources are landed, kvalitetssikret and analysed (Microsoft building blocks; Eviny/Bouvet delivery). They already have a platform. They would pay to discover and fetch *other* public series (NVE, MET, SSB, Statnett) into that stack with provenance — not to replace PIA.

**Concrete use case.** The dataflyt team needs a public vær / hydrologi / prisområde series that is not already in PIA, resolved to a licensed access path and a first row fetch before later landing it in Kafka / Delta Lake.

**Search → fetch → later analysis.**
- Search: "værprognose" / "magasin" / "kraftpris område" with publisher (MET, NVE, Statnett, SSB).
- Fetch: first rows / API sample; license and access path on every hit.
- Later analysis: land in PIA; this product does not replace Eviny's engineering.

**Public contact (only published / listed).**
- trond.stokken@eviny.no — printed on the dataflyt page as Digital sjef, Eviny Fornybar
- hei@eviny.no — printed on https://www.eviny.no/kundeservice as "Skriv til oss"
- Org: 880309102
- Do not invent a PIA or dataflyt team inbox.

**Key facts.**
- Eviny AS is morselskap; hovedkontor Bergen; eies of Statkraft, 17 Vestland kommuner, Tysnes Kraftlag AS and Etne Elektrisitetslag AS (printed on the 100-på-10 news page / årsrapport).
- Dataflyt stack printed: Kafka (Redpanda), Delta Lake, Postgres, Materialize, Nix/NixOS, Python.
- PIA name is Bouvet's published case name, not printed on the Eviny dataflyt page itself.

**Sources opened 2026-08-27.**
- https://www.eviny.no/jobb-med-oss/dataflyt-og-dataanalyse
- https://www.eviny.no/kundeservice
- https://www.eviny.no/nyheter/et-av-de-mest-verdiskapende-selskapene-i-norge
- https://www.bouvet.no/prosjekter/pa-vei-til-a-bli-datadrevet
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/880309102

---

## 21. Hafslund AS — Naturkompasset with NVE / Miljødirektoratet

**Why they would pay.** Hafslund prints that it helped develop *Naturkompasset*, the Fornybar Norge project-based naturregnskap method, with Miljødirektoratet and NVE in the external referansegruppe (Asplan Viak, Multiconsult, Rambøll as consultants). Ambition: naturregnskap in all new utbygginger. In 2026 the method goes into Låvi (effekt vann), Hol 1 (vann) and Trysil (vind); pilots already run at Aremark Sør and Hemsil 3. The method needs GIS layers and nature-type data that live at NVE, Miljødirektoratet, Kartverket and municipalities. They would pay to search and fetch those layers with provenance, then later score naturpoeng — not another Hafslund GIS.

**Concrete use case.** A project team for Låvi / Hol 1 / Trysil needs current Miljødirektoratet nature-type and NVE flood/vassdrag layers for the site, fetched as features with license before later Naturkompasset baseline.

**Search → fetch → later analysis.**
- Search: project area + naturtype / myr / vassdrag / INON with publisher (Miljødirektoratet, NVE, Kartverket, kommune).
- Fetch: first features/rows; record license (often NLOD) and publisher.
- Later analysis: Naturkompasset baseline vs inngrep; do not invent naturpoeng.

**Public contact (only published / listed).**
- post@hafslund.no — printed as sentralbord / generelle henvendelser
- Telephone: 24 11 65 00
- Org: 920596509
- Do not invent a Naturkompasset inbox.

**Key facts.**
- Hafslund has used naturregnskap since 2022 (UK Biodiversity Metric on two wind parks) before Naturkompasset.
- Fornybar Norge PDF lists Statkraft, Statnett, Hafslund, Hydro Energi, Equinor in the prosjektgruppe; ekstern referansegruppe is Miljødirektoratet and NVE.
- Hafslund page published 29 June 2026.

**Sources opened 2026-08-27.**
- https://www.hafslund.no/no/hjelp-og-kontakt
- https://www.hafslund.no/no/om-oss/baerekraft-i-hafslund/naturtiltak/naturregnskap-i-praksis
- https://www.fornybarnorge.no/nyheter/2026/lanserer-naturkompass/
- https://www.fornybarnorge.no/contentassets/35d377cfb07c4e37b381bf158ad2573e/260330-naturkompasset.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/920596509

---

## 22. Tensio AS — områdestudier replace KSU

**Why they would pay.** Tensio's 28 Feb 2025 (updated 22 Apr 2025) innspillsmøte page states that områdestudier for energiutviklingen in Trøndelag *skal erstatte* the former regionale kraftsystemutredninger (KSU). Meetings present nåsituasjon and the new konsept; local/regional actors are asked for utviklingstrekk. Drivers printed: elektrifisering of industri and transport, grønn næringsutvikling, mer ikke-regulerbar kraft, befolkningsvekst, new forbruksmønstre; lange ledetider and kø in transmisjonsnettet mean traditional nettutbygging is not enough. Energikoordinering is named as a new tool. Those studies need municipal plans, SSB forbruk/næring, NVE and Statnett områdeplan Midt series that do not live on tensio.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace Tensio's own nett model.

**Concrete use case.** The områdestudie project needs current municipal arealplaner and SSB/NVE series for one of the five meeting regions (Namsos, Orkanger, Fosen, Stjørdal/Innherred, Stor-Trondheim), fetched with license before later prognose work.

**Search → fetch → later analysis.**
- Search: region + "arealplan" / "industri" / "effekt" with publisher (kommune, SSB, NVE, Statnett).
- Fetch: first rows / features from the recorded access path.
- Later analysis: områdestudie behovsanalyse; keep provenance.

**Public contact (only published / listed).**
- kristin.fagerli@tensio.no — printed as prosjektleder for områdemøtene
- Org: 922828172
- No generic inbox listed on the innspillsmøte page. Do not invent one.

**Key facts.**
- Five open regional meetings around Easter 2025 (31 Mar–10 Apr).
- Energikoordinator is also a 2024–2026 pilot with Lnett and Elvia (printed on Lnett utredninger); NVE, RME and Statnett sit in that referansegruppe.

**Sources opened 2026-08-27.**
- https://www.tensio.no/no/proff/nyheter-proff/innspillsmote-energiutvikling-omradestudier
- https://www.l-nett.no/utredninger/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/922828172

---

## 23. Lnett AS (Lyse) — NVE nettutviklingskoordinator + Energikoordinator

**Why they would pay.** Lnett is NVE's nettutviklingskoordinator for Sør-Rogaland: it coordinates nettutredninger across eiere, gives innspill to other utredere, and can utrede/melde tiltak on others' behalf. As nettutreder it produces effektprognoser (≥20 years, not older than two years), områdestudier (behovsanalyse, 20 years, updated at least every other year) and KVU (40-year samfunnsøkonomi). Energikoordinator is a 2024–2026 pilot with Tensio and Elvia; referansegruppe is NVE, RME and Statnett. Those roles consume municipal plans, næringsutvikling, Statnett SUP/områdeplaner and NVE PlanNett — datasets that do not all live on l-nett.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace PlanNett.

**Concrete use case.** An utredning officer needs a municipal plan or Statnett områdeplan Sør-Rogaland og Agder layer that is not in Lnett's own effektprognose, fetched as rows/features with license before later KVU.

**Search → fetch → later analysis.**
- Search: "Sør-Rogaland" / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows from the recorded access path.
- Later analysis: effektprognose / områdestudie / KVU; keep provenance.

**Public contact (only published / listed).**
- epost@l-nett.no — printed on https://www.l-nett.no/elinstallatorer/vare-tjenester/ (byggestrøm / fjerning)
- Org: 980038408
- The utredninger page does not print a separate utredning inbox. Do not invent one.

**Key facts.**
- PlanNett is NVE's portal for områdestudier and KVU summaries.
- Lnett points to Statnett SUP and områdeplaner as the transmisjonsnett path.
- Postboks 8124, 4068 Stavanger; org printed on åpningstid-og-adresser.

**Sources opened 2026-08-27.**
- https://www.l-nett.no/utredninger/
- https://www.l-nett.no/elinstallatorer/vare-tjenester/
- https://www.l-nett.no/apningstid-og-adresser/
- https://www.statnett.no/om-statnett/nyheter-og-pressemeldinger/nyhetsarkiv-2025/systemutviklingsplan-2025/
- https://www.statnett.no/planer-for-stromnettet/omradeplaner/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/980038408

---

## 24. Fredrikstad kommune — Åpne data Hub + kart@

**Why they would pay.** Fredrikstad runs an ArcGIS Hub for åpne data (API download/connect). The Hub front page says the datasets there are the municipality's own, and that *other* datasets are available via data.norge.no or Geonorge.no. The kartdata page says Fredrikstad is in Norge Digitalt, that most digital kartdata are on Geonorge, and that the Hub/API is the path for users without Geonorge access (NLOD; Euref89 UTM 32N / NN2000). They already publish. They would pay to search and fetch the *other* publishers' layers named on their own Hub — Kartverket, NVE, SSB, neighbouring municipalities — with provenance, then later join to Hub layers.

**Concrete use case.** Virksomhet geomatikk wants a national flood, plan or SSB series that matches a Hub dataset (eiendom, planer, beredskap), fetched under a named license so a combined product can cite both sources.

**Search → fetch → later analysis.**
- Search: national registry / Geonorge access paths for the matching theme; return license and publisher.
- Fetch: first rows / features; do not scrape the Hub as if it were this product.
- Later analysis: join Hub tables to national series; provenance on every hit.

**Public contact (only published / listed).**
- kart@fredrikstad.kommune.no — printed on the digitale-kartdata page and as Hub contactUs mailto
- Org: 940039541
- Do not invent a Hub editor inbox.

**Key facts.**
- Hub categories printed: miljø, kretser, næring, beredskap, utdanning, helse og omsorg, eiendom, samferdsel, park/kultur/idrett/friluftsliv, IOT, planer.
- Kommunevåpen footer on the Hub also prints org 940039541 and kommunenummer 0106.
- Plandata (KPA 2023–2035 and gjeldende regulering) have a free SOSI self-service path; FKB is Geovekst / paid for non-parties.

**Sources opened 2026-08-27.**
- https://hub-frstadkomm.opendata.arcgis.com/
- https://www.fredrikstad.kommune.no/tjenester/byggesak-regulering-og-kart/kart-og-oppmaaling/tilgang-til-digitale-kartdata/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/940039541

---

## 25. Sandnes kommune — Prinsipp 6 «Vi deler og tar i bruk åpne data»

**Why they would pay.** *Sandnes – helt enkelt* (digitalisering, smartby and innovasjon) takes the national smartby veikart's eight principles. Prinsipp 6 is printed as «Vi deler og tar i bruk åpne data»: åpne data are a råvare for innovasjon and effektivisering; the municipality will tilgjengeliggjøre and *use* data for effektivisering, kvalitetsforbedring, innovasjon and næringsutvikling, while protecting personvern and giving innbyggere grunnlag for beslutninger. Geodata is the printed unit for matrikkel/kart (postmottak.geodata@). They would pay to find and fetch *other* agencies' and municipalities' open datasets into that "ta i bruk" side — not to replace the matrikkel.

**Concrete use case.** Geodata / innovasjon needs a Kartverket or SSB series that matches a local plan or eiendom layer, fetched with license and access path before later use in a tjeneste or åpne-data product.

**Search → fetch → later analysis.**
- Search: national registry for the matching publisher + theme; return NLOD vs other license.
- Fetch: first rows / API sample.
- Later analysis: join to municipal geodata; keep provenance.

**Public contact (only published / listed).**
- postmottak.geodata@sandnes.kommune.no — printed on the Eiendomsregisteret / Geodata block
- Org: 964965137
- Do not invent an innovasjon or åpne-data inbox.

**Key facts.**
- Strategy published 16.10.2019, last changed 07.02.2023; Enhet for innovasjon og digitalisering is named as pådriver; Innovasjon- og digitaliseringsfondet can finance tiltak.
- Geodata: Postboks 583, 4302 Sandnes; Rådhusgata 1; telephone 959 89 568 printed on the matrikkel page (not used as a second outreach number here).
- Prinsipp 2 also prints further collaboration on nasjonal and lokal bruk og deling av data.

**Sources opened 2026-08-27.**
- https://www.sandnes.kommune.no/sti/planer-strategier-og-analyser/vedtatte-strategier/sandnes-helt-enkelt/
- https://www.sandnes.kommune.no/sti/bolig-og-byutvikling/kart-og-eiendomsinformasjon/eiendomsopplysninger/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/964965137

---

## 26. Bodø kommune — Bodøkart + Geonorge

**Why they would pay.** Bodø forvalter and updates many kart types; Bodøkart is the published digital-kart inngang (ansatte get utvida tilgang). Bodø kommune is also a Geonorge organisation: plan and byutvikling datasets sit in Kartkatalogen next to national layers. The gap is finding and fetching Kartverket / NVE / SSB / neighbouring-municipality series that sit beside Bodøkart, with license and access path — they already have a kartklient.

**Concrete use case.** A Byutvikling / kart officer needs a national flood, plan or SSB series that matches a Bodøkart layer, fetched as features/rows before later overlay.

**Search → fetch → later analysis.**
- Search: "Bodø" + theme across the national registry and Geonorge access paths; do not assume Bodøkart is complete.
- Fetch: first features/rows; record publisher and license.
- Later analysis: overlay on Bodøkart; provenance on every hit.

**Public contact (only published / listed).**
- Sveinung.Bertnes.Raheim@bodo.kommune.no — printed on the Bodøkart page as Rådgiver, Byutvikling Prosjekt og Mobilitet
- Org: 972418013
- No generic kart inbox printed on that page. Do not invent one.

**Key facts.**
- Bodøkart page contact block also prints telephone 75 55 52 88 and mobil 91 86 81 86 (not listed as extra inboxes).
- Geonorge Kartkatalogen filter: organizations=Bodø kommune.
- Sibling pages: bestille digitale kart og eiendomsinformasjon; Eiendomsregisteret via Kartverket.

**Sources opened 2026-08-27.**
- https://bodo.kommune.no/tjenester/plan-bygg-og-eiendom/kart-og-eiendomsinformasjon/bodokart/
- https://bodo.kommune.no/tjenester/plan-bygg-og-eiendom/kart-og-eiendomsinformasjon/
- https://kartkatalog.geonorge.no/?organizations=Bod%C3%B8+kommune
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/972418013

---

## 27. Kristiansand kommune — Smartere sammen 2022–2030 + samfunnsdel public-data sentence

**Why they would pay.** *Smartere sammen* (digitaliseringsstrategi 2022–2030) is the organisational digital-transformasjon strategy under kommuneplanens samfunnsdel. The 2020 samfunnsdel prints: «Kommunens offentlige data skal gjøres mer tilgjengelige for forskning og utvikling av nye tjenester.» The strategy's målbilde repeats that kommunens offentlige data skal være tilgjengelig for forskning and danne grunnlag for nye tjenester; tiltak include «Legger bedre til rette for deling av åpne data» and «Benytter data fra ulike aktuelle og relevante kilder» for beslutningsstøtte, innsikt, analyse and tjenesteutvikling. They would pay to search those *various sources* (other municipalities, SSB, Kartverket, helse, energy) and fetch first rows with provenance — the printed gap is that municipal data are "ikke nødvendigvis tilgjengelig eller tilrettelagt for bruk av de som trenger dem."

**Concrete use case.** Digitalisering / a fagenhet needs a national or peer-city dataset for a Smartere-sammen tjeneste or forskningsutlevering, finds it only after portal-hopping, and needs a licensed first fetch before later analyse.

**Search → fetch → later analysis.**
- Search: the tjeneste question over the national registry; publisher + license on each hit.
- Fetch: first rows from the access path.
- Later analysis: municipal beslutningsstøtte or åpne-data product; this product stays deterministic on retrieval.

**Public contact (only published / listed).**
- post@kristiansand.kommune.no — printed on kontakt-oss (vanlig e-post when not personsensitive)
- Org: 820852982
- The contact page says employee emails are not on the site for personvern/IT-sikkerhet. Do not invent a digitalisering inbox.

**Key facts.**
- Strategy PDF: Digitaliseringsstrategi for Kristiansand kommune 2022–2030 Smartere sammen, listed under Forskning, innovasjon og digitalisering on the plans page. Samfunnsdel adjusted and vedtatt 26 March 2025.
- Contact page updated 03.08.2026; Postboks 4, 4685 Nodeland; kommunenummer 4204.
- Sikker post is eDialog; post@ is the printed ordinary-email path.

**Sources opened 2026-08-27.**
- https://www.kristiansand.kommune.no/kontakt-oss
- https://www.kristiansand.kommune.no/navigasjon/politikk-og-organisasjon/planer-og-strategier/planer-og-strategier/
- https://www.kristiansand.kommune.no/contentassets/6ba5acec23c0445aa1fe1ad1906fc280/digitaliseringsstrategi-20223.pdf
- https://www.kristiansand.kommune.no/globalassets/felles/politikk-og-organisasjon/planer-rapporter-og-meldinger/planer/sterkere-sammen--kristiansand-mot-2030-kommuneplanens-samfunnsdel-2020-2030-vedtatt-i-bystyret-23.09.2020-.pdf
- https://www.kristiansand.kommune.no/navigasjon/politikk-og-organisasjon/samfunnsutvikling/sterkere-sammen---kristiansand-mot-2030/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/820852982

---

## 28. Lillestrøm kommune — digitalisering 2020–2025 + klimabudsjett

**Why they would pay.** *Strategi for digitalisering 2020–2025* prints «Data skal deles, gjenbrukes og forvaltes» as a platform requirement, and under Informasjonsforvaltning: «En datadrevet offentlig forvaltning, med åpne og tilgjengelige data». Digitaliseringsavdelingen understøtter digitaliseringsinitiativ and owns architecture/forvaltning. *Plan for klimanøytral drift* (klimanøytral 2027) prints the årlige klimabudsjett as «det viktigste styringsverktøyet» for that plan. No first-party open-data portal is printed; municipal datasets sit on data.norge / Geonorge. They would pay to find and fetch SSB, Miljødirektoratet, NVE and neighbour Nedre Romerike series with provenance — not another municipal portal.

**Concrete use case.** Digitaliseringsavdelingen finds and fetches SSB / Miljødirektoratet / NVE and neighbour Nedre Romerike (Rælingen, Lørenskog, Nittedal, Aurskog-Høland) series for the next klimabudsjett and the Klimasats klimaplanlegger / dialogverktøy (Apr 2026–Nov 2027; 410 000 kroner; with Akershus fylkeskommune).

**Search → fetch → later analysis.**
- Search: Lillestrøm / Nedre Romerike + klimagass / areal / energi with publisher (SSB, Miljødirektoratet, NVE, neighbour kommuner).
- Fetch: first rows / features from data.norge or Geonorge access paths; license and publisher on every hit.
- Later analysis: feed klimabudsjett indicators and the klimaplanlegger; do not invent tonnes.

**Public contact (only published / listed).**
- Torbjørn Pedersen, Direktør for digitalisering: torbjorn.pedersen@lillestrom.kommune.no, 93 46 18 00 — printed on the digitalisering strategy page
- postmottak@lillestrom.kommune.no — printed on kontakt-oss
- Sentralbord: 66 93 80 00
- Org: 820710592
- Kommunenummer: 3205
- Do not invent a klima or åpne-data inbox.

**Key facts.**
- Postboks 313, 2001 Lillestrøm; Jonas Lies gate 18, 2000 Lillestrøm.
- Klimanøytral drift target 2027 (interpellasjon 17.12.19; klimastrategi 16.06.21). Klimabudsjett is the annual handlingsplan for that plan.
- Klimasats project printed on miljodirektoratet.no: under gjennomføring, Apr 2026–Nov 2027; tilpasset ny energiutredning for Nedre Romerike.

**Sources opened 2026-08-27.**
- https://www.lillestrom.kommune.no/politikk-og-administrasjon/digitalisering-i-lillestrom-kommune/digi/
- https://www.lillestrom.kommune.no/politikk-og-administrasjon/kontakt-oss/
- https://www.lillestrom.kommune.no/energi-klima-og-miljo/klimanoytral-drift/
- https://www.miljodirektoratet.no/ansvarsomrader/klima/for-myndigheter/kutte-utslipp-av-klimagasser/klimasats/2026/klimaplanleggerdialogverktoy-for-nedre-romerike/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/820710592

---

## Skipped, with reasons

Keep these notes in the living book. They are not leads.

- **KS** — shared-platform builder, not a discovery buyer.
- **Bane NOR / Nye Veier / Entra** — weaker published discovery mandate than Statens vegvesen.
- **SSB** — source / competitor, not a customer.
- **Bellona** — building a data product.
- **PwC / Itera** — weaker published data-platform programmes than Knowit.
- **Bekk** — close peer to Bouvet / Knowit (including the 2026 Kartverket rammeavtale); not a separate lead.
- **E24 / Kommunal Rapport** — weaker than Aftenposten's published data desk (Journalisten is the source for desk size «seks»).

---

## Changelog

- **27 Aug 2026, 10:00 Europe/Oslo.** First 15 sourced entries. No outreach.
- **27 Aug 2026, 10:15 Europe/Oslo.** Five deepen notes: Oslo DIG Tildelingsbrev 2026 datadeling + 45,5 mill. PC-ownership klimabudsjett measure (do not treat 817 699 / 75 000 as kroner) and DIG etat emails; Stavanger live Regnsensordata (updated 27 Aug 2026 02:01 CEST) and printed staff-ID next to opendata@; Bouvet Kartverket 477 mill. five-year grant (no Bouvet contract price) plus Kaasa phone and 200 vs 50/250 headcount print; Aftenposten Fossan mailto + author line + kvikkleire story (seks = Journalisten only); Statsbygg SIMBA 2.1 PDF dates and tungt.no 13,6 mrd marked second-hand.
- **27 Aug 2026, 10:25 Europe/Oslo.** Wave-2: 12 sourced entries (3 health, 5 energy, 4 mid-size kommuner). Contacts only as listed. No outreach.
- **27 Aug 2026, 10:30 Europe/Oslo.** Wave-2 add: Lillestrøm kommune (digitalisering 2020–2025 + klimabudsjett / Klimasats klimaplanlegger). Contacts only as printed. No outreach.

---

## Living-book rule

This is the Commercial Scout file. Contacts are only what each organisation prints. If a field is missing, write "none published." Never invent an email, phone, or person. No outreach from this file.
