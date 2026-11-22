"""Declaration-level dependency graph exported from Lean (see mathlib-graph/).

Usage:
  python3 -I decl_graph.py <decls.tsv> <target declaration> <out.json> [--max-users N]

Writes the cone of the target in the common graph format used by coarsen.py.

Two clean-ups are applied to the raw export:

* Auxiliary constants that Lean generates (`_proof_1`, `match_1`, recursors,
  constructors, equation lemmas) are folded into the declaration they belong to.
* The cone stops at "library" declarations.  Without this cut the cone of
  every theorem runs down to the foundations and is dominated by
  general-purpose material that says nothing about this proof.  Two rules are
  available:
    - by modules (ModuleShare, the default in try_mathlib.py): a module is
      library when a much larger part of Mathlib imports it than imports the
      module of the target theorem;
    - by users (--max-users N): a declaration is library when more than N
      declarations use it directly.  This rule works worse.
"""
import os
import pickle
import re
import sys
from array import array

AUX_LAST = re.compile(
    r'^(rec|recOn|casesOn|noConfusion|noConfusionType|below|brecOn|binductionOn|ibelow|'
    r'injEq|inj|sizeOf_spec|eq_def|congr_simp|ctorIdx|ctorElim|ctorElimType|toCtorIdx|ofNat|'
    r'eq_\d+|match_\d+|proof_\d+|_.*)$')


def load_raw(tsv):
    cache = tsv + '.pickle'
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(tsv):
        with open(cache, 'rb') as fh:
            return pickle.load(fh)
    names, kinds, mods, internal, tdeps, vdeps = [], [], [], [], [], []
    ids = {}
    with open(tsv, encoding='utf-8') as fh:
        for line in fh:
            p = line.rstrip('\n').split('\t')
            if len(p) < 7:
                continue
            ids[int(p[0])] = len(names)
            names.append(p[1]); kinds.append(p[2]); mods.append(p[3]); internal.append(p[4] == '1')
            tdeps.append(array('i', map(int, p[5].split())) if p[5] else array('i'))
            vdeps.append(array('i', map(int, p[6].split())) if p[6] else array('i'))
    # ids in the file are positions in Lean's table; remap to positions here
    remap = lambda a: array('i', (ids[x] for x in a if x in ids))
    tdeps = [remap(a) for a in tdeps]
    vdeps = [remap(a) for a in vdeps]
    raw = (names, kinds, mods, internal, tdeps, vdeps)
    with open(cache, 'wb') as fh:
        pickle.dump(raw, fh, protocol=5)
    return raw


