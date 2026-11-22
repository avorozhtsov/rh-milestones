# Method

How the proof was coarsened, which rules were compared, and what was checked.
Everything below was worked out and run by an AI model in one session. The numbers
are measurements; the choice of rule is a judgement.

## The graph

The graph is the import graph of the proof: 164,282 files, 700,597 import edges, and
a longest import chain of 201. The files are small (median 60 lines, about five
theorems each), so the file graph is close to a graph of statements.

The weight of a file is its number of non-blank lines.

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
- The graph has not been rebuilt at the level of declarations.
- The rule has been compared with a human plan on one project only.
