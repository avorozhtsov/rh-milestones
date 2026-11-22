"""Score the coarsening against a human-written Lean Blueprint.

Usage:
  python3 -I eval_blueprint.py <decls.tsv> <blueprint/src> <main label> <module prefix> [-v]

The human plan is the set of blueprint statements that the main theorem
depends on.  A statement counts as found when one of its Lean declarations
is among the chosen milestones.  Every method chooses as many milestones as
there are statements that could be found (K), so precision and recall are
close to each other; both are printed.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blueprint  # noqa: E402
from coarsen import Coarsening  # noqa: E402
from decl_graph import DeclGraph  # noqa: E402


def descendants(deps, n):
    """Number of nodes in the cone of every node (bitsets)."""
    order, state = [], [0] * n
    for s in range(n):
        if state[s]:
            continue
        state[s] = 1
        stack = [(s, iter(deps[s]))]
        while stack:
            v, it = stack[-1]
            for w in it:
                if not state[w]:
                    state[w] = 1
                    stack.append((w, iter(deps[w])))
                    break
            else:
                stack.pop()
                order.append(v)
    reach = [0] * n
    for v in order:
        b = 1 << v
        for d in deps[v]:
            b |= reach[d]
        reach[v] = b
    return [bin(b).count('1') for b in reach]


def main():
    verbose = '-v' in sys.argv
    tsv, src, label, prefix = [a for a in sys.argv[1:] if a != '-v'][:4]
    g = DeclGraph(tsv)
    bp = blueprint.parse(src)
    plan = blueprint.cone(bp, label)
    target = bp[label]['lean'][0]
    cone = g.cone(target, is_library=lambda i: not g.mods[i].startswith(prefix))
    where = cone['index_of']
    n = len(cone['nodes'])
    root = where[target]

    # blueprint statements of the plan that have a declaration inside the cone
    stmt_nodes = {}
    for lab in plan:
        ids = {where[d] for d in bp[lab]['lean'] if d in where}
        if ids:
            stmt_nodes[lab] = ids
    plan_ids = set().union(*stmt_nodes.values())
    any_bp_ids = {where[d] for b in bp.values() for d in b['lean'] if d in where}
    K = len(stmt_nodes)
    outside = sorted(lab for lab in plan if lab not in stmt_nodes)
    print(f'project cone of {target}: {n} declarations, {sum(map(len, cone["deps"]))} edges')
    print(f'human plan: {len(plan)} statements; {K} have a declaration in the cone '
          f'({len(plan_ids)} declarations); {len(outside)} point outside the project or have no \\lean')

    def score(chosen):
        chosen = set(chosen)
        found = sum(1 for ids in stmt_nodes.values() if ids & chosen)
        return found / K, len(chosen & plan_ids) / len(chosen), len(chosen & any_bp_ids) / len(chosen)

    users = [0] * n
    for i in range(n):
        for d in cone['deps'][i]:
            users[d] += 1
    desc = descendants(cone['deps'], n)
    rows = []

    def coarsen(tree, weight):
        gr = dict(cone, weight=weight)
        c = Coarsening(gr, cone['nodes'][root], tree)
        return c.select(K), c

    ones = [1] * n
    vsize = [1 + i['vsize'] for i in cone['info']]
    best = None
    for name, tree, w in (('nearest-user tree, weight 1', 'near', ones),
                          ('nearest-user tree, weight = proof size', 'near', vsize),
                          ('dominator tree, weight 1', 'dom', ones),
                          ('dominator tree, weight = proof size', 'dom', vsize)):
        chosen, c = coarsen(tree, w)
        rows.append((name, score(chosen), len(chosen)))
        if best is None:
            best = chosen
    rng = random.Random(0)
    rand = [score(rng.sample(range(n), K)) for _ in range(200)]
    rows.append(('random declarations (mean of 200)', tuple(sum(x) / len(rand) for x in zip(*rand)), K))
    rows.append(('most used inside the cone', score(sorted(range(n), key=lambda i: -users[i])[:K]), K))
    rows.append(('largest own cone', score(sorted(range(n), key=lambda i: -desc[i])[:K]), K))
    rows.append(('largest proof', score(sorted(range(n), key=lambda i: -vsize[i])[:K]), K))
    thm = [i for i in range(n) if cone['info'][i]['kind'] == 'thm']
    rows.append(('theorems with largest own cone', score(sorted(thm, key=lambda i: -desc[i])[:K]), K))

    # nearest-user tree, but milestones are simply the heaviest subtrees
    cn = Coarsening(dict(cone, weight=vsize), cone['nodes'][root], 'near')
    rows.append(('heaviest subtrees (nearest-user tree)',
                 score(sorted(cn.rpo, key=lambda i: -cn.W[i])[:K]), K))

    # how good are the first few milestones of each ordering?
    orders = {
        'nearest-user tree, weight = proof size': coarsen('near', vsize)[0],
        'dominator tree, weight = proof size': coarsen('dom', vsize)[0],
        'largest own cone': sorted(range(n), key=lambda i: -desc[i]),
        'largest proof': sorted(range(n), key=lambda i: -vsize[i]),
    }
    ks = [k for k in (5, 10, 20, 40) if k < K]
    print('\nshare of the first k milestones that are statements of the plan')
    print(f'{"method":42s} ' + ' '.join(f'k={k:<4d}' for k in ks))
    for name, order in orders.items():
        print(f'{name:42s} ' + ' '.join(
            f'{100 * len(set(order[:k]) & plan_ids) / k:5.0f}%' for k in ks))
    print(f'{"random":42s} ' + ' '.join(f'{100 * len(plan_ids) / n:5.0f}%' for _ in ks))

    print(f'\nK = {K} milestones per method')
    print(f'{"method":42s} {"recall":>7s} {"precision":>10s} {"in any bp":>10s} {"chosen":>7s}')
    for name, (r, p, a), k in rows:
        print(f'{name:42s} {100 * r:6.1f}% {100 * p:9.1f}% {100 * a:9.1f}% {k:7d}')

    if verbose:
        chosen = set(best)
        print('\nplan statements missed by the first method:')
        for lab, ids in sorted(stmt_nodes.items()):
            if not ids & chosen:
                print(f'  {bp[lab]["kind"]:11s} {lab:26s} {", ".join(bp[lab]["lean"])[:70]}')
        print('\nmilestones that are not in the plan:')
        for i in best:
            if i not in plan_ids:
                tag = 'other blueprint statement' if i in any_bp_ids else ''
                print(f'  {cone["info"][i]["kind"]:4s} {cone["nodes"][i][:70]:70s} {tag}')


if __name__ == '__main__':
    main()
