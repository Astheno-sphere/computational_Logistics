# How to describe an operation so an agent can find it

A specification for one catalogue entry, and the measurements each field is
required by. Normative schema: [`schema/operation.schema.json`](../schema/operation.schema.json).
Every entry in MapSmith's catalogue validates against it in CI.

This exists because tool discovery stops working before anybody notices. A server
with fifty operations feels fine; the same server with eight hundred returns three
plausible names and the right one is not among them, and nothing in the protocol
says so. The fields below are what we measured our way to, including the ones that
turned out to be worth nothing.

## The measurement everything rests on

118 requests written by two other model families from job scenarios — a hydrologist
with a flood report, a surveyor arguing with a field measurement — against a
catalogue neither of them was shown, because a model handed the entry writes a
paraphrase of the entry. Phrased the way somebody with a problem asks, not the way a
catalogue is written: *"the coastline is 400 000 nodes and the browser dies"*, not
*"simplify the geometry"*.

| what the caller declares | candidates left | ranked, found@3 | **in what comes back** |
|---|---|---|---|
| nothing — words alone | 77 | 29% | 29% |
| the input kind | 51 | 35% | 36% |
| + what it should produce | 32 | 45% | 54% |
| + how many datasets | 17 | 54% | 84% |
| **+ what geometry it holds** | **15** | **61%** | **98%** |

**Ranking is not the mechanism; narrowing is** — and the last column is why. Once
the two facts a caller genuinely knows have cut the catalogue to something readable,
every survivor is handed over, so the right operation is in the answer for all 118
requests *by construction*. That is not an accuracy figure. Ranking decides the
order; it does not decide membership.

Three more numbers say why the answer is a set rather than a pick:

| | |
|---|---|
| the ranker puts the answer in the top three | 61% |
| a model handed the same candidates and asked to **choose** | **69%** |
| the two labellers who wrote the ground truth agreeing **with each other** | **70%** |

All three over the same 118 requests, which is not a detail: agreement over all 155 in the file
is 68%, and the gap is the pairs where both labellers agreed a request was unanswerable.

The last is a ceiling, not a baseline. Where two competent labellers disagree a third
of the time about which operation answers a request, "the right one" is not a single
value to rank toward — so a discovery layer built to this specification should return
the surviving set with the text that separates its members, and say that the order is
a hint. Two GIS analysts with thirty years each do the same job with different tools
and neither is wrong.

So the specification is mostly about what an entry *declares*, and only then about
how it is written.

## 1. Facets — the fields a filter reads

These are machine-read and exact. A wrong value here does not degrade a result, it
**removes the operation from the caller's world**, and nothing raises.

The two live under `applicability`, which is one object so that "what can this be
pointed at" stays one question.

### `applicability.inputs` — what it can be pointed at

`vector`, `raster`, `dataset` (either), `plan`, or `none`.

`none` is not an empty list. It means the operation takes no dataset at all — a
question about a coordinate system, a distance between two coordinates — and an
entry declaring it is kept for *every* input kind. An empty list would read as
"applies to nothing" and drop it from every result, which is the opposite of true.

### `applicability.requires_projected_crs` — whether it refuses degrees

True only when the engine actually refuses. **Verify it by executing**, not by
reading the code: reading ours once reported five operations as refusing because
the word "geographic" appeared in a warning rather than in a `raise`.

### `applicability.dataset_inputs` — how many datasets are in hand

`0`, `1` or `2`: the number of datasets the operation consumes. REQUIRED.

It is the facet that makes a catalogue keep working as it grows, and the
measurement that put it here is worth stating because it is the failure mode this
whole specification is about. On 2026-08-29 a catalogue went from 51 operations to
61 in an afternoon. The commonest surviving set — one vector layer in, one vector
layer out — went from 26 candidates to 34, past the point at which the whole set
can be handed to the caller, and the measured consequence over 118 independent
requests was that the right operation stopped being delivered 100% of the time
and fell to 45%, with found@3 down from 48% to 36%. **Adding capability had made
discovery worse, and nothing raised.**

Raising the hand-over threshold would have bought about ten more operations.
Declaring arity took the median surviving set from 34 to 9, measured at sixty-one
operations. What the same facet is worth today is the table above.

Two things make it the right *kind* of facet, and they are the two to look for
when a catalogue of your own outgrows its facets:

