# rh-milestones

A map of the Lean proof of the Riemann Hypothesis, coarsened to 20, 100 and 1000
milestones.

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

- Source used here: [leanprover-community/riemann-hypothesis](https://github.com/leanprover-community/riemann-hypothesis)
  at commit [`7cce738`](https://github.com/leanprover-community/riemann-hypothesis/tree/7cce738ba719a32964ca3822d0994f4c6952c7ae).
  This is the community mirror set up to verify the submission. By that commit some
  unused files had already been removed from the original 175,187.
- Announcement note: <https://alpo.ge/remark.pdf>
- Frozen copy of the source as published: [homeowmorphism/riemann-hypothesis-original](https://github.com/homeowmorphism/riemann-hypothesis-original)
- Status of the verification:
  [statement of the Lean and Mathlib communities](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/)
  and [Andrew Sutherland's verification record](https://math.mit.edu/~drew/grh/)

The proof was published without a licence. This repository therefore contains none
of its Lean text: only the names of its files and declarations, graph data derived
from its import structure, and generated descriptions. Each milestone links to its
file in the source repository.

## What the map shows

Each node is a milestone: one file of the proof, named after the last theorem in it.
An arrow A → B means A is used in the proof of B. The final theorem is at the bottom.

There are three nested levels. The 20 milestones of the coarsest level also appear
among the 100, and those among the 1000. On the finer levels a box is a coarse
milestone and the nodes inside it are its parts.

Click a node to see:

- **Description** — what the statement says in plain English, its role, a confidence
  level, caveats, and whether it looks new or known from the literature;
- **Numbers** — how much of the proof it depends on, how much is left to do once its
  inputs are available, how much work flows through it;
- **Lean** — the name of the declaration and a link to its file in the source;
- **Links** — what it depends on and what uses it.

| Level | Links | Largest step | Most inputs of one milestone |
|---:|---:|---:|---:|
| 20 | 24 | 14.0% of the proof | 3 |
| 100 | 163 | 4.5% | 12 |
| 1000 | 3039 | 0.7% | 34 |

All milestones of the 20 and 100 levels have descriptions. On the 100 level the
generated marks are: 64 probably new, 11 known, 16 probably known, 9 unclear. The
generated confidence levels are: 13 high, 61 medium, 26 low.

## How milestones are chosen

Short version; the details and the comparison with other rules are in
[METHOD.md](METHOD.md).

- The **cone** of a statement is everything it depends on.
- **Flow**: every file is a source of work, measured in lines. Work flows up along
  dependencies to the final theorem and is split equally between the users of a
  file. The flow through a statement is the work that passes through it.
- A milestone needs its **inputs** (the milestones directly below it) plus its own
  **step**: the part of its cone that no input covers.

The plan is refined where it is coarsest. The milestone with the largest step gets a
new input: a statement inside that step with a large cone and a large flow for its
level. When a milestone would need more than seven inputs, a statement that groups
several of them is added first.

## Known limitations

- **The graph is the import graph of files**, not the graph of which declaration
  uses which. An import can be wider than actual use.
- **A node is named after the last theorem of its file.** Often that is a
  restatement, or not the theorem the file is named after. A few files have no
  theorem at all. The descriptions say so where it was noticed.
- **File and declaration names in the proof are often misleading.** The descriptions
  unfold the project's own definitions two or three levels deep and stop there.
- **Many statements are conditional** on large bundles of hypotheses named after
  published theorems. The descriptions summarize such bundles from field names.
- **The "new / known" marks are a model's guess** from the Lean source and from
  naming inside the proof. No literature search was done.
- **Work is measured in lines**, and flow is split equally between users. Both are
  crude.
- **The rule has hand-picked parameters**, chosen on this proof and on one smaller
  project.
- **On the 1000 level seven milestones still have more than seven inputs.**

## Files

- [`docs/`](docs/) — the three pages of the map: [`index.html`](docs/index.html)
  (the chosen rule), [`relative.html`](docs/relative.html) and
  [`absolute.html`](docs/absolute.html) (two simpler rankings, for comparison). Each
  page is a single self-contained file.
- [`data/levels_plan.json`](data/levels_plan.json) and the two other `levels_*.json`
  — milestones, numbers and links of every level.
- [`data/descriptions/descriptions.json`](data/descriptions/descriptions.json) — the
  119 generated descriptions, keyed by module name.
- [`code/`](code/) — the scripts that build all of the above.
- [`METHOD.md`](METHOD.md) — the method, the rules that were compared, and the checks.

## Rebuilding

You need Python 3, [Graphviz](https://graphviz.org/) and a checkout of the source
proof at the commit above (1.9 GB). Building takes about five minutes and 4 GB of
memory.

```bash
sh code/build.sh /path/to/riemann-hypothesis
```

The descriptions are not regenerated by the build. They were written by helper
instances of the model, each reading about ten files and the definitions they use.

## What was used

- [Claude Fable 5.2](https://www.anthropic.com/claude) in
  [Claude Code](https://claude.com/claude-code) — all code and all text.
- [Lean 4](https://lean-lang.org/) v4.33.1 and
  [Mathlib](https://github.com/leanprover-community/mathlib4) — to export the
  declaration graph of Mathlib for the checks in [METHOD.md](METHOD.md).
- [Graphviz](https://graphviz.org/) — layout of the diagrams.
- [PFR](https://github.com/teorth/pfr), the formalization of the polynomial
  Freiman–Ruzsa conjecture with its
  [Lean blueprint](https://github.com/PatrickMassot/leanblueprint) — a human-written
  plan used as a reference point when comparing rules.

## Licence

The code, the graph data and the generated descriptions in this repository are under
the [MIT licence](LICENSE). The source proof is not part of this repository and was
published by its author without a licence.
