# Known gaps

Living log of gaps we have measured. Each entry cites how it was observed. This file
records what is missing; it does not fix anything. Entries that stop being true get
removed, not archived — git history is the archive.

## What blocks "any question works"

- **Norwegian compounds miss.** `byggekostnader`, `energibruk`, `kraftproduksjon` and
  `kollektivtransport` return no fetchable hit, because the stored tokens are the parts
  (`bygge`, `kostnader`, …) and the query token is the compound. `QUERY_COMPOUND_SPLITS`
  holds two hand-written entries. A vocabulary-driven split — split only when both
  halves exist in the index — generalises; a longer hand-written list does not.
  Observed as 4 of 30 failures in `run_answerable`.

## Coverage

- **Fetchability is concentrated in one publisher.** Of ~12,900 catalogued datasets,
  ~3,790 classify as `observations` and essentially all are SSB PxWeb tables. Non-SSB
  numeric sources remain largely unreachable, so breadth outside SSB depends on new
  connectors, not on ranking work.

- **Most Data.norge records carry no variable list.** No harvested Resource Service
  payload stores `variables`, `variableList`, or `variable_list`. We do not invent
  measure lists. SSB PxWeb rows do carry `variableNames`, so the gap is now specific to
  Data.norge rather than universal. Source: `data/enrich_proof.json`,
  `data/harvest_stats.json`.

- **Spatial is missing on ~90% of Data.norge rows** (8243 of 9120). Publisher missing on
  322 (3.53%), licence on 585 (6.41%), `modified` on 7204 (78.99%). Do not infer any of
  them. Source: `data/harvest_stats.json`.

- **Klass versions go stale.** The stored `Kommuneinndeling` access path pointed at
  version `1160`, which now returns HTTP 404 upstream. There is no check that a stored
  classification version still resolves. Observed live, this session.

## Search and measurement

- **The gold benchmark does not measure whether the product works.** `pda benchmark`
  scores ranking against 65 expected Data.norge ids. It is blind to whether any hit can
  return a number, so a change can hold R@5 while making the system unable to answer
  anything. `run_answerable` over `data/answerable_questions.json` measures reach of the
  fetch layer instead. Both must be checked; neither is sufficient alone.
  Demonstrated this session: a change that held R@5 exactly took `arbeidsledighet` and
  `boligpriser` from four fetchable hits to zero.

- **Indirect questions remain the weakest class.** `indirect` R@5 is ~0.556 against
  ~1.00 for `simple` and `multi`. These are questions whose gold record shares no
  surface token with the query, which is the case lexical overlap cannot reach.

- **Coverage confidence can be 1.0 while the gold id is missing.** Coverage means "a
  retrieved row stores this token", not "we found the expected dataset". q036 (`Health`)
  and q056 (`AtB`) both score confidence 1.0 with recall@5 of 0.
  Source: `data/coverage_proof.json`.

- **Some gold entries are worth re-examining.** q038 (`offentlig sektor`) expects
  *"Ung.no, det offentliges informasjonskanal for ungdom"*, while SSB's
  `14667: Offentlig forvaltning …` is arguably the better answer and is fetchable. The
  gold set was built when nothing was fetchable; parts of it now encode that assumption.

## Source probes that did not become connectors

Kept because each one cost a live check and should not be repeated blindly.

- Norsk Polarinstitutt OGC Features (`geodata.npolar.no/ogc/features/v1/collections`) was
  not usable; the working printed catalogue is `api.npolar.no/service/?q=*&format=json`.
- Sikt DataverseNO `openapi` is the generic Dataverse software API, not a dataset list;
  the working catalogue is `dataverse.no/api/dataverses/:root/contents`.
- Kartverket Eiendom OpenAPI prints 3 GET paths and geocoding returns HTTP 400 without
  kommune/gard/bruksnummer.
- Trafikkdata is GraphQL; the swagger URL serves HTML and the old API host returns 410.
  The working Vegvesen catalogue is CKAN `dataut.vegvesen.no/api/3/action/package_list`.
- NVDB rejects requests without a User-Agent.

## Answerable set under-represents what the registry now holds

`data/answerable_questions.json` is 30 questions with one health topic among them. It
was written when the fetchable corpus was SSB-only, so it cannot register the reach
that the FHI registers added: 369 tables, 119 of them geographic. Health and education
questions now route `ready` with FHI observation sources, and the benchmark scores the
same 0.8667 either way.

Expanding the set is a change to the measuring instrument, so it should be done
deliberately and before the next source is promoted, not after a change whose effect it
would then appear to show.

## FHI rows are not yet reachable from `join.py`

FHI geography is printed as Klass codes — 36 of the 42 codes in Klass 1168 appear
verbatim in a `nokkel` table's `GEO` dimension — so the vocabulary composes with SSB.
The wiring does not. `join_classification_to_table` pairs a Klass classification with an
SSB PxWeb table through `ssb_pxweb.py`, and there is no FHI equivalent, so an SSB × FHI
question can retrieve both sides but cannot join them.

The labels differ where the codes agree (`Bydel Grünerløkka` against `Grünerløkka`), so
the join has to run on codes. Joining on names would silently match nothing.


## The answerability metric is barely above chance

`run_answerable` asks whether *a* fetchable dataset appears in the top hits. 4,160 of
13,281 datasets are fetchable, so five random picks satisfy it **79.7% of the time**
(measured over 400 draws; the closed form gives 0.847). Every score this metric has
produced must be read against that floor, not against zero:

```
random guessing      0.797
lexical              0.330
semantic / fused     0.920
```

Semantic beats chance by twelve points, not by the fifty-nine the raw comparison
suggests. Scores of 0.867 and 0.716 quoted earlier are not quality measures.

Worse, lexical scores *below* chance, and that is not a fault in lexical. It returns
well-matched Data.norge records, which are descriptive and unfetchable, while random
draws from a corpus that is a third fetchable. The metric rewards returning fetchable
junk over returning a relevant thing that cannot be fetched.

It still measures one real thing -- reach, the question "could this question have got
to any data at all" -- and the gap between keyword and natural phrasing is probably
real, since both slices carry the same bias. It does not measure whether the right
data was found, which is the v1 goal.

The replacement is a gold set for the fetchable lane: for each question, the table that
actually answers it. Candidates are pooled from every retrieval method so the labels
are not biased toward whichever method the set will later judge.

## A control must be the path production uses

Twice now a measurement has compared against `search()` when every production caller
uses `search_report()`, which recovers from an empty result with a follow-up search per
missing requirement. The first time it understated the control at 0.700 against 0.867;
the second time it produced a lexical figure of 0.330 that no user would ever
experience. Both made a change look better than it was.
