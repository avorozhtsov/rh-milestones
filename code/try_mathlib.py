"""Coarsen the proofs of a few well-known Mathlib theorems and print the milestones.

Usage: python3 -I try_mathlib.py <decls.tsv> <modules.json> [--k K] [--absolute | --relative] [target ...]

This is the sanity check for the coarsening method: for these theorems the
textbook proof plan is known, so the printed milestones can be judged by eye.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coarsen import FlowCoarsening, PlanCoarsening  # noqa: E402
from decl_graph import DeclGraph, ModuleShare  # noqa: E402

DEFAULT = [
    'Nat.Prime.sq_add_sq',                      # Fermat: p = a^2 + b^2 for p % 4 = 1
    'legendreSym.quadratic_reciprocity',        # quadratic reciprocity
    'Nat.sum_four_squares',                     # Lagrange four squares
    'Nat.exists_prime_lt_and_le_two_mul',       # Bertrand's postulate
    'Complex.exists_root',                      # fundamental theorem of algebra
]


def opt(name, default):
    if name in sys.argv:
        return int(sys.argv[sys.argv.index(name) + 1])
    return default


def main():
    k = opt('--k', 10)
    args = [a for a in sys.argv[1:] if not a.startswith('--') and a != str(k)]
    g = DeclGraph(args[0])
    share = ModuleShare(args[1])
    for target in args[2:] or DEFAULT:
        if target not in g.index:
            print(f'\n### {target}: not found')
            continue
        cone = g.cone(target, is_library=share.library_test(g, target))
        root = g.names[g.owner[g.index[target]]]
        if '--absolute' in sys.argv or '--relative' in sys.argv:
            c = FlowCoarsening(cone, root)
            c.select(min(k, len(c.rpo)), by='absolute' if '--absolute' in sys.argv else 'relative')
        else:
            c = PlanCoarsening(cone, root)
            c.select(min(k, len(c.rpo)))
        ms, own, edges, raw, _ = c.level(len(c.order))
        print(f'\n### {target}: {len(c.rpo)} declarations in the cone, {len(ms)} milestones, {len(edges)} edges')
        idx = {m: i for i, m in enumerate(ms)}
        for m in ms:
            info = cone['info'][m]
            needs = ', '.join(str(idx[b]) for a, b in edges if a == m)
            print(f'  {idx[m]:2d}. [cone {100 * c.cone[m] / len(c.rpo):5.1f}% flow {100 * c.flow[m] / c.total:5.1f}%] {info["kind"]:4s} {c.nodes[m]}'
                  + (f'   <- {needs}' if needs else ''))


if __name__ == '__main__':
    main()
