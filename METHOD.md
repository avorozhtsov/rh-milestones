# Method

How the proof was coarsened, which rules were compared, and what was checked.
Everything below was worked out and run by an AI model in one session. The numbers
are measurements; the choice of rule is a judgement.

## The graph

The first graph is the import graph of the proof: 164,282 files, 700,597 import
edges, and a longest import chain of 201. The weight of a file is its number of
non-blank lines. Most of this document describes the maps built on that graph.

A second graph, of declarations, was built later; see
[Files or declarations](#files-or-declarations).

## Terms

- **Cone** of a statement: everything it depends on.
- **Level** of a statement: its height, the length of the longest chain of
  dependencies below it.
- **Flow**: every statement is a source of work equal to its weight. Work flows up
  along dependencies to the final theorem. When a statement has several users, its
  flow is split equally between them. The flow through a statement is the work that
  passes through it. A statement that cannot be bypassed carries all the work below
  it; a lemma that many others also use carries a fraction.
- **Inputs** of a milestone: the milestones directly below it.
- **Step** of a milestone: the part of its cone that none of its inputs covers. This
  is the work left to do once the inputs are available.

## The chosen rule: "plan"

The plan is refined where it is coarsest.

1. Take the milestone with the largest step.
2. Look at the statements inside that step whose cones cover the most of it: every
   statement that covers at least half of what the best one covers. Among them, add
   the one with the largest flow for its level (flow divided by the median flow of
   statements at a similar height).
3. Statements whose flow is below the median of their level are never eligible. A
   statement that covers more than 90% of the step is a wrapper around the same work
   and is skipped.
4. If a milestone has more than seven inputs, first add a statement of its step that
   groups several of them.

The order in which milestones are added gives nested levels. The final theorem is
always a milestone.

An edge A → B between milestones means that A reaches B by a dependency path that
passes through no other milestone. Edges implied by other edges are removed. The
result is always acyclic, and every edge stands for a real dependency.

Code: `PlanCoarsening` in [`code/coarsen.py`](code/coarsen.py).

## Rules that were compared

Four rules were run on the proof.

- **Largest cone**: rank statements by cone size.
- **Absolute flow**: rank by flow.
- **Flow relative to level**: rank by flow divided by the typical flow at that height.
- **Plan**: the rule above.

Measures:

- **Largest step**: share of the proof's files in the largest step. This is the
  hardest single transition of the plan, so smaller is better.
- **Inputs**: how many milestones a milestone needs directly. Three to seven reads
  well; twenty does not.
- **Lowest level**: how far down the proof the milestones reach.

| Rule | K | Largest step | Most inputs (milestones with more than 7) | Lowest level |
|---|---:|---:|---:|---:|
| Largest cone | 20 | 47.2% | 3 (0) | 128 |
| | 100 | 47.2% | 6 (0) | 122 |
| | 1000 | 25.1% | 22 (17) | 97 |
| Absolute flow | 20 | 47.2% | 4 (0) | 123 |
| | 100 | 33.0% | 6 (0) | 77 |
| | 1000 | 9.0% | 29 (19) | 27 |
| Flow relative to level | 20 | 22.7% | 3 (0) | 88 |
| | 100 | 19.8% | 14 (1) | 34 |
| | 1000 | 9.9% | 42 (50) | 1 |
| **Plan** | 20 | **14.0%** | 3 (0) | 95 |
| | 100 | **4.5%** | 12 (1) | 51 |
| | 1000 | **0.7%** | 34 (7) | 9 |

What the table shows:

- **Largest cone stays at the top of the proof.** Even 1000 milestones lie at levels
  97 and above, each with a cone of at least 16% of the files, and almost half of
  the proof remains a single step.
- **Absolute flow behaves the same way** on the 20 and 100 levels.
- **Flow relative to level spreads milestones over all levels**, but the steps stay
  large, and on the 1000 level 50 milestones have more than seven inputs.
- **Plan has the smallest steps on every level** and the fewest overloaded
  milestones on the 1000 level.

Variants of the flow threshold inside the plan rule were also tried. A strict
threshold (flow in the top 10% of its level) left 247 milestones with more than
seven inputs on the 1000 level. A median threshold with no use of flow in the choice
let statements with almost no flow into the top 20. Letting flow decide among
candidates with similar cones raised the median flow of a top-20 milestone from 2.3%
to 3.2% and reduced the largest step on the 100 level from 5.9% to 4.5%.

Earlier attempts, kept in the code for comparison: the dominator tree (it leaves
three flat clusters, the largest holding 37% of the weight, because tens of
thousands of files are used along two or more independent paths) and repeated
balanced splitting of a tree (even clusters, but evenness is not importance).

## Files or declarations

The maps above were first built on the import graph of files, because that graph can
be read off the source without compiling anything. A file is a unit of compilation,
not of meaning, so a second map was built on the graph of declarations: which
theorem or definition uses which. Both maps are kept. The page header switches
between them.

### Where the declaration graph comes from

From the compiled proof. The community mirror publishes a build cache: one archive
per file, 4.94 GB compressed and 99 GB unpacked. It does not fit on the disk used
here, so the modules were unpacked in batches; from every compiled module its
declarations and what they refer to were written out, and the batch was deleted.
Each compiled module is read on its own, without loading the rest of the proof.

The cache corresponds to commit `e50d098` of the mirror: the proof as its author
published it (175,187 files) plus one added file. It was not compiled or checked
here; the archives were verified against the mirror's list of checksums.

- 1,173,961 declarations after folding auxiliary constants into their owners:
  907,937 theorems, 257,476 definitions, 8,450 structures and inductive types.
- 15.2 million dependencies between them.
- The final theorems depend on 873,689 declarations, 74% of all. The other 26% are
  written in the files of the proof but take no part in the final derivation.
- The longest chain of dependencies is 159.

### How far imports are from real dependencies

Measured on the 164,100 files present in both graphs. A file really depends on
another when one of its declarations uses a declaration of the other.

| Measure | Value |
|---|---:|
| Imports between common files | 695,159 |
| Imports that carry a direct real dependency | 62.9% |
| Imports with no direct use | 37.1% |
| Real dependencies between files | 1,659,141 |
| Real dependencies that are not a direct import (reached through other imports) | 73.7% |
| Real cone of a file / its cone by imports, median | 0.51 |
| The same, 10th and 90th percentiles | 0.03 and 0.87 |

The import cone of a file is typically twice its real cone, and for a tenth of the
files more than thirty times. That matters for the map, because both the step and
the flow are computed from cones.

### Computing the levels on a million nodes

Exact cones (one bit per pair of declarations) do not fit in memory. Sizes of cones
and steps are therefore estimated on a random sample of 65,536 declarations, and the
candidates for milestones are the 120,000 declarations with the largest flow for
their level. Dependencies stay exact; only sizes are estimated. The weight of a
declaration is the number of distinct constants its proof or body refers to.

The sampled mode was checked on the file graph, where the exact computation is
available: the first 20 milestones were identical, and 79 of the first 100. So part
of the difference between the two maps on the finer levels is sampling noise.

### The two maps side by side

| Level | Built on | Links | Largest step | Most inputs | Milestones with more than 7 inputs |
|---:|---|---:|---:|---:|---:|
| 20 | files | 24 | 14.0% | 3 | 0 |
| 20 | declarations | 21 | 10.4% | 3 | 0 |
| 100 | files | 163 | 4.5% | 12 | 1 |
| 100 | declarations | 124 | 3.2% | 6 | 0 |
| 1000 | files | 3039 | 0.7% | 34 | 7 |
| 1000 | declarations | 2432 | 0.5% | 26 | 40 |

The step is a share of files in one case and a share of declarations in the other,
so the numbers are only roughly comparable.

- On the 20 and 100 levels the declaration map has smaller steps and fewer inputs
  per milestone.
- On the 1000 level it has more overloaded milestones: 40 against 7.
- The two sets of milestones differ a lot. The files that contain the declaration
  milestones coincide with the file milestones in 6 cases out of 20, 15 out of 100
  and 202 out of 1000.
- On the 1000 level the declaration milestones are 969 theorems, 17 definitions and
  14 structures.

These measures do not say which map is better: they are close, and there is no
reference to compare with. The case for the declaration map is not in the measures.
It is that the map rests on real dependencies and that its node is one specific
theorem, not "the last theorem of a file".

## Check on theorems with a known plan

The declaration graph of Mathlib was exported from Lean (771,133 constants;
auxiliary constants folded into their declaration). For five theorems whose proof
plan is well known, the result of the plan rule was judged by eye.

| Theorem | Declarations | Result |
|---|---:|---|
| Bertrand's postulate | 7 | Matches Erdős's plan: the case of large n, the main inequality, the bound on the central binomial coefficient. |
| Fundamental theorem of algebra | 8 | Matches: the chain through Liouville's theorem. |
| Lagrange's four squares | 15 | Matches: the prime case, solvability of a² + b² + 1 ≡ 0, sums of two squares modulo p. |
| Fermat's two squares | 118 | Matches at the top: "−1 is a square modulo p" and "ℤ[i] is Euclidean"; below that, internal lemmas. |
| Quadratic reciprocity | 380 | Does not match: cyclotomic-field infrastructure crowds out the Gauss sums. |

For Mathlib the cone of any theorem runs down to the foundations, so it was cut at
"library" modules: a module counts as library when a clearly larger share of Mathlib
imports it than imports the module of the theorem itself (by more than one
percentage point). That threshold was picked on these five examples. The Riemann
Hypothesis proof needs no such cut: everything outside Mathlib belongs to the proof.

## Reference: a human-written plan

This is a reference point, not the criterion. Human plans also reflect which
statements were already familiar from the literature.

The [PFR project](https://github.com/teorth/pfr) has a Lean blueprint written by its
authors. For five of its main theorems, each rule chose as many milestones as the
blueprint has statements for that theorem (68–97 out of 406–511 declarations).
Averages over the five theorems:

| Rule | First 5 in the blueprint | First 20 in the blueprint | Blueprint statements found |
|---|---:|---:|---:|
| Random declarations | 21% | 21% | 21% |
| Flow relative to level | 80% | 40% | 29% |
| Plan | 84% | 69% | 39% |
| Absolute flow | 88% | 65% | 47% |
| Largest cone | 84% | 76% | 54% |

The first 5–20 milestones of the plan rule agree with the authors' choice about as
often as those of the largest-cone rule. At fine detail (a fifth of all
declarations) the largest-cone rule is closer to the authors.

## Descriptions and marks

For every milestone of the 20 and 100 levels a helper instance of the model read the
file, took the last theorem in it, unfolded the project's own definitions two or
three levels deep, and wrote: a title, what the statement says, its role, a
confidence level, caveats, and a judgement of whether the statement is known from
the literature or new to this proof.

What the helpers reported, and what a reader should keep in mind:

- **Names are poor guides.** The last theorem of a file is often a restatement or
  not the theorem the file is named after. Three files on the 100 level have no
  theorem at all, so a definition was described instead.
- **Many statements are conditional** on bundles of 50–70 hypotheses named after
  published theorems. The bundles were summarized from field names.
- **Some "published" statements are proved inside the proof** rather than assumed.
  Those chains were not checked.
- **A few theorems take a literature hypothesis that their proof does not use.**
- **Low confidence (26 of 100)** means the statement is phrased in the proof's own
  machinery and could not be reduced to ordinary mathematics; the description then
  gives only its logical shape.
- **The "new / known" marks rest on the Lean source and on naming inside the
  proof.** No literature search was done.

## What has not been done

- Nobody has checked the descriptions.
- The claim behind the "largest step" measure, that a smaller step is easier to
  prove, has not been tested.
- The sampled computation for the declaration map has been run with one random seed.
- The rule has been compared with a human plan on one project only.
