# Lead book — Norwegian open-data platform

Living file. Owner: Commercial Scout. Reports to Chief of staff, not Sølve.
No email, call, or outbound post from this file. Contacts are only what the org prints.

Product sold: registry of Norwegian public datasets (Data.norge first ingest, sources replaceable), natural-language search, first fetch of actual rows. Later analysis. LLM for intent and explanation. Deterministic retrieval. Provenance (source, publisher, license, access path) on every hit.
Repo: https://github.com/Solvelangseth/public-data-agent

Status 27 Aug 2026, 11:48 Europe/Oslo: 70 sourced leads. PR 38 merged. Wave 7 in the living file: health (Førde, Sunnaas, Diakonhjemmet), energy (Barents Nett, Noranett, Enida), mid-size (Hamar). Arendal held. Horten/Askøy/Rana were forslag-only this pass. No invented emails. No outreach.

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

## 19. Helse Vest RHF — Datastrategi I5 + SanntidsHub 2025–2026

**Why they would pay.** *Datastrategi for Helse Vest* (Arkitektur- og datastyring) sets how the region forvalter and shares data. Innsatsområde 5 (Samarbeid og koordinering) prints the målbilde «dra nytte av deling av data i sektoren» and that national/regional samarbeid shall give «bedre bruk av nasjonale data». Helsedirektoratet's veikart for nasjonal e-helsestrategi lists *SanntidsHub i regional data- og analyseplattform* as an Helse Vest RHF activity 01.01.2025–31.12.2026 (nær sanntids, avidentifisert sykehusdrift). The 2026 styringsdokument, news dated 12.02.2026, prints uønskt variasjon as a qualitative mål: spesialisthelsetjenesten shall work systematically with prioritering and reduce uønskt variasjon in kvalitet and forbruk. Those programmes already own regional dashboards and the hub. They would pay to search and fetch *national* FHI NPR styringsdata, Helsedirektoratet SAMDATA and Norgeshelsa series with provenance — not another Helse Vest portal.

**Concrete use case.** An Arkitektur- og datastyring / SanntidsHub analyst needs the latest FHI NPR styringsdata for RHF, SAMDATA spesialisthelsetjenesten tables and Norgeshelsa municipal/fylke series, fetched as rows with license and access path before later overlay on uønskt-variasjon indicators.

**Search → fetch → later analysis.**
- Search: "NPR styringsdata" / SAMDATA / Norgeshelsa + publisher (FHI, Helsedirektoratet).
- Fetch: first rows from the recorded access path (FHI publishes aggregated NPR files for RHF styring).
- Later analysis: compare Vest HF / sykehusområde against national rates; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- post@helse-vest.no
- helse@helse-vest.no — printed on Brønnøysund / Enhetsregisteret for org 983 658 725
- Telephone: 51 96 38 00 (printed on kontakt; telefontid 08.00–16.00)
- VestDialog — printed on the kontakt page as the secure digital-brev channel
- Org: 983658725
- Do not invent a SanntidsHub or datastrategi inbox.

**Key facts.**
- Kontor: Knud Holms gate 8, 4005 Stavanger; Postboks 303, 4068 Stavanger.
- Arkitektur- og datastyring leder etablering of overordnede føringer and follows up etterlevelse of the datastrategi.
- SanntidsHub is on the Hdir veikart under Helse Vest RHF; innføring 2025–2026.

**Sources opened 2026-08-27.**
- https://www.helse-vest.no/48f83b/siteassets/strategi-og-planer/datastrategi/datastrategi-for-helse-vest.pdf
- https://www.helse-vest.no/om-oss/kontakt/
- https://www.helse-vest.no/nyheiter/nyheiter-2026/arets-styringsdokument-dette-blir-viktig-for-sjukehusa-i-2026/
- https://www.helse-vest.no/vart-oppdrag/
- https://www.helsedirektoratet.no/digitalisering-og-e-helse/veikart-for-nasjonal-e-helsestrategi/helse-vest-rhf
- https://www.fhi.no/he/npr/styringsdata-for-rhf/
- https://www.helsedirektoratet.no/statistikk/samdata-spesialisthelsetjenesten
- https://www.norgeshelsa.no/norgeshelsa/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983658725

---

## 20. Helse Midt-Norge RHF — Helsedatasenter / Helsedatafellesskap + KI-delstrategi

**Why they would pay.** *Strategi for videreutvikling av Helsedatasenter og Helsedatafellesskap i Midt-Norge* v1.00 (28.05.2025, Audun Rimehaug / RHF HMN) is the named programme for regional helsedata: samarbeidsstrukturer, oversikt over tilgjengelige data, raskere og sikker tilgang, and deling between aktører. Styret adopted the first regional KI-delstrategi on 05.02.2026; Helsedatasenteret shall contribute tjenester that make it easier to research on and with KI. Those programmes already own the regional data community. They would pay to search and fetch *national and other-region* public series (FHI, Helsedirektoratet, SSB) with provenance into that community — not another Hemit lake.

**Concrete use case.** A Helsedatasenter officer needs a national NPR / KOSTRA / befolkning series that is not already in the regional fellesskap, resolved to a licensed access path and a first row fetch before later landing it for KI or research use.

**Search → fetch → later analysis.**
- Search: municipality / HF + "NPR" / "KOSTRA" / befolkning with publisher (FHI, SSB, Helsedirektoratet).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: land in Helsedatasenter / fellesskap; this product does not replace Hemit or the KI-delstrategi.

**Public contact (only published / listed).**
- postmottak@helse-midt.no — printed on the kontakt page for post that is not pasientrettet / sensitive
- HMN.Postmottak@helse-midt.no — printed on the offentlig postjournal page and as the ledelsen e-post target
- Telephone: 74 83 99 00
- Org: 983658776
- Do not invent villa@. The KI news quotes Villa; no personal inbox is printed there.

**Key facts.**
- Postboks 464, 7501 Stjørdal; Wessels veg 75 on the personvern block.
- KI-delstrategi news 5. februar 2026; four nytteområder printed; Helsedatasenteret named as forskningsstøtte.
- Strategy PDF v1.00 dated 28.05.2025.

**Sources opened 2026-08-27.**
- https://www.helse-midt.no/4a968d/siteassets/documents/rad-og-utvalg/samarbeidsorganet/strategi-for-videreutvikling-helsedatasenter-og-helsedatafellesskap-i-midt-norge-v1.00.pdf
- https://www.helse-midt.no/nyheter/2026/regional-strategi-for-kunstig-intelligens-innen-helse/
- https://www.helse-midt.no/om-oss/kontakt
- https://www.helse-midt.no/om-oss/offentlig-postjournal
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983658776

---

## 21. Helse Nord RHF — Helseatlas / SKDE (same org.nr)

**Why they would pay.** The programme is Helseatlas / SKDE, not a separate RHF data-lake story. SKDE is a unit in Helse Nord RHF and prints the same org.nr 883 658 752. *Helseatlas barn* (published 16.06.2025) analyses helsetjenester for barn 2017–2024 and fetches NPR, KPR, SSB and Legemiddelregisteret. DIS (Digitale innbygger- og samhandlingstjenester) is skipped: it is clinical patient-journey / documents, not a discovery buyer. They would pay to search and fetch those national series with provenance for the next atlas refresh — not to replace analyser.skde.no.

**Concrete use case.** An SKDE analyst preparing an atlas update needs current NPR styringsdata / aktivitet, KPR allmennlege series, SSB befolkning and Legemiddelregisteret utlevering, fetched as rows with license and access path before later rate calculation.

**Search → fetch → later analysis.**
- Search: "NPR" / KPR / "Legemiddelregisteret" / befolkning barn with publisher (FHI, SSB, Helsedirektoratet).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed Helseatlas rates; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- helseatlas@skde.no — printed on analyser.skde.no (barn2025 and other atlas reports)
- postmottak@helse-nord.no — printed on Helse Nord kontakt-oss and on SKDE kontakt
- SKDE telephone: 77 75 58 00
- RHF telephone: 75 51 29 00
- Org: 883658752 (SKDE and Helse Nord RHF)
- Do not use a Helse Førde helseatlas@ inbox. The skde.no/helseatlas page names SKDE and Helse Førde as atlas producers; the printed atlas inbox is helseatlas@skde.no.

**Key facts.**
- Helseatlas landing: skde.no/helseatlas (page notes the service has moved; analyser.skde.no is the live atlas).
- SKDE: Sykehusvegen 23, 9019 Tromsø; Postboks 6400, 9294 Tromsø on the SKDE kontakt page.
- Helse Nord RHF: Postboks 1445, 8038 Bodø.
- DIS skipped (clinical docs / pasientforløp). See skipped notes.

**Sources opened 2026-08-27.**
- https://www.skde.no/helseatlas
- https://analyser.skde.no/
- https://analyser.skde.no/no/rapporter/barn2025
- https://www.skde.no/nyheter/barn-far-ikke-likeverdige-helsetjenester-i-spesialisthelsetjenesten/
- https://www.skde.no/alt-om-oss/kontakt-skde/
- https://www.helse-nord.no/om-oss/kontakt-oss/
- https://www.fhi.no/he/npr/styringsdata-for-rhf/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/883658752

---

## 22. Oslo universitetssykehus HF — Avdeling for registerstøtte / Bruk av registerdata

**Why they would pay.** Avdeling for registerstøtte og forskningsapplikasjoner (virksomhetsområde Forskningsstøtte, HSØ) prints råd og veiledning on planlegging, design, formalisering, oppstart and drift of forskningsregistre and kvalitetsregistre, locally, regionalt and nasjonalt, plus IKT used for forskning and registerstøtte. The *Bruk av registerdata* page prints that tilgang to a nasjonalt medisinsk kvalitetsregister, a sentralt helseregister (Kreftregisteret, Reseptregisteret, Norsk Pasientregister m.fl.) or other nasjonale «ikke medisinske» registre (utdanningsdata from SSB or folkeregisterdata from Skatteetaten) must be søkt, and that Helsedata is the path for sentrale helseregistre, nasjonale medisinske kvalitetsregistre and store nasjonale helseundersøkelser. Data.norge lists NPR (ikke-allmenn tilgang). They already run registerstøtte. They would pay to search and fetch those national catalogue paths and published series with provenance for koblingsplaner — not another Medinsight portal.

**Concrete use case.** A registerstøtte officer preparing a koblingsplan needs the current NPR / Kreftregisteret / SSB utdanning access path and a first licensed fetch of the published catalogue metadata or aggregated series before later REK / Helsedata søknad.

**Search → fetch → later analysis.**
- Search: "NPR" / Kreftregisteret / SSB utdanning + publisher (FHI, Kreftregisteret, SSB, Helsedata).
- Fetch: first catalogue / access-path rows from data.norge or Helsedata; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed koblingsplan / registerstøtte; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- oushfpbregisterstott@ous-hf.no — printed on the registerstøtte page
- post@oslo-universitetssykehus.no — printed on kontakt-oss as sykehusets e-postmottak
- Telephone: 91 50 27 70
- Org: 993467049
- Do not invent extra project inboxes.

**Key facts.**
- Serviceoppdraget for nasjonale medisinske kvalitetsregistre in HSØ is forankret in the avdeling.
- Registerstøtte page last updated 11.03.2026; Bruk av registerdata last updated 22.08.2024.
- Postboks 4950 Nydalen, 0424 Oslo on the kontakt-oss page.

**Sources opened 2026-08-27.**
- https://www.oslo-universitetssykehus.no/forskningsstotte/registerstotte/
- https://www.oslo-universitetssykehus.no/forskningsstotte/registerstotte/bruk-av-registerdata/
- https://www.oslo-universitetssykehus.no/om-oss/kontakt-oss/
- https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/993467049

---

## 23. Helse Bergen HF — Perioperativt Register + Forsking og datatilgang

**Why they would pay.** Perioperativt Register is a regionalt medisinsk kvalitetsregister for operasjoner at Helse Vest sykehus. Helse Bergen HF is behandlingsansvarleg. *Forsking og datatilgang* (updated 19.06.2026) prints that registerdata can — with godkjenning — be koblet mot Norsk intensivregister (NIR), Dødsårsaksregisteret and Norsk pasientregister (NPR), and that kobling mot other nasjonale helseregistre needs Helsedataservice. They already own the register. They would pay to search and fetch those national series and Helsedataservice access paths with provenance for the next kobling — not another perioperativt portal.

**Concrete use case.** A register / forskning officer needs the current NPR / Dødsårsaksregisteret / NIR access path via Helsedataservice and a first licensed fetch of published catalogue or aggregated series before later styre / REK / Helsedataservice søknad.

**Search → fetch → later analysis.**
- Search: "NPR" / Dødsårsaksregisteret / NIR + publisher (FHI, Helsedataservice).
- Fetch: first catalogue / access-path rows; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed kobling / kvalitetsarbeid; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- operasjonsregister@helse-bergen.no — printed on Rettar og informasjon («Ta kontakt direkte»)
- post@helse-bergen.no — printed on kontaktinformasjon for formelle innsynsbegjæringar
- Telephone: 55 97 50 00 (kontaktsenter, printed on kontaktinformasjon and on the register page)
- Org: 983974724
- Do not invent extra project inboxes.

