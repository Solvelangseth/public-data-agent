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


## The routing result is partly circular, and the caveat matters

Measured on `data/fetchable_gold.json`:

```
method      recall@5     MRR   keyword   natural
lexical        0.442   0.327     0.651     0.233
semantic       0.709   0.577     0.744     0.674
fused          0.756   0.499     0.884     0.628
routed         0.779   0.622     0.884     0.674
```

The routing rule -- fuse for a subject, semantic alone for a question -- was derived
from this table and then scored on the same 88 questions, so `routed` is by
construction the better of the two columns and its 0.779 is optimistic. What is not
circular is the reason behind it: lexical ranking helps when a query names a subject
in the vocabulary the publisher used, and contributes function-word noise when the
query is a sentence. That is an explicable mechanism, not a fitted constant, which is
why it is worth keeping. A fresh question set would give the honest number.

The router classifies all 88 correctly, which is also weak evidence -- one author wrote
both phrasings and the split is unusually clean.

## What retrieval still cannot do

Nineteen of 86 questions still miss. They fall into three kinds.

**A word appears as a breakdown, not as the subject.** "Sysselsetting etter næring"
returns e-commerce tables broken down *by* employment size; "bruttonasjonalprodukt"
returns R&D as a share of GDP and never finds GDP. The index cannot tell a table about
X from a table split by X.

**The question needs a derivation, not a lookup.** "Hvilken bydel har flest innbyggere"
is a max over a table; "hvor mye har prisene steget" is a change between periods. No
single table is the answer, so retrieval alone cannot succeed and the gold label is
arguably wrong to expect it to.

**Plain vocabulary failure.** "Hvor mange barn er vaksinert mot meslinger" does not
reach `Vaksinasjonsdekning`, and "hvor gode er norske elever i lesing" does not reach
`Leseferdighet`, though both are indexed and embedded.


## Compound-word matching is worth six questions; the index is worth thirty-five

Norwegian compounds looked like the obvious next fix -- `Privathusholdninger` does not
tokenize to `husholdninger`, `Vaksinasjonsdekning` not to `vaksinasjon`. Measuring the
ceiling before building it showed otherwise:

```
gold questions                86
correct table matched by title exactly   45
would gain from prefix matching           4
would gain from suffix matching           2
correct table shares no word with query  35
```

Every title-based rule, compound-aware or not, tops out at 51 of 86 (0.593). Semantic
retrieval already scores 0.709, above that ceiling, so work on lexical matching is
capped below where retrieval already is.

The thirty-five are reachable only by what is *inside* a table. "Hvor mange bor det i
Bergen" is answered by 07459, whose title never mentions Bergen and whose Region
dimension lists it. That is what `resource_field_values` exists for, and it held 540 of
4,160 fetchable resources.

Suffix matching also carries a risk worth remembering: "strøm" is the suffix of
"Lillestrøm", which is a municipality, not electricity. The same collision already made
election statistics an answer about power production once.


## 588,442 stored observations are labelled with a table title

`cells_from_jsonstat` skipped `ContentsCode` -- the dimension saying what a cell
measures -- so the measure fell back to the table's own title. Two consequences, both
live in the store today.

Cells differing only in which statistic they report became identical in
`(measure, dimensions)`, which is the key `observations` is unique on, so one silently
overwrote the other. Fetching 08650 for a single year with both of its statistics
returned six cells and stored three. The survivors were percentage changes carrying the
label "Byggekostnadsindeks" -- a percentage stored as an index, with correct provenance
and a correct request URL.

The decoder is fixed and the same fetch now stores all six, correctly labelled. What is
not fixed is the store: **588,442 of 596,549 rows** have a table title as their measure,
so 98.6% of what is stored was written by the broken decoder. Those rows are provably
mislabelled -- a table title is never what a cell measures -- and any table with more
than one statistic is also missing rows that were overwritten.

Re-fetching does not repair them. The observation id includes the measure, so a corrected
fetch writes new rows beside the old ones rather than replacing them, leaving both in the
store. Deleting the mislabelled rows is a decision about the user's data, not a code
change, so it is recorded here rather than taken.


## Resource search is not a ranking signal

With the index complete, "Bruttonasjonalprodukt" is a stored value of 09189 and 09190 --
both gold answers -- so resource search finds them where title and embedding ranking do
not. It reaches the correct table for two of the eight remaining misses, in exactly the
cases where the query names something inside a table rather than in its title.

Fused into the observations lane it still does not pay:

```
current               recall@5 0.860  MRR 0.763  keyword 0.907  natural 0.814
fused with resource   recall@5 0.860  MRR 0.593  keyword 0.930  natural 0.791
```

One keyword question gained, one natural question lost, seventeen points of MRR spent.
That is the coverage lift's failure again in a milder form: blending a weaker ranking
into a stronger one dilutes it, and being right about two queries does not pay for being
noisier about the rest.

A fallback that fires only when the observations lane is empty would not help either --
the remaining misses have a full lane with the wrong things in it, not an empty one.

Resource search earns its place elsewhere: `inspect` reads the shape a caller plans a
fetch from, `covering` answers which resources hold a value, and `resource_keys` answers
which speak an identifier scheme. Those are questions about a resource, not rankings of
it.

## Retrieval is unchanged by the store cleanup

Measured after the decoder fix, the deletion of 588,442 mislabelled rows and the `ask`
rewiring: recall@5 0.860, MRR 0.763, keyword 0.907, natural 0.814 -- identical to the
measurement before them. The observation store is a cache; retrieval ranks the registry,
and emptying the cache does not touch it.


## The held-out number is 0.743, not 0.860

`data/answerable_questions.json` produced the routing rule and was then scored on it, so
its 0.860 was optimistic by construction. `data/heldout_questions.json` was written
blind and measured once:

```
              recall@5    MRR   keyword  natural      (tuned set, for comparison)
lexical         0.400    0.324    0.450    0.333      0.442 / 0.327 / 0.651 / 0.233
full stack      0.743    0.655    0.850    0.600      0.860 / 0.763 / 0.907 / 0.814
```

Three things follow.

**The tuned figure overstated by about twelve points.** 0.743 is the number to quote.

**The improvement is real.** Lexical 0.400 to 0.743 held up on data that chose nothing,
so it is not an artifact of fitting.

**Routing generalises worse than the tuned set implied.** Naturally phrased questions
score 0.600 held out against 0.814 tuned, the largest gap of any column. The rule --
fuse for a subject, semantic alone for a question -- was derived from one author's
phrasings, and the marker list behind `looks_like_a_question` is the part most likely
to be overfitted. Keyword phrasing barely moved (0.850 against 0.907), which fits: that
half depends on vocabulary rather than on the router.

Eight of 43 held-out questions were recorded as having no answer anywhere in the registry -- permitteringer,
luftfart passasjerer, oppdrettslaks produksjon, melkeproduksjon, lønnsomhet i industrien,
naturvernområder, vannforbruk per husholdning. That is a coverage finding for the
connector lane, not a retrieval failure, and those questions are excluded from recall.

The set is spent the moment it is used to choose anything. If a parameter is ever tuned
against it, a new held-out set is needed.


## Correction: the held-out gap was bad labels, not overfitting

The entry above concluded from 0.743 held out against 0.860 tuned that the routing rule
overfitted, and that naturally phrased questions generalised worst. Auditing every one of
the 35 scored questions -- not only the misses, which can only raise a score -- found four
labels naming a worse table than one that plainly answers the question: cancer *deaths*
for "hvor mange får kreft hvert år", ownership status for "hvor mange leier boligen sin",
`Tannhelse_DMFT` where `Tannhelsetilstand og kariesforekomst` exists.

```
                          recall@5    MRR   keyword  natural
lexical                     0.400    0.324    0.450    0.333
full, labels as written     0.743    0.655    0.850    0.600
full, labels corrected      0.857    0.762    0.850    0.867
tuned set                   0.860    0.763    0.907    0.814
```

Held out now matches tuned, so no meaningful overfitting is detectable, and natural
phrasing scores *higher* held out than tuned -- the opposite of what was concluded.

The residual risk is real and worth stating: labels were corrected after seeing which
questions failed. What limits it is that the audit was symmetric, and in the hit cases
the top result was usually already the labelled one, so there was no over-labelling to
correct in the other direction. The honest interval is [0.743, 0.857], nearer the top.

**This is the second time a conclusion here came from bad labels.** The first was nine
keyword misses in the other set, of which four were mislabelled. Roughly half of every
apparent retrieval failure examined this session has turned out to be the benchmark
rather than the retriever. Labelling is the weakest part of the measurement, and any
future set should be audited across all questions before a number from it is believed.

## What still genuinely fails

Five of 35, all one shape: a rare content word swamped by a common one in the averaged
query embedding.

```
yrkesdeltakelse kvinner   -> fruktbarhetstall, skilsmisserater   ("kvinner" dominates)
domfelte etter alder      -> Døde, etter aldersgrupper           ("alder" dominates)
hvor mange flyr innenlands-> Flyttinger innenfor kommunene       ("flyr" reads as "flytting")
barnehagedekning          -> Barnehagekvalitet_bemanning         (right domain, wrong table)
hvor mye handler vi på nett -> Formål med bruk av einingar
```

Two fixes were proposed and both are wrong.

**Rarity weighting cannot work.** The failing terms are not rare, they are absent: over
13,281 titles, `yrkesdeltakelse`, `domfelte`, `flyr`, `barnehagedekning` and `handler`
all have document frequency **zero**. Nothing can up-weight a term that matches nothing.
Absence also does not predict failure -- `leiepriser` is equally absent and its query
succeeds at rank one.

**Stripping filler before embedding is worse.** `semantic_ranking` embeds the raw query,
so "domfelte etter alder" carries a structure that hundreds of titles share. Removing it
helped one query and broke two:

```
query                              raw   content words only
hvor mange gifter seg i Norge        1   None
hvor mye handler vi på nett         25   None
hvor mange flyr innenlands          30     12   (still a miss)
```

The model reads a natural sentence better than the keywords inside it, which is
consistent with natural phrasing scoring 0.867 held out against 0.850 for keywords.
Phrasing is not the problem.

What remains is genuine vocabulary distance in Norwegian: `domfelte` against `straffede
personer`, `yrkesdeltakelse` against `arbeidsstyrken`. Closing those needs a
Norwegian-specific embedding model or synonym expansion, and neither is a small change.
At five failures in 35 the returns are thin; coverage is the binding constraint now.


## Embedding models: one tested, one deferred on purpose

`NbAiLab/nb-sbert-base` was indexed over all 13,281 datasets and scored through the same
harness as the baseline:

```
model                     tuned r@5   held-out r@5   natural (tuned)
nb-sbert-base                 0.721          0.743            0.651
text-embedding-3-small        0.860          0.743            0.814
```

It loses by fourteen points on the tuned set, ties held out, and gives up most on
naturally phrased questions. A 2021 sentence-similarity model against a modern
retrieval-trained one: **training objective and recency beat language specificity**, so
Norwegian-specific training is not the missing ingredient. That answers the expensive
question -- whether to train a Norwegian embedding model -- cheaply, and the answer is
not yet.

`intfloat/multilingual-e5-large` is **untested and deliberately deferred**. It tests the
other hypothesis: that model *size* rather than language is what is missing. It was not
run because 2.2 GB of weights would be resident for every query the MCP server answers,
on a 9 GB laptop, and a first attempt at downloading it exhausted the disk. Even a win
would not be deployable on this machine.

Revisit when the server has the memory to hold it. What it would settle: if e5-large
wins where nb-sbert lost, size is the factor and a larger multilingual model is the
answer; if it also loses, `text-embedding-3-small` is genuinely good at this and the
remaining five failures need synonym expansion rather than any new model.

The benchmark script takes `--models`, so re-running it there is one command. The
scoring harness measures `fuse(lexical, semantic)` only -- no routing, subject demotion
or lane filter -- so its numbers are lower than the production stack's and comparable
only to each other.


## Third label correction: two "coverage gaps" were retrieval failures

`lønnsomhet i industrien` and `hvor mye vann bruker en husholdning` were recorded as
having no answer in the registry. Both have one, as a **measure inside** a table rather
than in any title:

```
11787  Vannforsyning og beredskap   measure "Mengde kommunalt vann til husholdninger"
08120  Alle næringer. Resultatposter measure "Driftsresultat"
07371  Nøkkeltall for aksjeselskap   measure "Driftsmargin (prosent)"
08264  Konjunkturbarometeret         measure "Lønnsomhet"
```

The labels were written from titles. That is the systematic flaw in both sets, and it has
now produced a wrong conclusion three times. The resource index knew all along -- it
records what is inside a resource -- and was never queried that way while labelling.

This correction moves two questions from excluded to scored-and-failing, so unlike the
previous one it lowers the number:

```
                     scored   recall@5    MRR   keyword  natural
before this fix          35      0.857   0.762    0.850    0.867
after                    37      0.811   0.723    0.810    0.812
```

**Coverage is better than reported and retrieval is worse.** Six questions of 43 have no
answer anywhere, not eight, so the corpus reaches about 86% of ordinary questions rather
than 81%.

`scripts/eval_retrieval.py` now lives in the repo rather than a scratch directory, which
is why this was cheap to re-measure. Three earlier versions were written and lost.

## Resource search finds what titles cannot -- sometimes

Against the two newly-labelled questions, `search_resources` ranks `lønnsomhet i
industrien` **first**, through the measure "Lønnsomhet" in 08264, where the full stack
does not find it in fifty candidates. It misses the water question entirely.

That does not overturn the earlier finding that fusing it into the ranking costs more
than it wins. It does sharpen what it is for: a query naming something that exists only
as a value inside a resource. Worth revisiting as a **fallback for queries the main stack
fails**, which is narrower than fusion and was never tested.


## Five retrieval ideas measured and rejected — stop re-litigating them

Each was plausible, each was tested against a labelled set, each lost:

| idea | result |
|---|---|
| coverage lift from the resource index | 0.802 against 0.860; +6 misses |
| fusing resource search into the lane | recall level, MRR 0.593 against 0.763 |
| exact match on a measure's name | fires on 34/86 tuned questions, 9 correct (26%) |
| weighting query terms by rarity | the failing terms have document frequency **zero** |
| stripping filler before embedding | broke two queries to fix one |

The resource index does not add ranking value. It earns its place elsewhere -- `inspect`
reads the shape a fetch is planned from, `covering` answers which resources hold a value,
`resource_keys` answers which speak an identifier scheme -- and those are questions about
a resource rather than rankings of it.

The stack as it stands (lexical, semantic routed by phrasing, subject over breakdown,
retrievable-lane filter) is at its practical ceiling for this corpus. The five remaining
failures are Norwegian vocabulary distance -- `domfelte` against `straffede personer` --
and `NbAiLab/nb-sbert-base` was measured on that too and lost. What is untested is a
larger multilingual model, deferred for memory reasons, and synonym expansion.

Anything new here should be measured with `scripts/eval_retrieval.py` against both sets
before it is believed. Roughly half of every apparent retrieval failure examined in this
project has turned out to be the benchmark rather than the retriever.

## Search was scanning every row; an FTS5 pre-filter made it 10x faster and changed nothing

Every query scored every dataset in the registry — 13,744 rows, each one JSON-decoded
and tokenised in Python. That cost **1,761 ms per query** on an idle machine and 7,648 ms
on a loaded one, and it grows with the catalogue. For an MCP server answering
interactively, that is the difference between a tool call and a wait.

The fix is a SQLite FTS5 index used as a *candidate filter*, not as a ranker. FTS5
returns its top 2,000 by BM25; the existing scorer then ranks those 2,000 exactly as
before — same weights, same synonyms, same AND-decomposition. BM25 never has to agree
with the scorer, it only has to put the right rows *somewhere* in the candidate set.

Measured on all 131 labelled questions, top 50 each:

| | full scan | with the filter |
|---|---|---|
| latency | 1,761 ms/query | **168 ms/query** |
| identical top-50 | — | **131/131** |
| held-out recall@5 / MRR | 0.811 / 0.723 | 0.811 / 0.723 |
| tuned recall@5 / MRR | 0.860 / 0.763 | 0.860 / 0.763 |
| `pda benchmark` recall@5 | 0.892 | 0.892 |

Two things had to be right, and the first attempt got one of them wrong:

**Index every field the scorer scores.** A first prototype indexed title and
description only and kept **80.3%** of the scorer's top 20 — the scorer also matches
keywords, themes and publisher, so rows matching on those vanished. `_index_body` now
builds its text from the same `fields` dict `_iter_scored_rows` produces, which makes
the two impossible to drift apart. Query tokens are expanded through `_token_alts`
before matching, because the scorer accepts compound splits that a prefix match would
not.

**A stale index must be slow, not wrong.** An index built before an ingest does not
contain the new datasets, and using it would hide them from every search silently.
`search_index_state` records how many datasets were indexed; `index_is_current`
compares that against the live count, and `prefilter` returns `None` — meaning "score
everything" — whenever they disagree, whenever the index has never been built, and
whenever the query has no usable token. `pda ingest` rebuilds the index when it wrote
anything; `pda index` rebuilds it on demand (4.9 s for 13,744 rows, 14 MB).

The 168 ms that remains is the scorer reading 2,000 rows, not the FTS5 query, which is
0.4 ms. Cutting the depth to 500 would be faster and would keep only 73% of the
scorer's top 20, so the depth stays at 2,000: this change is worth having *because* it
alters nothing.

## The resource index cannot rank, and now it is clear why — a sixth rejection

`resource_field_values` holds 15,170 measure names across 4,158 datasets — the
names a table publishes for what it actually counts, none of which need appear in
its title. It looks like exactly the missing ingredient: `lønnsomhet` is a measure
in 08264, `Driftsmargin` in 07371 and 08142, and all three are gold labels for the
question "lønnsomhet i industrien" that the retriever misses. The index coverage is
not the problem either — 4,158 of the 4,160 retrievable datasets have a shape.

It has now been tried three ways and lost three times, and the third attempt found
the mechanism.

| | tuned recall@5 | MRR |
|---|---|---|
| baseline | **0.860** | **0.763** |
| measure as a scored field, weight 2 / 3 / 5 | 0.849 | 0.754 |
| the same, gated on token rarity, DF ≤ 5 / ≤ 30 | 0.849 | 0.745 |
| the same, **weight 0** | 0.849 | 0.750 |

Weight 0 is the result that matters. A measure match that contributes *nothing* to
the score costs exactly as much recall as one weighted 5. The damage is not scoring,
it is **admission**: `_rank_rows` keeps any row with at least one match, and
`_select_hits` then chooses among them, so a new field lets rows in that displace
better rows before any weight is consulted. No weighting or gating can fix that,
because no weighting or gating is what breaks it.

The other half of the finding kills the idea on its own terms. The questions that
fail hardest fail because their words are absent from the registry entirely, not
because they are hidden inside tables:

