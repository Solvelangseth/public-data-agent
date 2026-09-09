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

Eight of 43 held-out questions have no answer anywhere in the registry -- permitteringer,
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