- **It is a fact about the caller's situation, not a label from your vocabulary.**
  Somebody with a parcels layer and a flood-zone layer knows they are holding two
  datasets. They do not know, and should not have to know, that you filed
  `clip_layer` under `vector` and `zonal_statistics` under `raster`.
- **It is derivable from the operation's own signature**, so the declaration can
  be checked against the code rather than trusted. Declare it and test it; do not
  compute it at search time from an engine registry, because the catalogue is the
  reachability layer and has to be readable on its own.

> **Normative.** An implementation MUST declare `dataset_inputs` on every entry
> and SHOULD verify it against the operation's signature in CI. A wrong value is
> the worst kind of wrong: the operation becomes invisible to every caller who
> describes their situation correctly, and no error is raised anywhere.

### `produces` — what the caller gets back

`dataset:vector`, `dataset:raster`, `answer`, `description`, `plan_result`.

Worth 20 points of *in what comes back* on top of the input kind (36% to 54%, table above), and it is a facet the caller
always knows: they know whether they want a file, a number, or an account of
something they already have. Check it against what the code actually writes — a
declaration that disagrees makes the operation unreachable for the caller who
filters correctly.

### `category` — the family, and the one facet that MUST NOT filter

Measured the single most informative facet — and that is exactly why it is
dangerous. It is the only one the caller cannot read off their own situation: input
kind and projected-CRS are facts about the data in hand, `produces` is what they
want back, but the family is a guess about *your* taxonomy, which they cannot see.

Measured on the same set: as a hard filter it removes five candidates out of
fifteen, and when the guess is wrong it removes **the right operation**, with no
error, leaving a confident answer assembled from neighbours. Every request in the
set has 4.4 plausible families. At 800 operations the guess is among 43.

> **Normative.** An implementation MUST NOT use `category` to exclude candidates from
> a search a caller did not explicitly scope. It SHOULD use it to order them, so that
> a declared family comes first and a wrong guess costs positions rather than the
> answer. A hard cut MAY be offered as a separate, explicit operation.

This is a correction to an earlier version of this document, which called the family
the strongest facet and left it at that. The strength was real and the failure mode
was worse: a discovery layer that silently deletes the answer is the defect this
project exists to measure in other systems.

Keep the vocabulary small and stable; a family with one member in it is an ordering
nobody will guess.

## 2. Text — the fields a ranker reads

Both ranking engines index the same document, so this text is the corpus, not
documentation that happens to be nearby.

### `summary` and `description`

Write the description for an agent deciding whether to call it: what it needs, what
it refuses, and **what goes wrong silently if it is used for the wrong thing**. The
last part is the one that helps most, because it is the part no other entry says.

### `phrasings` — how a caller names the problem

Never a synonym of the operation's name. `"too many vertices"`, not `"simplify"`. A
synonym of the name only helps somebody who already knows the name, which is
somebody who does not need to search.

**Honest measurement**: adding these moved found@3 from 40% to 100% on the queries
they were written against, and from 10/20 to 10/20 on queries written afterwards.
The effect on unseen phrasing is not measurable. The field stays because it costs
nothing and because writing it forces the author to ask how somebody would look for
this — not because it fixed retrieval. **It is in this specification as a
requirement with a null result attached, which is the honest way to keep a field.**

### `distinguishes` — what it is NOT

The recommended field, and the one that matters most in a crowded catalogue.

After the facets, about twenty operations of the same family remain, and inside
that residue ranking is close to random: asked *"which vineyards sit under the
proposed reservoir footprint"*, the ranker returned `centroid_layer`, `buffer_layer`
and `hull_layer`, and the answer was `overlay_layers`. Every one of those takes a
layer and returns a layer, so nothing in the shape of the entry separates them.

Contrastive text does. Write **"not X, which does Y"**, naming the neighbour:

> `centroid_layer` — collapses each feature to one point for a distance calculation.
> **Not for map labels**: the centroid of a concave shape falls outside it, and
> `point_on_surface` is the one that cannot.

**Measured, and the honest answer is that it does not help retrieval.** Written
for six entries after seeing which six failed, it took a twenty-query set from 14
correct to 17 and silent misses from one to zero. Written properly — thirty-two
entries, contrasting the neighbour rather than echoing a query — the same set comes
back **14 of 20, unchanged**. The first number was contamination.

It does move BM25, by a little: 10 of 20 found@3 to 12. That direction is the
diagnostic. Our embedding engine is a *static* model — a token table with pooling and
no context — so it behaves more like a smarter BM25 than like a transformer, and text
that is semantically right but lexically different is precisely what it cannot use.
Writing better prose will not fix that; a different class of model might, and that is
a decision with a cost rather than a field in a specification.