| query token | datasets whose title/keyword/theme says it | datasets with it as a measure |
|---|---|---|
| `yrkesdeltakelse` | 0 | 0 |
| `barnehagedekning` | 0 | 0 |
| `domfelte` | 0 | 0 |
| `alder` | 905 | 116 (0 of them gold) |
| `nett` | 235 | 197 (1 of them gold) |

Where a token is rare enough for a measure lookup to be informative it is usually
absent from the measures too; where it is present in the measures it is common
enough to match everywhere. That is the same shape as the earlier rarity-weighting
rejection, measured from the other side.

**What this means for the next attempt.** The remaining held-out failures are a
Norwegian vocabulary problem — `yrkesdeltakelse` against `arbeidsstyrken`,
`domfelte` against `straffede personer`, `barnehagedekning` against `andel barn i
barnehage`. Writing those pairs into `QUERY_SYNONYMS` would raise the number and
destroy the held-out set, which exists to be measured once; it must not be done.
The honest routes left are a better embedding model (`multilingual-e5-large`,
deferred on disk, not on merit) or a synonym source derived from something other
than the questions being scored.

## Lifting each lane's top result: +0.035 tuned, +0.000 held out

A stage-by-stage trace of the twelve tuned-set misses found four where one lane
ranked the answer first and the combination buried it: `hvor mange studenter er det
i Norge` and `hvor mange boliger ble bygget i fjor` were lexical rank 1 and came out
9th and 7th; `husholdninger størrelse` was semantic rank 1 and came out 8th.

Two things were measured off that trace.

**The rules that buried them still earn their place.** Both routing and demotion were
chosen when recall was 0.709, and the stack has changed a great deal since, so both
were re-ablated through `find` on today's stack:

| | tuned recall@5 | MRR |
|---|---|---|
| baseline (route + demote) | **0.860** | **0.763** |
| always fuse + demote | 0.849 | 0.672 |
| route, no demote | 0.860 | 0.750 |
| always fuse, no demote | 0.860 | 0.648 |

Per-question the trace is right and both rules do throw away a rank-1 answer. In
aggregate they each win more than they lose. Neither should be removed.

**The obvious repair does not generalise.** The smallest rule that keeps those four —
move each lane's top result to the front, no threshold to tune — measures:

| | tuned recall@5 | tuned MRR | held-out recall@5 | held-out MRR |
|---|---|---|---|---|
| baseline | 0.860 | 0.763 | **0.811** | **0.723** |
| both lanes' top-1 to the front | 0.895 | 0.750 | 0.811 | 0.620 |
| only if absent from the top 5 | **0.895** | 0.762 | 0.811 | 0.665 |

Three questions gained on the set the rule was derived from; zero on the set it was
not, and MRR falls 6 to 10 points there. This is what looking at misses and fixing
them produces, and it is worth keeping as a calibration: a +0.035 tuned gain
transferred as exactly 0.000. Rejected.

## The questions nothing finds are not coverage gaps

The five tuned-set misses that neither lexical nor semantic ranking reaches at any
depth all have an answer sitting in the registry, and one BM25 lookup on the right
word returns it:

| question | what a direct lookup returns |
|---|---|
| hva er gjennomsnittsalderen i Tromsø | `13536: Gjennomsnittsalder og medianalder i kommuner, fylker og hele landet` |
| hvor mye tjener en sykepleier i gjennomsnitt | `13311: Månedslønn og alder, etter arbeidstid, kjønn og yrke` |
| hvor mye har prisene steget det siste året | `14710: Konsumprisindeks, historisk serie` |
| hvor stor er Norge i kvadratkilometer | `Arealstatistikk for Norge` |
| bruttonasjonalprodukt | `09391: Hovedtall fylkesfordelt nasjonalregnskap` |

So the ceiling is not the catalogue and it is not the index. The asker says "hvor mye
har prisene steget"; the table says "konsumprisindeks". Nothing in the query survives
tokenisation as a word the catalogue uses, and the embedding lane does not bridge it
either. Every remaining failure is this same translation gap, which is why six
attempts to squeeze more out of ranking have all failed: the ranking is not what is
broken.

## Pseudo-relevance feedback cannot repair a ranking it depends on

The translation gap has a standard IR answer: take the top few results, harvest the
terms that are frequent in them and rare in the catalogue, and search again with the
catalogue's own words. It needs no synonym list and nothing derived from the labelled
questions, and it visibly produces the right vocabulary — for `lønn etter yrke` it
proposes `månedslønn, arbeidstid, yrkesfordelt, årslønn` and the expansion lane then
ranks the gold table **1st**, as it does for `husholdninger størrelse` and `hvor mange
studenter er det i Norge`.

It still cannot be used. Expansion terms cannot be appended to the query, because
`decompose` makes every token a hard AND requirement and one wrong guess excludes
everything, so it has to be a third lane. As a lane it measures:

| | tuned recall@5 | MRR |
|---|---|---|
| baseline | **0.860** | **0.763** |
| PRF lane fused at full weight (RRF k=10) | 0.535 | 0.423 |
| PRF lane discounted, k=60 | 0.721 | 0.565 |
| PRF lane heavily discounted, k=200 | 0.756 | 0.638 |

The scores rise monotonically as the lane's weight falls, which is the whole result:
the best contribution this lane can make is not to participate. Dropping years and
table numbers from the terms — `1970`, `2026`, `12543` were eating half the budget —
improved the terms visibly and moved the numbers not at all.

The reason is structural, and it is why no tuning rescues it. The feedback set is the
semantic lane's top results. On a query the stack already answers, they are right and
the expansion is redundant; on a query it fails, they are wrong and the expansion
describes the wrong subject confidently. PRF amplifies an initial ranking; it cannot
repair one. Since the failures we care about are exactly where the initial ranking is
wrong, the technique is aimed away from the problem.

There was no cheap trigger to gate it, either. `lex = -` in the stage trace means the
gold table is absent from the lexical lane's top 50, not that the lane is empty — only
2 of 86 tuned questions have an empty lexical lane, and both are already answered.

## What finally moved the honest number: asking a model for the catalogue's word

Six attempts to improve the ranking all failed because the ranking was not what was
broken. The gap is translation — the asker writes "hvor mye har prisene steget",
Statistics Norway writes "konsumprisindeks", and neither the lexical index nor
`text-embedding-3-small` bridges it.

A language model bridges it in one call. It is asked for **search terms only**, never
sees a dataset and never names one, and the terms it returns are recorded in the
retrieval steps and surfaced by the MCP `search` tool as `ranking_steps`. Nothing it
says is evidence: results still come from the index, values still come from a fetch,
and a wrong term costs a bad search rather than a wrong answer. The knowledge comes
from Norwegian rather than from the labelled questions, which is why it was allowed to
be measured on the held-out set at all.

| | tuned recall@5 | tuned MRR | held-out recall@5 | held-out MRR | held-out natural |
|---|---|---|---|---|---|
| baseline | 0.860 | **0.763** | 0.811 | 0.723 | 0.812 |
| + query rewriting | **0.872** | 0.746 | **0.865 – 0.892** | 0.729 – 0.738 | **0.938 – 1.000** |

**The held-out gain is larger than the tuned gain**, which is the point. The previous
attempt — lifting each lane's top result — gained 0.035 on the set it was derived from
and 0.000 on the set it was not. This one gains 0.012 where it could have been fitted
and 0.054 to 0.081 where it could not, because nothing about it was fitted to anything.
Naturally phrased questions go from 13 of 16 to 15 or 16 of 16.

**The range is real and is not a choice of the best run.** Four runs of the held-out
set measured 0.892, 0.865, 0.892, 0.865. The model returns different terms for the same
question — 26 of 123 rewrites changed between two runs — and `temperature: 0` reduces
that without removing it. So the effect is +2 to +3 questions of 37, with a run-to-run
spread of one question. Anyone re-running this should expect a number in that band and
should not report the top of it.

**Integration matters as much as the terms.** Each term is searched separately, because
the terms are alternatives and `decompose` would make a conjunction of them exclude
everything. The results are interleaved behind the head of the original ranking, not
fused into it: fusing measured 0.802 tuned and 0.757 held-out, worse than doing nothing.
A rewrite is a second opinion about the subject, and RRF treats it as a second vote on a
ranking.

**What it costs.** One model call plus one search per term, so roughly six times the
work of a plain query. The FTS pre-filter landed first and made each search ten times
cheaper, which is most of what pays for this. Rewrites are cached in `query_rewrites`
keyed by query and model, so a repeated question costs nothing, and an empty result is
cached too — a question that gains nothing from rewriting should not pay for a call
every time it is asked.

**Still failing, and now clearly.** `yrkesdeltakelse kvinner`, `domfelte etter alder`
and `barnehagedekning` remain missed, and the rewriter is why: asked about
`yrkesdeltakelse` it returns `yrkesdeltakelse`, and about `domfelte` it returns
`domfelte`. It translates dagligtale into statistics vocabulary but does not translate
one statistics word into the synonym this catalogue happens to use. Sharpening the
prompt against those three would be fitting it to the held-out set and must not be done;
the legitimate version is a synonym source built from Klass or from SSB's own subject
hierarchy, which no question set would have chosen.

## Klass is a register of administrative renames, not a synonym source

The model-backed rewriter leaves one kind of failure: it translates dagligtale into
statistics vocabulary but not one statistics word into this catalogue's synonym for
it, so `yrkesdeltakelse` comes back as `yrkesdeltakelse`. Writing those pairs by hand
would fit the held-out set. Klass was the principled alternative — SSB's own
classification service, every historical version of every standard, one code carrying
different names over time. `2.03` was "Spesialiserte fosterhjem" and is now "Statlige
familiehjem". SSB maintains that record for its own reasons, so using it spends
nothing.

All 151 classifications and 837 versions were downloaded (`scripts/harvest_klass.py`,
about 12 minutes at 2 req/s, none failed). After extraction it yields 3,245 rename
pairs. It then proposes a term for **8 of the 131 labelled questions, and all 8 are
wrong**:

| query | Klass proposes |
|---|---|
| hvor mange bor det i Bergen | `Bergen amt` (abolished 1763) |
| hva koster en bolig i Oslo | `Christiania amt`, `Oslo Havn KF` |
| hva er gjennomsnittsalderen i Tromsø | `Tromsø Havn KF` |
| husholdninger størrelse | `Andre næringer - stasjonær forbrenning` |

| | tuned recall@5 | MRR | held-out recall@5 | MRR |
|---|---|---|---|---|
| baseline | 0.860 | 0.763 | 0.811 | 0.723 |
| + Klass rewriting | 0.860 | 0.763 | 0.811 | 0.723 |
| + model rewriting | 0.872 | 0.746 | 0.865 – 0.892 | 0.729 – 0.738 |
| + both | — | — | 0.892 | 0.738 |

Unchanged to three decimals on both sets. The combination lands inside the model
rewriter's own run-to-run band, so Klass adds nothing there either.

**Why, and it is the same reason as the resource index.** `husholdninger` →
`Andre næringer - stasjonær forbrenning` is a *correct* Klass rename, of a category
code in an emissions standard, and it is catastrophic as a synonym for a question
about household size. A word common enough to appear in a question is common enough
to name different things in different standards; a word unambiguous enough to be safe
is too rare for anyone to ask about. Klass records what administrative units and
category codes have been called, and questions are not about administrative units.

**Two hazards found on the way, both real and both handled.** Reading version history
naively claims Trøndelag is Vestlandet, because landsdel codes were *renumbered* — the
tell is a name that has belonged to two codes in one standard, and every pair such a
name appears in is now dropped. And most name changes are not renames at all:
punctuation (`Refne - Banken` / `Refne/Banken`), case (`Vold-Skog` / `Vold-skog`), a
corrected typo (`Sommerr0` / `Sommerro`), a renumbered paragraph reference. `is_rename`
compares word by word rather than as strings, ignoring digits and connectives, because
comparing whole names calls a typo fix in a short name a rename and a renumbered
statute a rename.

**A measurement bug worth remembering.** The first Klass run scored 0.865, beating
baseline. It was reading the model's cached terms: `terms_for` keyed its cache on a
default model name rather than on the rewriter, so any rewriter got whatever had been
written under `gpt-4.1-mini`. The cache key is now the rewriter's own name and
`test_rewriters_do_not_read_each_others_cached_terms` holds it there. A result that
flatters a new component is worth one look at whether the component ran at all.

**What is kept.** The harvester and the mirror, because a complete local Klass copy has
uses beyond vocabulary — join keys are already verified against Klass over the network.
The extraction and `KlassRewriter` are kept, opt-in and wired into nothing, with the
result at the top of the module. The remaining honest route for this gap is still a
better embedding model, which is deferred on this machine by choice rather than merit.

## `text-embedding-3-large` is worse here, at both widths

The remaining honest route for the vocabulary gap was a better embedding model, and
`multilingual-e5-large` is deferred on this machine by choice. `text-embedding-3-large`
tests the same hypothesis without local compute: it is an API call, so no download, no
2.2 GB resident, no local inference. It is also the stronger model on OpenAI's own
benchmarks.

It loses.

| | tuned recall@5 | tuned MRR | held-out recall@5 | held-out MRR | held-out keyword | held-out natural |
|---|---|---|---|---|---|---|
| `3-small` (1536) | **0.860** | **0.763** | **0.811** | **0.723** | 0.810 | 0.812 |
| `3-large` truncated to 1536 | — | — | 0.784 | 0.727 | 0.714 | 0.875 |
| `3-large` at full 3072 | 0.733 | 0.617 | 0.811 | 0.718 | 0.714 | 0.938 |
| `3-small` + rewriting | — | — | **0.865** | **0.733** | 0.810 | 0.938 |
| `3-large` + rewriting | — | — | 0.811 | 0.717 | 0.714 | 0.938 |

Truncation is not the explanation — full width scores the same 0.811 held-out and is
much worse on the tuned set. Both widths are stored under the same model name, so the
1536 index was replaced rather than kept alongside.

**A caution about reading the held-out split.** At full width `3-large` looks better on
naturally phrased questions there, 15 of 16 against 13 of 16, which is a tempting story:
a stronger model for the phrasing an MCP server actually receives. The tuned set has 43
natural questions rather than 16 and says the opposite — 0.628 against 0.814. Sixteen
questions cannot separate two models, and the apparent gain was noise. The tuned number
is the one to believe here, which is the reverse of the usual rule and only because this
comparison was never tuned on anything.

Once query rewriting is on, the question settles: `3-small` 0.865 against `3-large`
0.811. Rewriting already closes the natural-language gap — both reach 15 of 16 — so
`3-large`'s only remaining distinction is that it is worse on keyword queries, 15 of 21
against 17 of 21.

**What this does and does not establish.** Routing, fusion weights and demotion were all
fitted against `3-small`'s score distribution, so this measures `3-large` inside a stack
shaped for another model, not its ceiling. That is the practical question — swapping the
model in is not a win — but a rebuild of the ranking around it was not attempted. What it
does establish, together with the `nb-sbert` result, is that a bigger or more
language-specific embedding model is not the missing ingredient. Two models from opposite
directions have now failed to beat `text-embedding-3-small` on this corpus.

**A correctness fix came out of it.** `semantic_ranking` chose the index by vector width
when no model was named, which was safe only while one model was stored at each width.
`3-large` truncated to 1536 is the same width as `3-small` and means something entirely
different, and comparing across them ranks badly without erroring. The provider's own
model now selects the index, with `test_embedding_model_selection.py` holding it there.

## Reranking a shortlist: the answer was usually found, just placed too low

Two signals said the ranking was leaving something on the table rather than failing to
retrieve it. `pda benchmark` scored 0.938 at ten against 0.892 at five, and the held-out
misses sat at rank 10, 11 and 32 — retrieved, and ranked past where anyone looks.

Showing a model twenty real titles and asking which answers the question closes most of
that:

| | tuned recall@5 | tuned MRR | held-out recall@5 | held-out MRR |
|---|---|---|---|---|
| baseline | 0.860 | 0.763 | 0.811 | 0.723 |
| + query rewriting | 0.872 | 0.746 | 0.865 – 0.892 | 0.729 – 0.738 |
| + rewriting **and** reranking | **0.884** | **0.766** | **0.892** | **0.759** |

Held-out misses fall from 7 to 4, and the two the reranker fixes are exactly the ones
the diagnosis predicted: `barnehagedekning` at rank 10 and `hvor mye vann bruker en
husholdning` at rank 11. Keyword questions rise to 18 of 21. MRR is the clearest gain —
0.723 to 0.759 — which is what "it was already there, one page down" looks like when it
is fixed.

**The merge matters more than the reranking.** Handing the model's ordering straight to
the caller measured *worse* than doing nothing, 0.860 against 0.872 on tuned. What works
is holding the original first result in front and letting the model's top three follow:

| merge (tuned, with rewriting) | recall@5 | MRR |
|---|---|---|
| model's ordering, wholesale | 0.860 | 0.729 |
| model's top 1 first | 0.907 | 0.759 |
| **keep 1, then model's top 3** | 0.895 | 0.768 |

The shipped merge is the third, chosen on the tuned set *without* rewriting, where it
also won, before any held-out number for it existed. `model's top 1 first` scores higher
on tuned (0.907) and lower on held-out (0.865), which is the reason not to pick the best
cell in a table: these variants sit within each other's noise, and the difference between
them is smaller than the run-to-run spread. Implementation measured 0.884 tuned where the
prototype measured 0.895, from the same nondeterminism the rewriter has.

**Why this is safe, and it is structural rather than a promise.** The model is shown
titles the index returned and answers with *positions in that list*. It cannot name a
dataset, so it cannot introduce one; a position outside the list is discarded rather than
interpreted. Anything it does not rank keeps its original order behind what it did, so a
truncated, lazy or failed answer degrades to the ranking that was already there. It
reorders candidates, never supplies a value, and never authorises a fetch.

**Cost.** One call per query on top of the rewrite call, roughly 800 tokens of titles.
Orderings are cached in `query_reranks` keyed by the query *and the shortlist* — an
ordering is positions, and positions mean nothing without the list they were given, so a
changed shortlist is a cache miss rather than a silent mismatch.

**What still fails.** `yrkesdeltakelse kvinner`, `lønnsomhet i industrien` and `domfelte
etter alder` are all "not in depth" — the reranker only reorders what retrieval found,
and these are never found. They are the same vocabulary gap that Klass and a bigger
embedding model both failed to close.

## Plural questions, singular titles: the fix is real but only in the bare-noun case

NVDB names a register with a bare noun — `Bru`, `Gjerde`, `Rekkverk` — and a question
asks about several of them, so `bruer i Norge` reached none of the 423 road registers.
Codex hit the same wall from the other side: SSB titles table 08507 in Nynorsk
(`passasjerar`), and the Bokmål question `luftfart passasjerer` does not reach it. Two
independent sightings of one thing, which is what made it worth fixing as a language
rule rather than a special case.

