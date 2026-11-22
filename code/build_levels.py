"""Build nested milestone levels for a module graph and save them as JSON.

Usage:
  python3 -I build_levels.py <graph.json> <root> <src_dir> <out.json> [--rule R]
                             [--no-statements] [k1 k2 ...]

--no-statements keeps the name of each milestone's last theorem but not its text.

Rules (see coarsen.py):
  plan      big cones with enough flow, few inputs per step (default, PlanCoarsening)
  relative  flow relative to the typical flow of the level
  absolute  plain flow

For every level the output has the milestones, their clusters and the edges
between milestones.  Levels are nested: a milestone of a finer level records
which milestone of every coarser level its cluster belongs to.
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coarsen import FlowCoarsening, PlanCoarsening, load  # noqa: E402

DECL = re.compile(
    r'^(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|nonrec)\s+)*'
    r'(theorem|lemma|def|abbrev|structure|class|instance|inductive)\s+([^\s:({\[]+)', re.M)


def key_statement(path):
    """Name, kind and statement text of the last theorem of a Lean file.

    Falls back to the last definition when the file has no theorem.
    """
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return None
    decls = list(DECL.finditer(text))
    if not decls:
        return None
    thms = [d for d in decls if d.group(1) in ('theorem', 'lemma')]
    d = (thms or decls)[-1]
    body = text[d.end():]
    cut = len(body)
    for stop in (':=', '\nwhere', ' where\n', '\n\n'):
        i = body.find(stop)
        if i != -1:
            cut = min(cut, i)
    statement = ' '.join(body[:cut].split())
    return {'kind': d.group(1), 'name': d.group(2), 'statement': statement[:1200],
            'truncated': len(statement) > 1200, 'declarations': len(decls)}


def main():
    rule = 'plan'
    args = sys.argv[1:]
    keep_text = '--no-statements' not in args
    args = [a for a in args if a != '--no-statements']
    if '--rule' in args:
        i = args.index('--rule')
        rule = args[i + 1]
        del args[i:i + 2]
    graph_path, root, src, out = args[:4]
    levels = [int(x) for x in args[4:]] or [20, 100, 1000]
    g = load(graph_path)
    if rule == 'plan':
        c = PlanCoarsening(g, root)
        c.select(max(levels))
    else:
        c = FlowCoarsening(g, root)
        c.select(max(levels), by=rule)
    info = g.get('info')
    users = collections.defaultdict(list)
    for n in c.rpo:
        for d in c.deps[n]:
            users[d].append(n)
    height = c.height
    rank = {m: i for i, m in enumerate(c.order)}

    clusters = {}
    result = {'root': root, 'total_weight': c.total, 'total_nodes': len(c.rpo),
              'ranking': rule, 'max_height': height[c.root],
              'levels': []}
    for k in levels:
        ms, own, edges, raw, cluster = c.level(k)
        clusters[k] = cluster
        stats = {m: {'modules': 0, 'thm': 0, 'def': 0, 'private': 0,
                     'dirs': collections.Counter()} for m in ms}
        for n in c.rpo:
            s = stats[cluster[n]]
            s['modules'] += 1
            if info:
                s['thm'] += info[n]['thm']
                s['def'] += info[n]['def']
            s['dirs']['.'.join(c.nodes[n].split('.')[:3])] += c.weight[n]
            if all(cluster[u] == cluster[n] for u in users[n]):
                s['private'] += c.weight[n]
        index = {m: i for i, m in enumerate(ms)}
        # own step of a milestone: the part of its cone that none of its inputs covers
        step, n_inputs = {}, {m: 0 for m in ms}
        for a, b in edges:
            n_inputs[a] += 1
        if rule == 'plan':
            covered = {m: 0 for m in ms}
            for a, b in edges:
                covered[a] |= c.reach[b]
            step = {m: (c.reach[m] & ~covered[m]).bit_count() / len(c.rpo) for m in ms}
        nodes = []
        for m in ms:
            s = stats[m]
            name = c.nodes[m]
            node = {
                'id': index[m],
                'module': name,
                'order': rank[m],
                # share of all work that passes through this statement
                'flow': round(c.flow[m] / c.total, 6),
                # flow divided by the typical flow of statements at the same height
                'score': round(c.score[m], 1),
                # share of all files this statement depends on
                'cone': round(c.cone[m] / len(c.rpo), 6),
                # share of the files below it whose work passes through it
                'through': round(c.unit_flow[m] / c.cone[m], 4),
                'users': c.users[m],
                'inputs': n_inputs[m],
                # share of all files in its own step (None for rules that do not build a plan)
                'step': round(step[m], 6) if m in step else None,
                'weight': own[m],
                'modules': s['modules'],
                'theorems': s['thm'],
                'definitions': s['def'],
                # share of the cluster that nothing outside the cluster uses directly
                'private_share': round(s['private'] / max(1, own[m]), 3),
                'height': height[m],
                'dirs': [[d, round(w / max(1, own[m]), 3)] for d, w in s['dirs'].most_common(4)],
                'parents': {str(kk): clusters[kk][m] for kk in levels if kk < k},
            }
            if k <= 1000:
                node['key'] = key_statement(os.path.join(src, *name.split('.')) + '.lean')
                if node['key'] and not keep_text:
                    del node['key']['statement'], node['key']['truncated']
            nodes.append(node)
        # parents were stored as fine node ids; convert to module names
        for node in nodes:
            node['parents'] = {kk: c.nodes[v] for kk, v in node['parents'].items()}
        result['levels'].append({
            'k': len(ms),
            'nodes': nodes,
            'edges': [[index[a], index[b]] for a, b in edges],
            'edges_before_reduction': raw,
        })
        hs = sorted(height[m] for m in ms)
        print(f'level {len(ms)}: {len(edges)} edges, heights {hs[0]}..{hs[-1]}, '
              f'smallest flow {100 * min(c.flow[m] for m in ms) / c.total:.2f}%')
    with open(out, 'w') as fh:
        json.dump(result, fh)
    print('wrote', out)


if __name__ == '__main__':
    main()
