"""Coarsen a proof dependency DAG into a small graph of milestones.

The input graph has an edge  a -> d  when a depends on d (a uses d).
The root is the final theorem; everything it reaches is its "cone".

Two rules are implemented.  `FlowCoarsening` (work flow relative to the level
of a statement) is the current one.  `Coarsening` (balanced split of a tree) is
the earlier rule and is kept for comparison.

Balanced split
--------------
1. Dominator tree of the cone.  d dominates n when every dependency path from
   the root down to n passes through d.  So the dominator subtree of d is the
   work that exists only for the sake of d.  This generalises "fold hanging
   trees into the vertex they hang from": a hanging tree is a dominated
   subtree, but so is any sub-DAG with internal sharing.
2. Milestones are chosen greedily.  The milestones chosen so far cut the
   dominator tree into clusters.  Take the heaviest cluster and split it at the
   node that divides its weight most evenly.  The order of selection gives
   nested levels: the first 20 milestones are a subset of the first 100, etc.
3. The coarse graph on a set of milestones has an edge  m1 -> m2  when m1
   reaches m2 by a path that passes through no other milestone.  Then
   transitively redundant edges are removed.
"""
import heapq
import json
import os
import sys


def load(path):
    """Load a graph: the JSON format of extract_lean_modules.py, or the .npz
    declaration graph written by decl-graph/build_graph.py."""
    if path.endswith('.npz'):
        return load_declarations(path)
    with open(path) as fh:
        return json.load(fh)


ROOT = 'Main'            # name of the added root node of a declaration graph


def load_declarations(path, root_module='Main'):
    """Declaration graph as a graph dict.  A root node is added that depends on
    every theorem of `root_module` (the final theorems of the proof)."""
    import numpy as np
    z = np.load(path)
    names_path = path[:-4] + '_names.txt'
    if os.path.exists(names_path):
        with open(names_path, encoding='utf-8') as fh:
            names = fh.read().split('\n')[:-1]
    else:
        import gzip
        with gzip.open(names_path + '.gz', 'rt', encoding='utf-8') as fh:
            names = fh.read().split('\n')[:-1]
    indptr, indices = z['indptr'].tolist(), z['indices'].tolist()
    modules = [str(m) for m in z['modules']]
    module, kind, size = z['module'].tolist(), z['kind'].tolist(), z['size'].tolist()
    n = len(names)
    deps = [indices[indptr[i]:indptr[i + 1]] for i in range(n)]
    root_mod = modules.index(root_module)
    deps.append([i for i in range(n) if module[i] == root_mod and kind[i] == 0])
    label = ('thm', 'def', 'ind', 'other')
    info = [{'thm': int(kind[i] == 0), 'def': int(kind[i] != 0), 'kind': label[kind[i]],
             'module': modules[module[i]]} for i in range(n)]
    info.append({'thm': 0, 'def': 0, 'kind': 'thm', 'module': root_module})
    return {'nodes': names + [ROOT], 'deps': deps, 'weight': [1 + x for x in size] + [0],
            'info': info, 'declarations': True}


def rpo_from(deps, root):
    """Reverse postorder of the cone of `root`.  A node precedes its deps."""
    seen = {root}
    post = []
    stack = [(root, iter(deps[root]))]
    while stack:
        n, it = stack[-1]
        for d in it:
            if d not in seen:
                seen.add(d)
                stack.append((d, iter(deps[d])))
                break
        else:
            stack.pop()
            post.append(n)
    return post[::-1]


def dominators(deps, rpo):
    """Immediate dominators (Cooper-Harvey-Kennedy).  idom[root] == root."""
    pos = {n: i for i, n in enumerate(rpo)}
    users = {n: [] for n in rpo}
    for n in rpo:
        for d in deps[n]:
            users[d].append(n)
    root = rpo[0]
    idom = {root: root}

    def intersect(a, b):
        while a != b:
            while pos[a] > pos[b]:
                a = idom[a]
            while pos[b] > pos[a]:
                b = idom[b]
        return a

    changed = True
    while changed:
        changed = False
        for n in rpo[1:]:
            new = None
            for u in users[n]:
                if u in idom:
                    new = u if new is None else intersect(new, u)
            if idom.get(n) != new:
                idom[n] = new
                changed = True
    return idom