`fold_inflection` removes at most one regular Norwegian plural ending — `-ene`, `-ane`,
`-er`, `-ar` — and `-het` is handled first because it is derivational, not inflectional:
`leseferdighet` is already the base form and reading its `et` as a definite ending
produces `leseferdigh`, which is not what any other form reaches. This is deliberately
not a stemmer; it only ever compares a query token to a token some resource actually
publishes, so a fold that produces a non-word matches nothing.

**Where it applies is the whole result, and it took four measured attempts to find.**

| scope | tuned recall@5 | tuned MRR | held-out recall@5 | held-out MRR |
|---|---|---|---|---|
| no folding | **0.860** | **0.755** | **0.811** | **0.723** |
| all endings, all fields | 0.849 | 0.740 | 0.784 | 0.698 |
| all endings, title only | 0.849 | 0.746 | — | — |
| plural endings, all fields | 0.860 | 0.750 | 0.784 | 0.698 |
| plural endings, folded match at half weight | 0.860 | 0.750 | 0.784 | 0.698 |
| **plural endings, one-word titles only** | **0.860** | **0.755** | **0.811** | **0.723** |

Every broad version costs a question on each set, and in both cases by promoting tables
that are genuinely about the subject: folding `leiepriser` to `leiepris` lets more rent
tables compete and pushes the labelled one from rank 1 to 16; folding `prøver` to
`prøve` does the same for the national-test tables. Weighting a folded match at half an
exact one did not repair it. The gain lives entirely in the bare-noun case, so that is
where the rule now lives: a one-word title folds, a multi-word title does not.

The final version is **bit-for-bit identical** to no folding on both labelled sets —
0.860/0.755 and 0.811/0.723, 0.892/0.759 with the model steps, `pda benchmark` 0.8923 —
while `bruer i Norge` now returns `nvdb:60` first and `gjerder` returns `nvdb:855`.

