# rh-milestones

A map of the Lean proof of the Riemann Hypothesis that Levent Alpöge published on
20 November 2026 at [alpo.ge](https://alpo.ge/) (announcement note:
[remark.pdf](https://alpo.ge/remark.pdf)), coarsened to 20, 100 and 1000 milestones.
There are two versions of the map: one built on files, one on individual theorems.
The proof is not ours; only the maps are.

**View the map: <https://avorozhtsov.github.io/rh-milestones/>**

## Read this first

- This is an attempt to coarsen an existing, machine-written Lean proof into a small
  graph of milestones. Nothing more.
- It does not check the proof, does not explain the mathematics, and makes no claim
  about whether the proof is correct. For that, see the links under
  [The proof](#the-proof).
- Everything here was produced with an AI model, Claude Fable 5.2, in one working
  session: the code, the choice of the coarsening rule, the plain-English
  descriptions of the milestones, the "new / known" marks, and this README.
- The descriptions and marks are generated text. Nobody has checked them against the
  mathematics or the literature. Some are wrong. Do not quote them as facts.
- It is not a big deal. It is a navigation aid for a proof that is too large to read:
  164,282 files and about 16.5 million lines.

## The proof

The map is built from the Lean 4 formalization announced on 2026-11-20 by Levent
Alpöge, which claims a proof of the Riemann Hypothesis and of the generalized
Riemann Hypothesis for Dirichlet L-functions.

- Source used here: [leanprover-community/riemann-hypothesis](https://github.com/leanprover-community/riemann-hypothesis),
  the community mirror set up to verify the submission. The file map uses commit
  [`7cce738`](https://github.com/leanprover-community/riemann-hypothesis/tree/7cce738ba719a32964ca3822d0994f4c6952c7ae),
  by which some unused files had been removed from the original 175,187. The
  declaration map uses commit
  [`e50d098`](https://github.com/leanprover-community/riemann-hypothesis/tree/e50d09817ad81469f737e8f637561e6ccf86c670),
  the proof as published plus one added file.
- Announcement note: <https://alpo.ge/remark.pdf>
- Frozen copy of the source as published: [homeowmorphism/riemann-hypothesis-original](https://github.com/homeowmorphism/riemann-hypothesis-original)
- Status of the verification:
  [statement of the Lean and Mathlib communities](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/)
  and [Andrew Sutherland's verification record](https://math.mit.edu/~drew/grh/)

The proof was published without a licence. This repository therefore contains none
of its Lean text: only the names of its files and declarations, graph data derived
from its import structure, and generated descriptions.

### Reading the source

Every milestone has two links to its Lean file, both fixed to the exact commit its
map was built from, so later changes to the source do not affect them:

- in the source repository on GitHub;
- in the [Software Heritage archive](https://archive.softwareheritage.org/browse/revision/7cce738ba719a32964ca3822d0994f4c6952c7ae/?path=src),
  an independent archive of source code. Use it if the GitHub link stops working.

To browse the files locally, check out the same commit (1.9 GB):

```bash
git clone https://github.com/leanprover-community/riemann-hypothesis.git
cd riemann-hypothesis
git checkout 7cce738ba719a32964ca3822d0994f4c6952c7ae
```

A module `A.B.C` shown on the map is the file `src/A/B/C.lean`.

The source repository records the archive the author published: `lean.tar.gz`,
239,275,554 bytes, sha256
`9631b4f020199e580ba86178cb56c6e9b09f690c2369a80dc4334aa93f49c7fc`. Its first commit,
`40e56bab`, is that archive unchanged; see its
[verification notes](https://github.com/leanprover-community/riemann-hypothesis/blob/7cce738ba719a32964ca3822d0994f4c6952c7ae/verification/NOTES.md).

## What the map shows

Each node is a milestone of the proof. An arrow A → B means A is used in the proof
of B. The final theorem is at the bottom.

There are two maps, and the page header switches between them:

- **Files** — the first map. A node is one file of the proof, named after the last
  theorem in it. The graph is the import graph of the files.
- **Declarations** — the second map. A node is one theorem or definition. The graph
  is the graph of which declaration uses which, read from the compiled proof.

A file is a unit of compilation, not of meaning, and its imports turn out to be
about twice as wide as what it really uses (see [METHOD.md](METHOD.md)). The
declaration map rests on real dependencies. The file map is kept because it came
first, has more descriptions, and the two have not been shown to differ in quality.

Each map has three nested levels. The 20 milestones of the coarsest level also
appear among the 100, and those among the 1000. On the finer levels a box is a
coarse milestone and the nodes inside it are its parts.

Click a node to see:

- **Description** — what the statement says in plain English, its role, a confidence
  level, caveats, and whether it looks new or known from the literature;
- **Numbers** — how much of the proof it depends on, how much is left to do once its
  inputs are available, how much work flows through it;
- **Lean** — the name of the declaration and links to its file in the source;
- **Links** — what it depends on and what uses it.

| Level | Built on | Links | Largest step | Most inputs of one milestone |
|---:|---|---:|---:|---:|
| 20 | files | 24 | 14.0% of the proof | 3 |
| 20 | declarations | 21 | 10.4% | 3 |
| 100 | files | 163 | 4.5% | 12 |
| 100 | declarations | 124 | 3.2% | 6 |
| 1000 | files | 3039 | 0.7% | 34 |
| 1000 | declarations | 2432 | 0.5% | 26 |

The two maps choose rather different milestones: the files that contain the
declaration milestones coincide with the file milestones in 6 cases out of 20, 15
out of 100 and 202 out of 1000.

Descriptions:

- **File map:** every milestone of the 20 and 100 levels has one. On the 100 level
  the generated marks are 64 probably new, 11 known, 16 probably known, 9 unclear;
  the generated confidence levels are 13 high, 61 medium, 26 low.
- **Declaration map:** every milestone of the 20 level has one (18 probably new,
  2 probably known; confidence 3 high, 9 medium, 8 low), and 28 of the 100.

## How milestones are chosen

Short version; the details and the comparison with other rules are in
[METHOD.md](METHOD.md).

- The **cone** of a statement is everything it depends on.
- **Flow**: every statement is a source of work. For a file the work is its number
  of lines; for a declaration it is the number of constants its proof refers to.
  Work flows up along dependencies to the final theorem and is split equally between
  the users of a statement. The flow through a statement is the work that passes
  through it.
- A milestone needs its **inputs** (the milestones directly below it) plus its own
  **step**: the part of its cone that no input covers.

The plan is refined where it is coarsest. The milestone with the largest step gets a
new input: a statement inside that step with a large cone and a large flow for its
level. When a milestone would need more than seven inputs, a statement that groups
several of them is added first.

## Known limitations

Both maps:

- **File and declaration names in the proof are often misleading.** The descriptions
  unfold the project's own definitions two or three levels deep and stop there.
- **Many statements are conditional** on large bundles of hypotheses named after
  published theorems. The descriptions summarize such bundles from field names.
- **The "new / known" marks are a model's guess** from the Lean source and from
  naming inside the proof. No literature search was done.
- **Flow is split equally between users**, and work is measured crudely.
- **The rule has hand-picked parameters**, chosen on this proof and on one smaller
  project.

The file map:

- **The graph is the import graph of files.** For a typical file the import cone is
  twice as large as what the file really depends on.
- **A node is named after the last theorem of its file.** Often that is a
  restatement, or not the theorem the file is named after. A few files have no
  theorem at all. The descriptions say so where it was noticed.
- **On the 1000 level seven milestones still have more than seven inputs.**

The declaration map:

- **Sizes are estimated on a random sample** of 65,536 declarations, because exact
  cones for a million declarations do not fit in memory. On the file graph, where
  both can be computed, the sampled result matched the exact one for the first 20
  milestones and for 79 of the first 100.
- **The compiled proof was taken from the mirror's build cache** and was not
  compiled or checked here; only the checksums of the archives were verified.
- **It describes a slightly different version of the proof**: the files as
  published (commit `e50d098`), while the file map uses a later commit from which
  unused files had been removed.
- **On the 1000 level 40 milestones have more than seven inputs.**

## Files

- [`docs/`](docs/) — the pages of the map, each a single self-contained file:
  [`index.html`](docs/index.html) (files, the chosen rule),
  [`declarations.html`](docs/declarations.html) (declarations, the chosen rule),
  [`relative.html`](docs/relative.html) and [`absolute.html`](docs/absolute.html)
  (files, two simpler rankings, for comparison).
- [`data/levels_plan.json`](data/levels_plan.json),
  [`data/levels_declarations.json`](data/levels_declarations.json) and the two other
  `levels_*.json` — milestones, numbers and links of every level.
- [`data/decl_graph/`](data/decl_graph/) — the declaration graph itself: 1,173,961
  declarations and 15.2 million dependencies, as numpy arrays plus a list of names.
  It holds names and dependencies only, no Lean text.
- [`data/descriptions/descriptions.json`](data/descriptions/descriptions.json) — the
  130 generated descriptions, keyed by module name (file map) or declaration name
  (declaration map).
- [`code/`](code/) — the scripts that build the levels and the pages;
  [`code/decl-graph/`](code/decl-graph/) — the scripts that produced the declaration
  graph from the build cache.
- [`METHOD.md`](METHOD.md) — the method, the rules that were compared, the two
  graphs, and the checks.

## Rebuilding

You need Python 3 with numpy, [Graphviz](https://graphviz.org/) and a checkout of
the source proof (1.9 GB). Building the levels and pages takes about ten minutes and
6 GB of memory.

```bash
sh code/build.sh /path/to/riemann-hypothesis
```

The declaration graph is shipped in `data/decl_graph/`, so the build does not need
the compiled proof. To produce the graph again you need Lean (through
[elan](https://github.com/leanprover/elan)), about 25 GB of free disk and half an hour.
Run from `code/decl-graph/`:

```bash
python3 -I fetch_cache.py
```

```bash
RH_PROOF=/path/to/riemann-hypothesis python3 -I run_export.py
```

```bash
python3 -I build_graph.py ../../data/decl_graph/rh_decls
```

The descriptions are not regenerated by the build. They were written by helper
instances of the model, each reading about ten files and the definitions they use.

## What was used

- [Claude Fable 5.2](https://www.anthropic.com/claude) in
  [Claude Code](https://claude.com/claude-code) — all code and all text.
- The [build cache of the proof](https://github.com/leanprover-community/riemann-hypothesis/blob/7cce738ba719a32964ca3822d0994f4c6952c7ae/verification/CACHE.md)
  published by the community mirror — the compiled modules the declaration graph
  was read from.
- [Lean 4](https://lean-lang.org/) v4.33.1 — to read the compiled modules; and
  [Mathlib](https://github.com/leanprover-community/mathlib4) — its declaration
  graph was used for the checks in [METHOD.md](METHOD.md).
- [Graphviz](https://graphviz.org/) — layout of the diagrams.
- [PFR](https://github.com/teorth/pfr), the formalization of the polynomial
  Freiman–Ruzsa conjecture with its
  [Lean blueprint](https://github.com/PatrickMassot/leanblueprint) — a human-written
  plan used as a reference point when comparing rules.

## Licence

The code, the graph data and the generated descriptions in this repository are under
the [MIT licence](LICENSE). The source proof is not part of this repository and was
published by its author without a licence.