**Key facts.**
- Deltakande HF printed: Helse Bergen, Helse Stavanger, Helse Fonna, Helse Førde.
- Post: Perioperativt Register, KSK Haukeland universitetssjukehus, 5009 Bergen; HF postboks 1400, 5021 Bergen.
- The register landing page also prints perioperativtregister@helse-bergen.no; this book uses the Rettar-page inbox listed above.

**Sources opened 2026-08-27.**
- https://www.helse-bergen.no/avdelinger/kirurgisk-serviceklinikk/perioperativt-register/
- https://www.helse-bergen.no/avdelinger/kirurgisk-serviceklinikk/perioperativt-register/forsking-og-datatilgang/
- https://www.helse-bergen.no/avdelinger/kirurgisk-serviceklinikk/perioperativt-register/rettar-og-informasjon/
- https://www.helse-bergen.no/om-oss/kontaktinformasjon/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983974724

---

## 24. Universitetssykehuset Nord-Norge HF — Registerenheten + NORGAST / SAMDATA USK

**Why they would pay.** Registerenheten in Fag-, analyse- og styringssentret prints as hovedansvar to serve the kvalitetsregistre UNN has dataansvar for (including NORGAST). NORGAST *Årsrapport 2024* prints dekningsgrad 91 percent against NPR and 100 percent tilslutning (andel reseksjoner in NORGAST of reseksjoner in NPR). Styresak 98-2023 (*Utskrivningsklare pasienter*) uses SAMDATA for USK overliggerdøgn: UNN-området 48,5 vs Norge 13,1 per 1 000 innbygger in 2022. They already run the registers. They would pay to search and fetch NPR / SAMDATA series with provenance for the next dekningsgrad or USK brief — not another NORGAST portal.

**Concrete use case.** Registerenheten / NORGAST needs the current NPR reseksjon counts used in dekningsgrad, plus SAMDATA USK tables for UNN-området, fetched as rows with license and access path before later overlay on the årsrapport or styresak.

**Search → fetch → later analysis.**
- Search: "NPR" / dekningsgrad / SAMDATA USK + publisher (FHI, Helsedirektoratet).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed NORGAST dekningsgrad or SAMDATA USK; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- post@unn.no — printed on kontakt-oss and in the styresak 98-2023 footer
- nra@unn.no — printed on the NRA register page (send aldri personopplysninger)
- Telephone: 77 62 60 00 (sentralbord) / 777 54 287 (Registerenheten, printed on the NORGAST page next to Elin Golde)
- Org: 983974899
- Do not invent Golde@. The NORGAST page names Elin Golde under Registerenheten and prints the phone; it does not print a Golde inbox.

**Key facts.**
- UNN-ansvar registers printed on the kvalitetsregistre page include PHBU, ryggkirurgi, nakke- og rygg, NORNMD, NRA, NORGAST and Nordnorsk kvalitetsregister for endokarditt.
- NORGAST dataansvar: administrerende direktør, Universitetssykehuset Nord-Norge HF. Postboks 20, 9038 Tromsø.
- Styresak 98-2023 footer also prints www.unn.no and org.nr 983 974 899.

**Sources opened 2026-08-27.**
- https://www.unn.no/fag-og-forskning/medisinske-kvalitetsregistre/
- https://www.unn.no/fag-og-forskning/medisinske-kvalitetsregistre/norgast-norsk-register-for-gastrokirurgi
- https://www.unn.no/48cfd1/siteassets/documents/styremoter-dokumenter/2023/191223/sak-98---utskrivningsklare-pasienter-ved-universitetssykehuset-nord-norge-hf.pdf
- https://www.kvalitetsregistre.no/49da7b/siteassets/dokumenter/arsrapporter/gastrokirurgiregisteret/arsrapport-2024-norgast.pdf
- https://www.unn.no/om-oss/kontakt-oss/
- https://www.unn.no/fag-og-forskning/medisinske-kvalitetsregistre/nra-norsk-register-for-analinkontinens/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/983974899

---

## 25. Akershus universitetssykehus HF — HØKH + Analyseavdelingen / nasjonale registre

**Why they would pay.** Avdeling for helsetjenesteforskning (HØKH) is the koordinerende miljø for Nasjonalt nettverk for helsetjenesteforskning. HØKH and Analyseavdelingen consume Norsk pasientregister (NPR), Reseptregisteret and Dødsårsaksregisteret — registers they do not host. The behandlings- og evalueringsforskning group (psykisk helse og avhengighet) prints that it still needs to solve technical, juridiske and praktiske issues when kobling sykehusdata to Reseptregisteret, NPR, Dødsårsaksregisteret and similar. Data.norge lists NPR (ikke-allmenn tilgang). They already run helsetjenesteforskning. They would pay to search and fetch those national catalogue paths and published series with provenance for the next kobling — not another Ahus register portal.

**Concrete use case.** HØKH / Analyseavdelingen preparing a kobling needs the current NPR / Reseptregisteret / Dødsårsaksregisteret access path and a first licensed fetch of published catalogue metadata or aggregated series before later REK / Helsedata søknad.

**Search → fetch → later analysis.**
- Search: "NPR" / Reseptregisteret / Dødsårsaksregisteret + publisher (FHI, Helsedata).
- Fetch: first catalogue / access-path rows from data.norge or Helsedata; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed kobling / helsetjenesteforskning; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- analyse@ahus.no — listed
- postmottak@ahus.no — printed on kontakt-oss
- Telephone: 67 96 00 00
- Org: 983971636
- Do not invent extra project inboxes.

**Key facts.**
- HØKH is printed as koordinerende miljø for Nasjonalt nettverk for helsetjenesteforskning (page last updated 25.05.2026).
- Postboks 1000, 1478 Lørenskog on the kontakt-oss page.
- NPR, Reseptregisteret and Dødsårsaksregisteret are consumed, not hosted, by HØKH / Analyseavdelingen.

**Sources opened 2026-08-27.**
- https://www.ahus.no/fag-og-forskning/helsetjenesteforskning/
- https://www.ahus.no/499ef9/contentassets/dba033c24e044c32b0b9551a05b9495b/arsrapport-hokh-2024.pdf
- https://www.ahus.no/fag-og-forskning/forskning-og-innovasjon/forskningsgrupper/psykisk-helsevern-og-rus-divisjon/behandlings--og-evalueringsforskning-psykisk-helse-og-avhengighet/
- https://www.ahus.no/om-oss/kontakt-oss/
- https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d/norsk-pasientregister
- https://virksomhet.brreg.no/nb/oppslag/enheter/983971636

---

## 26. Vestre Viken HF — Brukerstyrt epilepsioppfølging + Ventetidsløftet / NPR

**Why they would pay.** *Brukerstyrt epilepsioppfølging* prints that research may koble pasientrapporterte data to Norsk Pasientregister, Kommunalt pasient- og brukerregister (KPR) and Statistisk sentralbyrå. Styrepapirer for styremote 10. juni 2024 print that Ventetidsløftet uses monthly NPR. They already run the oppfølging. They would pay to search and fetch those national series with provenance for the next kobling or ventetid brief — not another epilepsi portal.

**Concrete use case.** A forskning / styring officer needs current NPR / KPR / SSB access paths and a first licensed fetch of published catalogue or aggregated series before later REK / ventetid overlay.

**Search → fetch → later analysis.**
- Search: "NPR" / KPR / SSB + publisher (FHI, Helsedirektoratet, SSB).
- Fetch: first catalogue / access-path rows; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed kobling or Ventetidsløftet; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- postmottak@vestreviken.no — printed on kontakt-oss
- Kristine.Sahlberg@vestreviken.no — listed
- marsyv@vestreviken.no — printed on the epilepsioppfølging page (Marte Roa Syvertsen)
- Telephone: 03525 / 32 80 30 00
- Org: 894166762
- Do not invent extra project inboxes.

**Key facts.**
- Brukerstyrt epilepsioppfølging names NPR + KPR + SSB as the kobling registers.
- Ventetidsløftet in the 10 June 2024 styrepapirer uses monthly NPR.
- Do not treat the study page as a live recruitment path (stengt for rekruttering).

**Sources opened 2026-08-27.**
- https://www.vestreviken.no/kliniske-studier/brukerstyrt-epilepsioppfolging/
- https://www.vestreviken.no/49c597/siteassets/documents/styrepapirer/2024/samledokument-til-styremote-i-vvhf-10.-juni-2024.pdf
- https://www.vestreviken.no/om-oss/kontakt-oss/
- https://virksomhet.brreg.no/nb/oppslag/enheter/894166762

---

## 27. Sykehuset Østfold HF — Styresak 123-24 RBF + Ventetidsløftet / NPR

**Why they would pay.** Styresak 123-24 (*Mål og budsjett 2025*) uses NPR and NKI in the RBF / styring material. Ventetidsløftet-vedlegg to sak 57-24 (10.06.2024) uses monthly NPR. TROLL and NOR-ITP are the HF's own kvalitetsregistre — they are not the buy reason. They already run those registers. They would pay to search and fetch NPR / NKI series with provenance for the next RBF or ventetid brief — not another TROLL / NOR-ITP portal.

**Concrete use case.** Økonomi / styring needs current NPR / NKI tables used in RBF and the monthly NPR series used in Ventetidsløftet, fetched as rows with license and access path before later overlay on the neste styresak.

**Search → fetch → later analysis.**
- Search: "NPR" / NKI / ventetid + publisher (FHI, Helsedirektoratet).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed RBF or Ventetidsløftet; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- postmottak@so-hf.no — listed
- Heidi.hassel.pettersen@so-hf.no — listed
- waleed.ghanima@so-hf.no — listed
- Telephone: 69 86 00 00
- Org: 983971768
- Do not invent extra project inboxes.

**Key facts.**
- Postboks 300, 1714 Grålum on the kontakt-oss page.
- TROLL (lokalt venøs blodpropp) and NOR-ITP (nasjonalt ITP) are own registers; not the discovery buy.
- Styresak 123-24 and sak 57-24 vedlegg are the printed NPR / NKI uses.

**Sources opened 2026-08-27.**
- https://www.sykehuset-ostfold.no/4aeb2f/siteassets/seksjon/styremoter/documents/2024/2024-12-16/sak-123-24-mal-og-budsjett-2025-for-sykehuset-ostfold-hf.pdf
- https://www.sykehuset-ostfold.no/49bd5f/siteassets/seksjon/styremoter/documents/2024/2024-06-10/sak-57-24-ventetidsloftet_vedl1.pdf
- https://www.sykehuset-ostfold.no/helsefaglig/forskning/kvalitetsregistre/
- https://www.sykehuset-ostfold.no/kontakt-oss/
- https://virksomhet.brreg.no/nb/oppslag/enheter/983971768

---

## 28. Sykehuset Innlandet HF — ROPforsk / NPR + MSIS + SSB + Legemiddelregisteret

**Why they would pay.** ROPforsk consumes Norsk pasientregister (NPR), MSIS, SSB and Legemiddelregisteret — registers it does not host. Data.norge lists NPR (ikke-allmenn tilgang). They already run ROPforsk. They would pay to search and fetch those national catalogue paths and published series with provenance for the next kobling — not another Innlandet register portal.

**Concrete use case.** ROPforsk / forskning needs the current NPR / MSIS / SSB / Legemiddelregisteret access path and a first licensed fetch of published catalogue metadata or aggregated series before later REK / Helsedata søknad.

**Search → fetch → later analysis.**
- Search: "NPR" / MSIS / SSB / Legemiddelregisteret + publisher (FHI, Helsedata, SSB).
- Fetch: first catalogue / access-path rows from data.norge or Helsedata; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed ROPforsk kobling; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- postmottak@sykehuset-innlandet.no — listed
- forskning@sykehuset-innlandet.no — listed
- Bjorn.Stensrud@sykehuset-innlandet.no — listed
- Anne.Landheim@sykehuset-innlandet.no — listed
- Telephone: 91 50 62 00
- Org: 983971709
- Do not invent extra project inboxes.

**Key facts.**
- Postboks 104, 2381 Brumunddal; Furnesvegen 26, 2382 Brumunddal on the Enhetsregisteret page.
- ROPforsk consumes NPR + MSIS + SSB + Legemiddelregisteret; it does not host them.

**Sources opened 2026-08-27.**
- https://www.sykehuset-innlandet.no/
- https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d/norsk-pasientregister
- https://virksomhet.brreg.no/nb/oppslag/enheter/983971709

---

## 29. Sykehuset Telemark HF — Helsefellesskapet Retningslinje 1 + Gastronet / NPR

**Why they would pay.** Helsefellesskapet Retningslinje 1 uses data from NPR and SSB. Gastronet (dataansvar Sykehuset Telemark HF) prints NPR dekningsgrad. Those programmes consume national series they do not host. They already run Gastronet. They would pay to search and fetch NPR / SSB series with provenance for the next retningslinje or dekningsgrad brief — not another Gastronet portal.

**Concrete use case.** Helsefellesskapet / Gastronet needs current NPR / SSB tables used in Retningslinje 1 and Gastronet dekningsgrad, fetched as rows with license and access path before later overlay.