**A bias worth naming.** When the broad version cost a question, inspection suggested the
displacing tables were better answers than the label — SSB's `Mestringsnivå ... etter
klassetrinn, prøve` tables outranking FHI's `Leseferdighet_UTDANN_1` indicator for
"leseferdighet nasjonale prøver". That may well be true, and I did not relabel, because
the incentive to declare a label wrong is at its strongest exactly when a change of mine
caused the regression. The labels stand and the narrow rule was found instead.

**A limit of the instrument, stated plainly.** The labelled sets contain no NVDB
question, so they can measure this change's cost and not its benefit. That asymmetry is
why the bar here was "costs nothing measurable" rather than "wins on the metric"; a
version that traded held-out MRR for an unmeasurable gain was available and was not
taken. `luftfart passasjerer` still does not reach 08507: that needs Nynorsk/Bokmål
vocabulary, not plural folding, and it is a held-out question, so it should not be
optimised against directly.

## Nynorsk and Bokmål: 52 spellings bridged, at no measured cost

SSB writes each table in whichever written norm its authors chose, so the catalogue
holds `Overnattingar` in 24 titles and `Overnattinger` in 4, `personar` in 4 and
`personer` in 494. A question using one spelling could not see the tables using the
other. This was found twice independently — Codex hit it on `passasjerar`, and the
NVDB work hit the neighbouring plural problem.

**The rule is a swap between endings, never a removal, and that is the whole safety
argument.** Removing `-er` turns `leiepriser` into `leiepris`, which lets every rent
table compete and cost a question on both labelled sets when inflection folding was
tried. Swapping it produces `leieprisar`, which nothing publishes, so it matches
nothing and costs nothing. `spelling_variants` never reaches a bare stem.

Four correspondences, each checked against the catalogue before it was added:
`-ar`/`-er`, `-ane`/`-ene`, `-leg`/`-lig`, `-ande`/`-ende`.

**The precision check is the part worth keeping.** Every variant the rule can generate
that is *also* a published word was enumerated — 52 distinct pairs, the only ones that
can change any search — and all 52 are genuine variants of one word: `personer`/
`personar`, `offentlig`/`offentleg`, `sommer`/`sommar`, `elver`/`elvar`,
`næringsdrivande`/`næringsdrivende`. No false pair.

**Rules that were tried and refused**, all on evidence from the same sweep:

| candidate | why not |
|---|---|
| `au` ↔ `ø` | would equate **Aurland** with **Ørland**, and `austre` with `østre` |
| `ei` ↔ `e` | would equate **Eigersund** with **Egersund**, `eid` with `ed` |
| `dd` ↔ `d` | `skadde`/`skade`, `idd`/`id` — different words |
| `hamn` ↔ `havn` | a genuine correspondence, but stem-internal rather than a suffix, so it needs a different mechanism for three pairs. Also noticed while diagnosing a held-out question, which makes it the wrong thing to add on a hunch |

A minimum stem of three letters does the rest of the work: `sande` is a municipality and
would otherwise swap to `sende`.

**Measured at zero cost and demonstrated gain.** Both labelled sets are bit-for-bit
unchanged — tuned 0.860/0.755, held-out 0.811/0.723, 0.892/0.759 with the model steps,
`pda benchmark` 0.8923. The gain is in reach the labelled sets do not measure: a query
for `personar` reached 4 datasets and now reaches 100, `barnehagar` 5 and now 88,
`gjennomsnittleg` 11 and now 100, `fagleg` 2 and now 39. Read the other way,
`overnattinger` reached 1 and now reaches 24, `bekymringsmeldinger` 1 and now 10.

**A claim I made here was wrong.** This entry originally said `luftfart passasjerer`
still does not reach table 08507, because the title says `Lufttransport` where the
question says `luftfart`. I wrote that without re-testing after the spelling rule landed.
It is false: `passasjerer` now matches `Passasjerar`, and 08507 ranks **first** both with
and without the model steps. The `luftfart`/`Lufttransport` mismatch never had to be
solved, because the other token in the query carries the match. Stating a limitation is
a measurement like any other and should not be done from memory.

## Two more labels corrected, and the number went down

`data/heldout_gold.json` recorded `luftfart passasjerer` (h018) and `oppdrettslaks
produksjon` (h024) as having no answer in the registry. Both now have one, and neither
was judged from a title — both were verified by live one-cell fetches in the crawler
lane. `ssbtable:08507` returned 2,737,712 passengers for Oslo Gardermoen in 2026M07, and
`fdirpx:A06002a` returned 1,754,557 tonnes of salmon for 2025.

The original labels were not wrong when they were written: 08507 sat in the registry
unverified, and the Fiskeridirektoratet connector did not exist. Coverage moved, so the
labels had to.

**This lowers the reported number, which is the point of recording it.** Two questions
move from excluded to scored, and only one of them is answered:

| | before (37 scored) | after (39 scored) |
|---|---|---|
| lexical + semantic | 0.811 / 0.723 | 0.795 / 0.712 |
| + rewriting and reranking | 0.892 / 0.759 | **0.872 / 0.745** |

The absolute count went up — 33 of 37 became 34 of 39 — while the rate went down. Any
future comparison against 0.892 is against a set that excluded a question the stack
cannot answer.

`oppdrettslaks produksjon` is now a scored miss, not in the top 50. The connector lane
predicted exactly this: the publisher's title is `Matfisk. Salg av laks`, and the
question's `oppdrettslaks` is a compound whose second element is the word that matches.

## Splitting compounds the catalogue never names anything with

`oppdrettslaks` appears in no title. The publisher wrote `Matfisk. Salg av laks`, so the
question reached nothing even though the word that matches was sitting there. The
connector lane predicted this in writing before it became a scored miss.

The splitter cuts a token where **both halves are words the catalogue publishes**, and
it is the conditions on that, not the idea, that took the work. Each one exists because
a looser version measured worse:

| condition | what it prevents |
|---|---|
| the compound is not itself a **title** word | `eierskap` → `eier` + `skap` (cupboard), `barnehage` → `barn` + `hage` (garden). The catalogue titles 30 things `barnehage`, so the exact match is the right match |
| both halves appear in ≤ 5% of resources | `datahotell` → `data` + `hotell`. `data` is in 7.5% of the catalogue, and splitting on it dropped the answer from rank 8 out of the top 20 |
| a part match scores a tenth of a whole match | a title part (10 × 0.5 = 5) outscored a description match on the word itself (2), and five single-word benchmark queries fell from rank 1 to 2 |
| four letters minimum per half | stops arbitrary cuts of short words |

Checking the title specifically is what made it work at all: `oppdrettslaks` does occur
in some description, so asking "is this word published anywhere" left it unsplit. Asking
"does the catalogue **name** things with it" is the right question, and it needed a
`title` column on the FTS index to answer.

Audited the same way as the spelling rule: of the 223 tokens across both labelled
question sets, 29 can be split and only 11 survive the conditions — `oppdrettslaks`,
`barnehagedekning`, `yrkesdeltakelse`, `boligpriser`, `byggekostnader`, `deltidsarbeid`,
`gjennomsnittsalderen`, `kraftproduksjon`, `leiepriser`, `strømpriser`, `vindkraft`. All
eleven are genuine compounds. The rule also reproduces `befolkningsvekst` →
`befolkning` + `vekst`, which was one of the two hand-written entries in
`QUERY_COMPOUND_SPLITS`, which is some evidence the rule is the one a person was
approximating.

**A latent bug it exposed.** `_requirement_satisfied` compared the *question's* word
against the *stored* tokens that matched. Any match found through a split, an inflection
fold or the other written norm therefore failed its own requirement and the row was
dropped — the split found `laks` and then threw the row away for not containing
`oppdrettslaks`. Matches now carry the query token that produced them.

| | before | after |
|---|---|---|
| held-out, lexical + semantic | 0.795 / 0.712 | **0.821 / 0.724** |
| held-out, full stack | 0.872 / 0.745 | **0.897 / 0.745** |
| tuned, lexical + semantic | 0.860 / **0.755** | 0.860 / 0.741 |
| `pda benchmark` | 0.8923 / 0.9385 / 0.8287 | 0.8923 / 0.9385 / 0.8210 |

The held-out set gains a question and improves on both measures. The cost is MRR
elsewhere: three tuned questions move from rank 1 to ranks 2–5 while staying hits, and
five single-word benchmark queries move from 1 to 2. Both protected benchmark
recalls hold exactly. That trade was taken because the honest set improved on both
measures and no question was lost anywhere.

## Word-level embeddings match spelling, not meaning

The three remaining held-out misses are all one shape: the asker's word is a synonym the
catalogue never uses. `yrkesdeltakelse` where the titles say `arbeidsstyrken`, `domfelte`
where they say `Straffede personer`, `lønnsomhet` where they say `Nøkkeltall`.

The obvious mechanism, and the one that would need no per-question tuning: embed the
catalogue's title vocabulary and, for a word the catalogue never uses, propose its
nearest published word. Tested before building, on 1,503 sampled title words with the
right answers deliberately included in the pool:

```
domfelte         feierode, ferjelem, fortalt, fjelldal, dumpefelt
fattigdom        volden, alvorlig, arbeidskraft, overflatesaltholdighet
folketall        folketeljinga, statsborger, generelt, grunnboken
yrkesdeltakelse  yrkesstatus, deltakelse, yrkestilknytning
```

`domfelte` finds `feierode` and `fjelldal`. `fattigdom` never finds `lavinntekt`. An
isolated Norwegian word out of context gives `text-embedding-3-small` almost nothing but
characters to go on, so the neighbours are words that *look* alike. Only
`yrkesdeltakelse` produces anything sensible, and not the word its gold titles use.
Rejected without building it.

**What the model does know, and where.** Asked about a single word with instructions to
give SSB's term, the same model answers well — `fattigdom` → `lavinntekt`,
`folketall` → `befolkning, folkemengde`, `yrkesdeltakelse` → `arbeidsstyrke,
sysselsatte`. Asked about the whole question, it returns `yrkesdeltakelse` unchanged,
because in context the word already reads as a statistical term. Sharpening the prompt to
say "if the user's word is a fagord but not the one SSB titles things with, give SSB's"
helped generally (held-out MRR 0.745 → 0.749, recall unchanged) but did not move these
three. Iterating the prompt further until they pass would be fitting it to the held-out
set, so it was not done.

**A flaw the prompt work exposed.** Rewrites were cached on the model name alone, so
changing the instructions kept serving terms the old prompt wrote — a silently stale
answer and an experiment that measures nothing. The cache key now includes a digest of
the instructions.

## A question word that is the head of a longer title word: measured, not built

`pengemarked` does not retrieve `norgesbank:MONEY_MARKET`, titled `Pengemarkedsdata`. The
prefilter keeps the row because FTS5 matches by prefix, and the scorer then drops it
because it matches whole words. The compound splitter handles the opposite shape — a
question compound whose halves the catalogue publishes — so this case was measured before
anything was written.

Occurrence counts only; no gold label was read, so this cannot fit to either set.

| | question tokens | unpublished heads of longer title words |
|---|---|---|
| tuned | 159 | 8 |
| held-out | 76 | 2 |

Reach is small, which makes dilution a minor risk: the widest, `konkurs` and
`overnatting`, each touch 27 titles (0.2%). Quality is mixed. `sykepleier` → `sykepleiere`,
`røyker` → `røykere` and `kollektivt` → `kollektivtransport` are the right words;
`tømmer` → `tømmerneset` is a place name. `pengemarked` itself is in no labelled question.

So a rule here would be low-risk and nearly unmeasurable: ten tokens across both sets,
several already reached another way, and the case that prompted it not represented at all.
Not built. The obvious guard would be the splitter's — accept a longer title word only if
the tail after the question's word is itself a published word — and checking the tails
shows it is too blunt to rescue the idea. It refuses `tømmerneset` (`neset` is in no title),
which is right, and keeps `kollektivtransport` (`transport`, 14 titles) and `konkursbo`
(`bo`, 1). But it equally refuses `sykepleiere` (`e`, 0), `vindkraftselskap`
(`kraftselskap`, 0) and `konkursdebitor` (`debitor`, 0), which are the right words. The guard
tracks whether a tail happens to be published, not whether the match is good.

## Fetchable gold grew by 12 questions (dairy, nature areas, Oslo, Norges Bank)

`data/fetchable_gold.json` was 88 questions. a089–a100 add dairy deliveries,
nature-protection areas, Oslo kommune statbank population, and Norges Bank
policy rate / exchange rates. Labels from published titles; 2025 dairy litres,
naturvern features, Oslo BEF008, and Norges Bank IR/EXR were confirmed by live
fetches. Dairy expected is every year-card of the same series (2013–2025), not
only 2025.

Held-out h023/h041 were widened the same way. That is a label correction from
titles, not a ranking change. Scored held-out questions stay 42.

Lexical `retrieval.find` on the 12 new questions, 2026-09-14: **8/12 = 0.667**
recall@5. Hits: milk (both), naturvern (both), `folkemengden i Oslo`,
styringsrente (both), valutakurser. Misses: Oslo 1801, Oslo bydel (keyword and
natural), dollarkursen. Held-out h022/h023/h041 all hit after the dairy widen
(h023 rank 2 on the 2022 year-card).

The original 88-question 0.860 figure is not remeasured here. Comparing 0.860
to a 100-question run would mix two instruments.

## Sources never harvested, and one run stuck as "running"

Resolved 2026-09-22: brreg, npolar, sodir, valg and hiwms are
harvested (63 datasets); see CONNECTOR_LOG. trondheim is retired
upstream and cannot be harvested at all. fdirpx run 16, started
2026-09-10, is still marked `running`. It was not closed, pending a
decision about Codex's crawl.

What remains is depth, not reach: the 2026-09-12 harvest stopped at 10
datasets per source, and today's five were capped at 25. valg needs
about a minute per dataset, so a full walk of it is a long job.

## Question routing re-measured: semantic alone still wins (2026-09-21)

Question-style queries are ranked by embedding alone (8a0fc89,
2026-09-06). That was re-measured on the tuned set with complete
embeddings, embedding plus lexical only (no rewriting or reranking).
There are 49 question-style queries:

| variant | recall@5 | MRR |
|---|---|---|
| A semantic only (current) | 0.816 | 0.750 |
| B RRF fusion with lexical | 0.776 | 0.582 |
| C semantic top 2, then lexical top 3 | 0.857 | 0.721 |

B loses on 18 of the 23 questions whose rank changed, for example
"avfall per innbygger" 1 → 18. C lifts two questions into the top 5
(studenter 10 → 3, boliger bygget 7 → 2) but pushes four rank-1
answers down. Both gains come from the set being tuned on, so C was not
adopted. Subject queries are unaffected by all three variants.
Remaining question misses are semantic: the table's title does not say
what the question asks about. Examples: "gjennomsnittsalder" is a
column of 07459; Norway's area is a row of 11342.

## The ten remaining tuned misses are not a value-index problem (2026-09-23)

What is left after embedding coverage was fixed: ten questions whose
answer is a column, a row or a value inside a table rather than its
title. Examples: "gjennomsnittsalderen i Tromsø" is a column of 07459,
Norway's area is a row of 11342, "sykepleier" is a value in 11418's
occupation dimension.

The value index records exactly this, and for 6 of the 10 the query's
distinctive word is recorded as a value of the expected table at low
document frequency: bruttonasjonalprodukt 0.2%, organisasjonsform
0.4%, sykepleier 1.1%, studenter 1.6%, gjenvinning 1.7%, ansatte 2.2%.
Three cannot work that way at all: "frafall" is never a value,
"kvadratkilometer" is a unit rather than a value, and "tromsø" sits in
6.6% of indexed resources, which is the common-value failure that sank
the first attempt.

Feeding those hits into the ranking was measured twice and lost twice;
the numbers are in the comment in `retrieval.find`. Ranked on its own,
the value index puts the expected table at rank 2 for two of the ten
and at 6, 12, 14, 23 and 42 for the rest, so it is not a ranking of how
well a resource answers -- it is a filter for what a resource holds.

What these questions actually need is a match against a resource's
*columns and units*, not its values: "gjennomsnittsalder" and "areal"
are field labels, "kvadratkilometer" is a unit. `search_resources`
weights a field label at 2 against a value label at 6. Whether
promoting field-label and unit matches fixes these ten without
disturbing the other 88 has not been measured.

## A second vector built from a resource's fields: gained on the tuned set, gained nothing held out (2026-09-23)

The ten remaining tuned misses need a resource's *columns*, not its title:
11342 is titled "Areal og befolkning i kommuner" and measures "Areal
(km²)"; 11418 measures "Månedslønn (kr)" and offers "Gjennomsnitt".
Re-weighting `search_resources` cannot help, because `find` does not
call it -- the ranking is the title lane. So the field text was put
into the embedding instead. Three designs, all measured on the tuned
set with embeddings only, against 0.867 recall@5 / 0.741 MRR:

| design | recall@5 | MRR |
|---|---|---|
| field text appended to the embedded text, narrow fields | 0.837 | 0.670 |
| the same, measure field only, 300 chars | 0.806 | 0.686 |
| a second vector, ranked by max(title, 0.90 x fields) | 0.888 | 0.750 |

Appending loses because the added vocabulary dilutes the title the
ranking depends on: 8 losses to 3 gains for the first, 7 losses to 0
for the second. Keeping the two representations separate and merging by
the stronger score does better, and the discount is what makes it work
-- undiscounted, a resource merely listing the query's words outranks
one about them:

| discount | recall@5 | MRR |
|---|---|---|
| 1.00 | 0.816 | 0.681 |
| 0.95 | 0.867 | 0.752 |
| 0.90 | 0.888 | 0.750 |
| 0.85 | 0.878 | 0.746 |
| 0.80 | 0.867 | 0.742 |

That is a real curve with a peak, not a spike, and it was tempting. It
does not survive the held-out set:

| set and stack | base | with the field vector |
|---|---|---|
| tuned, embeddings only | 0.867 / 0.741 | 0.888 / 0.750 |
| tuned, full stack | 0.898 / 0.769 | 0.898 / 0.766 |
| held-out, embeddings only | 0.833 / 0.716 | 0.833 / 0.716 |
| held-out, full stack | 0.905 / 0.746 | 0.881 / 0.735 |

The tuned gain is two questions, neither of them one of the ten misses
this was built for (measles vaccination 16 -> 1, exports 7 -> 2). Under
the full stack the rewriter and reranker already recover them. Held
out, the gain is exactly nothing, and the full stack loses a question.
Reverted, and the index deleted: 4,697 vectors, about 29 MB.

The field text rule is worth keeping on record, since building it again
is the only cost: the values of every field with at most 60 of them,
excluding period fields and fields whose values are numbers (years,
ages), the resource's title first, capped at 1,500 characters (the
median is 414 and 90% fit in 1,300). `embeddings.fields_text` in the
reverted commit's parent has the implementation.

What this says about the ten misses: three separate mechanisms for
reaching a resource through its contents rather than its title have now
been measured and none of them ranks better than the title lane. The
next thing to try is not another ranking signal over the same index.

## A verification pass was writing the claim it was built to check (2026-10-16)

`record_evidence` wrote `capability = "observations"` for every resource
`pda verify --discover` probed, whatever the probe returned. The count of
cells was the evidence; the kind was a constant. So `crinst:1000`, whose one
stored cell is `institution_name = "AOF Haugaland"`, was recorded as a
verified observation source and competed in the lane that answers numeric
questions. It is the project's own rule — metadata and entity records are not
observations — broken by the code written to enforce it.

`demonstrated_capability` now reads the label off the rows the fetch stored. A
`records` row states its own kind and decides. Observation cells are judged by
their values: one number anywhere makes it a measurement source, an all-empty
sample stays one (a suppressed cell is still an observation), and an
all-label sample is a code list, a feature set or an entity record by the
dimensions it is addressed through. Numbers published as strings count as
numbers, or Norges Bank's `"4.25"` key policy rate would read as a label.

`scripts/relabel_capabilities.py` re-derived the labels already written:
**754 of 4,952** verified `observations` rows were contradicted by their own
stored rows — 714 to `entities`, 38 to `lookup`, 2 to `features` (crbio,
crinst, crperson, crproj, crresult, crunit 100 each, entur 42, grep 31,
fiskerigis 15). Rows a connector had declared itself are left alone: the
connector knows what a cell shape cannot, and `brkommuner:0301` is declared
`lookup` while storing an entity record, because BRREG's municipality
endpoint returns a thing whose role is a join key.

What it cost, measured on the same registry with the same caches, embeddings
plus rewriting and no reranker, so the comparison isolates the labels:

| set | before | after |
| --- | --- | --- |
| tuned, recall@5 / MRR | 0.878 / 0.719 | 0.878 / 0.720 |
| held-out, recall@5 / MRR | 0.857 / 0.710 | 0.857 / 0.710 |

With the reranker on top, tuned recall@5 reads 0.888 before and 0.878 after,
and held-out is unchanged at 0.905. No gold answer in any of the three sets
was relabelled (0 of 315), so the one tuned question that moved —
`hvilken bydel i Oslo har flest innbyggere`, whose answers are untouched SSB
tables — moved because 38 lookups left the lane and the reranker was handed a
different shortlist. The labels are neutral; the reranker is sensitive to the
list it reads.

## 11,374 observation rows hold a label rather than a measurement (2026-10-16)

Of 31,830 stored observation rows, 18,581 hold a number, 1,875 are empty or
suppressed, and **11,374 hold a label**: `datanorge` code lists 7,527 (a
bydel name against `{"code", "level"}`), cristin 913, entur 555 (`name` =
`"SCOOTER"`), grep 534, hi 328, envreportreg 200, brreg 104. The capability
labels now say what these resources return, so a caller is no longer told
they answer numeric questions, but the rows are still in the wrong table:
`records`, with its `kind` column, is where an entity or a feature belongs.

This is connector work, not a ranking change, and it is not done. Until it
is, `observations` is two things at once, and any count over that table is a
count of cells plus name cards.

## The reranker merge is sensitive but not exploitable (2026-10-21)

`rerank` merges the model's judgement with the ranking it was given as
`ranked[:keep] + lifted[:lift] + ranked`, deduped. With `keep=1` the original
rank-1 is pinned in front of the model's choices whatever it is, and this
session watched the tuned MRR move three separate times — 0.747, 0.752, 0.746
— with nothing in the ranking itself changing, only which datasets were in
the lane the reranker reads.

So the merge was measured. Six variants, on the tuned set only, all reading
the same cached model answers: `keep` and `lift` change how a judgement is
merged, not the head the model is shown, so every variant scores the same
judgements and the comparison carries no sampling noise from the model.

| keep | lift | recall@5 | MRR |
|---|---|---|---|
| 0 | 3 | 0.878 | 0.753 |
| 0 | 5 | 0.867 | 0.751 |
| **1** | **3** | **0.878** | **0.752** |
| 1 | 5 | 0.878 | 0.750 |
| 2 | 3 | 0.878 | 0.734 |
| 2 | 5 | 0.888 | 0.732 |

Nothing dominates. `keep=0, lift=3` is +0.001 MRR, which across 98 questions
is one answer moving one position — noise, not a result. The one real trade
is `keep=2, lift=5`: +0.010 recall@5, one more answer inside the top five,
against −0.020 MRR, the best answer pushed down. Holding more of the original
head is monotonically worse for MRR at a fixed lift.

The default stays at `keep=1, lift=3`. The held-out set was not run for this:
choosing a merge by its numbers would retire it, and there is nothing here
worth choosing. What the grid does settle is that the sensitivity seen all
session is real but bounded at roughly ±0.02 MRR, so a change of that size
after a registry edit is the shortlist moving, not the ranking improving or
degrading.

The knob is now named (`RERANK_KEEP`, `RERANK_LIFT`), threaded through `find`,
and exposed as `--rerank-keep` / `--rerank-lift`, so the next person to
suspect it can re-run the grid in two minutes instead of arguing about it.

## Some tuned "misses" are label errors, and the measure says which (2026-10-21)

The ten tuned misses were carried as a ranking problem needing column- and
unit-level matching. Looking at what each one actually returned, several are
not ranking failures at all: the retrieval found a table that answers the
question and the label names a different one.

The gold file warns about exactly the wrong way to fix that — "adopting
whatever was returned would make the benchmark circular" — so the labels were
audited by a test that does not involve any retriever. The registry already
records, per dataset, which measures a table publishes
(`resource_fields.field_role = 'measure'` and its values). A question asking
for a published statistic can be checked against that directly: does the
labelled table publish the measure the question asks for?

| question | labelled tables publish | verdict |
|---|---|---|
| a047 `gjennomsnittsalderen i Tromsø` | `Personer`; `Areal (km²)` | neither publishes an average age |
| a063 `hvor mange ansatte har Norges største selskaper` | `Bedrifter` | counts of establishments, not employees |
| a025 `foretak etter organisasjonsform` | `Nye foretak` | narrower than the question: new enterprises, not enterprises |
| a035 `avfall og gjenvinning` | `Mengd (tonn)`, `Avfallsmengde` | defensible, but misses the waste accounts by treatment method |
| a058 `hvor mange studenter er det i Norge` | `Studenter` | right measure; the retrieved tables publish it too |
| a049 `hvor mye tjener en sykepleier` | `Avtalt månedslønn (kr)` | right measure; so does the table at rank 2 |

a047 is decisive and was corrected. 13536 publishes `Gjennomsnittsalder` and
`Medianalder` for kommuner, fylker og hele landet. The two labelled tables
publish a count by age and sex, and an area with a population — an answer
would have to be computed from a distribution, which this system is built not
to do. So the label named tables the agent is not allowed to answer from and
omitted the one that publishes the figure. Added, with the reasoning written
into the gold file's own log.

    tuned, full stack   before  0.878 / 0.752    after  0.888 / 0.757

The correction can only raise the number, which is why both are recorded. It
is not a retrieval improvement: the ranking did not change, the question's
answer did.

a063 is the next clear one and needs a different kind of answer. The question
asks for a per-company employee count; 230 verified tables publish an
employment measure and none of them is per company, because that figure lives
in Enhetsregisteret as `antallAnsatte` on an enhet. The label is wrong and the
right resource is in the entities lane rather than the statistics lane, which
is worth settling deliberately rather than in passing.

The remaining four are breadth-of-label questions, where the labelled table
and the retrieved one publish the same measure and both answer. Those want the
careful audit the file's convention describes, judged from titles and measures
alone, and are not corrected here.

## a063 is a coverage gap, and the label is left wrong on purpose (2026-10-21)

`hvor mange ansatte har Norges største selskaper` is labelled with 07091,
10308 and 10309, which publish the measure `Bedrifter` — counts of
establishments, banded by employee count. They answer "how many
establishments have 250 or more employees", not "how many employees does this
company have". The question asks for a per-company figure.

Nothing in the registry answers it. 230 verified tables publish an employment
measure and none is per company. Enhetsregisteret holds `antallAnsatte` on an
enhet, but naming the largest companies means ranking 1.1 million of them, and
the resource is reachable one subject at a time: the collection endpoint
refuses as too large by design. The two stored brreg entity records both say
`harRegistrertAntallAnsatte: false`.

By the gold file's convention that would make it `expected: []` — a coverage
finding, excluded from recall. **It has not been changed.** Excluding a scored
miss raises recall@5, and "this question turned out to be hard, so it stopped
counting" is the failure mode the whole set exists to prevent. The label stays
wrong in the direction that costs us, and the finding is recorded here
instead. Changing it would need a separate decision, made deliberately and
not while the number is in view.

## Seven Havforskningsinstituttet collections do not answer (2026-10-21)

The Norkyst current-field collections, `Raadgivning_2022` and
`Mareano_observerte_vme` answer HTTP 0 — the request never completes. Three
attempts over forty minutes, spaced four seconds apart, and with `limit=100`
and `limit=1000` on the OGC request: every one times out at 90 seconds. It is
not our request rate and it is not paging; the server does not deliver these
collections.

Nothing was recorded against them. They hold no capability row, so they are
not claimed as fetchable, and a server that is timing out today may serve
tomorrow — writing `withdrawn` or `empty` for it would bake a transient into
the registry as a finding. The note is the record.

## The rest of the label audit, and what it leaves (2026-10-21)

The four remaining tuned misses were audited the same way as a047: enumerate
candidates from the registry's own index of published measures and dimensions,
then judge each on what it publishes.

**a025 was corrected.** `foretak etter organisasjonsform` was labelled with
13702, 08076 and 09028, which publish `Nye foretak` and `Nyetablerte føretak`
— newly established enterprises, a narrower subject than the question. The
candidate query (a measure counting foretak, with an `organisasjonsform`
dimension) returns 14001, `Føretak, etter organisasjonsform og sektor`,
publishing `Talet på føretak`. That is the question itself. 14002 and 14003
publish the same measure with næring added and were left out as breakdowns.

This is the error pattern the file already records fixing once, for the
agriculture, fisheries and foreign-trade labels: the original named a niche
cut and the plain subject table was omitted.

**a035, a049 and a058 were left alone.** Their labels publish the measure the
question asks for — `Mengd (tonn)` and `Avfallsmengde`, `Avtalt månedslønn
(kr)`, `Studenter` — and are not wrong. The retrieval's top hits also answer,
but "both answer" is not a label error, and widening on that basis would move
the number without correcting anything.

    tuned, full stack
      before the audit   0.878 / 0.752
      after a047         0.888 / 0.757
      after a025         0.898 / 0.761

Both steps raise the number and both are recorded as what they are: the
ranking did not change once. What changed is that two questions were being
scored against tables that do not answer them.

What is left of the original "ten misses needing column- and unit-level
matching":

- a010 `bruttonasjonalprodukt`, a027 `regnskapstall aksjeselskap`,
  a080 `kvadratkilometer` — not in depth 50 at all. These are retrieval
  failures and the only ones that clearly are.
- a024 `frafall videregående`, a035, a048, a049 — found at rank 6 or 7, so
  retrieved and placed below five. This is the reranker's business, and the
  grid above says the merge is not the lever.
- a045 `bydel i Oslo` at 12, a058 `studenter` at 11.
- a063 is a coverage gap, deliberately left mislabelled.

So three genuine depth failures, not ten. The framing was carrying four label
errors and a coverage gap as if they were ranking problems.

## The measure test nearly produced a false correction (2026-10-21)

Audited by published measures, a010 `bruttonasjonalprodukt` looks like the
clearest label error of the lot. None of its four labelled tables publishes a
measure matching BNP or bruttonasjonalprodukt, while 09842 publishes one
called exactly `Bruttonasjonalprodukt` and is not labelled. Two corrections
had already gone in on that reasoning, so the third looked routine.

It is wrong. 09189's measure is the price basis — `Faste 2023-priser (mill.
kr)`, `Løpende priser (mill. kr)` — and the aggregate itself is a dimension:
`Makrost`, 51 values, among them `Bruttonasjonalprodukt, markedsverdi` and
`Bruttonasjonalprodukt Fastlands-Norge`. The table publishes GDP. So does
09190 and so does 11721. The label is right and the measure test read it
backwards, because in a PxWeb table the thing being measured can sit in either
place: as a `ContentsCode` value, or as a dimension value with `ContentsCode`
carrying the unit.

The corrected rule, for anyone running this audit again: **a question's
subject can live in the measure labels or in the dimension values, and a test
that reads only one of them returns a confident wrong answer.** a047 and a025
survive it — 07459's `Personer` has no age dimension either, and 08076's `Nye
foretak` is the measure and the subject both — but they were checked again
rather than assumed.

One real label error did fall out: 11722, `Alderspensjonister, etter
bosettingsstatus`, is in a010's expected list and has 14 indexed values, none
of them macroeconomic. It cannot answer a question about GDP; it is almost
certainly 11721 mistyped. Removing it changes no score — a010 misses either
way — so it is recorded here and left for the same deliberate pass that owes
a063 an answer.

### What this says about the three depth failures

a010 is the case the original framing described exactly: the answer is a
dimension value inside a table whose title says `Makroøkonomiske
hovedstørrelser`, and nothing in the title, the keywords or the description
says GDP. The registry already indexes it — 587,333 `resource_field_values`
rows, with `Bruttonasjonalprodukt, markedsverdi` among them — and retrieval
does not search that index.

So the lever for the remaining misses is real and already in the registry. The
three value-index mechanisms that measured worse than the title lane were
searching all 587,333 values; the measure labels alone are 15,210 rows, and
for a080 the match is a unit (`Areal (km²)` against a question that says
kvadratkilometer) rather than a subject. Those are two different lanes and
worth measuring separately rather than as one "value index" again.

## The three depth failures, measured one lane at a time (2026-10-21)

The measure-label lane was the hypothesis: the earlier value-index attempts
searched all 587,333 `resource_field_values` rows, and measure labels alone
are 15,210 — smaller and more informative. Measured on the tuned set, that
lane finds a gold answer in its top ten for **30 of 98** questions and for
**none of the three** depth failures. Refuted.

It is refuted for a reason recorded an hour earlier in this same file: a010's
answer is `Bruttonasjonalprodukt, markedsverdi`, a value of the `Makrost`
*dimension*, and a measure-only lane excludes dimensions by construction. The
finding was already written down and did not get connected to the hypothesis
it disproved.

Then each table's true semantic rank, over all 17,505 embeddings:

| query | gold table | semantic rank |
|---|---|---|
| `hvor stor er Norge i kvadratkilometer` | 11342 | 2827 |
| `areal` | 11342 | 212 |
| `landareal` | 11342 | 6690 |
| `bruttonasjonalprodukt` | 09189 | 548 |
| `bruttonasjonalprodukt` | 09842 *(unlabelled)* | 53 |
| `regnskapstall aksjeselskap` | 07371 | 42 |
| `regnskapstall aksjeselskap` | 08142 | 41 |

These are three different problems wearing one label.

**a080 is not an indexing problem.** 11342 sits at 2827 for the question and
at 6690 for `landareal`, the rewriter's own term. Nothing that reorders a
depth-50 shortlist reaches rank 2827. Its embedding text does not say that
this is the table with the whole country's area in it, and that is where the
work is.

**a010 is a label-and-embedding problem.** The three labelled tables are at
548 and below because their titles say `Makroøkonomiske hovedstørrelser` and
GDP is a dimension value. 09842, whose title says BNP, is at 53 — just outside
the depth — and is not in the gold list. The question deserves the deliberate
pass that owes a063 and 11722 an answer.

**a027 is the real lead.** 07371 and 08142 are at semantic rank 42 and 41,
inside depth 50, and the full stack returns neither. The query routes as
"names a subject", so lexical and semantic are fused; lexical returns 15 hits,
the rewrite lane interleaves `regnskap, aksjeselskap`, and the two tables that
the semantic lane already ranked in its top fifty are not in the 40 that come
out. Something in the fuse-then-interleave is dropping them, and that is a
mechanism to read rather than a signal to add.

## Fusing two depth-50 lists and keeping 50 loses the tail by arithmetic (2026-10-21)

`regnskapstall aksjeselskap` turned out not to be a missing signal. 07371 and
08142 are at semantic rank 42 and 41, inside depth 50, and the fused list does
not contain them at all. The reason is arithmetic, not a bug:

    RRF_K = 60
    a lexical hit at position 0   scores 1/61  = 0.0164
    a lexical hit at position 14  scores 1/75  = 0.0133
    a semantic hit at position 40 scores 1/101 = 0.0099

Every one of the 15 lexical hits outscores every semantic hit past position
about 15, so the fused order is the 15 lexical hits, then the semantic list in
its own order. That is 65 distinct ids, and `fuse` keeps `limit`, which `find`
sets to `depth` -- 50. The bottom 15 of the semantic list are cut, and 41 and
42 are in that 15.

The general form: fusing a list of L with a list of S and keeping D loses the
tail whenever L + S exceeds D, and the loss falls entirely on the ranker that
ranked deeper. With both lists at depth and the output at depth, which is what
`find` does, a disjoint lexical list of 15 costs the semantic lane its last 15
places every time.

Two routes, and the cheap one is being measured first. The rewrite lane finds
07371 again at position 6 of its 20 alternatives, and `alternative[:3]` throws
it away; `rewrite_take` is now a parameter of its own and the grid on the tuned
set will say whether widening it pays. The other route is to stop letting the
output depth decide how much of each input survives -- fuse into a longer list
and trim once, at the end, after the reranker has seen it. That is a bigger
change to the shape of `find` and should be measured on its own, not folded in.

Worth keeping in view: three mechanisms were added over previous sessions to
find a stronger signal for these questions, and for this one the signal was
twice in hand and twice discarded.

## Widening the rewrite take: a tuned peak that coverage refuses (2026-10-21)

The mechanism is real. `regnskapstall aksjeselskap` goes from absent to rank 8
when the interleave takes six of the rewrite lane's hits instead of three,
which is exactly what tracing predicted: the lane ranked 07371 sixth and three
were being taken.

The grid, tuned set, all variants reading the same cached rewrite terms:

| take | recall@5 | MRR |
|---|---|---|
| **3** | **0.898** | **0.761** |
| 6 | 0.908 | 0.765 |
| 8 | 0.908 | 0.762 |
| 10 | 0.908 | 0.760 |

A peak at 6 on both. Then the miss lists, which say what the averages hide:

- gained: `hvilken bydel i Oslo har flest innbyggere` (was 12),
  `hva er arbeidsledigheten i Norge nå` (was 6)
- lost: `hvor mange bor i bydelene i Oslo` — inside five, now **22**
- `regnskapstall aksjeselskap`: absent, now 8 (MRR only, no recall)
- `hvor mange studenter er det i Norge`: 11, now 12

Two in, one out. The +0.010 is one net question and the movement under it is
churn, including a question that fell from the top five to 22.

And the coverage set settles it:

    coverage, take=3   recall@5 1.000   MRR 0.652
    coverage, take=6   recall@5 1.000   MRR 0.598

A 0.054 drop in coverage MRR against a 0.004 gain in tuned MRR. **The default
stays at 3.** The tuned set alone would have taken this change: a clean peak
on both its measures, a mechanism traced to the line, and a test pinning it.
The second set is what says no, which is the entire argument for having one
that was not used to choose anything.

What survives: `rewrite_lead` and `rewrite_take` are separate parameters and
measurable from the command line, the interleave's behaviour is pinned by a
test that fails the old way, and the fusion arithmetic above explains why the
semantic lane's tail is lost in the first place. The route worth measuring
next is the one that does not trade anything -- fuse into a list longer than
the output depth and trim once, after the reranker has seen it -- because the
answers here were ranked 41 and 42 by a lane whose last fifteen places are
being discarded before anything downstream can read them.

## Showing the reranker more candidates, and what actually moved (2026-10-21)

The investigation started from `regnskapstall aksjeselskap`, whose answers sit
at semantic rank 41 and 42 and are lost by the fusion arithmetic above. It
ended in a change that helps three other questions and not that one. Both
halves of that are worth recording.

The grid, tuned and coverage, with the reranker and rewriting on:

| working list | reranker sees | tuned recall@5 / MRR | coverage |
|---|---|---|---|
| 50 | 20 | 0.898 / 0.761 | 1.000 / 0.652 |
| 100 | 20 | 0.898 / 0.761 | 1.000 / 0.652 |
| 100 | 50 | 0.918 / 0.762 | 1.000 / 0.652 |
| **50** | **50** | **0.929 / 0.764** | **1.000 / 0.652** |

Three questions gained, none lost: `avfall og gjenvinning` from rank 7,
`hvilken bydel i Oslo har flest innbyggere` from 12, and `hva er
arbeidsledigheten i Norge nå` from 6, all into the top five. Coverage does not
move at all, which is what the rewrite-take experiment failed.

And the mechanism is not the one the investigation predicted. **Positions 6, 7
and 12 were already inside the old depth of 20.** The reranker could always
see those candidates; what changed is that with fifty titles in front of it,
it chooses differently among the ones it could already see. More context, not
more reach.

`regnskapstall aksjeselskap` is still not in depth in the winning
configuration, because without the longer working list its answers are still
cut by the fusion before the reranker is called. The one configuration that
retrieves them -- 100/50 -- places them at 41 and costs a question elsewhere,
8 misses against 7. So the question that motivated all of this remains open,
and the fusion arithmetic remains the thing that would fix it.

The honest summary: a correct diagnosis of one question produced a measurable
improvement on three others, and the parameter it predicted would matter is
the one that measured worse.

### Adopted: the reranker reads fifty titles

`RERANK_DEPTH` 20 -> 50, chosen on tuned with coverage as the veto, then
confirmed once on held-out:

    tuned      recall@5 0.898 -> 0.929   MRR 0.761 -> 0.764
    coverage   recall@5 1.000 -> 1.000   MRR 0.652 -> 0.652
    held-out   recall@5 0.905 -> 0.905   MRR 0.746 -> 0.748

The middle of the range is worse than either end: 35 reads 0.918/0.759 on
tuned and drops coverage MRR to 0.639, so this is 50 because 50 measured
best, not because bigger is better. The cost is fifty titles per rerank call
against twenty, and three questions moved into the top five for it with none
lost.

Held-out was run once, after the choice was made on the other two sets. A
number that picks a parameter is not a held-out number any more.

## A declaration outranks an inference, and 68 rows say so (2026-10-21)

The registry has two ways of knowing what a resource returns. A connector can
declare it, and `demonstrated_capability` can read it off the rows that were
stored. They disagree on 68 verified rows, and that is deliberate.

| source | rows | source | rows |
|---|---|---|---|
| grep | 22 | nor, udir | 4 each |
| stortinget | 7 | miljodir | 3 |
| nbr, nfr | 6 each | nxr, aqua, kystverket | 2 each |
| npr | 5 | stpartier, stkomiteer, hoydedata, nve, baf | 1 each |

Every one carries a reason. 57 say in the notes that the connector declared
it, 35 of those with the connector's own wording -- `names are labels, not
observation values` for the Storting's party list -- and the remaining 11
carry a note from some earlier pass. None is silent.

Why the inference loses: it reads a proxy. The attribute test asks whether a
record is "all code and no label", or whether its attributes are only
hierarchy and validity, and both of those can move without the resource
changing at all. Copying Udir's titles this session flipped 22 grep rows from
`lookup` to `entities` -- the vocabularies were identical before and after,
and only the quality of our reading of them had improved.

The temptation at that moment was to widen the code-list vocabulary until the
inference agreed again: `uri`, then `grep-type`, then `id`, then `status`,
then the validity dates. That is fitting a rule to a wanted answer, and it was
reverted in favour of the connector declaring its role the way `brkommuner`
always has.

So the rule, stated once: **the inference is for resources nobody has
declared.** It exists because `record_evidence` used to hardcode
`observations` for everything discovered, and reading the rows is better than
hoping. It is not better than a connector that knows, and a growing count of
disagreements is not drift as long as each one is a declaration with its
reason written down.

Retrieval after the grep rows left the fetchable lane -- `lookup` is not
retrievable -- is unchanged on all three sets: tuned 0.929/0.764, coverage
1.000/0.652, held-out 0.905/0.748. They were never answering a gold question.

## The fusion is balanced right, and a027 was never a ranking failure (2026-10-21)

Two results, and the second one undercuts four ticks of work on the first.

**The lexical weight does not pay at any setting.** Damping the lexical lane
was the one remaining route to bringing `regnskapstall aksjeselskap`'s answers
at semantic 41 and 42 into a 50-item output. Measured on the tuned set, with
coverage flat at 1.000/0.652 throughout:

| lexical weight | tuned recall@5 / MRR |
|---|---|
| **1.0** | **0.929 / 0.764** |
| 0.8 | 0.918 / 0.761 |
| 0.7 | 0.918 / 0.760 |
| 0.6 | 0.918 / 0.755 |

Monotonic and always worse. The prediction written before the grid said 0.8 to
1.0 would be inert and 0.7 roughly neutral; both were wrong, and for a reason
the synthetic test could not show -- damping also reorders the ids both
rankers found, which evicts every lexical-only id from the head at the first
notch. The lexical lane earns its weight. The displacement of the semantic
tail is real and removing it costs more.

**And the question did not need fixing.** `regnskapstall aksjeselskap` was
labelled with 07371 and 08142, whose measures are `Driftsmargin`,
`Egenkapitalrentabilitet`, `Likviditetsgrad` -- ratios, which are nøkkeltall,
not regnskapstall. The tables the ranking returns instead are 09350,
`Utvalgte regnskapsposter i ikke-finansielle aksjeselskaper`, measure
`Beløp`, and 08121, `Balanseposter`, publishing `Aksjekapital`,
`Anleggsmidler` and `Egenkapital` in mill. kr. Those are accounting figures.
The ranking was returning better answers than the label named.

Same test as a047 and a025, same error pattern as a025: the label named a
derived cut and left out the plain subject tables.

    tuned, full stack   0.929 / 0.764  ->  0.939 / 0.769
    coverage            1.000 / 0.652  unchanged
    held-out            0.905 / 0.748  unchanged

So the fusion arithmetic is still true -- fusing L with S and keeping D does
discard the deeper ranker's tail -- and it was not costing this question
anything that mattered. Of the three "real depth failures", one was a label
error. Two remain: a010, whose answer is a dimension value in a table titled
`Makroøkonomiske hovedstørrelser`, and a080, at semantic rank 2827.

The lesson is about where to look first. Four ticks went into the ranking
because the miss list said "not in depth", and the measure audit that settles
these questions in one query had already corrected two labels that same day.

## Measures in the embedded text: the ranks improved and the answers got worse (2026-10-21)

a080 and a010 both pointed at the same thing. SSB files 11342, `Areal og
befolkning i kommuner, fylker og hele landet`, under Befolkning and Folketall,
so the one table holding the country's area embedded with no area vocabulary
past the title word, while the tables SSB files under Areal ranked first and
second. 11342's measures are `Areal (km²)` and `Landareal (km²)`, and 3,277
datasets had at least one measure label their embedded text did not contain.

So the measures went in, 4,171 embeddings were rebuilt, and the targeted
semantic ranks improved sharply:

    hvor stor er Norge i kvadratkilometer   11342   2827 -> 435
    bruttonasjonalprodukt                   09189    548 -> 315

And the retrieval got much worse:

    tuned      recall@5 0.939 -> 0.888   MRR 0.769 -> 0.685
    coverage   recall@5 1.000 -> 0.909   MRR 0.652 -> 0.644

Coverage had been at 1.000 through every change this session and this is what
broke it. Reverted: the 4,171 vectors were restored from a targeted backup and
both sets read exactly their previous numbers again.

Why it fails is visible in the data. Measure labels are mostly boilerplate
shared across unrelated tables -- `Antall personer som svarte` appears in 98
datasets, `Personer` in 80, `Andel (%)` in 55 -- so embedding them makes
tables about different subjects look alike. The title and the publisher's
subject tree were carrying the discrimination, and 13,673 added labels diluted
it. A vocabulary that identifies a resource and a vocabulary shared by
hundreds are different things, and only the first belongs in a vector meant to
tell resources apart.

What the improved ranks say is still worth keeping: the signal for a080 and
a010 genuinely is in the measures, and nothing that reads only titles,
descriptions and subject trees will find it. A per-measure lane that is
weighted by how few resources carry a label -- which `search_resources`
already does for values -- is the shape that could work. Blending it into one
vector cannot, because a vector has no way to down-weight its own boilerplate.

Note on method: the first evidence for all this was wrong. 11342's embedded
text was read through `get_dataset`, which does not join
`harvested_payloads`, so it looked like title-and-publisher only and the
keywords were invisible. The count that followed -- "only 12 datasets would
gain" -- was answering a different question, thin text rather than missing
measures. Both were corrected before the change was made, which is the only
reason the experiment measured the thing it claimed to.

## P4 closed: the last two misses are explained, not fixable here (2026-10-21)

### a080 `hvor stor er Norge i kvadratkilometer`

Every lane was checked, and each one fails for the same reason.

- The query reads as a question, so `rank_for_query` routes it to the
  **semantic ranking alone**. No synonym, no measure lane and no value index
  touches it, because the lexical half is not consulted.
- Semantically 11342 sits at **2827**. SSB's themes for it are `Befolkning`,
  `Folketall`, `Barn, familier og husholdninger`, `Innvandring og
  innvandrere`. There is no area vocabulary in its description at all.
- The rewrite lane proposes `areal` and `landareal`, which is exactly right,
  and 11342 is **not in the lexical top 50 for either**. Its title does carry
  the token: `Areal og befolkning i kommuner, fylker og hele landet`. It loses
  on relevance weighting to `Areal av land og ferskvatn, etter kommune`,
  where the term accounts for more of a shorter title.
- Putting its measures -- `Areal (km²)`, `Landareal (km²)` -- into the
  embedding raised it to 435 and broke coverage, recorded above.

So this is not a ranking defect. **SSB describes 11342 as a population table
that happens to include area**, and every retrieval signal faithfully
reflects the publisher's description. The tables SSB files under Areal rank
first and second and answer the question only by summing municipalities,
which this system must not do.

Fixing it would mean writing area keywords onto the dataset that the publisher
did not provide. That is inventing metadata, so it is not done. The question
stays a miss with the reason recorded.

### a010 `bruttonasjonalprodukt`

The label is right: 09189, 09190 and 11721 all publish
`Bruttonasjonalprodukt, markedsverdi` as a value of the `Makrost` dimension.
The two unlabelled tables that publish it as a *measure* are worse answers --
09842 is per capita, and 12880 mixes `Regnskap og prognoser`, so labelling it
would make a forecast the answer to a factual question.

Reaching a dimension value needs the value index, and that has now measured
worse than the title lane four times: the coverage lift, two interleaving
attempts recorded in `retrieval.py`, and the measure-only lane this session at
30 of 98. The signal is real and every way of blending it in costs more than
it returns.

### What P4 produced

One adopted change -- the reranker reads fifty titles, tuned 0.898 to 0.929 --
and four label corrections found by auditing what each table publishes rather
than how it ranks. Tuned went 0.878/0.747 to 0.939/0.769 across the session,
and of that, 0.031 is retrieval and the rest is the instrument being wrong.

Three mechanisms were built, measured and rejected: a longer working list, a
damped lexical weight, and measures in the embedded text. Each is documented
beside the code it would have changed, with the numbers, so the next person
does not pay for them again.

## Four readers described a world the rows had left (2026-10-21)

Moving 11,374 rows out of `observations` and into `records` was the easy half.
Every reader that described the old arrangement kept describing it,
confidently, and each one had to be found separately:

1. `run_analysis` reported `completed` with no rows for 17,900 records, then
   explained it could not read them, then read them.
2. The geometry was stored and unreadable, then readable and unbounded -- one
   advisory polygon is 24 MB -- before being named and bounded.
3. `tool_search`'s lane note said catalogue records "describe data that no
   registered connector can retrieve", while 571 `lookup` datasets held entity
   records that `run_analysis` returns.
4. `_analysis_warnings` told the caller "call fetch for this dataset first" for
   a dataset whose rows were already in the registry -- sending it to the
   network for data it had. Asked of the Oslo bydel classification, it now
   says 42 entity records are stored and not to fetch.

Three of the four were found by stumbling into them while doing something
else. The fourth was found by looking on purpose, with
`grep -rn "list_observations\|observation_count"` over `src`, which is the
check that should have followed the migration rather than trailing it by a
day.

The general lesson, written here because it will apply to the next schema
move: a migration is not finished when the writes are right. Every place that
*reports* on the old shape is part of the migration, and the ones that give
advice -- fetch this, this cannot be retrieved, nothing is stored -- are the
ones that cost a caller something when they are stale.

## The Geonorge backlog resolves to links, not data (2026-10-21)

7,425 `datanorge` datasets with no capability row point at
`kartkatalog.geonorge.no/metadata/uuid/…`, which is 82% of the whole
unclaimed backlog. A resolver from the UUID to the real distribution URL
looked like the single highest-value connector left, and that was asserted
from the count alone.

The resolver exists and works: `kartkatalog.geonorge.no/api/getdata/{uuid}`
returns `DistributionUrl`, `DistributionProtocol` and the licence under
`Constraints`. So the question is only what the protocols are. Two
independent samples, 55 datasets:

| DistributionProtocol | n |
|---|---|
| `WWW:LINK-1.0-http--link` | 49 |
| `GEONORGE:DOWNLOAD` | 3 |
| `WWW:LINK`, `GEONORGE:OFFLINE`, `(none)` | 1 each |

Nothing queryable. No `OGC:WFS`, no REST, no API in 55 draws. One of them is
`GEONORGE:OFFLINE`, which is a distribution you request by email.

So resolving the backlog would turn 7,425 metadata pages into 7,425 web links
and about 400 bulk downloads. The right capability for a web link is
`documents` or nothing, and a bulk zip is what this project already declines
-- the naturvern note records choosing an ArcGIS layer over a 61 MB national
zip for exactly that reason.

**P6.1 is struck, not handed on.** What the resolver is worth is smaller and
real: it carries the publisher's licence, and licences stay null in this
registry when unknown. Reading 7,425 licence statements from the catalogue is
a day of polite requests and would fill in a field that is currently empty by
rule, which is the opposite kind of value from "7,429 new fetchable
datasets".

Worth being plain that the first claim came from a count and one example whose
protocol was `OGC:WMS` -- the one protocol in the sample space that looks like
a service. 55 draws cost three minutes and moved the item from the top of the
roadmap to struck.

### The sweep, finished (2026-10-21)

`grep -rn "list_observations\|observation_count\|FROM observations"` over
`src`, `methods` and `scripts`, then every phrase that asserts absence or
unfetchability. Five readers described the arrangement the rows had left; the
fifth was `tool_search`'s `connector_candidates_note`, which told a caller
catalogue hits "are not fetchable" and stopped there. It now names the ones
holding rows: asked for `yrkeskatalogen` it points at the Klass occupation
catalogue, and for `organisasjonsformer i Enhetsregisteret` at four
`brorgformen` and `brreg` datasets.

Two readers were examined and deliberately left alone:

- `ask.py` reads observations after its fetch and reports no numbers when
  there are none. That is correct: `ask` answers numeric questions and a
  register holds no numbers.
- `executor.py` reads the observation ids a fetch returned, so a records-only
  step yields nothing. Changing it means deciding what a plan step targeting a
  register should produce, which is the planner's question and not one to
  answer in passing.

So the sweep is complete rather than exhausted, and the two it did not change
are recorded with the reason.

## The probe could not see the datasets it was built for (2026-10-21)

`probe_unverified.py` selected from `resource_capability WHERE verified_at IS
NULL`. A dataset with **no capability row at all** was therefore invisible to
it — and that is 11,564 of 17,505 datasets, including every one of the twelve
sources that have never been probed. The tool meant to find out what a
resource does could not reach the resources nothing was known about.

Fixed with a left join, and the write path now creates a row where there was
none, recording the access path the probe actually used.

### And the first source it reached produced the bug this session removed

Sokkeldirektoratet, 39 datasets, all previously invisible. The probe fetched
every one successfully and `record_evidence` — correctly, by its own rules —
recorded 39 verified `entities` capabilities over **840 stored rows**. The
rows were these:

    name = "OBJECTID"          {"alias": "OBJECTID", "domain": "", "editable": "False", …}
    name = "afxNpdidAfexArea"  {"alias": "NPDID Afex Area", "nullable": "True", …}

Column definitions. `factmaps.sodir.no/.../FeatureServer/3200?f=json` answers
with one layer's descriptor — `type: "Feature Layer"`, `fields`,
`capabilities`, `drawingInfo`, no `features` — which is the service listing
its own columns, one level below the MapServer root that was already refused
this morning.

So a visibility fix, applied to a source nobody had looked at, immediately
recreated metadata-as-observations: 840 rows and 39 verifications in one
command. Reverted, backed up, and the refusal extended to layer descriptors. A
query response carries `fields` and `features` together, so requiring the
absence of `features` leaves real data alone — pinned by a test that passes a
descriptor and the same descriptor with one row beside it.

sodir now reads `catalogue` on all 39, which is true: the URL is reachable and
it is the wrong door. The data is at `<layer>/query?where=1=1&outFields=*`,
which no connector asks for yet.

**The lesson for the remaining eleven sources**: nvemap 63, ssbver 39,
nbcodelist 37, hoydegis 35, mdirwms 30, riksantikvaren 29, ngu 28, npitema 27,
npiintern 24, nbprov 24, nbdsd 24. Several are WMS or ArcGIS by name. Probing
them without reading what the first few actually return would manufacture
thousands of rows of service metadata and verify every one of them. Probe one
source, read the rows, then decide — not the other way round.

## ssbver: a Klass classification's version list is not its contents (2026-10-21)

Probing `ssbver` stored 168 rows across 39 datasets and recorded every one as
a verified `entities` source. The rows:

    name = "Bydelsinndeling 2004 - Delområde- …"
      {"changeTable": "False", "id": "734", "lastModified": "2021-04-23T…",
       "owningSection": "320"}

`data.ssb.no/api/klass/v1/versions/1` returns the **versions of
classification 1**, each with an id, a last-modified date and which SSB
section owns it. That is a change log, not a vocabulary. The classification's
actual items come from `/versions/{version_id}.json`, which is what
`_fetch_klass` reads and what the datanorge Klass datasets use.

Predicted wrongly, too: the URL matches `is_klass_url`, so the expectation was
that these would go through the corrected Klass path and land as entity
records with titles. They did not -- they stored as observation cells, which
means the dispatcher routed them somewhere else, and that is the thing to find
before probing this source again.

Reverted and backed up. Nothing was learned about these 39 resources except
that the endpoint the registry has for them is the wrong one.

**Where the probe sweep stands.** Reading the URL shapes of the eleven
unprobed sources costs nothing and predicts most of the outcome:

| expected verdict | sources |
|---|---|
| catalogue, ArcGIS or WMS root | nvemap 63, hoydegis 35, mdirwms 30, riksantikvaren 29, npitema 27, npiintern 24 |
| catalogue, OGC collection description | ngu 28 — confirmed by hand: `itemCount`, `extent`, `links`, no `features` |
| catalogue, SDMX structure metadata | nbprov 24, nbdsd 24 |
| genuine vocabulary | nbcodelist 37 — `/api/codelist/NB/CALC_METHOD`, confirmed `data`/`meta` by hand |
| wrong endpoint, needs connector work | ssbver 39 |

So of 384 datasets, about 37 look like real content and the rest are services
describing themselves. That ratio is the argument for reading before probing,
and against handing the sweep to anything that will not look at the rows.

## A licence is not an access level, and the registry has one column for both

Found 2026-10-21 while writing up the two access routes that need a company
behind them. Three counts from the registry, each verified before it was
written down:

- **6,350 datasets carry a Norge digitalt licence URL and zero have a
  capability row.** Not one has ever been fetched. The licence field was
  already naming the restriction; every fetch attempt rediscovered it one row
  at a time. 4,218 of them are Norge i bilder, which is aerial imagery this
  project refuses anyway, so the part worth an agreement is nearer 2,100.
- **3 FKB rows declare `noConditionsApply` and are restricted anyway**, and 11
  more FKB rows carry no licence. 244 rows across the registry make that
  `noConditionsApply` claim. The field is not a reliable access signal in
  either direction.
- **51 datasets declare CC-BY-NC**, 38 from Kartverket and 8 from
  Havforskningsinstituttet.

The first count was nearly reported as 1,643. The query used
`license LIKE '%NC%'`, and SQLite's LIKE is case-insensitive for ASCII, so it
matched every URL containing the word "lice**nc**e". Checking which strings
the pattern actually matched is what caught it, and that check is now the
habit for any count that becomes a claim.

### What this means for P6.4

The Geonorge licence backfill was filed as "fill 7,425 null licences from
`api/getdata/{uuid}`, honest provenance, no new fetchability". It still is,
but it must not be read as an access answer. A dataset can declare
`noConditionsApply` and be closed; a dataset can be open and declare nothing.
Filling the column tells us what the publisher *says*, which is worth having
and is not the same question as whether an agent can read it.

### The schema question

Three different things are currently blurred into one column plus one table:

    can it be fetched    `resource_capability` -- has a verdict and a date
    may it be used       `datasets.license` -- a URL, no verdict
    may it be passed on  nowhere at all

Only the first carries a verdict. The third does not exist, and for a service
intended to become a commercial API it is the one that decides what can ship:
Kartverket requires a separate framework agreement to redistribute Matrikkel
or Grunnbok data, and 51 datasets forbid commercial use outright.

Not acted on yet, and deliberately so. Adding a redistribution column means
deciding a verdict per licence family, which is a legal reading and not a
shape test — the kind of judgement this project has been careful to keep out
of inference. The honest first step is smaller: record the licence family as
a derived, named value (NLOD, CC-BY, CC-BY-NC, Norge digitalt, INSPIRE
codelist, null) so the question can at least be *asked* of the registry
without a LIKE pattern. That is a migration, not a guess.

## What is unverified, counted rather than estimated (2026-10-21)

The goal is all Norwegian open data, searchable, better than data.norge. That
makes "how much have we never asked" the governing number, so here it is in
full. 12,294 of 18,280 datasets carry no verdict. They are not one problem.

| bucket | datasets | what it is | what it needs |
|---|---|---|---|
| **A** | **7,233** | `kartkatalog.geonorge.no/metadata/uuid/…` | `scripts/resolve_geonorge.py`, running |
| **B** | 60 | no `access_path` at all | nothing to probe; a harvest gap |
| **C** | **5,001** | a real URL, never probed, across **299 hosts** | a host-ordered sweep |

Only **117 datasets in the whole registry are known-blocked** — 32 withdrawn,
28 catalogue, 10 empty, 8 restricted and the rest since added. Everything else
unreadable is unasked, not refused. That is a very different problem from the
one "69 of 190 sources hold rows" implies, and the per-source framing was
misleading: those 121 row-less sources are 1,412 datasets, 8% of the registry.

### Bucket C is concentrated, which makes it tractable

The top 22 of 299 hosts hold about 3,500 of the 5,001:

    769  www.barentswatch.no        (our own bwfish weeks, awaiting backfill)
    479  opencom.no
    444  data.ssb.no
    273  data.stortinget.no
    196  kartkatalog.geonorge.no    (not /metadata/uuid/, a different path)
    174  nedlasting.geonorge.no
    168  ess.sikt.no
    161  api.met.no
    141  raw.githubusercontent.com
    136  kart.hi.no

A sweep ordered by host rather than by dataset learns a host's shape once and
applies it to every row on it. `scripts/discover.py --unreadable` already
groups this way; what it does not yet do is order by host volume.

### Bucket A, measured properly

Struck earlier in the session as "nothing queryable" from a 55-row draw. A
399-row sample classified per dataset -- by the **best** access each one has,
not per distribution entry, which was the counting error -- gives:

| tier | share | of 7,233 |
|---|---|---|
| queryable API | 4% | ~290 |
| bulk download | 8% | ~580 |
| map service | 0% | ~20 |
| web page only | 86% | ~6,220 |
| offline / none | 1% | ~70 |

81% are declared `Åpne data`. Of the web-page tier, 71% is aerial imagery and
most of the remainder is LiDAR elevation; **zero of 344 carried a tabular
format**. So there is nothing to scrape into a table there, and the earlier
call was right about that and wrong about what follows from it. The resolved
download URL, the formats, the owner and the licence are worth holding whether
or not the raster is ever ingested, because the catalogue page does not show
them and a search that does is better than the catalogue. That is the product
difference, stated as a measurable thing rather than a slogan.

### The order this implies

Breadth work that touches hundreds of rows at once outranks the next
hand-written connector, unless that connector unblocks a mechanism several
sources need. By that rule: P8.5 (the select mechanism, three callers) stays
first, then bucket A's resolver output, then a host-ordered bucket C sweep,
then HydAPI.

## B2b: where the 1,028 machine-readable Geonorge rows actually live

Grouped by the host of their resolved URL, 2026-10-21. 41 hosts, and four of
them hold 87%:

| host | rows | what it speaks | verdict |
|---|---|---|---|
| `nedlasting.geonorge.no` | 608 | Geonorge download service | **solved** — `api/capabilities/{uuid}` addresses each one and publishes formats, projections and kommune coverage. See `dataset_coverage`. |
| `thredds.met.no` | 151 | OPeNDAP | **gridded projections, not observations** — see below |
| `pycsw.nina.no` | 82 | OGC:OAPIF | **the hostname does not resolve** |
| `kart8.nibio.no` | 49 | Geonorge download service | same software as row 1; `api/capabilities/{uuid}` applies |

Only **30 of 1,021** land on a host this registry already reads from
(`kart.hi.no` 15, `kart.miljodirektoratet.no` 14, one Kartverket). So these are
new readers, not more rows for existing ones.

### thredds.met.no: 151 rows, and they are grids

The resolved URL already ends `.nc.html`, which is OPeNDAP's own HTML form.
Strip that and `.dds` answers 200. One of them,
`change-evap` from Klima i Norge 2025:

    Int32   time[time = 2]
    Float32 change-evap_annual[time = 2][Yc = 1550][Xc = 1195]
    Float32 change-evap_winter[time = 2][Yc = 1550][Xc = 1195]
    ... units "days since 2056-01-01"

That is a 1 km grid, 1.85M cells per variable per time step, and it is a
**climate projection** rather than a measurement. Pulling it into
`observations` would be wrong twice over: wrong shape, and wrong kind of claim.

Two things are worth having and one is not:

- **worth it:** the variable list and units, which `.das` publishes, so a
  search for "fordampning" finds them. One request per dataset, no download.
- **worth it later:** OPeNDAP subsets server-side, so
  `?change-evap_annual[0:1:0][775:1:775][597:1:597]` returns a single cell.
  A point query against a grid is a capability nothing in this registry has,
  and it needs no storage at all. Real, and depth work rather than breadth.
- **not worth it:** ingesting the grids. There is no disk for it and no
  question they answer better than a point query would.

### pycsw.nina.no does not exist

`socket.gethostbyname("pycsw.nina.no")` fails with `gaierror`, so 82 datasets
that Geonorge advertises as `OGC:OAPIF` point at a hostname with no DNS
record. Not a firewall and not a 404 -- there is nothing to connect to. Those
82 should be recorded `unreachable` rather than left looking like the
second-largest queryable group, and it is worth telling Geonorge.

`geo.ngu.no` by contrast answers: `api/features` returns a listing of **28
OGC API Features APIs**, each with a description. That is a catalogue to
follow, and the registry holds 10 rows pointing into it.

### 34 rows declare a download service that 404s, and I do not know why

Of 535 datasets resolved against `nedlasting.geonorge.no/api/capabilities/{uuid}`,
**34 answer HTTP 404**. Every failure is a 404; none is a timeout or a refusal.
So the catalogue advertises `Geonorge nedlastning` for them and the download
service has no entry.

Five of those titles said "historiske versjoner", which is a tidy explanation,
so it got counted before it got written down: **65% of the failures carry
"histor" in the title against 46% of the successes, and 228 historical
datasets resolve perfectly well.** The lean is far too weak to be the cause.

Recorded as 34 unresolved with their 404, cause unknown. The tidy version
would have been read as settled by whoever picked this up next, and a wrong
settled explanation is worse than an open question.

### The download capabilities, applied — and two things the counting got wrong

644 of 689 datasets applied. 239 list kommuner, 62 need a Norge digitalt role,
13 offer CSV. `dataset_coverage` holds **71,749 rows over 1,538 kommune
codes**, and `datasets_covering("0301")` returns **197 datasets for Oslo**,
202 for Trondheim, 191 for Alstahaug — with the format and the licence on each.

**1,538 codes, and Norway has 357 kommuner.** 361 of the registry's 365 current
kommune codes are covered, which is near-complete. The other 1,177 are
historical numbers — `0101`, `0104`, `0121` and the rest of the pre-2020
numbering — which is correct, because a historical dataset covers historical
kommuner. It is also a trap: a query for Oslo as `0301` misses anything filed
under the old `0301`→`03` reorganisation and vice versa, and nothing currently
tells the two apart. The registry holds `klass:131` with validity dates and
this table does not join to it yet.

**The format names are not one vocabulary.** The publisher's own lists carry
**52 spellings of 34 formats**: trailing spaces on sixteen of them, plus
`GeoJSON`/`GEOJSON` and `Shape`/`SHAPE`. My own count of "how many offer CSV"
said 10 because it matched `"CSV"` exactly, and three datasets say `"CSV "`.
The real answer is 13.

Fixed in the resolver rather than in each consumer, because every consumer
would otherwise repeat it, and the printed spelling is kept beside the normal
form -- it is the publisher's, and normalising is a reading. The 689 already
resolved were re-normalised in place rather than re-fetched.

### N8: 1,538 kommune codes were 801, and the gap was one dataset

The first count of `dataset_coverage` said 1,538 distinct kommune codes
against Norway's 357, and I filed it as "current versus historical numbering".
Checking it found something else.

**737 of the 1,538 came from one dataset.** `N50 Raster - historiske data
2022 (UTM32)` files 737 raster tiles under `type: "kommune"`, each named after
its own number -- code `2005`, name `2005`. A kommune has a name; a tile has a
number. The resolver now drops an area whose name is its own code, which is
the grid-cell exclusion met one layer further in, and the already-resolved
rows were re-filtered in place rather than re-fetched.

With those gone the split explains itself, checked against Klass 131:

| | codes |
|---|---|
| current kommuner (Klass `codesAt` today) | **357 of 358** |
| historical (Klass `codes` 1838–2026, not current) | 426 |
| in neither | 18 |

The 18 are not errors. The publisher names them: Svalbard, Spitsbergen,
Bjørnøya, Hopen, Jan Mayen, `Sokkelen sør for 62 grader Nord`, `Sokkelen nord
for 62 grader Nord`, Antarktis, Europa. Klass 131 is a classification of
*kommuner* and these are not kommuner, so both sources are right.

Also corrected: I said the registry "holds klass:131 with validity dates". It
does not. `brkommuner` holds 365 current codes with empty attributes, and the
Klass API returns `validFrom`/`validTo` as **null on all 966 codes** -- the
populated fields are `validFromInRequestedRange` and `validToInRequestedRange`,
which are relative to the dates you asked for. Any join on validity has to
request a range and read those, not the plain fields.

**Still open:** nothing marks a coverage code current or retired, so a query
for Oslo `0301` still misses whatever is filed under the numbering it
replaced. That needs the Klass correspondence map, not just the code lists.

### N3: the NGU connector was storing a table of contents as measurements

`geo.ngu.no/api/features` lists 28 OGC API Features APIs and the registry
holds all 28 as `ngu:` datasets with the right landing pages. Six probed, six
returned features -- 3 to 6 collections each, 7 to 15 published fields per
feature. So this is ~100 readable collections behind one protocol `hi.py`
already speaks.

They were all unprobed, and finding out why cost a real mistake. I fetched
`ngu:ankringsforhold` to see what would happen, and it stored **17
observations whose measure was `title`**, with values like "This document as
HTML" and "OGC API conformance classes implemented by this server", then
marked the dataset verified with a sample count of 17. I reverted it scoped to
that one dataset.

`cells_from_ngu` was built to do that, and said so:

    """Copy printed NGU landing-page links into observation cells."""

An OGC landing page is a door. It prints a `data` link saying where the rooms
are. The reader now refuses the landing page and names that link in the error;
`collections_url` reads the link rather than composing `access_path +
"/collections"`, which gives the same string today and is a guess tomorrow.

**Two tests asserted the old behaviour**, by value:

    assert set(by_value) == {"Access the data (ankringOmr)",
                             "This document", "conformance"}

They were not wrong about what the code did. They were wrong about what it
should do, which is the harder kind to catch: the suite was green for the
entire time this connector was storing a service's table of contents as
measurements of the world. Both are replaced by tests that assert the refusal
and explain what they used to say.

Still to do: dispatch `_fetch_ngu` through collections and items, and store
the features as `feature` records rather than observations -- a seabed polygon
is a thing in a place.

### N3 finished: 28 NGU APIs, 7,765 features, and a label rule relearned

All 28 fetched, zero failures, **26 datasets carry a `features` verdict** and
`ngu` holds 7,765 feature records with zero observations.

The first run of all 28 produced labels that were not names:

    2.731                                            a soil temperature
    2016-11-17                                       a date
    SN15270:0:2500:mean(soil_temperature P1D):P1D    a Frost series id

Cause: `cells_from_ngu_items` fell back to `next(iter(scalars))` when a
feature had neither a `*Navn` field nor a known identifier, which promoted
whatever came first into the record's label. 1,067 in
`grunnundersokelser_utvidet`, 400 in `frostonline`, 60 in
`grunnvannborehull`.

A soil temperature is not the name of a borehole. The reader now names
nothing in that case: every scalar stays an attribute, the cell carries no
value, and `records_from_cells` keys the record by a digest of what it
printed -- which is exactly what it already does for a member whose publisher
gave it no handle. That rule was written for Cristin's funding list and Udir's
curriculum codes and it applies here unchanged.

**And then the check I used to find it gave a false positive.** After
re-fetching, 267 records in `grunnundersokelser_utvidet` still had labels
starting with a digit, and they are `2.pdf`, `365.pdf`, `175.pdf` -- document
filenames from its `geotekniskdokument` collections, which is genuinely what
the publisher calls them. "Starts with a digit" is not a test for
value-as-label; it was a way of noticing, and it needed reading afterwards.

Open: those `geotekniskdokument` collections are documents rather than
features, and the registry has a `documents` capability for that. Filed, not
guessed at -- they arrive through an OGC feature collection, so `feature` is
defensible until someone decides otherwise.

### N1: 82 datasets advertise a host that does not exist

Geonorge advertises 82 datasets as `OGC:OAPIF` on `pycsw.nina.no`. Checked
before anything was written: **NXDOMAIN from the local resolver, from 1.1.1.1
and from 8.8.8.8**, while `nina.no` and `www.nina.no` both resolve. So the
subdomain is gone and the institution is not.

They now carry a new verdict, `unreachable`, with the resolvers and the date
in the notes. It is deliberately not `withdrawn`: a withdrawn resource
answered 404, which means a server considered the request and declined it.
This one has no server. The catalogue's entry is wrong, no connector will fix
it, and the difference matters to whoever reads the row next.

**The correction this makes to a number I had been reporting:** the
`queryable-api` tier was 324. 82 of those are this host. Honestly queryable:
**242**. A 25% overstatement, carried in three updates before it was checked.

`scripts/mark_unreachable.py` re-resolves each host itself and refuses to mark
anything if the host answers. A DNS failure can be local and temporary, and
82 verdicts written from a claim in a docstring would be worse than none.

Two things worth keeping about how this went:

- The declared tier is left untouched. What the publisher says it offers and
  what we found are two facts, and overwriting the first with the second
  loses the catalogue's own claim -- the same reason `datasets.license` is not
  overwritten by the resolver.
- `test_no_capability_row_is_unverified_without_saying_why` failed on all 82
  until `unreachable` was registered in its `decided` set. That is the
  invariant working: a new way of saying "nothing came back" has to be
  declared as a decided answer rather than slipped in beside the others.

### N4: reading the 151 climate grids without moving them

`src/public_data_agent/opendap.py` reads a THREDDS dataset's variable list
from `.dds` and its units and names from `.das`. Two requests per dataset, no
data transferred.

THREDDS serves nothing easier: `.ncml`, `.iso` and `.dods.json` all answer
HTTP 400 on this server, so the two custom formats are the only way in. Both
parsers are shallow on purpose -- they read the declarations they understand
and ignore the rest -- because a `.das` carries free-form attribute blocks no
fixed grammar covers, and a variable list is worth having when one attribute
is unparseable. What they will not do is return an empty list: a `.dds` that
parses to nothing raises, because "no variables" and "the parser failed" are
different answers and only one is ever true here.

On the live `change-evap` dataset: **11 declared variables, 5 measured.**
Units `%`, long name "change in mean evapotranspiration", shape
`time=2, Yc=1550, Xc=1195`.

The six excluded are excluded for four different reasons, all live in that one
dataset: `time` and `lon` declare themselves coordinates in their own
attributes; `Xc` and `Yc` are indexed only by themselves; `projection_utm`
holds the CRS and has no dimensions at all; and `lat` has a `standard_name` of
`latitude`. A grid's axes say where a value sits, not what was measured, and
promoting one would be the same error as naming a borehole after its soil
temperature.

Next: run it over the 151 and store the variables in `resource_fields`, which
is the field index search already reads -- so "fordampning" starts finding
them. No `observations` row for any of it: a 1.85M-cell projection is not a
measurement.

### The field index is 20,451 rows that neither search lane reads

Found by checking a claim I had just put in a commit message. I wrote that
indexing the THREDDS variables means "'fordampning' and 'snømengde' start
reaching 151 datasets". Then I ran the searches.

    fordampning          4 results -- matched on **title**, which already said it
    evapotranspiration   3 results -- matched on **keyword**, already in the payload
    swemax               **0 results**, and `diff-swemax_annual` is now a
                         `measure` field on three datasets

So the indexing changed nothing about what is findable. `embedding_text` is
built from title, description, keywords and themes; the lexical ranker scores
the same four, at title=10, keyword=5, theme=5, description=2. Neither reads
`resource_fields`.

That is not a THREDDS problem. It is the whole index:

| | |
|---|---|
| `resource_fields` rows | **20,451** |
| datasets with at least one field | **4,872** |
| distinct field codes | 1,633 |
| rows carrying a label | 20,300 |
| `resource_field_values` rows | **587,333** |

4,872 datasets have had their shape read and 587,333 field values stored, and
a query cannot reach a single one of them through search. The 151 THREDDS
datasets join that set rather than escaping it.

**One obvious fix has already been measured and refused.** Appending measures
to `embedding_text` earlier in this session moved tuned recall@5 from 0.939 to
0.888 and coverage from 1.000 to 0.909. Concatenating field names into the
embedded text dilutes it.

What has *not* been tried is a lane: score field-code and field-label matches
separately and fuse them, the way lexical and semantic are already fused,
rather than concatenating. That is P4-shaped work with a measurable outcome
and it has to be measured on tuned **and** coverage before adoption, like
every other ranking change here.

Until then, the field index is worth having for `tool_inspect` and for SQL --
"which datasets hold a measure called X" is answerable, just not from the
search box. The commit message that claimed otherwise is corrected here.

### The field-match lane, refused before it was built

Last tick's note proposed scoring field-code and field-label matches as a
third lane and fusing them. Measuring the headroom first killed it, for about
a tenth of the cost of building it.

**Which gold questions could a field match help?** A question term that the
gold dataset's fields carry and its title and description do not:

| set | questions | helpable |
|---|---|---|
| tuned | 98 | **5** (5%) |
| held-out | 42 | 3 (7%) |

    a002  sysselsetting etter næring      ssbtable:11654   ['næring']
    a004  lønn etter yrke                 ssbtable:11418   ['yrke']
    a011  utenrikshandel eksport import   ssbtable:10191   ['eksport','import']
    a017  dødsårsaker                     fhi:nokkel:343   ['dødsårsaker']
    a052  … vaksinert mot meslinger       fhi:nokkel:395   ['mot']

**And the decisive part.** The tuned questions that currently miss are a010,
a025, a027, a035, a047, a049, a058, a063, a080. The overlap with the five
above is **empty**. All five are already found; none of the nine missed would
be helped. So the lane's measurable gain on the tuned set is zero, against the
regression risk that the measures-in-embedding experiment already demonstrated
(0.939 → 0.888).

Not built. Recorded so the next person who notices 20,451 unread field rows
does not spend a day on it either.

(a052's hit is `mot`, a Norwegian preposition. That is a false positive in my
own headroom measure, and it means the real figure is 4 of 98, not 5.)

### Correction: the *values* index is read, the field *names* are not

I wrote that "none of it is reachable". That was too broad.
`resource_field_values` is read by `resource_index.py:883` through
`datasets_containing_value`, which is how the kommune/fylke/bydel select path
finds a table whose title never mentions a place:

    value_code "5001"  ->  ssbtable:06505  field=Region  label="Trondheim - Tråante"

It matches on `value_code`, not on `value_label`, so a query for "Alstahaug"
finds nothing and one for `1820` finds it. That is deliberate -- codes are
the join keys -- but it is worth knowing before concluding the index is
unused.

It also surfaced the collision this project already knows: `value_code 1820`
matches both Alstahaug the kommune and 1820 the year, in a `Tid` field. The
same ambiguity that made `PERIOD_VALUE` read municipality numbers as periods.

### N2 confirmed, and the format names are six vocabularies not one

All six hosts running the Geonorge download software answer
`api/capabilities/{uuid}`:

| host | datasets | resolved | 404 | lists kommuner | CSV |
|---|---|---|---|---|---|
| `nedlasting.geonorge.no` | 609 | 567 | 42 | 220 | 13 |
| `kart8.nibio.no` | 49 | 48 | 1 | 15 | 0 |
| `nedlasting.ngu.no` | 21 | 20 | 1 | 1 | 0 |
| `kartkatalog.nibio.no` | 8 | 7 | 1 | 2 | 0 |
| `kartiskolen.no` | 1 | 1 | 0 | 1 | 0 |
| `exledfor.atlas.vegvesen.no` | 1 | 1 | 0 | 0 | 0 |

644 resolved, 46 of the 404s from N7 still unexplained.

**36 distinct format names across those six hosts**, and the variation is not
the whitespace-and-case problem fixed earlier. It is five different kinds of
difference:

    geojson    GEOJSON / GeoJSON              case only
    shape      ESRI Shape / SHAPE / Shape     vendor prefix
    gml        GML / GML 3.2.1                version suffix
    postgis    PostGIS / PostGIS.sql          file extension
    tiff       GeoTIFF / TIFF                 **not the same format**

The last line is why this is not getting an equivalence table. GeoTIFF carries
georeferencing and TIFF need not, so merging them would destroy a real
distinction in the name of tidiness -- and `GEODATABASE_FILE` against `FGDB`
is probably the same Esri format but "probably" is not a basis for collapsing
two publishers' vocabularies.

Case and whitespace are safe to normalise because the string is the same
string. Everything above is a **mapping**, which is a claim about equivalence
and belongs to whoever is willing to defend it per pair. What would be safe
and useful is prefix matching -- a query for `GML` matching `GML 3.2.1` --
because that follows from the names rather than from a judgement about them.

Recorded, not acted on.

### N5 and N6 fixed, and a third found while testing the fix

**N6** — 151 THREDDS rows resolve to `<dataset>.nc.html`, which is the HTML
request form OPeNDAP generates *from* the dataset it names. The classifier
called them `unclear: not JSON`, which is true of the form and says nothing
about the `.dds` one character away. `discover.py` now follows both `.dds` and
`.das`, and recognises an OPeNDAP document as `rows` rather than a parse
failure. Marked `convention:` and not `declared:`, because no link in any
response says to do it.

**N5** — `resolve_geonorge.py` now reports, at the end of a run, how many rows
share a `best_url` and names the worst offenders. 608 rows resolved to
`nedlasting.geonorge.no/api/capabilities/`, which is the download service's
root, and reading that as one resource nearly cost the per-dataset endpoint
behind it. The url is the publisher's own declaration and is kept; what was
missing was the tool saying so.

**And a third, found by running the N6 fix live.** The form timed out at 45
seconds, so `investigate` returned early on `unreachable` and never tried the
doors -- the fix could not fire in exactly the case it was written for.
Generating the HTML page for a 1.85M-cell grid is slow while `.dds` answers in
a moment, so a form's failure says nothing about its dataset. The early return
now makes an exception for OPeNDAP, with a test that drives it through a
client where every request fails.

**Worth owning:** both the form and the `.dds` timed out on a server that had
answered 151 `.dds` requests minutes earlier. That is 302 requests from this
machine at 0.4s spacing, and the slowness is far more likely mine than theirs.
`thredds.met.no` is done with for today; the indexing it was needed for is
finished.

### N7 answered: 34 of 45 are series parents, 11 are still unexplained

The 404s from the download service. My first hypothesis was "the historical
versions", checked and rejected. The second was "a different uuid", checked
and rejected -- the uuid we send matches the catalogue's own `Uuid` exactly.

The catalogue says it outright, in a field I had not read:

    a failure   HierarchyLevel "series"   Type "series"   "Datasettserie"
    a success   HierarchyLevel "dataset"  ParentIdentifier 86a4c445-…

A **Datasettserie** is a parent record grouping versions. It has no
distribution of its own, so the download service has no entry for it and the
404 is correct behaviour by both parties.

Checked across all 45 rather than claimed from one:

| | series | dataset |
|---|---|---|
| all 45 failures | **34** | 11 |
| 30 successes, for contrast | 0 | 30 |

So **34 of 45 are explained and 11 are not.** Those 11 are `HierarchyLevel:
dataset` and still 404, and I have no hypothesis for them. Saying "N7 is
solved" would be wrong by eleven rows.

Fixed: `resolve_geonorge.py` now captures `HierarchyLevel` and
`ParentIdentifier`, and `resolve_download_capabilities.py` skips a series
instead of recording a failure -- a failure invites someone to debug a service
that is behaving correctly. Backfilling `hierarchy_level` onto the 7,425
already resolved means another full run, about 45 minutes, and is worth doing
before anyone counts failures again.

Incidentally the title test that failed as a hypothesis works as a
discriminator for part of it: "versjoner" appears in 25 of 45 failures and
**0 of 644** successes, while "historiske data" appears in 284 successes and 1
failure. Which is a reminder that a signal can separate two groups without
being the reason they differ.

### N7 finished: the last 11, and a 200 that meant nothing (2026-10-22)

Two things in the section above were wrong, and the second nearly got written
into the registry as a finding.

**The series skip was dead code.** `resolve_download_capabilities.py` grew a
`hierarchy_level == "series"` branch, and `main()` never passed the argument --
the column it would have read is part of the 45-minute backfill that has not
run. The `series-skipped` counter sat at 0 across all 689 rows while the commit
message said 34 were answered. It was answered on paper only.

**And the fallback I was about to build would have been a false negative.**
The 11 remaining 404s each return `200` from `codelists/format/{uuid}` and
`codelists/area/{uuid}`, which looked like the download service knowing the
uuid after all, and like formats and kommune coverage recoverable without the
capabilities call. The bodies are `[]`. So is the body for
`00000000-0000-0000-0000-000000000000`:

    codelists/format/<a 404 uuid>   200 []
    codelists/area/<a 404 uuid>     200 []
    codelists/format/<garbage>      200 []
    codelists/area/<garbage>        200 []
    codelists/format/<a working>    200, 3 entries
    codelists/area/<a working>      200, 102 entries

The status code says the route exists, not that the dataset does. Reading `200`
as presence would have recorded "offers no formats, covers no kommune" for all
11 -- a positive claim, published, sourced from an empty list that means
nothing. The same shape as the `%NC%` licence count and the kommune-shaped
tiles: a query that answers, with an answer about the wrong thing.

**What does answer is the catalogue the uuid came from**, one request per 404
rather than a re-run of 7,425:

| verdict | rows | what it means |
|---|---|---|
| `series` | 34 | a Datasettserie, no distribution of its own |
| `offline` | 1 | `GEONORGE:OFFLINE` -- the publisher says not online |
| `unregistered_download` | 10 | `GEONORGE:DOWNLOAD` declared, no entry in the service |

45 of 45 decided, 0 errors. The 10 are a real disagreement between publisher
and platform. The catalogue record carries the format list itself, with
versions the download service does not state -- `GML 3.2.1`, `FGDB 10.0`,
`PostGIS 9.4`, `SOSI 4.5`, and `GPKG 1.3.1` for NIBIO's Jordsmonn -- but
checked against the registry, **0 of the 10 carry a format name that is not
already in `formats_json`**: `resolve_geonorge.py` harvested the same list from
the same record, minus the versions. So the format recovery is worth a version
string and nothing else, and is not written: putting versioned names into
`download_formats_json` would attribute to the download service a statement the
catalogue made. The selection flags and the area list stay unrecoverable, so
these 10 contribute no coverage.

**The find is on the same record.** 9 of the 10 declare a view service, and
8 of those are GeoServer layers that answer WFS at the address their WMS is
published at:

    mareano_biologi:bomtraal_arter                      411 features, 12 fields
    mareano_biologi:slede_individer                     337
    mareano_biologi:grabb_biomasse                      412
    mareano_biologi:hornkorall_paragorgia_arborea       853
    mareano_biologi:hornkorall_primnoa_resedaeformis    453
    mareano_biologi:hornkorall_isidella_lofotensis      316
    mareano_biologi:hornkorall_paramuricea_placomus     252
    mareano_biologi:hornkorall_radicipes                119

3,153 point features with species, depth, date, bottom type and cruise number.
Three of the eight failed on first contact with a timeout and answered on
retry, which is latency on a cold layer, not a gap -- worth remembering before
calling a Mareano layer dead. The ninth is NIBIO's `jordsmonn_harmonisert` on a
MapServer `cgi-bin` with no layer name in the record, and MapServer does not
answer WFS by default.

So the datasets with *nothing* to download are the ones with data to read, and
the path to it was in the field beside the one that 404s.

**New issue, and it is a sweep not a fix.** `ServiceDistributionProtocolForDataset`
is `OGC:WMS` on far more than these 11 records. Every GeoServer one is a
candidate `features` source, and the registry currently stores none of it --
`resolve_geonorge.py` does not capture `ServiceDistributionUrlForDataset`. Two
caveats before counting it as breadth: a WMS on MapServer or ArcGIS is not a
WFS, and the layer name arrives in two spellings, `a:b` and `a/b`, which has to
be normalised to a `typeNames` value.

### N10 measured: 797 layers behind 165 declarations, and they are GML (2026-10-22)

The sweep found by the N7 leftovers, run over the whole catalogue. The field is
`ServiceWfsDistributionUrlForDataset` and the search API returns it per hit at
500 hits a page, so this is 15 requests rather than 7,437.

    165 of 7,437 dataset records declare a WFS
    134 distinct addresses, 31 records sharing one with another dataset
    116 of the 165 are in this registry
    116 of the 116 have no capability row at all -- not one has been asked

Then one `GetCapabilities` per address. **130 of 134 answer, with 797 layers.**
The four that do not are a 404 on an ArcGIS Online service, a 401 on
`matrikkel.no` (which is the Kartverket framework-agreement gate, already
written up in ACCESS.md), one malformed url in the catalogue itself --
`https://kart.hi.no/mareano/https://kart.hi.no/mareano/magik/…`, a host
pasted twice -- and one `dservices2.arcgis.com` path that no longer exists.

