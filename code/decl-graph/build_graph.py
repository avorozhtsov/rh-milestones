"""Build the declaration dependency graph of the proof from the exported parts.

Usage (from this folder):

    python3 -I build_graph.py [out_prefix]

Reads out/part_*.tsv (written by run_export.py) and writes

    <prefix>.npz        nodes and edges as arrays (see below)
    <prefix>_names.txt  one declaration name per line, in node order

Nodes are user-visible declarations. Auxiliary constants that Lean generates
(`_proof_1`, `match_1`, recursors, constructors, equation lemmas) are folded
into the declaration they belong to. Lean creates some of them later, in another
file (equation lemmas, simp lemmas); those only redirect their users to the
declaration and contribute no dependencies of their own, otherwise a declaration
would seem to depend on files that come after it. Declarations that still form
a dependency cycle (mutual definitions) are merged into one node. Dependencies
on anything outside the proof (Lean core, Mathlib) are dropped.

Arrays in the .npz file:
    indptr, indices  CSR adjacency: deps of node i are indices[indptr[i]:indptr[i+1]]
    kind             0 theorem, 1 definition, 2 inductive type or structure, 3 other
    module           index into `modules` of the file the declaration is in
    size             number of distinct constants its proof or body refers to (all, incl. Mathlib)
    folded           number of raw constants folded into the node
    modules          module names
"""
import glob
import os
import re
import sys
from array import array

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AUX_LAST = re.compile(
    r'^(rec|recOn|casesOn|noConfusion|noConfusionType|below|brecOn|binductionOn|ibelow|'
    r'injEq|inj|sizeOf_spec|eq_def|congr_simp|ctorIdx|ctorElim|ctorElimType|toCtorIdx|'
    r'eq_\d+|match_\d+|proof_\d+|_.*)$')
KIND = {'thm': 0, 'def': 1, 'ind': 2}


def strongly_connected(n, deps):
    """Tarjan's algorithm, iterative. Returns the components with more than one node."""
    index = [-1] * n
    low = [0] * n
    on = [False] * n
    stack, out, counter = [], [], 0
    for s in range(n):
        if index[s] != -1:
            continue
        index[s] = low[s] = counter
        counter += 1
        stack.append(s)
        on[s] = True
        work = [(s, iter(deps[s]))]
        while work:
            v, it = work[-1]
            for w in it:
                if index[w] == -1:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on[w] = True
                    work.append((w, iter(deps[w])))
                    break
                if on[w] and index[w] < low[v]:
                    low[v] = index[w]
            else:
                work.pop()
                if work and low[v] < low[work[-1][0]]:
                    low[work[-1][0]] = low[v]
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on[w] = False
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1:
                        out.append(comp)
    return out


def parts():
    files = sorted(glob.glob(os.path.join(HERE, 'out', 'part_*.tsv')))
    if not files:
        sys.exit('no exported parts in out/')
    return files


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'rh_decls')
    files = parts()

    # Pass 1: every constant of the proof.
    ident = {}                    # name hash -> raw id
    names, kinds, internal, module_of = [], [], [], array('i')
    modules, module_index = [], {}
    for f in files:
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                mod, h, name, kind, inter, _ = line.split('\t', 5)
                h = int(h)
                if h in ident:
                    continue      # the same constant exported twice; keep the first
                ident[h] = len(names)
                names.append(name)
                kinds.append(kind)
                internal.append(inter == '1')
                if mod not in module_index:
                    module_index[mod] = len(modules)
                    modules.append(mod)
                module_of.append(module_index[mod])
        print(f'pass 1: {os.path.basename(f)}  {len(names)} constants', flush=True)
    n_raw = len(names)

    # Owner of every constant: the user-visible declaration it belongs to.
    by_name = {name: i for i, name in enumerate(names)}
    owner = list(range(n_raw))
    for i, name in enumerate(names):
        p = name.split('.')
        if not (internal[i] or kinds[i] in ('ctor', 'rec') or AUX_LAST.match(p[-1])):
            continue
        public = p[p.index('0') + 1:] if p[0] == '_private' and '0' in p else None
        for cut in range(len(p) - 1, 0, -1):
            j = by_name.get('.'.join(p[:cut]))
            if j is None and public and cut > len(p) - len(public):
                j = by_name.get('.'.join(public[:cut - (len(p) - len(public))]))
            if j is not None and not internal[j]:
                owner[i] = j
                break
    for i in range(n_raw):
        j = owner[i]
        while owner[j] != j:
            j = owner[j]
        owner[i] = j
    kept = [i for i in range(n_raw) if owner[i] == i]
    node_of = {raw: k for k, raw in enumerate(kept)}
    n = len(kept)
    print(f'{n_raw} constants -> {n} declarations after folding', flush=True)

    # Pass 2: dependencies, folded onto owners.
    deps = [set() for _ in range(n)]
    size = np.zeros(n, dtype=np.int32)
    folded = np.zeros(n, dtype=np.int32)
    seen = set()
    for f in files:
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                _, h, _, _, _, tdeps, vdeps = line.rstrip('\n').split('\t')
                raw = ident[int(h)]
                if raw in seen:
                    continue
                seen.add(raw)
                me = node_of[owner[raw]]
                folded[me] += 1
                if module_of[raw] != module_of[owner[raw]]:
                    continue      # auxiliary constant created later, in another file
                vd = vdeps.split()
                size[me] += len(vd)
                mine = deps[me]
                for token in tdeps.split() + vd:
                    d = ident.get(int(token))
                    if d is not None:
                        d = node_of[owner[d]]
                        if d != me:
                            mine.add(d)
        print(f'pass 2: {os.path.basename(f)}', flush=True)

    # Merge dependency cycles (mutual definitions) into single nodes.
    comp = strongly_connected(n, deps)
    merged = 0
    for members in comp:
        if len(members) < 2:
            continue
        merged += len(members) - 1
        rep_node = min(members)
        union = set()
        for m in members:
            union |= deps[m]
            folded[rep_node] += folded[m] if m != rep_node else 0
            size[rep_node] += size[m] if m != rep_node else 0
        members_set = set(members)
        deps[rep_node] = union - members_set
        for m in members:
            if m != rep_node:
                deps[m] = {rep_node}          # kept as a thin alias of the merged node
    print(f'{merged} declarations merged into cycles', flush=True)

    indptr = np.zeros(n + 1, dtype=np.int64)
    for i in range(n):
        indptr[i + 1] = indptr[i] + len(deps[i])
    indices = np.empty(int(indptr[-1]), dtype=np.int32)
    for i in range(n):
        if deps[i]:
            indices[indptr[i]:indptr[i + 1]] = sorted(deps[i])
        deps[i] = None
    kind = np.array([KIND.get(kinds[raw], 3) for raw in kept], dtype=np.int8)
    module = np.array([module_of[raw] for raw in kept], dtype=np.int32)
    np.savez_compressed(prefix + '.npz', indptr=indptr, indices=indices, kind=kind, module=module,
                        size=size, folded=folded, modules=np.array(modules))
    with open(prefix + '_names.txt', 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(names[raw] for raw in kept) + '\n')
    print(f'{n} declarations, {len(indices)} dependencies -> {prefix}.npz', flush=True)


if __name__ == '__main__':
    main()
