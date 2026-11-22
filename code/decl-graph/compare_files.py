"""How far is the file import graph from the real dependencies between files?

Usage (from the repository root, after code/build.sh has written build/modules.json):

    python3 -I code/decl-graph/compare_files.py data/decl_graph/rh_decls.npz build/modules.json

A file "really" depends on another when one of its declarations uses a
declaration of the other. The import graph is what the earlier maps were built
on. The two are compared on the files present in both (the declaration graph
comes from the original publication, the import graph from a later commit with
unused files removed).
"""
import json
import sys

import numpy as np


def reach_counts(deps, order_hint=None):
    """Size of the cone of every node of a DAG given as dict node -> iterable of deps."""
    nodes = list(deps)
    index = {n: i for i, n in enumerate(nodes)}
    state, post = {}, []
    for s in nodes:
        if s in state:
            continue
        state[s] = 1
        stack = [(s, iter(deps[s]))]
        while stack:
            v, it = stack[-1]
            for w in it:
                if w not in state:
                    state[w] = 1
                    stack.append((w, iter(deps[w])))
                    break
            else:
                stack.pop()
                post.append(v)
    users = {n: 0 for n in nodes}
    for n in nodes:
        for d in deps[n]:
            users[d] += 1
    reach, out = {}, {}
    for v in post:
        b = 1 << index[v]
        for d in deps[v]:
            b |= reach[d]
            users[d] -= 1
            if users[d] == 0:
                del reach[d]
        reach[v] = b
        out[v] = b.bit_count()
    return out


def main():
    npz, modules_json = sys.argv[1], sys.argv[2]
    z = np.load(npz)
    mods = [str(m) for m in z['modules']]
    module, indptr, indices = z['module'], z['indptr'], z['indices']
    src = np.repeat(np.arange(len(module)), np.diff(indptr))
    a, b = module[src], module[indices]
    keep = a != b
    real = set(zip(a[keep].tolist(), b[keep].tolist()))
    real = {(mods[x], mods[y]) for x, y in real}

    g = json.load(open(modules_json))
    names = g['nodes']
    imports = {(names[i], names[d]) for i, ds in enumerate(g['deps']) for d in ds}
    common = set(names) & set(mods)
    imports_c = {e for e in imports if e[0] in common and e[1] in common}
    real_c = {e for e in real if e[0] in common and e[1] in common}
    print(f'files: {len(names)} in the import graph, {len(mods)} in the compiled proof, {len(common)} in both')
    print(f'import edges between common files: {len(imports_c)}')
    print(f'real dependency edges between common files: {len(real_c)}')
    used = imports_c & real_c
    print(f'imports that carry a real dependency: {len(used)} ({100 * len(used) / len(imports_c):.1f}%)')
    print(f'imports with no direct use: {len(imports_c - real_c)} ({100 * len(imports_c - real_c) / len(imports_c):.1f}%)')
    print(f'real dependencies that are not a direct import (reached through other imports): '
          f'{len(real_c - imports_c)} ({100 * len(real_c - imports_c) / len(real_c):.1f}%)')

    # cones: transitive imports versus transitive real dependencies
    imp = {n: [] for n in common}
    for x, y in imports_c:
        imp[x].append(y)
    rl = {n: [] for n in common}
    for x, y in real_c:
        rl[x].append(y)
    ci, cr = reach_counts(imp), reach_counts(rl)
    ratio = sorted(cr[n] / ci[n] for n in common if ci[n] >= 100)
    q = lambda p: ratio[int(p * (len(ratio) - 1))]
    print(f'cone by real dependencies / cone by imports, for files with an import cone of 100+ files: '
          f'median {q(0.5):.2f}, 10th percentile {q(0.1):.2f}, 90th percentile {q(0.9):.2f}')
    if 'Main' in common:
        print(f'Main: {ci["Main"]} files by imports, {cr["Main"]} by real dependencies')


if __name__ == '__main__':
    main()