Two things the first pass got wrong, both my own:

**The regex.** `<(?:\w+:)?Name>` reported **zero layers for every
wfs.geonorge.no service**, 24 false negatives out of 40, because their `<Name>`
carries an `xmlns:app` attribute and the pattern demanded `>` straight after
the tag. Parsed with ElementTree the same services have 1 to 36 layers each.
A pattern that answers for 14 addresses and silently fails for 24 looks like a
finding about the publisher.

**The retries.** 7 addresses failed the first pass; 4 of them are `kart.hi.no`
and all 4 answered on retry, with 92 layers between them. That is now twice
that HI has timed out on first contact and answered afterwards -- it is a cold
layer warming up, and anything that probes HI once and records a verdict will
be wrong about it.

**797 layers behind 165 declaring datasets**, and the ratio is the interesting
part. `factmaps.sodir.no` carries 97 layers for 1 declared dataset; SSB's
`boliger_paa_rutenett` 57 and `bygninger_paa_rutenett` 56; `wfs.dybdedata` 36.
The catalogue itemises a fraction of what the services hold, which is the same
shape as the 28 NGU APIs behind 10 catalogue rows.

#### The reader has to parse GML, and that is measured rather than assumed

Of 130 answering addresses, **128 advertise GML and nothing else**:

    515 layers   text/xml; subtype=gml/3.2.1
    515          application/gml+xml; version=3.2
    195          text/xml; subtype=gml/3.1.1
    195          text/xml; subtype=gml/2.1.2
     12          application/json
      2          application/json; subtype=geojson
      2          text/csv