**Search → fetch → later analysis.**
- Search: "NPR" / dekningsgrad / SSB + publisher (FHI, Helsedirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed Retningslinje 1 or Gastronet dekningsgrad; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- postmottak@sthf.no — listed
- gastronet@sthf.no — listed
- fou@sthf.no — listed
- hhge@sthf.no — listed
- Telephone: 35 00 35 00
- Org: 983975267
- Do not invent extra project inboxes.

**Key facts.**
- Postboks 2900 Kjørbekk, 3710 Skien; Ulefossvegen 55 on the Enhetsregisteret page.
- Helsefellesskapet Retningslinje 1 uses NPR + SSB. Gastronet prints NPR dekningsgrad.

**Sources opened 2026-08-27.**
- https://www.sthf.no/
- https://www.kvalitetsregistre.no/registeroversikt/gastronet
- https://virksomhet.brreg.no/nb/oppslag/enheter/983975267

---

## 30. Sykehuset i Vestfold HF — NorCP / NPR + MFR

**Why they would pay.** NorCP consumes Norsk pasientregister (NPR) and Medisinsk fødselsregister (MFR) — registers it does not host. They already run NorCP. They would pay to search and fetch those national series with provenance for the next dekningsgrad or kobling — not another NorCP portal.

**Concrete use case.** NorCP / forskning needs current NPR / MFR access paths and a first licensed fetch of published catalogue or aggregated series before later REK / register overlay.

**Search → fetch → later analysis.**
- Search: "NPR" / MFR / NorCP + publisher (FHI, Helsedata).
- Fetch: first catalogue / access-path rows; license and publisher on every hit. Do not fetch personidentifiable register rows.
- Later analysis: feed NorCP; keep provenance; do not invent clinical figures.

**Public contact (only published / listed).**
- post@siv.no — listed
- norcp@siv.no — listed
- forskning@siv.no — listed
- personvern@siv.no — listed
- Telephone: 33 34 20 00
- Org: 983975259
- Do not invent extra project inboxes.

**Key facts.**
- Postboks 2168, 3103 Tønsberg; Halfdan Wilhelmsens alle 17, 3116 Tønsberg on the Enhetsregisteret page.
- NorCP consumes NPR + MFR; it does not host them.

**Sources opened 2026-08-27.**
- https://www.siv.no/
- https://virksomhet.brreg.no/nb/oppslag/enheter/983975259

---

### Helse Førde HF

- **Why they would pay.** Helseatlas (seksjon for forsking og innovasjon; landing 24.08.2026) consumes specialist-helseteneste activity they do not host (NPR / KPR). HOD-oppdraget is shared with SKDE — SKDE is already a taken seat; Førde is the Helse Vest shop. Strategi 2025–2028 for Sogn og Fjordane helsefellesskap names styringsdata and framskrivingsverktøy. Not a Data.norge publisher (0 hits).
- **Concrete use case.** Helseatlasteamet finds and first-fetches official NPR and KPR catalogue rows before the next atlas or helsefellesskap styringsnotat, with provenance on every hit.
- **How the service should look.**
  - Search: data.norge first (NPR, KPR, Helsedataservice). Førde is the consumer.
  - Fetch: first official metadata/distribution row. NPR/KPR are NON_PUBLIC — landing helsedata.no.
  - Later analysis: geografisk variasjon / framskriving. Helsedata søknad stays theirs.
- **Public contact.**
  - Role / unit: Helseatlas / seksjon for forsking og innovasjon (Jagrati Jani-Bølstad, Oddne Skrede named).
  - Email: `jagrati.jani-bolstad@helse-forde.no`; `oddne.skrede@helse-forde.no`; `samhandling@helse-forde.no`
  - Phone: 57 83 90 00
  - Form/URL: https://www.helse-forde.no/helseatlas
- **Key facts.** Org.nr 983 974 732. Postboks 1000, 6807 Førde.
- **Sources** (opened 2026-08-27).
  - https://www.helse-forde.no/helseatlas
  - https://www.helse-forde.no/om-oss/kontaktinformasjon/
  - https://www.helse-forde.no/samhandling/
  - https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d/norsk-pasientregister
  - https://virksomhet.brreg.no/nb/oppslag/enheter/983974732
  - https://data.brreg.no/enhetsregisteret/api/enheter/983974732

### Sunnaas sykehus HF

- **Why they would pay.** NorREHAB (landing 02.06.2026; Hdir nasjonal status juni 2026) names NPR as an external data source. Parallel: Afasi og registerdata samarbeider with FHI and Helsedirektoratet. Own kvalitetsregister is in-house capture, not the buy reason. Not a Data.norge publisher (0 hits).
- **Concrete use case.** NorREHAB finds and first-fetches the official NPR catalogue row before dekningsgrad / automatisk datafangst against own rehabilitering counts.
- **How the service should look.**
  - Search: data.norge first (NPR, Helsedataservice). NorREHAB is not harvested yet.
  - Fetch: first official NPR row. Helsedata søknad stays theirs.
  - Later analysis: oppstart-dekningsgrad vs NPR.
- **Public contact.**
  - Role / unit: NorREHAB (Frank Becker named; no personal inbox).
  - Email: `norskrehabregister@sunnaas.no`; `firmapost@sunnaas.no`
  - Phone: 66 96 90 00
  - Form/URL: https://www.sunnaas.no/om-oss/mer-om-oss/kvalitet-og-pasientsikkerhet/norsk-rehabiliteringsregister/
- **Key facts.** Org.nr 883 971 752. Bjørnemyrveien 11, 1453 Bjørnemyr.
- **Sources** (opened 2026-08-27).
  - https://www.sunnaas.no/om-oss/mer-om-oss/kvalitet-og-pasientsikkerhet/norsk-rehabiliteringsregister/
  - https://www.sunnaas.no/om-oss/kontakt-oss
  - https://www.sunnaas.no/fag-og-forskning/forskning/forskningsgrupper/Afasi-og-registerdata/
  - https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d/norsk-pasientregister
  - https://virksomhet.brreg.no/nb/oppslag/enheter/883971752
  - https://data.brreg.no/enhetsregisteret/api/enheter/883971752

### Diakonhjemmet sykehus AS

- **Why they would pay.** REMEDY WP6: «kobling til nasjonale registre.» NOR-ECON already links NOR-DMARD to DÅR, Kreftregisteret, NPR, Leddproteser, SYSVAK, FD-trygd, A-ordningen and extracts from NPR + SSB. Hosting NOR-DMARD is publisher-side; those catalogues are the consume. Not a Data.norge publisher (0 hits).
- **Concrete use case.** REMEDY WP6 / NOR-ECON finds and first-fetches official NPR, DÅR and Kreftregisteret rows before a helseøkonomi / arbeidsdeltagelse kobling.
- **How the service should look.**
  - Search: data.norge first (NPR, DÅR, Kreftregisteret, Helsedataservice).
  - Fetch: first official row/landing. Helsedata / SSB søknad stays theirs.
  - Later analysis: langtids-sikkerhet / arbeidsdeltagelse after kobling.
- **Public contact.**
  - Role / unit: REMEDY / Avdeling for forskning og innovasjon (Provan, Uhlig, Hagen named; no personal inboxes).
  - Email: `postmottak@diakonsyk.no`; `personvern@diakonsyk.no`
  - Phone: 22 45 15 00
  - Form/URL: https://www.diakonhjemmetsykehus.no/om-diakonhjemmet-sykehus/kontakt-oss
- **Key facts.** Org.nr 982 791 952. Postboks 23 Vinderen, 0319 Oslo.
- **Sources** (opened 2026-08-27).
  - https://www.diakonhjemmetsykehus.no/om-diakonhjemmet-sykehus/kontakt-oss
  - https://www.diakonhjemmetsykehus.no/fag-forskning-og-innovasjon
  - https://data.norge.no/nb/datasets/e842f90c-0555-3f56-8b66-540a9d9d911d/norsk-pasientregister
  - https://virksomhet.brreg.no/nb/oppslag/enheter/982791952
  - https://data.brreg.no/enhetsregisteret/api/enheter/982791952

---

## 31. Statnett SF — SUP 2025 + 10 områdeplaner + Omstillingsplan 2026

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

## 32. Eviny AS — 100-på-10 / PIA / dataflyt

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

## 33. Hafslund AS — Naturkompasset with NVE / Miljødirektoratet

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

## 34. Tensio AS — områdestudier replace KSU

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

## 35. Lnett AS (Lyse) — NVE nettutviklingskoordinator + Energikoordinator

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

## 36. Elvia AS — NVE NUK Oslo / Innlandet / Akershus / Østfold + PlanNett

**Why they would pay.** Elvia is NVE's nettutviklingskoordinator for Oslo, Innlandet, Akershus and Østfold. The langsiktig-planlegging page says KSU was avviklet 1 March 2024 and that Elvia now publishes effektprognoser, områdestudier, KVU and regionalnettiltak on NVE PlanNett. Ambition printed on the Innlandet solkraft page: øke kapasiteten i det eksisterende strømnettet with 20 percent. This is Elvia AS (DSO), not Hafslund AS (already a Naturkompasset lead). Those NUK / PlanNett roles consume municipal plans, SSB, Statnett områdeplaner and NVE layers that do not all live on elvia.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace PlanNett.

**Concrete use case.** An utredning officer needs a municipal arealplan or Statnett områdeplan layer for Oslo / Innlandet / Akershus / Østfold that is not in Elvia's own effektprognose, fetched as rows/features with license before later KVU.

**Search → fetch → later analysis.**
- Search: area / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: effektprognose / områdestudie / KVU; keep provenance.

**Public contact (only published / listed).**
- firmapost@elvia.no — printed on the arbeid-i-egen-bolig page and on tariffvilkår
- kundeservice@elvia.no — printed on the pressekontakter page («Andre henvendelser»)
- Telephone: 02024
- HQ: Vangsvegen 71, 2317 Hamar (Innlandet office; also Harbitzalléen 5, Oslo)
- Org: 980489698
- Not Hafslund AS. Do not invent a NUK or PlanNett inbox.

**Key facts.**
- Postboks 4100, 2307 Hamar.
- PlanNett is NVE's portal for områdestudier and KVU summaries.
- 20 percent existing-grid ambition is printed next to Anne Sagstuen Nysæther on the Innlandet solkraft page.

**Sources opened 2026-08-27.**
- https://www.elvia.no/hva-er-elvia/vart-stromnett/langsiktig-planlegging-i-regionalnettet/
- https://www.elvia.no/proff/planlegge-prosjekter/planlegging/fordeling-av-ledig-kapasitet-i-nettet/
- https://www.elvia.no/hva-er-elvia/kontakt-oss/kundeservice/
- https://www.elvia.no/hva-er-elvia/kontakt-oss/pressekontakter-og-nyheter/
- https://www.elvia.no/hva-er-elvia/om-oss/legger-til-rette-for-solkraft-i-innlandet/
- https://plannett.nve.no/
- https://www.statnett.no/planer-for-stromnettet/omradeplaner/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/980489698

---

## 37. Glitre Nett AS — DataArena IPN 332323 + NUK Agder / Buskerud / Hadeland

**Why they would pay.** Glitre Nett AS (org.nr 982 974 011) is the successor of Agder Energi Nett. DataArena is printed as IPN 332323: a kapasitetskart for 1–20 MW forbruk/produksjon, led by Glitre Nett. NVE has utpekt Glitre Nett as nettutviklingskoordinator for Agder, Buskerud and Hadeland. Nine områdestudier (2 June 2025 news) cover those areas. Norgesnett is folded into Glitre Nett — not a fourth energy seat. They already publish a capacity map. They would pay to search and fetch Statnett områdeplaner, NVE PlanNett, municipal plans and SSB series with provenance into DataArena / områdestudier — not to replace the map.

**Concrete use case.** An energikoordinator / regionalnett team needs a municipal plan or Statnett områdeplan layer for one of the nine studieområder, fetched as features/rows with license before later overlay on DataArena capacity.

**Search → fetch → later analysis.**
- Search: Agder / Buskerud / Hadeland + arealplan / effekt / industri with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: områdestudie / DataArena; keep provenance.

**Public contact (only published / listed).**
- jon.vehus@glitrenett.no — printed on the DataArena page as Energikoordinator
- Petter.Tollefsen@glitrenett.no — printed on organisasjon-og-ledelse as Leder Regionalnett
- Otto.Rustand@glitrenett.no — printed on the same page as Leder Operativ drift, digitalisering og beredskap
- post.nett@glitrenett.no — printed on Brønnøysund / Enhetsregisteret for org 982 974 011
- Telephone: 38 60 72 72 (kundesenter on kontakt-oss)
- HQ: Grønland 67, 3045 Drammen
- Org: 982974011
- Do not invent post@glitrenett.no. The kontakt-oss page prints the phone and a form, not that inbox.

**Key facts.**
- Postboks 7007, 3007 Drammen.
- Nine områdestudier: Agder (Øvre Setesdal, Agder Øst, Agder Vest, Sirdal) and Buskerud/Hadeland (Eiker–Ringerike, Drammen–Hurum, Kongsberg–Numedal, Ringerike–Hadeland, Hallingdal–Hemsedal).
- Norgesnett fusjon printed 28 Nov 2025 / 7 March brand; not a separate lead.

**Sources opened 2026-08-27.**
- https://www.glitrenett.no/om-Glitre-Nett/teknologi-utvikling-og-prosjekter/dataarena
- https://www.glitrenett.no/om-Glitre-Nett/vart-stromnett/nettutvikling
- https://www.glitrenett.no/kontakt-oss
- https://www.glitrenett.no/om-Glitre-Nett/organisasjon-og-ledelse
- https://www.glitrenett.no/aktuelt/18549428?type=pressRelease
- https://www.glitrenett.no/aktuelt/fusjon-mellom-glitre-nett-og-norgesnett
- https://www.statnett.no/planer-for-stromnettet/omradeplaner/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/982974011

---

## 38. Linea AS — TILKO digitaliseringsstrategi + kapasitetsregime 5 / 1 / 0.1 MW

**Why they would pay.** Linea's 20 May 2025 news prints TILKO as «en viktig del av vår digitaliseringsstrategi» (Steinar Benum): a national tilknytningsportal for ≥1 MW, developed through ElBits, with data shared to Statnett. The store-anlegg page prints the kapasitetsregime: 5 MW (transmisjonsnett reservation / kø at Statnett), 1 MW (Sør-Helgeland and some Linea-nett limits), and 0.1 MW (100 kW) in named kommuner/områder. Those pages point at Statnett *Områdeplan Helgeland og Salten* (2025). Linea already runs TILKO. They would pay to search and fetch the Statnett områdeplan layers plus municipal / NVE / SSB series with provenance — not to replace TILKO.

**Concrete use case.** A tilknytning / nettutvikling officer needs the current Statnett Helgeland og Salten målnett and municipal plan layers for a ≥1 MW kø-sak, fetched as rows/features with license before later TILKO / områdeplan overlay.

**Search → fetch → later analysis.**
- Search: Helgeland / Salten / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path (Statnett 2025 områdeplan PDF).
- Later analysis: kapasitetskø / områdeplan; keep provenance.

**Public contact (only published / listed).**
- post@linea.no — printed on the personvern page
- steinar.benum@linea.no — printed on pressekontakter as daglig leder
- bjorn.aune@linea.no — printed on pressekontakter as teknisk sjef
- Telephone: 75 10 04 00
- HQ: Industrivegen 7, 8657 Mosjøen
- Org: 917424799
- Do not invent extra project inboxes.

**Key facts.**
- Postboks 702, 8654 Mosjøen.
- TILKO news published 20. mai 2025 (updated 23. juni 2025).
- Statnett Områdeplan Helgeland og Salten, juni 2025, names Linea as the Helgeland regional nettselskap.

**Sources opened 2026-08-27.**
- https://www.linea.no/no/kunde/nyheter/ny-digital-losning-gir-bedre-oversikt-og-samhandling-om-fremtidens-stromnett
- https://www.linea.no/no/kunde/tilkoble-og-endre/koble-til-store-anlegg
- https://www.linea.no/no/kunde/kundeforhold/personvern
- https://www.linea.no/no/kontakt-oss/pressekontakter
- https://www.statnett.no/globalassets/for-aktorer-i-kraftsystemet/planer-og-analyser/omradeplaner/helgeland-og-salten/omradeplan-helgeland-og-salten-2025.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/917424799

---

## 39. Arva AS — NUK Troms + Midtre-Nordland + §15 Kapasitetskart

**Why they would pay.** NVE has utpekt Arva as nettutviklingskoordinator for Troms and for Midtre-Nordland. Forskrift om energiutredninger §15 (*Ledig nettkapasitet*) requires nettutredere to publish anslag on ledig kapasitet; the NVE veileder names Kapasitetskart (Arva) as an example. On 27 Aug 2026 `https://arva.no/Kapasitetskart` returned 404 — keep the NVE cite; do not claim the page is live. Arva's own 22.04.2026 press prints Statnett's stopp in tildeling of nettkapasitet nord for Svartisen. Own news 04.05.2026 prints 607 millioner kroner invested in the grid in 2025 and planned investments of sju to ti milliarder kroner over the coming ten years. Those NUK / §15 / områdeplan roles consume Statnett, NVE PlanNett, municipal and SSB series that do not all live on arva.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace a capacity map.

**Concrete use case.** A NUK / nettstrategi officer needs a Statnett områdeplan layer or municipal arealplan for Troms / Midtre-Nordland that is not in Arva's own effektprognose, fetched as rows/features with license before later PlanNett / KVU.

**Search → fetch → later analysis.**
- Search: Troms / Midtre-Nordland / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: NUK / områdestudie / PlanNett; keep provenance. Do not treat arva.no/Kapasitetskart as a live source.

**Public contact (only published / listed).**
- eirin.kjolstad@arva.no — listed
- hege.villumstad@arva.no — printed on the presse page
- thor.magne.hoff@arva.no — listed
- HQ: Jernbaneveien 85, 8006 Bodø
- Org: 979151950
- Do not invent post@arva.no. The opened pages print named inboxes and a presse form, not that address.

**Key facts.**
- NUK Troms: Balsfjord, Bardu, Dyrøy, Karlsøy, Kåfjord, Lavangen, Lyngen, Målselv, Nordreisa, Salangen, Senja, Skjervøy, Storfjord, Sørreisa and Tromsø, plus named Vissi-konsesjon areas in Kautokeino, Loppa and Kvænangen.
- NUK Midtre-Nordland: Lurøy, Træna, Rødøy, Meløy, Gildeskål, Bodø, Saltdal, Fauske, Sørfold, Steigen, Hamarøy and a named Kystnett area sør in Narvik.
- 607 MNOK 2025 and 7–10 mrd over ten years are printed on Arva's own 4 May 2026 news. Årsrapport 2025 also prints MNOK 607 invested in 2025.

**Sources opened 2026-08-27.**
- https://kommunikasjon.ntb.no/pressemelding/18885159/arva-bygger-stromnettet-klart-for-ekstremvaer-beredskap-og-vekst?publisherId=17848600&lang=no
- https://kommunikasjon.ntb.no/pressemelding/18874290/arva-stans-i-tildeling-av-nettkapasitet-viser-kritisk-behov-for-handling-i-nord?publisherId=17848600&lang=no
- https://arva.no/nyheter
- https://arva.no/presse
- https://arva.no/sites/a/arva.no/files/2026/04/arva-__rsrapport2025-oppslag.pdf
- https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
- https://veiledere.nve.no/forskrift-om-energiutredninger/ledig-kapasitet/
- https://plannett.nve.no/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/979151950

---

## 40. Lede AS — NUK Vestfold og Telemark + Tilko / Wattapp / KSU 2022–2041

**Why they would pay.** Lede is NVE's nettutviklingskoordinator for Vestfold og Telemark (including the Drammen-konsesjon slice; excluding Høgefoss / the Nissedal slice that is Glitre Nett). *Kraftsystemutredningen 2022–2041* for Vestfold og Telemark is the printed 20-year regionalnett utredning and is also registered toward NVE PlanNett. *Større tilknytninger* uses Tilko for ≥1 MW; *Kapasitet og køordning* points at Wattapp for tidlig-fase ledig kapasitet. Those NUK / Tilko / KSU roles consume Statnett områdeplaner, municipal plans and SSB series that do not all live on lede.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace Tilko or Wattapp.

**Concrete use case.** An utredning officer needs a municipal arealplan or Statnett områdeplan layer for Vestfold / Telemark that is not in Lede's own KSU / effektprognose, fetched as rows/features with license before later KVU.

**Search → fetch → later analysis.**
- Search: Vestfold / Telemark / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: KSU / PlanNett / Tilko; keep provenance.

**Public contact (only published / listed).**
- firmapost@lede.no — printed on kontaktinformasjon («For andre henvendelser til nettselskapet»)
- kundeservice@lede.no — printed on the same page
- Telephone: 35 51 89 90 (kundeservice, hverdager 9–14)
- HQ: Floodeløkka 1, 3915 Porsgrunn
- Org: 979422679
- Do not invent a NUK or Tilko inbox.

**Key facts.**
- Postboks 80, 3901 Porsgrunn.
- KSU 2022–2041 describes 132 and 66 kV regionalnett in Vestfold og Telemark; Lede is the largest regionalnetteier in that utredning.
- PlanNett is NVE's portal for områdestudier and KVU summaries.

**Sources opened 2026-08-27.**
- https://lede.no/kunde/om-lede/var-samfunnsrolle/kraftsystemutredning/
- http://lede.no/getfile.php/1329066-1659443591/Lede/Dokumenter/Hovedrapport%20KSU%20Vestfold%20og%20Telemark%202022%20-%202041.pdf
- https://lede.no/proff/bygge-og-tilknytte/tilknytning-av-nye-anlegg/storre-tilknytninger/
- https://lede.no/proff/bygge-og-tilknytte/kapasitet-og-koordning/
- https://lede.no/kunde/om-lede/kontakt-oss/kontaktinformasjon/
- https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
- https://plannett.nve.no/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/979422679

---

## 41. Fagne AS — NUK Sunnhordaland og Nord-Rogaland + dialogmøter 2026 + Tilko

**Why they would pay.** Fagne is NVE's nettutviklingskoordinator for Sunnhordaland og Nord-Rogaland. May–June 2026 regional dialogmøter with Statnett (11 May Sunnhordaland / Stord; 10 June Haugalandet) are printed as a new early-dialog path into områdestudier; 110 påmeldte across the two meetings; høst 2026 meetings in Indre Hardanger and Ryfylke. *Større tilknytninger over 1 MW* uses Tilko. Those NUK / dialog / Tilko roles consume Statnett områdeplaner, municipal plans and SSB series that do not all live on fagne.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace Tilko.

**Concrete use case.** An energikoordinator / nettutvikling officer needs a municipal plan or Statnett områdeplan layer for Haugalandet / Sunnhordaland that is not in Fagne's own områdestudie, fetched as rows/features with license before later PlanNett / Tilko overlay.

**Search → fetch → later analysis.**
- Search: Sunnhordaland / Haugalandet / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: områdestudie / dialogmøte follow-up / Tilko; keep provenance.

**Public contact (only published / listed).**
- trude.froyland@fagne.no — printed on the større-næring page as Energikoordinator
- post@fagne.no — printed on kontakt for henvendelser from myndigheter and offentlige instanser
- HQ: Haukelivegen 25, Haugesund
- Org: 915635857
- Do not invent extra project inboxes.

**Key facts.**
- NUK area printed by NVE: Austevoll, Tysnes, Fitjar, Stord, Bømlo, Kvinnherad, Etne, Sveio and the Fagne-konsesjon slice of Ullensvang (Vestland); Suldal, Sauda, Vindafjord, Tysvær, Bokn, Karmøy, Utsira, Haugesund and the Fagne-konsesjon slice of Hjelmeland nord for Jøsenfjorden (Rogaland).
- Dialogmøtene are printed as input to oppdatering of områdestudier; Statnett presented områdeplan-status on the Haugalandet programme.
- Tilko is printed as the nasjonal tilknytningsportal for ≥1 MW.

**Sources opened 2026-08-27.**
- https://fagne.no/inviterer-til-regionale-dialogmoter/
- https://fagne.no/110-deltakere-pa-dialogmoter-om-stromnettet-i-regionen/
- https://fagne.no/bygge-grave-rive/koble-til-eller-oke-kapasitet/storre-naering-og-kraftkrevende-industri/
- https://fagne.no/kontakt/
- https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/915635857

---

## 42. Vissi AS — nettutreder in Arva NUK Troms + >0,5 MW / modenhetsmatrise

**Why they would pay.** Vissi is the nettutreder inside Arva's NVE NUK Troms area (Arva already names Vissi-konsesjon slices). The tilknytning page prints a process for større tilknytningssaker >0,5 MW and Vissi's own modenhetsmatrise. Those tilknytning / NUK-area roles consume Statnett, NVE PlanNett, municipal and SSB series that do not all live on vissi.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace the modenhetsmatrise.

**Concrete use case.** A nettutreder officer needs a municipal arealplan or Statnett områdeplan layer for the Vissi-konsesjon area that is not in Vissi's own tilknytning file, fetched as rows/features with license before later >0,5 MW / NUK overlay.

**Search → fetch → later analysis.**
- Search: Nordreisa / Skjervøy / Kautokeino / Troms + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: >0,5 MW tilknytning / NUK follow-up; keep provenance.

**Public contact (only published / listed).**
- kunde@vissi.no — listed
- post@vissi.no — listed
- Telephone: 77 77 04 00
- HQ: Sørkjosen
- Org: 921683057
- Do not invent extra project inboxes.

**Key facts.**
- Hovedkontor printed: Bjørklysvingen 3, 9152 Sørkjosen. Montørstasjoner in Birtavarre, Skjervøy and Kautokeino.
- Nettutreder in Arva NUK Troms; not a second NUK seat.
- Own modenhetsmatrise and >0,5 MW process are printed on the tilknytning page.

**Sources opened 2026-08-27.**
- https://www.vissi.no/priser-og-vilkar/tilknytning/
- https://www.vissi.no/om-oss/
- https://www.vissi.no/kontakt-oss/
- https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
- https://data.brreg.no/enhetsregisteret/api/enheter/921683057

---

## 43. Elinett AS — NUK Romsdal og Nordmøre + PlanNett

**Why they would pay.** Elinett (former Istad Nett) is NVE's nettutviklingskoordinator for Romsdal og Nordmøre. The energiutredninger page (updated 07.08.2026) prints that KSU / utredningsansvarlig was avviklet 1.3.2024 and that Elinett is nettutreder for eget nett plus NUK for Romsdal og Nordmøre; Sunnmøre is now Linja's NUK. PlanNett is printed as the sentral plattform. Those NUK / PlanNett roles consume Statnett områdeplaner, municipal plans and SSB series that do not all live on elinett.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace PlanNett.

**Concrete use case.** An utredning officer needs a municipal arealplan or Statnett områdeplan layer for Romsdal / Nordmøre that is not in Elinett's own områdestudie, fetched as rows/features with license before later PlanNett / KVU.

**Search → fetch → later analysis.**
- Search: Romsdal / Nordmøre / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: NUK / PlanNett; keep provenance.

**Public contact (only published / listed).**
- nettservice@elinett.no — printed on kontakt
- nett@elinett.no — listed
- Telephone: 71 21 35 00 / 71 21 35 05
- Org: 979379455
- Do not invent named-person emails. The opened pages print functional inboxes, not personal ones.

**Key facts.**
- Besøksadresse printed: Plutovegen 5, Molde.
- Former Istad Nett. Last RKSU Møre og Romsdal July 2022 (previous forskrift); those PDFs are no longer public after kraftsensitiv §6-2 from 1.1.2025.
- Tilknytning page splits <100 kW / 100–999 kW / ≥1 MW.

**Sources opened 2026-08-27.**
- https://www.elinett.no/om-oss/kraftsystemutredning
- https://www.elinett.no/om-oss/kontakt
- https://www.elinett.no/kunde/tilknytning-til-stroemnettet
- https://data.brreg.no/enhetsregisteret/api/enheter/979379455

---

## 44. Linja AS — NUK Sunnmøre og Sogn og Fjordane + PlanNett / Tilko >1 MW

**Why they would pay.** Linja (former Mørenett) is NVE's nettutviklingskoordinator for Sunnmøre og Sogn og Fjordane. This is not Linea AS (Helgeland, already in this book). PlanNett is the NVE portal for områdestudier; Tilko is printed for tilknytning >1 MW. Those NUK / PlanNett / Tilko roles consume Statnett områdeplaner, municipal plans and SSB series that do not all live on linja.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace Tilko or PlanNett.

**Concrete use case.** A tilknytning / nettutvikling officer needs a municipal arealplan or Statnett områdeplan layer for Sunnmøre / Sogn og Fjordane that is not in Linja's own PlanNett file, fetched as rows/features with license before later Tilko / KVU.

**Search → fetch → later analysis.**
- Search: Sunnmøre / Sogn og Fjordane / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: NUK / PlanNett / Tilko; keep provenance.

**Public contact (only published / listed).**
- sindre.nordang@linja.no — listed
- atle.isaksen@linja.no — listed
- post@linja.no — printed on kontakt-oss for brev og administrative henvendelser (not kundeservice)
- Org: 912631532
- Do not use firmapost@morenett.no. That address is stale (Mørenett).

**Key facts.**
- Hovudkontor printed: Industrivegen 6, 6080 Gurskøy (Dragsund). Post: Langemyra 6, 6160 Hovdebygda.
- Not Linea AS (org 917424799, Mosjøen / Helgeland).
- Elinett's energiutredninger page also names Linja as NUK for Sogn og Fjordane og Sunnmøre.

**Sources opened 2026-08-27.**
- https://www.linja.no/kontakt-oss
- https://plannett.nve.no/
- https://data.brreg.no/enhetsregisteret/api/enheter/912631532

---

## 45. Jæren Everk AS — PlanNett actor + Lnett NUK Sør-Rogaland + anleggsbidrag

**Why they would pay.** Jæren Everk is a PlanNett actor inside Lnett's NVE NUK Sør-Rogaland area. The anleggsbidrag page prints that anleggsbidrag applies at all nettnivå. Those PlanNett / NUK-area / anleggsbidrag roles consume Statnett, NVE PlanNett, municipal and SSB series that do not all live on jev.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace PlanNett or the anleggsbidrag kalkyle.

**Concrete use case.** A tilknytning / nettutvikling officer needs a municipal arealplan or Statnett områdeplan layer for the Jæren / Sør-Rogaland area that is not in Jæren Everk's own PlanNett file, fetched as rows/features with license before later anleggsbidrag / NUK overlay.

**Search → fetch → later analysis.**
- Search: Jæren / Hå / Sør-Rogaland / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: PlanNett / anleggsbidrag / NUK follow-up; keep provenance.

**Public contact (only published / listed).**
- post@jev.no — printed on kontakt-oss
- Telephone: 51 79 95 00
- Org: 824914982
- Do not invent extra project inboxes.

**Key facts.**
- Besøksadresse printed: Bernervegen 28, 4365 Nærbø. Postboks 55, 4367 Nærbø.
- PlanNett actor; Lnett is NUK Sør-Rogaland. Anleggsbidrag is printed for all nettnivå.

**Sources opened 2026-08-27.**
- https://jev.no/kontakt-oss
- https://jev.no/anleggsbidrag
- https://plannett.nve.no/
- https://data.brreg.no/enhetsregisteret/api/enheter/824914982

---

## 46. Midtnett AS — PlanNett + Tilko >1 MW + Glitre NUK Buskerud

**Why they would pay.** Midtnett is a PlanNett actor inside Glitre Nett's NVE NUK Buskerud area. Tilko is printed for tilknytning >1 MW. Those PlanNett / Tilko / NUK-area roles consume Statnett områdeplaner, municipal plans and SSB series that do not all live on midtnett.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace Tilko or PlanNett.

**Concrete use case.** A tilknytning / nettutvikling officer needs a municipal arealplan or Statnett områdeplan layer for the Midtnett / Buskerud area that is not in Midtnett's own PlanNett file, fetched as rows/features with license before later Tilko / KVU.

**Search → fetch → later analysis.**
- Search: Modum / Buskerud / kommune + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: PlanNett / Tilko / NUK; keep provenance.

**Public contact (only published / listed).**
- post@midtnett.no — listed
- kunde@midtnett.no — listed
- Telephone: 32 78 32 98
- Org: 917856222
- Do not invent extra project inboxes.

**Key facts.**
- Forretningsadresse printed: Øvre Nedmarken 15, 3370 Vikersund.
- PlanNett actor; Glitre Nett is NUK Buskerud. Tilko for >1 MW.

**Sources opened 2026-08-27.**
- https://plannett.nve.no/
- https://data.brreg.no/enhetsregisteret/api/enheter/917856222

---

## 47. S-Nett AS — printed modenhetsvurdering + Elinett NUK Romsdal og Nordmøre

**Why they would pay.** S-Nett prints a modenhetsvurdering. It sits inside Elinett's NVE NUK Romsdal og Nordmøre area. Those tilknytning / NUK-area roles consume Statnett, NVE PlanNett, municipal and SSB series that do not all live on snett.no. They would pay to search and fetch those rows with provenance, then later feed prognoser — not to replace the modenhetsvurdering.

**Concrete use case.** A nettutreder officer needs a municipal arealplan or Statnett områdeplan layer for the S-Nett / Romsdal og Nordmøre area that is not in S-Nett's own tilknytning file, fetched as rows/features with license before later modenhetsvurdering / NUK overlay.

**Search → fetch → later analysis.**
- Search: Surnadal / Rindal / Heim / Romsdal / Nordmøre + arealplan / industri / effekt with publisher (Statnett, NVE, kommune, SSB).
- Fetch: first rows / features from the recorded access path.
- Later analysis: modenhetsvurdering / NUK follow-up; keep provenance.

**Public contact (only published / listed).**
- nettkunde@snett.no — listed
- Telephone: 71 65 91 00
- Org: 923819177
- Do not use nett@svorka.no. That address is leftover (Svorka).

**Key facts.**
- Forretningsadresse printed: Svartvassvegen 6, 6650 Surnadal.
- Printed modenhetsvurdering. Elinett is NUK Romsdal og Nordmøre.

**Sources opened 2026-08-27.**
- https://www.snett.no/
- https://data.brreg.no/enhetsregisteret/api/enheter/923819177

---

### Barents Nett AS

- **Why they would pay.** NVE NUK for Finnmark (minus Vissi’s slivers in Kautokeino / Loppa; plus Alut’s sliver in Kvænangen). Named programme: Tilko for ≥1 MW + Fornybar Norge modenhetsmatrise — «Alle søknader på 1 MW eller mer og modenhetsvurderinger går gjennom Tilko.» Køordning: umodne projects block modnere ones; every uttak >5 MW or 20 GWh/year must be approved by Barents Nett and Statnett; forespurt lokasjon «skal være regulert for formålet». WattApp is the printed kapasitetskart (NVE § 15). DF-vurdering from 1 Jan 2026. Dialogmøte Kirkenes 16 Jan 2025 on Områdeplan Nord. ~17 500 nettkunder; ~70 ansatte; HQ Vadsø; ~550 km regionalnett + ~2750 km fordelingsnett; Plan/prosjekt avdeling. 100 % Varanger Kraft AS. Those NUK / Tilko / DF files pull Statnett Områdeplan Nord, NVE PlanNett / Atlas, municipal arealplan, FeFo / Sametinget and SSB that WattApp does not host.
- **Concrete use case.** Plan/prosjekt first-fetches Statnett Områdeplan Nord / KVU, NVE PlanNett / Atlas, kommuneplan/regulering, Seeiendom / Geonorge, FeFo / Sametinget / Statsforvalter and SSB for a named Finnmark NUK områdestudie or Tilko ≥1 MW sak (Skaidi–Varangerbotn 420 kV interface, Kirkenes / Sør-Varanger industri, or Vadsø–Båtsfjord regionalnett) so the modenhetsmatrise and PlanNett drop cite official rows.
- **How the service should look.**
  - Search: data.norge first, then PlanNett, Statnett, Geonorge / municipal plan, SSB. Queries such as «NVE PlanNett områdestudie Finnmark / Vadsø / Sør-Varanger», «Statnett Områdeplan Nord / KVU Skaidi–Varangerbotn».
  - Fetch: first official rows / GeoJSON / PDF. Not a replacement for Tilko, WattApp, Elsmart or own NIS.
  - Later analysis: corridor overlay of plan + hazard + SSB against WattApp and the ≥1 MW kø. Out of first-fetch scope.
- **Public contact.**
  - Role / unit: kundeservice. No named-person emails printed (Jens Betsi quote only). Leftover `firmapost@varanger-kraft.no` unused.
  - Email: `kundeservice@barents-nett.no`
  - Phone: 78 96 26 10
  - Form/URL: https://www.barents-nett.no/kontakt/
- **Key facts.** Org.nr 971 058 854. Nyborgveien 70, 9800 Vadsø. Kommune 5607. Historisk navn VARANGER KRAFTNETT AS (to 28.01.2022). NUK Finnmark.
- **Sources** (opened 2026-08-27).
  - https://www.barents-nett.no/
  - https://www.barents-nett.no/om-barents-nett/
  - https://www.barents-nett.no/kontakt/
  - https://www.barents-nett.no/aktuelt/barents-nett-tar-i-bruk-tilko-ny-nasjonal-losning-for-nettilknytning
  - https://www.barents-nett.no/kundeservice/bygge-grave-rive/tilknytning-til-nett-storre-anlegg/modenhetsvurderinger/
  - https://www.barents-nett.no/kundeservice/bygge-grave-rive/koordning-for-storre-tilknytninger-til-stromnettet/
  - https://www.barents-nett.no/kundeservice/bygge-grave-rive/tilknytning-til-nett-storre-anlegg/kapasitetskart/
  - https://www.barents-nett.no/kundeservice/bygge-grave-rive/tilknytning-til-nett-storre-anlegg/driftsmessig-forsvarlig-vurdering-df-vurdering/
  - https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
  - https://veiledere.nve.no/forskrift-om-energiutredninger/ledig-kapasitet/
  - https://plannett.nve.no/
  - https://virksomhet.brreg.no/nb/oppslag/enheter/971058854
  - https://data.brreg.no/enhetsregisteret/api/enheter/971058854

### Noranett AS

- **Why they would pay.** NVE NUK for Nordre-Nordland og Sør-Troms. Named programme: Tilko for ≥1 MW — «Noranett bruker Tilko – bransjens felles portal for større tilknytninger.» DF-vurdering + utredningsavtale; normalt forbruk under 1 MW; vestsnittet already at a 1 MW Statnett floor. Joint Vestall / Elmea press: innmeldt fremtidig effektbehov «om lag 1300 MW»; first byggetrinn 420 kV Kvandal–Kilbotn. Lødingen trafo + 16 km for Torghatten Nord’s 9,2 MW elferge. After Nordkraft / Trollfjord / Andøy Energi fusion the three grids stay separate legal persons; NUK seat is Noranett AS (Hålogaland) — Hadsel / Andøy are sister DSOs, not this seat. Combined brand «om lag 52 000» kunder; Noranett AS ca. 42 000 / 4 200 km / 1 147 GWh. Those NUK / Tilko / DF / KVU files pull Statnett Områdeplan Nord / Kvandal–Kilbotn, NVE PlanNett / Atlas, municipal arealplan and SSB that Serviceportal / Tilko do not host.
- **Concrete use case.** Nettplan / NUK first-fetches NVE PlanNett, Statnett Områdeplan Nord / KVU Kvandal–Kilbotn, municipal arealplan/regulering and SSB for a named NUK områdestudie or DF / Tilko ≥1 MW sak (Lødingen trafo + 9,2 MW elferge, Harstad / vestsnittet, or the 420 kV first byggetrinn) so the DF note and the NUK annual meeting cite official rows.
- **How the service should look.**
  - Search: data.norge first, then PlanNett, Statnett, Geonorge / municipal plan, SSB. Queries such as «NVE PlanNett områdestudie Nordre-Nordland / Sør-Troms / Harstad / Narvik», «Statnett KVU Kvandal Kilbotn / Områdeplan Nord».
  - Fetch: first official PDF / GeoJSON / table. Not a replacement for Tilko, Serviceportal, Elsmart, Elwin or own NIS.
  - Later analysis: overlay municipal + NVE + Statnett layers on the vestsnittet 1 MW kø and the Lødingen / Kvandal–Kilbotn files. Out of first-fetch scope.
- **Public contact.**
  - Role / unit: Hålogaland / Noranett AS. Hadsel and Andøy stay on their own printed addresses and are not this seat. No mailbox for Molund or Brendvik.
  - Email: `haalogaland@noranett.no`
  - Phone: 77 04 26 26
  - Form/URL: https://www.noranett.no/kontakt-oss/
- **Key facts.** Org.nr 985 411 131. Rødbergveien 14, 9408 Harstad. Kommune 5503. Historisk navn HÅLOGALAND KRAFT NETT AS (to 06.03.2023). NUK Nordre-Nordland og Sør-Troms. Sister DSOs Noranett Hadsel AS and Noranett Andøy AS are not this seat.
- **Sources** (opened 2026-08-27).
  - https://www.noranett.no/
  - https://www.noranett.no/om-noranett/
  - https://www.noranett.no/kontakt-oss/
  - https://www.noranett.no/media/artikler/noranett-tar-i-bruk-tilko-for-storre-tilknytninger
  - https://www.noranett.no/nettjenester/bygge-nytt-rive-grave-endre/driftsmessig-forsvarlig-vurderinger/
  - https://www.noranett.no/media/pressemeldinger/uenighet-om-veien-videre-for-stromnettet-i-nord
  - https://www.noranett.no/media/pressemeldinger/felles-pressemelding-fra-noranett-vestall-og-elmea
  - https://www.noranett.no/media/pressemeldinger/betydelig-mer-nettkapasitet-i-lodingen
  - https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
  - https://plannett.nve.no/
  - https://virksomhet.brreg.no/nb/oppslag/enheter/985411131
  - https://data.brreg.no/enhetsregisteret/api/enheter/985411131

### Enida AS

- **Why they would pay.** PlanNett actor (ENIDA AS 918312730 on the public aktørliste — anleggskonsesjon over 46 kV). Not the NUK; sits inside Lnett’s NUK Sør-Rogaland (Eigersund, Bjerkreim, Lund, Sokndal). Named programme: Tilko for ≥1 MW — «sømløs koordinering mellom Statnett og andre nettselskaper»; «bedre datagrunnlag for nettplanlegging og kapasitetsvurderinger»; støtte for myndighetspålagte modenhetsvurderinger. Avdelingsleder Plan og Prosjekt Karl-Einar Svendsen (`kes@enida.no`). Second programme: 132 kV Kjelland–Kaupanes (Eigerøy) + Kaupanes TS konsesjon; NVE, Eigersund kommune and Statsforvalteren i Rogaland have already moved the trasé (fuglefredningsområde at Fotlandsvatnet). Those KU / Tilko / PlanNett files pull Statnett områdeplan Sør-Rogaland, Lnett NUK layers, NVE PlanNett / Atlas, municipal arealplan and SSB that Tilko does not host.
- **Concrete use case.** Plan og Prosjekt first-fetches Statnett områdeplan Sør-Rogaland, NVE PlanNett / Atlas, Eigersund kommuneplan/regulering, Statsforvalter / fuglefredning and Seeiendom for the Kjelland–Kaupanes 132 kV / Kaupanes TS file (or the next ≥1 MW Tilko sak on Eigerøy industri) so the revised konsesjonssøknad and the PlanNett tiltak cite official rows.
- **How the service should look.**
  - Search: data.norge first, then PlanNett, Statnett Sør-Rogaland, Geonorge / Eigersund plan, SSB. Queries such as «NVE PlanNett tiltak Dalane / Eigerøy / Eigersund», «Statnett områdeplan Sør-Rogaland», «kommuneplan Kaupanes / Eigerøy industri».
  - Fetch: first official PDF / GeoJSON / table. Not a replacement for Tilko, Elsmart or Enida’s kundeportal.
  - Later analysis: overlay municipal + NVE + Statnett layers on the two Eigerøy traséalternativer and the ≥1 MW kø. Out of first-fetch scope.
- **Public contact.**
  - Role / unit: firmapost / Plan og Prosjekt. Do not invent a mailbox for Hjørungnes.
  - Email: `firmapost@enida.no`; `kes@enida.no` (Karl-Einar Svendsen, avdelingsleder Plan og Prosjekt)
  - Phone: sentralbord 51 46 25 01; Svendsen 476 29 881
  - Form/URL: https://enida.no/kontaktinfo
- **Key facts.** Org.nr 918 312 730. Elganeveien 1, 4373 Egersund. Kommune 1101. Historisk navn DALANE NETT AS (to 19.08.2020). 39 ansatte. PlanNett aktør. Sits in Lnett NUK Sør-Rogaland. Not the NUK.
- **Sources** (opened 2026-08-27).
  - https://enida.no/
  - https://enida.no/str%C3%B8mtilknytning-st%C3%B8rre-eller-lik-1-megawatt
  - https://enida.no/t-dag-i-enida
  - https://enida.no/ny-hoyspentledning-til-eigeroy
  - https://enida.no/kontaktinfo
  - https://plannett.nve.no/
  - https://plannett.nve.no/aktoerliste
  - https://veiledere.nve.no/forskrift-om-energiutredninger/roller/nettutviklingskoordinator/
  - https://virksomhet.brreg.no/nb/oppslag/enheter/918312730
  - https://data.brreg.no/enhetsregisteret/api/enheter/918312730

---

## 48. Fredrikstad kommune — Åpne data Hub + kart@

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

## 49. Sandnes kommune — Prinsipp 6 «Vi deler og tar i bruk åpne data»

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

## 50. Bodø kommune — Bodøkart + Geonorge

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

## 51. Kristiansand kommune — Økonomiplan 2026–2029 (datadeling + klimabudsjett)

**Why they would pay.** Økonomiplan 2026–2029, vedtatt bystyret 17.12.2025, is the current mandate — not only the 2022 *Smartere sammen* title. Kap. 5.4 («Kristiansand kommune skal være en digital og innovativ organisasjon») prints the focus area «Økt datadeling og utnytte mulighetene i data»: data shall be tilgjengelige, gjenfinnbare, mulig å bruke and kunne sammenstilles so they give verdi in tjenesteutvikling; «Det bør etableres tydeligere interne retningslinje for hvordan man må gå frem for å få tilgang til data.» Kap. 6 uses Miljødirektoratets kommunefordelte klimagassstatistikk as basisgrunnlaget for the municipal klimabudsjett (Klima- og miljøbarometeret is the published indicator surface). They would pay to find and fetch those Miljødirektoratet / SSB / neighbour series with provenance, then later sammenstille them — the printed gap is gjenfinnbarhet, access rules and sammenstilling, not another strategy PDF.

**Concrete use case.** Klima / digitalisering needs the latest Miljødirektoratet kommunefordelte tall and related SSB series for the next klimabudsjett and barometer update, fetched as rows with license and access path before later overlay on Kap. 6 sectors (veitrafikk, industri, annen mobil forbrenning, jordbruk).

**Search → fetch → later analysis.**
- Search: Kristiansand + klimagass / veitrafikk / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett / Klima- og miljøbarometeret; do not invent tonnes.

**Public contact (only published / listed).**
- post@kristiansand.kommune.no — printed on kontakt-oss and on the barometer footer
- post.byutvikling@kristiansand.kommune.no — printed on the klima- og miljøstrategi page (Klima og arealutvikling)
- Org: 820852982
- Do not invent a digitalisering or klima inbox.

**Key facts.**
- Økonomiplan 2026–2029: bystyret 17. desember 2025. Kap. 5.4 also names Kommune Los 4.0 / Støtte Los and a new municipal architecture-principles veileder.
- Kap. 6.4: Miljødirektoratets kommunefordelte statistikk «publiseres årlig og utgjør basisgrunnlaget for Kristiansands klimabudsjett.» 2022–2023: 10,4 % reduction year-on-year (printed).
- Klima- og miljøbarometeret: samfunn vs organisasjon views; page updated 10. november 2025. Postboks 4, 4685 Nodeland; kommunenummer 4204.

**Sources opened 2026-08-27.**
- https://www.kristiansand.kommune.no/contentassets/712daaa8832d482180d6d7cfd9ef1c38/okonomiplan-2026-2029---kristiansand-kommune.pdf
- https://www.kristiansand.kommune.no/kontakt-oss
- https://www.kristiansand.kommune.no/navigasjon/bolig-kart-og-eiendom/miljo-og-klima/klima--og-miljoledelse/klimaogmiljostrategi/
- https://www.baerekraftigkristiansand.no/temasider/klima-og-miljobarometer
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/820852982

---

## 52. Lillestrøm kommune — digitalisering 2020–2025 + klimabudsjett

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

## 53. Tønsberg kommune — HØP 2026–2029 klimabudsjett

**Why they would pay.** Kommuneplanens handlingsdel og økonomiplan (HØP) 2026–2029 prints a klimabudsjett and the 60 percent cut by 2030. The same document says Tønsberg «ligger langt etter» that mål. For 2026, Plan, eiendom og teknikk is named as ansvarlig to «Evaluere hvordan klimabudsjettet kan være et relevant og effektivt verktøy». They would pay to find and fetch Miljødirektoratet kommunefordelte klimagassstatistikk, SSB and neighbour Vestfold series with provenance so that 2026 evaluation has actual rows — not another strategy PDF.

**Concrete use case.** Plan, eiendom og teknikk evaluates the klimabudsjett as a styringsverktøy and needs the latest municipal GHG inventory and related SSB series for Tønsberg, fetched as rows with license and access path before later overlay on the 2030 60 percent bane.

**Search → fetch → later analysis.**
- Search: Tønsberg + klimagass / veitrafikk / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed the 2026 klimabudsjett evaluation; do not invent tonnes.

**Public contact (only published / listed).**
- postmottak@tonsberg.kommune.no — printed on kontakt-oss
- Telephone: 33 40 60 00
- Org: 921383681
- Kommunenummer: 3905
- Do not invent a klima or plan inbox.

**Key facts.**
- Postboks 2410, 3104 Tønsberg; Halfdan Wilhelmsens alle 1 C, 3110 Tønsberg.
- HØP 2026–2029 / budsjett 2026 is the current mandate; klimabudsjett is a named chapter.
- 2026 tool-evaluation is assigned to Plan, eiendom og teknikk.

**Sources opened 2026-08-27.**
- https://www.tonsberg.kommune.no/_f/p1/i36860351-6702-4da2-9ba7-c50861540221/kommuneplanens-handlingsdel-og-okonomiplan-2026-2029.pdf
- https://www.tonsberg.kommune.no/tjenester/tonsberg-kommune-organisasjon-og-administrasjon/budsjett-handlingsprogram-og-okonomirapporter/
- https://www.tonsberg.kommune.no/tjenester/kontakt-oss/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/921383681

---

## 54. Larvik kommune — KEP 2026–2029 + årlige klimabudsjett in HØP

**Why they would pay.** Klima- og energiplan (KEP) 2026–2029 is the named climate programme. The høring page prints that Larvik operasjonaliserer KEP-oppdrag with konkrete tiltak årlig through klimabudsjett, økonomiplan and virksomhetsplan. HØP 2026–2029 was vedtatt as KST-230/25; that PDF lists Klimabudsjett as a chapter in the web-utgave. They would pay to find and fetch Miljødirektoratet / SSB series with provenance for the next årlige klimabudsjett — not another KEP PDF.

**Concrete use case.** Klima / miljø needs the latest kommunefordelte klimagassstatistikk and related SSB series for Larvik, fetched as rows with license and access path before later overlay on the årlige klimabudsjett in HØP.

**Search → fetch → later analysis.**
- Search: Larvik + klimagass / energi / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett / KEP indicators; do not invent tonnes.

**Public contact (only published / listed).**
- postmottak@larvik.kommune.no — printed on kontakt-oss / innbyggerkontakt
- miljo@larvik.kommune.no — printed on the KEP 2026–2029 høring page
- Telephone: 33 17 10 00
- Org: 918082956
- Do not invent a klimabudsjett inbox.

**Key facts.**
- Postboks 2020, 3255 Larvik; Feyers gate 7.
- KEP 2026–2029: høring frist 12. desember 2025; kommunestyret vedtok 11. februar 2026 (printed on the KEP page).
- HØP 2026–2029: KST-230/25; klimabudsjett chapter in the web-utgave.

**Sources opened 2026-08-27.**
- https://www.larvik.kommune.no/media/gdjlfx3a/handlings-og-oekonomiplan-2026-2029-kommunestyrets-vedtak.pdf
- https://www.larvik.kommune.no/politikk/hoeringer/hoeringer-arkiv/hoering-klima-og-energiplan-2026-2029/
- https://www.larvik.kommune.no/miljoe-natur-og-landbruk/klima-og-energiplan/
- https://www.larvik.kommune.no/administrasjon/kontakt-oss/innbyggerkontakt/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/918082956

---

## 55. Porsgrunn kommune — HP 2026–2029 Klimabudsjett chapter

**Why they would pay.** Handlingsprogram 2026–2029 (bystyret 11.12.2025) has a named Klimabudsjett chapter from s. 54 (Kommunens klimamål; Klimastatus from s. 55; Klimatiltak from s. 58). The opened PDF (s. 16–17) prints that Porsgrunn already has «en rekke gode klimatiltak, både for direkte utslipp og klimafotavtrykket fra kommunen som egen virksomhet», but «for å nå klimamålene kreves det flere og mer målrettede tiltak framover». It also prints 500 000 kroner to start revisjon of klima- og energiplanen (verbalvedtak 2024; today's KEP lasted to 2025; table line «Klima- og energiplan 500» in 1 000 kroner). They would pay to find and fetch Miljødirektoratet / SSB series with provenance for that klimabudsjett and the KEP revision — not another HP PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Porsgrunn, fetched as rows with license and access path before later overlay on the HP Klimabudsjett chapter (from s. 54).

**Search → fetch → later analysis.**
- Search: Porsgrunn + klimagass / energi / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett / KEP revision; do not invent tonnes.

**Public contact (only published / listed).**
- postmottak@porsgrunn.kommune.no — printed on kontakt-oss
- Telephone: 35 54 70 00
- Org: 939991034
- Kommunenummer: 4001
- Do not invent a klima inbox.

**Key facts.**
- Postboks 128, 3901 Porsgrunn; Storgata 153.
- HP 2026–2029: bystyret 11.12.2025. Klimabudsjett chapter opened from s. 54 of the vedtatt PDF.
- 500 000 kroner for KEP revision is printed in the opened HP PDF.

**Sources opened 2026-08-27.**
- https://www.porsgrunn.kommune.no/organisasjon/oekonomi-og-planer/handlingsprogram-2026-2029-med-budsjett-2026/
- https://www.porsgrunn.kommune.no/kontakt-oss/
- https://www.porsgrunn.kommune.no/media/fpqlkox3/hp-2026-2029-bystyrets-vedtak-11122025-v3.pdf
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/939991034

---

## 56. Sarpsborg kommune — Plattform for digitalisering + KDP klima og energi

**Why they would pay.** *Plattform for digitalisering*, vedtatt bystyret 02.02.2023, is the named digital mandate. Kap. 1.3 («Deling og gjenbruk av data») says the municipality shall legge til rette for deling og gjenbruk, including data it produces or henter from other sources, and follow Digitaliseringsdirektoratet «orden i eget hus». Kap. 3.2 («Samarbeid og verdiskapning») prints that Sarpsborg shall «sørge for løsninger som enkelt gir næringslivsaktører tilgang til kommunens åpne data». Kap. 4.2 («Informasjonssikkerhet») prints «dele data når den kan og skjerme data når den må». Virksomhet Digitalisering (virksomhetsleder Atle Johnsen) owns the platform work. *Kommunedelplan klima og energi 2021–2030* (bystyret 17.06.2021) prints a klimabudsjett as part of the handlingsdel and cites Miljødirektoratet municipal GHG calculations plus SSB. They would pay to find and fetch those national series and other-municipality open datasets with provenance — not another municipal portal.

**Concrete use case.** Virksomhet digitalisering / klima needs the latest Miljødirektoratet kommunefordelte tall and related SSB series for Sarpsborg, plus a neighbour Østfold open dataset that matches a local tjeneste, fetched as rows with license and access path before later gjenbruk.

**Search → fetch → later analysis.**
- Search: Sarpsborg + klimagass / «åpne data» / KOSTRA with publisher (Miljødirektoratet, SSB, neighbour kommuner).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett / platform gjenbruk; do not invent tonnes or invent a portal.

**Public contact (only published / listed).**
- atle.johnsen@sarpsborg.com — listed
- postmottak@sarpsborg.com — printed on the digitalisering page
- servicetorget@sarpsborg.com — printed on the digitalisering page
- Telephone: 90 75 40 33 (Johnsen, printed as virksomhetsleder) / 69 10 80 00 (sentralbord / servicetorget, printed on the same page)
- Org: 938801363
- Kommunenummer: 3105
- Do not invent an åpne-data inbox.

**Key facts.**
- Postboks 237, 1702 Sarpsborg; Glengsgata 38, 1706 Sarpsborg.
- Plattform PDF title block: Bystyrets vedtak 02.02.2023.
- KDP klima og energi vedtatt 17.06.2021; klimabudsjett is printed as part of the handlingsdel and cites Miljødirektoratet + SSB.

**Sources opened 2026-08-27.**
- https://www.sarpsborg.com/globalassets/dokumenter/politikk-og-planer/andre-planer/digitaliseringsstrategi-bystyrets-vedtak-2023.pdf
- https://www.sarpsborg.com/byen-og-kommunen/om-organisasjonen/digitalisering/
- https://www.sarpsborg.com/globalassets/dokumenter/byggesak-og-teknisk/forurensning-klima-og-miljo/kommunedelplan-klima-og-energi-2021-2030-sarpsborg-kommune-2.pdf
- https://virksomhet.brreg.no/nb/oppslag/enheter/938801363

---

## 57. Skien kommune — HP 2026–2029 Framsikt klimabudsjett

**Why they would pay.** Handlings- og økonomiplan 2026–2029 (Framsikt klimabudsjett) is the current mandate. The climatesummary prints that yearly Klimakost stopped after 2023, a 7 mill. kr pot, and that the municipality needs arealverktøy. The older HP 2025–2028 PDF still cites Miljødirektoratet kommunefordelte geografiske utslipp. They would pay to find and fetch the latest Miljødirektoratet / SSB / areal series with provenance for that 2026–2029 klimabudsjett and the missing arealverktøy — not another HP PDF.

**Concrete use case.** Klima / OU needs the latest Miljødirektoratet kommunefordelte tall and related SSB / areal series for Skien, fetched as rows with license and access path before later overlay on the HP 2026–2029 klimabudsjett and the printed arealverktøy gap.

**Search → fetch → later analysis.**
- Search: Skien + klimagass / veitrafikk / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed the HP 2026–2029 klimabudsjett / arealverktøy; do not invent tonnes.

**Public contact (only published / listed).**
- post@skien.kommune.no — printed on kontakt-oss
- servicesenteret@skien.kommune.no — printed on the same page for Skien servicesenter
- Telephone: 35 58 10 00
- Org: 938759839
- Kommunenummer: 4003
- Do not invent a klima or digitalisering inbox. Do not invent a digitaliseringsstrategi contact.

**Key facts.**
- Postboks 158, 3701 Skien; servicesenter Henrik Ibsensgate 2.
- HP 2026–2029 Framsikt klimabudsjett: yearly Klimakost stopped after 2023; 7 mill. kr pot; needs arealverktøy.
- Older HP 2025–2028 PDF still prints a 35 percent cut from 2015 by end of 2025 (geografiske utslipp). Digitaliseringsstrategi in that PDF is announced, not vedtatt.

**Sources opened 2026-08-27.**
- https://pub.framsikt.net/2026/skien_gmltenant/bm-2026-hop_2026_til_2029/#/generic/summary/climatesummary
- https://www.skien.kommune.no/media/vxdlsbdv/handlingsprogram-og-oekonomiplan-2025-2028.pdf
- https://skien.kommune.no/administrasjon/kontakt-oss/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/938759839

---

## 58. Moss kommune — ØP 2026–2029 Klimabudsjett

**Why they would pay.** Økonomiplan 2026–2029 prints a Klimabudsjett. The 60 percent cut in direkte utslipp by 2030 (referanseår 2016) is the named mål; framskrivninger with today's tiltak reach about 45–49 percent by 2030. Miljødirektoratet kommunefordelte klimagassstatistikk is the printed source for those geografiske utslipp. The klimabudsjett page says the budget is integrert in the ordinære økonomiplanen. They would pay to find and fetch the latest Miljødirektoratet / SSB series with provenance so the 60 percent vs 45–49 percent gap has actual rows — not another ØP PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Moss (knr 3103), fetched as rows with license and access path before later overlay on the ØP 2026–2029 klimabudsjett (veitrafikk is printed as the largest source, 41 percent in 2023).

**Search → fetch → later analysis.**
- Search: Moss + klimagass / veitrafikk / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett; do not invent tonnes.

**Public contact (only published / listed).**
- post@moss.kommune.no — printed on personvern
- Telephone: 69 24 80 00
- Org: 920817521
- Kommunenummer: 3103
- Do not invent a klima inbox.

**Key facts.**
- Postboks 175, 1501 Moss on the personvern page.
- 60 percent / 2030 vs ~45–49 percent path is printed in the ØP 2026–2029 climatesummary / fremlegg. Mdir is the printed inventory source.
- Klimabudsjett is a named chapter of the økonomiplan, not a separate portal.

**Sources opened 2026-08-27.**
- https://www.moss.kommune.no/alle-tjenester/natur-klima-og-miljo/klima/klimabudsjett/
- https://pub.framsikt.net/2026/moss/bm-2026-okonomiplan_2026-2029/#/generic/summary/climatesummary
- https://www.moss.kommune.no/personvern/
- https://www.miljodirektoratet.no/tjenester/klimagassutslipp-kommuner/?area=3103&sector=-2
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/920817521

---

## 59. Haugesund kommune — Budsjett 2026 Klimabudsjett

**Why they would pay.** Budsjett 2026 / Handlings- og økonomiplan 2026–2029, vedtatt kommunestyret 10.12.2025, has a named Klimabudsjett chapter in the Framsikt climatesummary. That is the current mandate. They would pay to find and fetch Miljødirektoratet kommunefordelte klimagassstatistikk and related SSB series with provenance for that chapter — not another budget PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Haugesund (knr 1106), fetched as rows with license and access path before later overlay on the 2026 Klimabudsjett chapter.

**Search → fetch → later analysis.**
- Search: Haugesund + klimagass / energi / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett; do not invent tonnes.

**Public contact (only published / listed).**
- postmottak@haugesund.kommune.no — printed on contact-us
- hos@haugesund.kommune.no — printed on the same page for the service centre / Kirkegata 85
- Telephone: 21 04 33 00
- Org: 944073787
- Kommunenummer: 1106
- Do not invent a klima inbox.

**Key facts.**
- Postboks 2160, 5504 Haugesund; Kirkegata 85, 5528 Haugesund.
- Vedtak 10.12.2025 (sak 70/2025). Framsikt document: bm-2026-hkbud2026.
- Klimabudsjett is a named chapter of the vedtatt 2026 budget, not a separate portal.

**Sources opened 2026-08-27.**
- https://pub.framsikt.net/2026/haugesund/bm-2026-hkbud2026/#/generic/summary/climatesummary
- https://www.haugesund.kommune.no/organisasjonen/planer-og-rapporter/budsjett-og-okonomiplan/budsjett-og-okonomiplaner/
- https://www.haugesund.kommune.no/welcome-to-haugesund/contact-us/
- https://data.brreg.no/enhetsregisteret/oppslag/enheter/944073787

---

## 60. Molde kommune — KEP 2023–2035 klimabudsjett + Smart data

**Why they would pay.** Klimabudsjett is the yearly handlingsdel of Klima- og energiplan 2023–2035. The 2024 HØP klimabudsjett chapter plots Miljødirektoratet kommunefordelte tall. The Smart data page prints «dele data med viktige interessenter» as a named reason for the project. The 2026 klimabudsjett chapter was not opened — do not invent 2026 cells. They would pay to find and fetch the latest Miljødirektoratet / SSB series with provenance for that yearly handlingsdel — not another KEP PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Molde (knr 1506), fetched as rows with license and access path before later overlay on the yearly klimabudsjett.

**Search → fetch → later analysis.**
- Search: Molde + klimagass / veitrafikk / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed the yearly klimabudsjett; do not invent tonnes. Do not invent 2026 cells.

**Public contact (only published / listed).**
- postmottak@molde.kommune.no — printed on skriv-til-oss
- Telephone: 71 11 10 00
- Org: 921221967
- Kommunenummer: 1506
- Do not invent a klima or smart-data inbox.

**Key facts.**
- Klimabudsjett is the yearly handlingsdel of KEP 2023–2035, not a separate portal.
- 2024 HØP chapter plots Miljødirektoratet. 2026 klimabudsjett chapter not opened.
- Smart data prints «dele data med viktige interessenter».

**Sources opened 2026-08-27.**
- https://www.molde.kommune.no/klima-og-miljo/hva-gjor-molde-kommune/klimabudsjett.35081.aspx
- https://budsjett.molde.kommune.no/2024/budsjett-og-%C3%B8konomiplan/klimabudsjett.html
- https://www.molde.kommune.no/horinger-planer-og-samfunnsutvikling/vare-satsingsomrader/flere-satsingsomrader-og-prosjekter/prosjekter/smart-data.28761.aspx
- https://www.molde.kommune.no/kontakt-oss/skriv-til-oss/
- https://data.brreg.no/enhetsregisteret/api/enheter/921221967

---

## 61. Gjøvik kommune — Åpne data (SSB API) + årlig klimabudsjett

**Why they would pay.** The official *Åpne data i Gjøvik kommune* page points at SSB APIs as the hovedvekt of the municipality's open data (data and nøkkeltall reported to sentrale myndigheter). Klimabudsjett is printed as yearly and as part of kommunens styringsdokument. The 2026 Framsikt klimabudsjett view is empty — do not invent cells. They would pay to find and fetch SSB / Miljødirektoratet series with provenance for that yearly chapter — not another åpne-data page.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Gjøvik (knr 3407), fetched as rows with license and access path before later overlay on the yearly klimabudsjett.

**Search → fetch → later analysis.**
- Search: Gjøvik + klimagass / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett; do not invent tonnes. Do not invent 2026 Framsikt cells.

**Public contact (only published / listed).**
- postmottak@gjovik.kommune.no — printed on kontakt-oss
- Telephone: 61 18 95 00
- Org: 940155223
- Kommunenummer: 3407
- Do not invent a klima or åpne-data inbox.

**Key facts.**
- Postboks 630, 2810 Gjøvik; Kauffeldts plass 1, 2815 Gjøvik.
- Åpne data page points at SSB APIs. Only «grønne» data are offered as åpne data.
- Yearly klimabudsjett sits in styringsdokumentet. 2026 Framsikt empty.

**Sources opened 2026-08-27.**
- https://www.gjovik.kommune.no/personvern-og-informasjonskaplser/apne-data-fra-gjovik-kommune/
- https://www.gjovik.kommune.no/satsningsomrader-og-pagaende-prosjekter/klima/
- https://www.gjovik.kommune.no/kontakt-oss/
- https://data.brreg.no/enhetsregisteret/api/enheter/940155223

---

## 62. Karmøy kommune — HP 2026–2029 Framsikt climatesummary

**Why they would pay.** Handlingsprogram 2026–2029, vedtatt 15.12.2025, has a Framsikt climatesummary. That is the current mandate. They would pay to find and fetch Miljødirektoratet kommunefordelte klimagassstatistikk and related SSB series with provenance for that chapter — not another HP PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Karmøy (knr 1149), fetched as rows with license and access path before later overlay on the HP 2026–2029 climatesummary.

**Search → fetch → later analysis.**
- Search: Karmøy + klimagass / energi / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimabudsjett / climatesummary; do not invent tonnes.

**Public contact (only published / listed).**
- ehs@karmoy.kommune.no — listed
- postmottak@karmoy.kommune.no — listed
- Telephone: 52 85 75 00
- Org: 940791901
- Kommunenummer: 1149
- Do not invent a klima inbox.

**Key facts.**
- Postboks 167, 4291 Kopervik; Statsråd Vinjes gate 25, 4250 Kopervik on the Enhetsregisteret page.
- Vedtak 15.12.2025. Framsikt document: bm-2026-handlingsprogram_2026-2029_kommunestyrets_vedtak.

**Sources opened 2026-08-27.**
- https://pub.framsikt.net/2026/karmøy/bm-2026-handlingsprogram_2026-2029_kommunestyrets_vedtak/#/generic/summary/climatesummary
- https://www.karmoy.kommune.no/innbygger/klima-natur-og-miljo/klima-og-miljo/klimaarbeidet/
- https://data.brreg.no/enhetsregisteret/api/enheter/940791901

---

## 63. Kongsberg kommune — ØHP 2026–2029 Klima / klimaregnskap + klimabudsjett

**Why they would pay.** Økonomi- og handlingsplan 2026–2029 Klima prints: «Dette følges opp gjennom klimaregnskap og klimabudsjett.» That is the named follow-up. They would pay to find and fetch Miljødirektoratet kommunefordelte klimagassstatistikk and related SSB series with provenance for that klimaregnskap / klimabudsjett — not another ØHP PDF.

**Concrete use case.** Klima / økonomi needs the latest kommunefordelte klimagassstatistikk and related SSB series for Kongsberg (knr 3303), fetched as rows with license and access path before later overlay on the ØHP 2026–2029 klimaregnskap and klimabudsjett.

**Search → fetch → later analysis.**
- Search: Kongsberg + klimagass / «kommunefordelt» with publisher (Miljødirektoratet, SSB).
- Fetch: first rows from the recorded access path; license and publisher on every hit.
- Later analysis: feed klimaregnskap / klimabudsjett; do not invent tonnes.

**Public contact (only published / listed).**
- postmottak@kongsberg.kommune.no — listed
- Telephone: 32 86 60 00
- Org: 942402465
- Kommunenummer: 3303
- Do not invent a klima inbox.

**Key facts.**
- Postboks 115, 3602 Kongsberg; Kirkegata 1, 3616 Kongsberg on the Enhetsregisteret page.
- ØHP 2026–2029 Klima: «Dette følges opp gjennom klimaregnskap og klimabudsjett.»

**Sources opened 2026-08-27.**
- https://pub.framsikt.net/2026/kongsberg/bm-2026-handlingsplan_2026-2029/#/generic/summary/focusarea/2319
- https://data.brreg.no/enhetsregisteret/api/enheter/942402465

---

### Hamar kommune

- **Why they would pay.** Handlings- og økonomiplan 2026–2029 Framsikt title is **Kommunestyrets vedtak**. Named **Klimabudsjett** chapter: 55 % vs 2015 (141 kt → 77,5 kt cut); 2023 still 115 kt / −19,7 % («reduksjonen går for sakte»). The chapter already names two Miljødirektoratet ledgers (geografiske direkteutslipp by sector, and skog/arealbruk). Yearly job is to re-pull kommune 3403 into the 2015 / 2023 / 2030 rows, not another Framsikt rebuild.
- **Concrete use case.** Klima owners first-fetch Miljødirektoratet kommune 3403 sector series and overlay the chapter’s 2015 / 2023 / 2030 rows, then Mdir skog/arealbruk plus SSB KOSTRA 09574 for the −30 % / 2016 bygg-energi line.
- **How the service should look.**
  - Search: data.norge first, then Mdir kommuneregnskap, SSB 09574.
  - Fetch: first official Excel/PxWeb rows. Their Framsikt chapter stays theirs.
  - Later analysis: 2023→2024/2025 refresh on the 77 500 t / 2030 gap; keep Trehørningen and arealbruk hogst as residuals.
- **Public contact.**
  - Role / unit: klima- og miljø-satsingsområde (Lise Urset, Karoline Finstad Vold named).
  - Email: `postmottak@hamar.kommune.no`; `Lise.Wenche.Dufseth.Urset@hamar.kommune.no`; `karoline.finstad.vold@hamar.kommune.no`
  - Phone: 62 56 30 00; Vold 962 27 215
  - Form/URL: https://www.hamar.kommune.no/klima/klima-og-miljo-som-satsingsomrade/
- **Key facts.** Org.nr 970 540 008. Kommunenr. 3403. Postboks 4063, 2306 Hamar.
- **Sources** (opened 2026-08-27).
  - https://www.hamar.kommune.no/politikk-og-administrasjon/planer-i-en-kommune/temabaserte-planer/handlings-og-okonomiplan-2026-2029-1/
  - https://pub.framsikt.net/2026/hamar/bm-2026-hop26-29
  - https://pub.framsikt.net/2026/hamar/bm-2026-hop26-29/#/generic/summary/climatesummary
  - https://www.hamar.kommune.no/klima/klima-og-miljo-som-satsingsomrade/
  - https://data.brreg.no/enhetsregisteret/api/enheter/970540008
  - https://www.miljodirektoratet.no/tjenester/klimagassutslipp-kommuner/

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
- **DIS (Helse Nord)** — Digitale innbygger- og samhandlingstjenester; clinical patient-journey / documents, not a discovery buyer. Helse Nord programme in this book is Helseatlas / SKDE.
- **Norgesnett** — folded into Glitre Nett; not a fourth energy seat.
- **Asker / Bærum / Ålesund / Tromsø / Drammen** — mid-size seats held; not numbered in this book.
- **Arendal kommune** — held: 2026 klimabudsjett is only in kommunedirektørens forslag; the vedtatt HØP (bystyret 11.12.2025) has no Klimabudsjett chapter. Same skip as an un-vedtatt skisse.

---

## Changelog

- **27 Aug 2026, 10:00 Europe/Oslo.** First 15 sourced entries. No outreach.
- **27 Aug 2026, 10:15 Europe/Oslo.** Five deepen notes: Oslo DIG Tildelingsbrev 2026 datadeling + 45,5 mill. PC-ownership klimabudsjett measure (do not treat 817 699 / 75 000 as kroner) and DIG etat emails; Stavanger live Regnsensordata (updated 27 Aug 2026 02:01 CEST) and printed staff-ID next to opendata@; Bouvet Kartverket 477 mill. five-year grant (no Bouvet contract price) plus Kaasa phone and 200 vs 50/250 headcount print; Aftenposten Fossan mailto + author line + kvikkleire story (seks = Journalisten only); Statsbygg SIMBA 2.1 PDF dates and tungt.no 13,6 mrd marked second-hand.
- **27 Aug 2026, 10:25 Europe/Oslo.** Wave-2: 12 sourced entries (3 health, 5 energy, 4 mid-size kommuner). Contacts only as listed. No outreach.
- **27 Aug 2026, 10:30 Europe/Oslo.** Wave-2 add: Lillestrøm kommune (digitalisering 2020–2025 + klimabudsjett / Klimasats klimaplanlegger). Contacts only as printed. No outreach.
- **27 Aug 2026, 10:40 Europe/Oslo.** Kristiansand mandate is Økonomiplan 2026–2029 (bystyret 17.12.2025) kap. 5.4 datadeling + kap. 6 klimabudsjett / Miljødir kommunefordelte tall. Contacts post@ and post.byutvikling@. No competitor section.
- **27 Aug 2026, 11:10 Europe/Oslo.** Wave-3: 9 sourced entries (Helse Vest RHF, Helse Midt-Norge RHF, Helse Nord RHF / SKDE, Elvia, Glitre Nett, Linea, Tønsberg, Larvik, Porsgrunn). Contacts only as listed. No invented emails. No outreach. No competitor section.
- **27 Aug 2026, 11:20 Europe/Oslo.** Wave-3 add: Sarpsborg (Plattform for digitalisering 02.02.2023 + KDP klima) and Skien (HP 2025–2028 klimabudsjett; digitaliseringsstrategi announced, not vedtatt). Porsgrunn HP 2026–2029 PDF opened (Klimabudsjett from s. 54); timeout caveat dropped. Contacts only as listed. No competitor section.
- **27 Aug 2026, 12:40 Europe/Oslo.** Wave-4: 8 sourced entries (Oslo universitetssykehus HF, Helse Bergen HF, Universitetssykehuset Nord-Norge HF, Arva, Lede, Fagne, Moss, Haugesund). Skien Why they would pay updated to HP 2026–2029 Framsikt klimabudsjett (Klimakost stopped after 2023; 7 mill. kr pot; needs arealverktøy); contacts stay post@skien.kommune.no. Arva Kapasitetskart: NVE §15 cite kept; arva.no/Kapasitetskart 404 on 27 Aug 2026 — do not claim the page is live. No invented emails (no Golde@, no post@arva.no). No outreach. No competitor section.
- **27 Aug 2026, 13:10 Europe/Oslo.** Wave-5: 8 sourced entries (Akershus universitetssykehus HF, Vestre Viken HF, Sykehuset Østfold HF, Vissi, Elinett, Linja, Molde, Gjøvik). Contacts only as listed. No invented emails (no firmapost@morenett.no; no named-person emails for Elinett). 2026 klimabudsjett cells not opened for Molde or Gjøvik — not invented. TROLL/NOR-ITP noted as own registers, not the buy. Linja is not Linea. No outreach. No competitor section.
- **27 Aug 2026, 13:25 Europe/Oslo.** Arendal kommune pulled / skipped: 2026 klimabudsjett is only in kommunedirektørens forslag; vedtatt HØP (bystyret 11.12.2025) has no Klimabudsjett chapter. Same skip as an un-vedtatt skisse. Not a lead. Wave-5 stays the eight. No outreach. No competitor section.
- **27 Aug 2026, 14:10 Europe/Oslo.** Wave-6: 8 sourced entries (Sykehuset Innlandet HF, Sykehuset Telemark HF, Sykehuset i Vestfold HF, Jæren Everk, Midtnett, S-Nett, Karmøy, Kongsberg). Contacts only as listed. No invented emails (no nett@svorka.no). Arendal held (klimabudsjett only in kommunedirektørens forslag; vedtatt HØP 11.12.2025 has no Klimabudsjett chapter). Asker / Bærum / Ålesund / Tromsø / Drammen stay skipped. No outreach. No competitor section.
- 2026-08-27: Added Barents Nett, Noranett and Enida.
- 2026-08-27: Added Helse Førde, Sunnaas and Diakonhjemmet.
- 2026-08-27: Added Hamar kommune (vedtatt HØP klimabudsjett). Wave 7 mid-size closed. Still no outreach.

---

## Living-book rule

This is the Commercial Scout file. Contacts are only what each organisation prints. If a field is missing, write "none published." Never invent an email, phone, or person. No outreach from this file.