One caution learned here: naming the neighbour puts the neighbour's words in this
entry's document, so an entry becomes findable by its neighbour's query. Measured, the
net effect on BM25 was still positive — but write the contrast around what the
operation DOES differently, not around a list of names.

**So why is the field here at all.** Two reasons that are not retrieval:

1. **It is read at selection time, not at search time — and selection is where the
   accuracy is.** A model handed the surviving candidates and asked to choose gets
   its first pick right 69% of the time, against 61% for the ranker putting it in the
   top three. Entries that all say "one point per polygon" give it nothing to choose
   on. `distinguishes` is the only field written to be read *against its neighbours*,
   and that is the moment it pays. Measured against retrieval it is worth nothing;
   measured at the point of choice it is the field the choice is made on.
2. **Writing it catches catalogue defects.** Forcing an author to name the neighbour
   is what surfaced that `centroid_layer` was advertising `point_on_surface`'s job —
   and recommending a defect our own correctness suite measures as a trap.

It is `RECOMMENDED` and not required, and the null result stays in this document
rather than being quietly dropped. A specification that only reports the fields that
worked is an advertisement.

### `parameters`

Type, whether it is required, and a sentence each. **Where a wrong value fails
silently, say so in the parameter's own description** — that is where somebody
reads it at the moment they are choosing a value. A parameter with no safe default
should have no default at all, and the description is where the reason goes.

`planned` entries have none, and are not required to: an entry that does not run
yet cannot describe arguments it does not have. The schema requires the full
description only of `available`.

## 3. `examples` — the discoverability contract

At least two, and **the first is a test probe, not decoration**. The contract runs a
search with that goal and the entry's own facets. Write the *goal a caller has*, not
the invocation.

A catalogue-wide average will not do here: 90% found@3 over fifty entries means five
are unreachable and the average does not say which. The contract is per entry, so a
new operation is under it the moment it is added.

**What the contract requires is not a rank.** Two things: the facets an entry declares
must never drop that entry, and the entry must reach the caller. Rank inside the
delivered set is measured and reported; it does not fail a build.

> **Normative.** A conformance test for this specification MUST NOT gate on ranking
> position. The reason is mechanical, not philosophical: the only way to repair such a
> failure is to reword the entry until the ranker likes it, and a suite whose repair
> procedure is *fit the text to the scorer* manufactures the number it reports. Ours
> did — entries tuned that way scored nineteen points better on examples we wrote than
> on requests written by anyone else.

**It found a real defect on its first run.** `centroid_layer` advertised *"label
points for a polygon layer"* and ranked below `point_on_surface`. The ranking was
right — a centroid can fall outside its own polygon, which is a defect our own
correctness suite measures as a trap. Our catalogue was recommending it. Before
adjusting wording to make the contract pass, **check whether the ranking is right**:
an entry that loses to a neighbour may be advertising the neighbour's job.

## 4. Growth

An operation very close to an existing one competes with it forever, in every
future search. Before adding one, either distinguish them in text — by what they do
differently to the *number*, not to the prose — or ask whether it should be a
parameter of the existing operation instead.

## What this specification does not claim

It is measured on one catalogue, in one domain, against requests written by language
models rather than by the people who will make them. The mechanism generalises —
facets narrow, contrastive text separates neighbours, one probe per entry beats an
average — but the exact percentages are ours.

**Two limits stated rather than buried.**

The 70% ceiling was measured between two language models — 68% if the requests both of them
called unanswerable are counted in, which is the same figure over a larger population. Whether working GIS analysts
agree with each other more, less or about the same is unmeasured. Until people have
tried it, every number here is agreement with model-written labels and not accuracy,
and this document uses the word "agreement" deliberately.

And the narrowing does not yet scale on its own. At 800 operations the honest facets
leave hundreds of candidates — the 800 we tested against are all raster-in,
raster-out, so only the family cuts, and the family must not. What that catalogue
needs is more facts a caller can state without knowing the taxonomy: how many inputs
an operation takes, whether it changes geometry or only attributes, whether the output
has as many features as the input. Structural, checkable against the code. Not in this
version of the specification, because it is not built and not measured.

The measurements live in `tests/test_retrieval_degradation.py`,
`tests/test_retrieval_at_scale.py` and `tests/test_discovery_contract.py`, and they
run in CI, so the numbers above are checkable rather than remembered.