An advertised list can understate, so it was tested rather than trusted --
`kart.hi.no` answers `outputFormat=application/json` with GeoJSON while
advertising none, because GeoServer always carries it. The dominant host does
not:

    wfs.geonorge.no   outputFormat=application/json   HTTP 400 ExceptionReport
    wfs.geonorge.no   no outputFormat                 200 gml/3.2.1
    kart.ssb.no       outputFormat=application/json   HTTP 400
    kart.hi.no        outputFormat=application/json   200 GeoJSON

97 of the 165 declarations are on `wfs.geonorge.no`. So the format question is
settled: **GML 3.2.1**. Nothing in `src/` mentions GML today.

The shape is tractable -- flat property elements under a namespaced feature
element, with geometry inlined:

    <app:Hornkoraller gml:id="hornkoraller.177378">
      <app:art>Paragorgia arborea</app:art>
      <app:prøveNummer>35</app:prøveNummer>
      <app:posisjon>
        <gml:Point srsName="urn:ogc:def:crs:EPSG::4258">
          <gml:pos>70.435100 21.948400</gml:pos>

**And there is the trap.** `EPSG::4258` is latitude-first, so that `gml:pos` is
70.43 N 21.94 E -- off Finnmark, which is where Paragorgia arborea is. The
GeoJSON from the same publisher's other service writes the same kind of point
as `[16.1687, 69.1226]`, longitude first. Reading one convention as the other
puts every Norwegian feature in the Indian Ocean, and nothing in the payload
complains. `srsName` has to be read per geometry, not assumed per source.

