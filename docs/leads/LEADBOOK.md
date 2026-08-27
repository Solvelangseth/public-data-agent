# Lead book — Norwegian open-data platform

Living file. Owner: Commercial Scout. Reports to Chief of staff, not Sølve.
No email, call, or outbound post from this file. Contacts are only what the org prints.

Product sold: registry of Norwegian public datasets (Data.norge first ingest, sources replaceable), natural-language search, first fetch of actual rows. Later analysis. LLM for intent and explanation. Deterministic retrieval. Provenance (source, publisher, license, access path) on every hit.
Repo: https://github.com/Solvelangseth/public-data-agent
Competitor note: offentligdata.no is a competitor, not a customer. Do not treat that site as a lead.

Status 27 Aug 2026, 10:15 Europe/Oslo: 15 sourced leads. Mix: 4 municipalities, 3 consultancies, 2 media, 2 property/infra, 2 research, 2 NGOs. Five deepen notes added same day (Oslo DIG tildelingsbrev, Stavanger Regnsensordata, Bouvet Kartverket grant, Aftenposten Fossan mailto, Statsbygg SIMBA 2.1 + tungt.no second-hand). No invented emails. No outreach.

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
- Later analysis: overlay on Vegkart / NVDB geometry; do not treat offentligdata.no as a customer path.

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

---

## Living-book rule

This is the Commercial Scout file. Contacts are only what each organisation prints. If a field is missing, write "none published." Never invent an email, phone, or person. No outreach from this file.