def strongly_connected(nodes, succ):
    """Tarjan's algorithm, iterative.  Returns a list of components (lists)."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = 0
    for s in nodes:
        if s in index:
            continue
        work = [(s, iter(succ(s)))]
        index[s] = low[s] = counter
        counter += 1
        stack.append(s)
        on.add(s)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(succ(w))))
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    out.append(comp)
    return out


class DeclGraph:
    def __init__(self, tsv):
        names, kinds, mods, internal, tdeps, vdeps = load_raw(tsv)
        self.names, self.kinds, self.mods = names, kinds, mods
        index = {n: i for i, n in enumerate(names)}
        self.index = index
        n = len(names)
        # owner[i]: the user-visible declaration that constant i belongs to
        owner = list(range(n))
        for i, name in enumerate(names):
            parts = name.split('.')
            aux = internal[i] or kinds[i] in ('ctor', 'rec') or AUX_LAST.match(parts[-1])
            if not aux:
                continue
            # `_private.<module>.0.<name>` is the private spelling of <name>
            public = parts[parts.index('0') + 1:] if parts[0] == '_private' and '0' in parts else None
            for cut in range(len(parts) - 1, 0, -1):
                j = index.get('.'.join(parts[:cut]))
                if j is None and public and cut > len(parts) - len(public):
                    j = index.get('.'.join(public[:cut - (len(parts) - len(public))]))
                if j is not None and not internal[j]:
                    owner[i] = j
                    break
        # resolve chains
        for i in range(n):
            j = owner[i]
            while owner[j] != j:
                j = owner[j]
            owner[i] = j
        self.owner = owner
        self.orphan_aux = [internal[i] and owner[i] == i for i in range(n)]
        deps = [set() for _ in range(n)]      # all dependencies, folded
        sdeps = [set() for _ in range(n)]     # dependencies of the statement only
        for i in range(n):
            o = owner[i]
            for d in tdeps[i]:
                if owner[d] != o:
                    deps[o].add(owner[d])
                    if i == o:
                        sdeps[o].add(owner[d])
            for d in vdeps[i]:
                if owner[d] != o:
                    deps[o].add(owner[d])
        self.deps, self.sdeps = deps, sdeps
        self.vsize = [0] * n                  # distinct constants in the proof or body
        for i in range(n):
            self.vsize[owner[i]] += len(vdeps[i])
        self.size = [0] * n                   # number of raw constants folded in
        for i in range(n):
            self.size[owner[i]] += 1
        users = [0] * n
        for i in range(n):
            for d in deps[i]:
                users[d] += 1
        self.users = users

    def cone(self, target, max_users=None, is_library=None):
        """Cone of `target`, cut at library declarations (see module docstring)."""
        root = self.owner[self.index[target]]
        if is_library is None:
            is_library = lambda i: (not self.mods[i].startswith('Mathlib')) or self.users[i] > max_users
        seen = {root}
        stack = [root]
        while stack:
            i = stack.pop()
            for d in self.deps[i]:
                if d not in seen and not is_library(d):
                    seen.add(d)
                    stack.append(d)
        # Folding auxiliary constants can create small dependency cycles
        # (mutually defined declarations).  Merge every cycle into one node.
        comp = strongly_connected(sorted(seen), lambda i: [d for d in self.deps[i] if d in seen])
        rep = {}
        for members in comp:
            r = root if root in members else min(members, key=lambda i: (len(self.names[i]), i))
            for i in members:
                rep[i] = r
        order = sorted(set(rep.values()))
        pos = {i: k for k, i in enumerate(order)}
        deps = {i: set() for i in order}
        weight = {i: 0 for i in order}
        for i in seen:
            weight[rep[i]] += 1
            for d in self.deps[i]:
                if d in seen and rep[d] != rep[i]:
                    deps[rep[i]].add(rep[d])
        return {
            'nodes': [self.names[i] for i in order],
            'deps': [sorted(pos[d] for d in deps[i]) for i in order],
            'weight': [weight[i] for i in order],
            # every declaration of the cone -> the node it ended up in
            'index_of': {self.names[i]: pos[rep[i]] for i in seen},
            'info': [{'kind': self.kinds[i], 'module': self.mods[i], 'users': self.users[i],
                      'vsize': self.vsize[i],
                      'thm': int(self.kinds[i] == 'thm'), 'def': int(self.kinds[i] != 'thm')}
                     for i in order],
        }


class ModuleShare:
    """For every module, the share of all modules that import it (transitively)."""

    def __init__(self, module_graph_json):
        import json
        with open(module_graph_json) as fh:
            mg = json.load(fh)
        names, deps = mg['nodes'], mg['deps']
        n = len(names)
        users = [[] for _ in range(n)]
        for i in range(n):
            for d in deps[i]:
                users[d].append(i)
        order, state = [], [0] * n          # post-order over "is imported by"
        for s in range(n):
            if state[s]:
                continue
            state[s] = 1
            stack = [(s, iter(users[s]))]
            while stack:
                v, it = stack[-1]
                for w in it:
                    if not state[w]:
                        state[w] = 1
                        stack.append((w, iter(users[w])))
                        break
                else:
                    stack.pop()
                    order.append(v)
        importers = [0] * n                  # bitsets
        for v in order:
            b = 0
            for u in users[v]:
                b |= importers[u] | (1 << u)
            importers[v] = b
        self.share = {names[i]: bin(importers[i]).count('1') / n for i in range(n)}

    def library_test(self, graph, target, margin=0.01):
        """A declaration is library when its module is imported by a clearly
        larger share of the project than the module of the target: by more
        than `margin` (1 percentage point of all modules by default)."""
        own = self.share.get(graph.mods[graph.owner[graph.index[target]]], 0.0)
        return lambda i: self.share.get(graph.mods[i], 1.0) > own + margin


def main():
    import json
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    max_users = 30
    if '--max-users' in sys.argv:
        max_users = int(sys.argv[sys.argv.index('--max-users') + 1])
        args = [a for a in args if a != str(max_users)]
    tsv, target, out = args[:3]
    g = DeclGraph(tsv)
    cone = g.cone(target, max_users)
    with open(out, 'w') as fh:
        json.dump(cone, fh)
    print(f'{target}: cone of {len(cone["nodes"])} declarations, '
          f'{sum(map(len, cone["deps"]))} edges (library cut at {max_users} users) -> {out}')


if __name__ == '__main__':
    main()