### The answer path stops after "fetch", measured on one question (2026-10-22)

A reviewer proposed a test question and it turned out to be the sharpest thing
anyone has run at this system:

> Hvor mye husholdningsavfall per innbygger hadde Bærum i 2024 sammenlignet
> med Asker?

Run through `ask()` with the real provider, the stages separate cleanly:

| stage | result |
|---|---|
| search | finds `ssbtable:12241` and `ssbtable:13035` in the top four. `(K)` is kommune-level. **Correct.** |
| plan | `catalog_search_and_optional_fetch`, no refusal. Correct. |
| fetch | **264,033 observations** from `13035`. It worked. |
| select | nothing. No kommune filter, no year, no measure. |
| compute | nothing. |
| report | `numbers_retrieved: true`, "Values are copied from stored observations; no join or derived number was emitted." |

So the system answers a question about two kommuner in one year with a quarter
of a million rows covering every kommune, every year and every waste fraction,
and calls it a success. **`numbers_retrieved: true` is not an answer**, and it
is currently the only thing measured.

The table does carry what the question needs -- `Årsinnbyggere (antall)` is the
denominator, and the dimensions are `KOKkommuneregion0000` and `Tid`. Nothing
is missing from the data. What is missing is the three stages after the fetch.

`ask()` has exactly one special-cased intent, `bydel_population_size_and_growth`,
which does join two years and derive a rate. Everything else falls through to
`_execute_catalog_plan`, which fetches and copies. So the general answer path
is the fall-through, and it has never been scored.