def nearest_user_tree(deps, rpo):
    """Spanning tree of the cone: each node hangs from its nearest user.

    The nearest user is the one with the smallest height (longest dependency
    chain below it), i.e. the most specific statement that needs the node.
    This tree refines the dominator tree: a dominated subtree stays together,
    and a lemma shared by several users is attributed to the first place that
    needed it instead of floating up to their common dominator.
    """
    height = {}
    for n in reversed(rpo):
        height[n] = 1 + max((height[d] for d in deps[n]), default=0)
    pos = {n: i for i, n in enumerate(rpo)}
    parent = {rpo[0]: rpo[0]}
    best = {}
    for n in rpo:
        key = (height[n], -pos[n])
        for d in deps[n]:
            if d not in best or key < best[d]:
                best[d] = key
                parent[d] = n
    return parent


def milestone_edges(rpo, deps, ms):
    """Edges between milestones: m1 -> m2 when m1 reaches m2 by a dependency
    path that crosses no other milestone.  Transitively redundant edges are
    removed.  Returns (edges, number of edges before the reduction)."""
    bit = {m: 1 << i for i, m in enumerate(ms)}
    frontier = {}
    for n in reversed(rpo):
        f = 0
        for d in deps[n]:
            f |= bit[d] if d in bit else frontier[d]
        frontier[n] = f
    pos = {n: i for i, n in enumerate(rpo)}
    reach, edges, raw = {}, [], 0
    for m in sorted(ms, key=lambda x: -pos[x]):      # dependencies first
        direct = frontier[m]
        raw += bin(direct).count('1')
        below = 0
        for i, c in enumerate(ms):
            if direct >> i & 1:
                below |= reach[c]
        reach[m] = direct | below
        kept = direct & ~below
        edges += [(m, c) for i, c in enumerate(ms) if kept >> i & 1]
    return edges, raw


def level_quantile(rpo, height, value, window, q=0.5):
    """q-quantile of `value` among statements of similar height, per height.

    The window of heights around h is widened until it holds `window` statements.
    """
    by_h = {}
    for n in rpo:
        by_h.setdefault(height[n], []).append(value[n])
    hs = sorted(by_h)
    out = {}
    for h in hs:
        lo = hi = h
        pool = list(by_h[h])
        while len(pool) < window and (lo > hs[0] or hi < hs[-1]):
            lo -= 1
            hi += 1
            pool = [f for x in range(lo, hi + 1) for f in by_h.get(x, ())]
        pool.sort()
        out[h] = pool[min(len(pool) - 1, int(q * len(pool)))]
    return out