**Two consequences, and the second was not expected.**

The first is P0.1: the harness has to score the *value*, not the retrieval,
and it will fail most questions on day one. That is the point of building it.

The second is a storage problem. One question grew `observations` from 25,921
to 290,000. The standing rule here is "save pointers, not payloads" because
the machine is storage-constrained, and the fetch path ignores it when a
question arrives -- it pulls the whole table. A hundred-question harness run
would be tens of millions of rows. So the harness has to pass `max_cells`, and
the real repair is for the plan to narrow the request before it is sent:
`13035` with `KOKkommuneregion0000` and `Tid` pinned is two cells, not 264,033.

Incidentally the stored dimension values name the kommune as
`"Agdenes (-2017)"` -- SSB marks a retired kommune inline, in the label, with
no separate validity field. That is a third spelling of the N8 problem and it
is in the data we now hold.

### A 167 MB write-ahead log read as a publisher throttling us (2026-10-22)

The bwfish backfill stopped advancing at 65 of 766 weeks. No error, no output,
the process asleep in an SSL socket read. Every reading said "the publisher is
throttling us", which is a conclusion this project has reached correctly
before -- thredds.met.no really did start timing out after 302 requests from
this machine.

It was wrong here, and one probe settled it:

    token           ok in 0.1s
    one week        HTTP 200 in 0.4s, 1,749 entries

BarentsWatch was answering throughout. What had happened is that the
un-narrowed `ask()` fetch described above wrote 264,033 rows into the same
database, leaving a **167 MB** write-ahead log. Every commit in the backfill
then had more WAL to work through, and the run slowed to a stop without ever
raising anything.

    PRAGMA wal_checkpoint(TRUNCATE)     0.5s, WAL gone
    the same ten weeks, after it        11.8s, 1.18s each

So the backfill now checkpoints every 25 weeks, and the comment in the code
carries the measurement rather than calling it hygiene.

**The lesson is about the diagnosis, not the pragma.** A stalled process, a
socket read and a publisher who asks for single-threaded access compose into
a story that explains everything and is false. The thing that broke it was
asking the publisher directly instead of reasoning about them -- the same move
that settled the `codelists` 200s and the NGU title bug. Two independent
symptoms traced to one cause, and that cause was a bug of ours from twenty
minutes earlier.

### P0.0 closed: 264,033 becomes 54, and nothing new was needed (2026-10-22)

The repair for the section above. `fetch_observations` has accepted `kommune`,
`from_year`, `to_year` and `max_cells` since long before today; the caller
passed none of them and then returned `list_observations(dataset_id)`, which
is every row the dataset has ever accumulated. So the whole defect was that
nothing read the words.

Same question, same tables, same connector:

| | before | after |
|---|---|---|
| observations returned | 264,033 | **54** |
| covering | every kommune, every year | Bærum and Asker, 2024 |
| population denominator | somewhere in the 264,033 | `Årsinnbyggere (antall)` 132,411 and 101,641 |
| explanation | "Values are copied from stored observations" | "The request was narrowed to place Bærum, Asker; year 2024. …" |

The narrowing is `constraints.py`, grounded in `brkommuner`, and the rule it
enforces is that **a name becomes a code only where a publisher said so**.
Three behaviours matter more than the count:

**One request per place.** A comparison asks about two kommuner and a single
filter holds one. Two requests, and the rows come back by `observation_ids`
rather than by dataset.

**An ambiguous name is not narrowed, and the answer says so.** The register
holding `0301` and `301` for Oslo is not a tie to break. The explanation ends
"Not narrowed to Oslo: the register holds more than one code for that name",
because an answer that quietly picked one would be indistinguishable from an
answer that got it right.

**A refused filter is reported, not absorbed.** A connector that cannot filter
on kommune raises rather than ignoring the argument, which is correct. The
fallback asks once without the place, keeps the year and the budget, and
records `filter_not_supported`. A nationwide answer that reads as if it were
Bærum's is the failure this prevents.

`ASK_MAX_CELLS = 20_000` is a ceiling for when narrowing fails, not a target.

8 tests, mutation-checked: dropping the `kommune=code` pass-through fails
three of them, and the fake registry raises outright if anything asks for
observations by dataset id again.

**What is still not done, and it is the remaining half of the question.** The
54 rows contain everything needed to answer and nothing divides them. A
customer asking "per innbygger" gets the waste tonnage and the population as
separate rows. `numbers_retrieved: true` is now honest about *which* numbers,
which it was not before, but it is still not an answer. That is P0.1.

### P0.3: the third question has a column, and the first number it produced corrected me (2026-10-22)

`datasets.license` answers "may it be used". Nothing answered "may it be
passed on", which for a service that hands data to other people's agents is
the permission that decides what can ship. `licence_terms` is that answer,
keyed by **family** rather than by dataset: a family is a lookup over
published identifiers, a verdict is a reading of a licence text, and recording
the reading once per family means 18,280 datasets inherit a handful of
decisions instead of carrying 18,280 unsourced ones.

`source_url` is `NOT NULL` and rejected when blank. A redistribution verdict
with no text behind it is an opinion.

Three families recorded, each read from the licence itself today:

| family | redistribution | commercial | read from |
|---|---|---|---|
| NLOD | allowed, attribution required | allowed | data.norge.no/nlod/no/2.0 |
| CC-BY | allowed, attribution required | allowed | creativecommons.org/licenses/by/4.0/ |
| CC-BY-NC | **denied** | denied | creativecommons.org/licenses/by-nc/4.0/ |

NLOD is worth quoting because it settles the question in its own words: the
licence "gir deg rett til å kopiere, bruke og tilgjengeliggjøre ... gitt at du
navngir bidragsyterne", and **`tilgjengeliggjøre` is defined to include
`distribuere ... selge`**. Redistribution and sale are named by the licence,
not inferred from it.

The resolver never returns `allowed` by default. A missing row, an
unrecognised licence and an absent licence are all `unknown`. Two overrides
sit above the lookup: a **declined agreement** beats a recorded permission,
because a permissive licence on data we may not obtain is still data we may
not pass on; and **CC-BY-NC cannot be recorded into permission**, because a
stray row must not be able to contradict the licence's own name.

#### And the first count it produced corrected a number I had given twice

| | datasets |
|---|---|
| no recognised family | 9,301 |
| **Norge digitalt** | **6,350** |
| NLOD | 1,370 |
| CC-BY | 865 |
| INSPIRE no-conditions | 244 |
| CC0 | 95 |
| CC-BY-NC | 51 |

I had been saying 1,939 for Norge digitalt, and repeated it in the launch
plan. The real number is **6,350**. The gap is one URL:

    4,344  …/Geodataarbeid/geografisk-infrastruktur/Norge-digitalt/Avtaler-og-maler/Norge-digitalt-lisens/
    1,939  …/Geodataarbeid/Norge-digitalt/Avtaler-og-maler/Norge-digitalt-lisens/

The first is the same licence at a longer path. Earlier in this session it was
printed truncated at 62 characters, which cut it at `geografisk-infrastruktur`
and made it look like a generic infrastructure page, and I counted it as one.
So Kartverket's decline closes **three times** what I told the user it did.

The lesson is the same one as the `%NC%` licence count and the kommune-shaped
tiles: a display truncation is not a fact, and a number read off a truncated
column is a guess wearing a count's clothes.

### N10b: the guard was refusing the data along with the menu (2026-10-22)

`fetch_observations` refused every URL carrying `/wfs`, `/ows` or
`service=wfs`:

    "access_path is a map/tile service (WMS/WFS/OGC);
     it returns imagery or geometry, not numeric cells"

That refusal was earned. Fetching a capabilities document once stored
seventeen layer names as observations, with `measure: "title"` and values like
"This document as HTML", and marked the dataset verified. The guard was the
fix.

But it drew the line between **protocols** when the real line is between
**requests**. A `GetCapabilities` is a listing of what a service offers, which
is metadata. A `GetFeature` is the things themselves. Same protocol, opposite
sides of the rule this registry is built on.

So `is_wfs_feature_url` requires all three of `service=WFS`,
`request=GetFeature` and a `typeNames`, and the dispatch sits **above** the
guard rather than beside it -- a feature URL matches the same marks, so order
is what separates them. A test asserts both halves, because a later edit that
moves the dispatch below the guard would silently close the door again.

Live, against `wfs.geonorge.no/skwms1/wfs.hornkoraller`:

    25 GML features, capability `features`, verified, record kind `feature`
    subject_scheme  wfs:app:Hornkoraller
    attributes      art, bunnDybde, bunnForhold, dato, toktNummer, …

**And the first run got the label wrong in a way worth keeping.** Every record
came back with `subject_label` equal to `subject_code` -- the same UUID twice.
`records_from_cells` has a documented rule for exactly this ("the record
carries the code and no label, because inventing a name for it is the failure
this whole change is about") and my cells were defeating it by passing the
identifier as the cell's value as well as its measure. A label that repeats
the code says nothing and is one step from an invented name. Fixed in the
reader: no printed name means the cell carries the identifier and **no value**,
and 0 of 25 records now carry a label. The species, depth and bottom type were
never at risk -- they are attributes either way.

15 tests. What remains for N10b is the sweep itself: resolving each of the 116
datasets to its layer, which needs the capabilities read per address, and
applying the WFS address to the registry so the dispatch can see it. The
reader and the door are done; the 116 have not been walked through yet.

### P1.2b: 83 datasets read, and the 41 "failures" were the publisher being correct (2026-10-22)

The sweep ran. 85 datasets own their WFS address, 237 layers answered, and
**93,916 feature records** landed — species, depth, bottom type, noise limits,
bathymetry, ground surveys. The largest single layers:

    2,602  grunnundersokelser_utvidet
    1,138  app:Støygrense
    1,124  app:Støy
    1,001  hi_basemap:basemap_ne_10m_bathymetry_5000m

`features` capabilities went from 456 to **539**, and the 116 datasets that
had never been asked are now 83 answered, 27 deferred and 4 to retry.

**41 layers stored nothing, and I nearly recorded that as 41 failures.**
Re-running them with the exception text printed says what they actually are:

    29 of 30 re-checked   "a FeatureCollection with no members"
     1 of 30              a kart.hi.no timeout

And their names say why:

    SpatialDataSet · AccessRestriction · ConditionOfFacility
    MaintenanceAuthority · MarkerPost · OwnerAuthority · RestrictionForVehicles

These are **INSPIRE schema stubs**. The directive requires the service to
publish them; the publisher has nothing to put in them. An empty layer is a
fact about the data, not a fault in the fetch, and `gml.py` raising on it was
right — "an empty layer and a response this reader misread are different
answers" — but the sweep was collapsing that distinction back into "failed".

So the sweep now counts `layer empty` separately, does not retry it, and
prints which layers a dataset serves nothing from. Reporting these as broken
would send someone to debug a service doing exactly what the schema demands,
which is the same mistake as calling a Datasettserie's 404 a failure.

Retries went from two to three with a widening gap, because `kart.hi.no` has
now timed out on first contact and answered afterwards four separate times
today.

**Still not recorded: how big each layer really is.** A stored sample of 500
and a layer holding exactly 500 are indistinguishable in
`verified_sample_count`, and `wfs.geonorge.no` answers every GetFeature
`numberMatched="unknown"`. `hits_url` exists and nothing calls it. That is
P1.2d and it is one request per layer.

### P1.2d: the denominator, and a four-cell finding that was three-quarters noise (2026-10-22)

A stored sample of 500 and a layer holding exactly 500 were written
identically in `verified_sample_count`. `total_count` is the fix -- how many
records the resource holds **as the publisher reports it**, NULL when the
publisher declines to say, which is a real and common answer. `set_capability`
refuses a sample larger than its total: both numbers must describe the same
resource or the registry publishes a coverage above 100%.

The connector now asks. For Hornkoraller it stores `25 of 1,993`, so the
registry can state that it holds 1.3% of that layer rather than implying it
holds the layer.

**And the route there is the lesson.** `wfs.geonorge.no` 404'd the generated
hits URL while answering a hand-built one that looked identical. One request
per spelling produced a clean four-cell table:

    typeNames=app:Hornkoraller   &resultType=hits   200
    typeNames=app%3AHornkoraller &resultType=hits   404
    typeNames=app%3AHornkoraller &count=2           200
    typeNames=app:Hornkoraller   &count=2           404

which reads as a server whose URL decoding depends on which other parameter
is present -- two backends, a tidy story, and I wrote it into a docstring.

Six requests per spelling say it is false:

    typeNames=app%3AHornkoraller &resultType=hits   200 x6
    typeNames=app:Hornkoraller   &resultType=hits   200 x3, 404 x3
    typeNames=app%3AHornkoraller &count=2           200 x6
    typeNames=app:Hornkoraller   &count=2           200 x6

The service is **flaky on the unencoded colon** and fine on the encoded one.
The single sample had caught **three of its four cells on the wrong side of a
coin flip**, and every one of those wrong readings fitted the story.

This is the same shape as the `codelists` 200s, the truncated Norge digitalt
URL, and the WAL stall that read as throttling: a measurement that explains
everything, taken once. Against a flaky server one request is not a
measurement, and the tell is that the result is *too* tidy -- four cells, four
clean answers, a mechanism that accounts for all of them.

The generated URL now answers 1,993 five times out of five.

### P1.2e/f: a sample count that described one layer of five, and four addresses explained (2026-10-22)

**The capability row was describing the wrong thing.** `_fetch_wfs` sets a
capability per call and the sweep calls it per layer, so a dataset with five
layers had its single row overwritten five times and kept the last. The
registry read `verified_sample_count: 20` beside **1,500 stored records**.
Neither number was wrong on its own; the row simply answered a question
nobody asked -- how big the last layer's sample was.

The sweep now writes one row per dataset, after all its layers, summing both
the sample and the totals. What that produces is the honest version:

    Administrative enheter          115 sampled across 3 layers of   27,752
    Aktsomhetskart jord/flomskred    50 sampled across 1 layer  of  503,461

Half a million features in one layer, and we hold five hundred. The registry
can now say that, which it could not an hour ago.

**And the four addresses that did not answer are all explained**, each with a
cause already written down elsewhere:

| address | after 3 retries | why |
|---|---|---|
| `kart.hi.no/data/svo_forslag2021/ows` | **5 layers on attempt 2** | the HI cold-layer pattern, now five times |
| `kart.hi.no/.../Bunnstromretning…` | **1 layer** | same |
| `dservices2.arcgis.com/…` | HTTP 404 x3 | the service is gone |
| `www.matrikkel.no/geoservergeo/wfs` | HTTP 401 x3 | the Kartverket gate, ACCESS.md §7 |
| `kart.hi.no/mareano/https://kart.hi.no/…` | error x3 | the catalogue url with its host pasted twice |

So two recovered and three are decided answers rather than failures. Nothing
here is unexplained, which is the state N7 had to be dragged to and this one
reached on the first retry.

One more worth noting: `wms.test.artsdatabanken.no` answers and publishes
**zero layers**. A host with `test` in its name is in the production
catalogue, which is a finding about Geonorge rather than about us.

#### The guard earned its place within the hour

The first full re-run stopped on the rule added an hour earlier:

    ValueError: verified_sample_count 141 exceeds total_count 104;
    the sample and the total are not describing the same resource

My aggregation summed the sample across **every** layer and the total across
only the layers that **stated** one, so a dataset whose first layer gave 100
features and no size, and whose second gave 41 features and a size of 104,
came out as "141 of 104". Without the guard that writes a coverage of 136%
into the registry and nothing notices.

A total is now reported only when every layer read gave one, and otherwise the
note says how many did not. A partial sum is not the dataset's size, and
publishing it would understate exactly the layer a reader most needs to know
is large.