def bits(mask):
    """Positions of the set bits of an int."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


class FlowCoarsening:
    """Milestones are the statements that an unusual amount of work flows through.

    Every statement is a source of work (its weight).  Work flows upwards along
    dependencies towards the final theorem; when a statement has several users
    its flow is split equally between them.  The flow through a statement is
    then the work that has to pass through it: all of it for a statement that
    cannot be bypassed, a fraction for a lemma that many others also use.

    Flow grows with the level of a statement (its height: the longest chain of
    dependencies below it), so it is compared with the typical flow at that
    level - the median over statements of similar height.  The score of a
    statement is its flow divided by that typical flow.  Milestones are taken
    in order of score, so the levels are nested.

    A statement and a wrapper around it carry the same stream.  Only one
    statement of a stream is taken.
    """

    def __init__(self, graph, root_name, window=None, same_stream=0.9, exact_cones=True):
        self.nodes = graph['nodes']
        self.deps = graph['deps']
        self.weight = graph['weight']
        self.root = self.nodes.index(root_name)
        self.rpo = rpo = rpo_from(self.deps, self.root)
        deps, weight = self.deps, self.weight
        if window is None:                    # statements needed to estimate a typical flow
            window = max(10, min(200, len(rpo) // 10))
        users = {n: 0 for n in rpo}
        for n in rpo:
            for d in deps[n]:
                users[d] += 1
        self.users = users
        self.flow, self.unit_flow, self.height = {}, {}, {}
        reach, pending, pos = {}, dict(users), {n: i for i, n in enumerate(rpo)}
        self.cone = {}                        # number of statements a statement depends on
        for n in reversed(rpo):               # dependencies first
            self.flow[n] = weight[n] + sum(self.flow[d] / users[d] for d in deps[n])
            self.unit_flow[n] = 1 + sum(self.unit_flow[d] / users[d] for d in deps[n])
            self.height[n] = 1 + max((self.height[d] for d in deps[n]), default=0)
            if not exact_cones:               # too large for exact cones; see PlanCoarsening
                continue
            b = 1 << pos[n]
            for d in deps[n]:
                b |= reach[d]
                pending[d] -= 1
                if pending[d] == 0:
                    del reach[d]              # keep memory bounded on large graphs
            reach[n] = b
            self.cone[n] = b.bit_count()
        self.total = self.flow[self.root]
        # typical flow at a height: median over a window of heights with enough statements
        self.window = window
        self.typical = level_quantile(rpo, self.height, self.flow, window, 0.5)
        self.score = {n: self.flow[n] / max(self.typical[self.height[n]], 1e-9) for n in rpo}
        # streams: an edge that carries almost all the flow of both its ends
        stream = {n: n for n in rpo}

        def find(x):
            while stream[x] != x:
                stream[x] = stream[stream[x]]
                x = stream[x]
            return x

        for n in rpo:
            for d in deps[n]:
                f = self.flow[d] / users[d]
                if f >= same_stream * self.flow[n] and f >= same_stream * self.flow[d]:
                    stream[find(d)] = find(n)
        self.stream = {n: find(n) for n in rpo}
        self.idom = nearest_user_tree(deps, rpo)      # used only to attribute work to milestones
        self.order, self.gain = [], {}

    def select(self, k, by='relative'):
        """by='relative': flow relative to the typical flow of the level;
        by='absolute': plain flow, i.e. the share of all work passing through."""
        key = self.score if by == 'relative' else self.flow
        self.order = [self.root]
        used = {self.stream[self.root]}
        for n in sorted(self.rpo, key=lambda x: -key[x]):
            if len(self.order) >= k:
                break
            if self.stream[n] in used:
                continue
            used.add(self.stream[n])
            self.order.append(n)
        self.gain = {n: self.flow[n] for n in self.order}
        return self.order

    def level(self, k):
        """Coarse graph on the first k milestones: same result shape as Coarsening.level."""
        ms = self.order[:k]
        chosen = set(ms)
        cluster, own = {}, {m: 0 for m in ms}
        for n in self.rpo:
            cluster[n] = n if n in chosen else cluster[self.idom[n]]
            own[cluster[n]] += self.weight[n]
        edges, raw = milestone_edges(self.rpo, self.deps, ms)
        return ms, own, edges, raw, cluster


class PlanCoarsening(FlowCoarsening):
    """Milestones form a plan: big cones, enough flow, few inputs per step.

    A milestone needs the milestones directly below it (its inputs) plus its
    own step: the part of its cone that no input covers.  The plan is refined
    where it is coarsest:

    1. Take the milestone with the largest step.
    2. Look at the statements inside that step whose cones cover the most of
       it: every statement that covers at least `near_best` of what the best
       one covers.  Among them add the one with the largest flow for its level
       (flow divided by the typical flow at its height).  So a milestone has a
       big cone and is also a place that the work has to pass through.
       Statements whose flow is below the `flow_quantile` quantile of their
       level are never eligible.  A statement covering more than
       1 - `skip_wrappers` of the step is a wrapper around the same work and
       is skipped.
    3. If a milestone has more than `max_inputs` inputs, first add a statement
       of its step that groups several of them.

    The order of selection gives nested levels.

    Large graphs.  Cones are kept as bitsets, which is exact but needs
    (statements x eligible statements) bits.  With `sample=N` the size of a
    cone or of a step is instead measured on a random sample of N statements,
    and only the `max_candidates` eligible statements with the largest flow for
    their level are kept as candidates.  Dependencies stay exact; only sizes are
    estimated.
    """

    def __init__(self, graph, root_name, flow_quantile=0.5, near_best=0.5, max_inputs=7,
                 skip_wrappers=0.1, sample=None, max_candidates=None, seed=0, **kw):
        super().__init__(graph, root_name, exact_cones=sample is None, **kw)
        self.max_inputs, self.skip, self.near_best = max_inputs, skip_wrappers, near_best
        rpo, deps = self.rpo, self.deps
        gate = level_quantile(rpo, self.height, self.flow, self.window, flow_quantile)
        eligible = [n for n in rpo if self.flow[n] >= gate[self.height[n]] and n != self.root]
        if max_candidates and len(eligible) > max_candidates:
            eligible = sorted(eligible, key=lambda n: -self.score[n])[:max_candidates]
        eligible.append(self.root)
        if sample is None:
            # exact: one bit per statement, used both to measure and to name candidates
            self.pos = {n: i for i, n in enumerate(rpo)}
            self.bitnode = rpo
            self.count_mask = -1
            own_bits = {n: 1 << i for i, n in enumerate(rpo)}
        else:
            # sampled: bits [0, sample) measure sizes, the bits after them name candidates
            import random
            sampled = random.Random(seed).sample(rpo, min(sample, len(rpo)))
            base = len(sampled)
            self.count_mask = (1 << base) - 1
            self.pos = {n: base + j for j, n in enumerate(eligible)}
            self.bitnode = [None] * base + eligible
            own_bits = {n: 1 << p for n, p in self.pos.items()}
            for i, n in enumerate(sampled):
                own_bits[n] = own_bits.get(n, 0) | 1 << i
        wanted = set(eligible)
        pending, reach, keep = dict(self.users), {}, {}
        for n in reversed(rpo):               # cones of the eligible statements, as bitsets
            b = own_bits.get(n, 0)
            for d in deps[n]:
                b |= reach[d]
                pending[d] -= 1
                if pending[d] == 0 and d not in wanted:
                    del reach[d]
            reach[n] = b
            if n in wanted:
                keep[n] = b
        self.reach = keep
        self.measure = (keep[self.root] & self.count_mask).bit_count()   # size of everything
        if sample is not None:
            scale = len(rpo) / self.measure
            self.cone = {n: (b & self.count_mask).bit_count() * scale for n, b in keep.items()}
        self.eligible = 0
        for n in eligible:
            self.eligible |= 1 << self.pos[n]

    def cone_share(self, m):
        """Share of all statements that m depends on (estimated when sampled)."""
        return (self.reach[m] & self.count_mask).bit_count() / self.measure

    def step_shares(self, ms, edges):
        """Share of all statements in the own step of every milestone."""
        covered = {m: 0 for m in ms}
        for a, b in edges:
            covered[a] |= self.reach[b]
        return {m: (self.reach[m] & ~covered[m] & self.count_mask).bit_count() / self.measure
                for m in ms}

    def select(self, k, by=None):
        rpo, reach, pos, stream = self.bitnode, self.reach, self.pos, self.stream
        cm = self.count_mask
        ms, index = [self.root], {self.root: 0}
        below = {self.root: 0}                # milestones inside the cone, as a bitset over `ms`
        placed = 1 << pos[self.root]
        used = {stream[self.root]}
        inputs_cache, step_cache = {}, {}
        dead, ungroupable = set(), set()

        def inputs(m):
            if m not in inputs_cache:
                inner = 0
                for i in bits(below[m]):
                    inner |= below[ms[i]]
                inputs_cache[m] = [ms[i] for i in bits(below[m] & ~inner)]
            return inputs_cache[m]

        def step(m):
            if m not in step_cache:
                mask = reach[m]
                for c in inputs(m):
                    mask &= ~reach[c]
                step_cache[m] = (mask, (mask & cm).bit_count())
            return step_cache[m]

        def add(v):
            nonlocal placed
            i = len(ms)
            bv = 0
            for u in ms:
                if reach[v] >> pos[u] & 1:
                    bv |= 1 << index[u]
            for u in ms:
                if reach[u] >> pos[v] & 1:
                    below[u] |= 1 << i
                    inputs_cache.pop(u, None)
                    step_cache.pop(u, None)
                    dead.discard(u)
                    ungroupable.discard(u)
            ms.append(v)
            index[v] = i
            below[v] = bv
            placed |= 1 << pos[v]
            used.add(stream[v])

        while len(ms) < k:
            crowded = [m for m in ms if m not in ungroupable and len(inputs(m)) > self.max_inputs]
            if crowded:
                m = max(crowded, key=lambda x: len(inputs(x)))
                ins = inputs(m)
                inmask = 0
                for c in ins:
                    inmask |= 1 << pos[c]
                best, best_key = None, None
                for p in bits(step(m)[0] & self.eligible & ~placed):
                    v = rpo[p]
                    if stream[v] in used:
                        continue
                    count = (reach[v] & inmask).bit_count()
                    if count < 2 or count >= len(ins):
                        continue
                    key = (min(count, self.max_inputs), -count, self.cone[v])
                    if best_key is None or key > best_key:
                        best, best_key = v, key
                if best is None:
                    ungroupable.add(m)
                else:
                    add(best)
                continue
            live = [m for m in ms if m not in dead]
            if not live:
                break
            m = max(live, key=lambda x: step(x)[1])
            mask, total = step(m)
            limit = (1 - self.skip) * total
            found, best_r = [], 1
            for p in bits(mask & self.eligible & ~placed):
                v = rpo[p]
                if stream[v] in used:
                    continue
                r = (reach[v] & mask & cm).bit_count()
                if 1 < r <= limit:
                    found.append((r, v))
                    best_r = max(best_r, r)
            if not found:
                dead.add(m)
            else:
                near = [v for r, v in found if r >= self.near_best * best_r]
                add(max(near, key=lambda v: self.score[v]))
        self.order = ms
        self.gain = {n: self.flow[n] for n in ms}
        return ms


class Coarsening:
    def __init__(self, graph, root_name, tree='near'):
        self.nodes = graph['nodes']
        self.deps = graph['deps']
        self.weight = graph['weight']
        self.root = self.nodes.index(root_name)
        self.rpo = rpo_from(self.deps, self.root)
        if tree == 'dom':
            self.idom = dominators(self.deps, self.rpo)
        else:
            self.idom = nearest_user_tree(self.deps, self.rpo)
        self.children = {n: [] for n in self.rpo}
        for n in self.rpo[1:]:
            self.children[self.idom[n]].append(n)
        # W[n]: weight of the whole dominator subtree of n
        self.W = {n: self.weight[n] for n in self.rpo}
        for n in reversed(self.rpo[1:]):
            self.W[self.idom[n]] += self.W[n]
        self.total = self.W[self.root]
        self.order = []      # milestones in order of selection
        self.gain = {}       # weight a milestone took over when selected
        self.parent = {}     # the milestone whose cluster it was split from

    def _best_split(self, m, R, chosen):
        """Node inside the cluster of m that splits its weight most evenly."""
        T = R[m]
        u = m
        while True:
            best_c, best_r = None, 0
            for c in self.children[u]:
                if c not in chosen and R[c] > best_r:
                    best_c, best_r = c, R[c]
            if best_c is None:
                break
            if best_r * 2 > T:
                u = best_c
                continue
            if u != m and T - R[u] >= best_r:
                return u, T - R[u]
            return best_c, best_r
        if u != m:
            return u, T - R[u]
        return None, 0

    def select(self, k):
        """Choose k milestones (the root is always the first)."""
        R = dict(self.W)     # remaining weight of each dominator subtree
        chosen = {self.root}
        self.order = [self.root]
        self.gain = {self.root: self.total}
        self.parent = {self.root: None}
        heap = [(-R[self.root], self.root)]
        while len(self.order) < k and heap:
            negr, m = heapq.heappop(heap)
            if -negr != R[m]:
                continue                      # stale entry
            v, _ = self._best_split(m, R, chosen)
            if v is None:
                continue                      # cluster cannot be split further
            g = R[v]
            a = self.idom[v]
            while True:
                R[a] -= g
                if a == m:
                    break
                a = self.idom[a]
            chosen.add(v)
            self.order.append(v)
            self.gain[v] = g
            self.parent[v] = m
            heapq.heappush(heap, (-R[m], m))
            heapq.heappush(heap, (-R[v], v))
        return self.order

    def level(self, k):
        """Coarse graph on the first k milestones.

        Returns (milestones, own_weight, edges) where edges are pairs
        (user, dependency) after transitive reduction.
        """
        ms = self.order[:k]
        bit = {m: 1 << i for i, m in enumerate(ms)}
        # cluster of each node: nearest chosen dominator
        cluster = {}
        own = {m: 0 for m in ms}
        for n in self.rpo:
            cluster[n] = n if n in bit else cluster[self.idom[n]]
            own[cluster[n]] += self.weight[n]
        edges, raw = milestone_edges(self.rpo, self.deps, ms)
        return ms, own, edges, raw, cluster

    def _pos(self, n):
        if not hasattr(self, '_posmap'):
            self._posmap = {n: i for i, n in enumerate(self.rpo)}
        return self._posmap[n]


def short(name, parts=2):
    return '.'.join(name.split('.')[-parts:])


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path, root = args[0], args[1]
    levels = [int(x) for x in args[2:]] or [20, 100, 1000]
    if '--split' in sys.argv or '--dom' in sys.argv:      # the earlier rule
        tree = 'dom' if '--dom' in sys.argv else 'near'
        c = Coarsening(load(path), root, tree)
        print(f'rule: balanced split, tree: {tree}')
    else:
        c = FlowCoarsening(load(path), root)
        print('rule: flow relative to level')
    print(f'cone: {len(c.rpo)} nodes, total weight {c.total}')
    c.select(max(levels))
    print(f'selected {len(c.order)} milestones')
    for k in levels:
        ms, own, edges, raw, _ = c.level(k)
        sizes = sorted(own.values(), reverse=True)
        print(f'\nlevel {k}: {len(ms)} milestones, {len(edges)} edges '
              f'(before transitive reduction {raw}); '
              f'largest cluster {100 * sizes[0] / c.total:.1f}% of weight, '
              f'median {100 * sizes[len(sizes) // 2] / c.total:.2f}%, '
              f'ideal {100 / len(ms):.2f}%')
    print('\nfirst 40 milestones (order, gain %, own % at level 40, name):')
    ms, own, _, _, _ = c.level(40)
    for i, m in enumerate(ms):
        print(f'{i:3d} {100 * c.gain[m] / c.total:6.2f} {100 * own[m] / c.total:6.2f}  '
              f'{c.nodes[m]}')


if __name__ == '__main__':
    main()
