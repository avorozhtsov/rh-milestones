"""Render nested milestone levels as one self-contained interactive HTML page.

Usage: python3 -I render_html.py <levels.json> <out.html> <title>
           [--descriptions <dir>] [--pages key=file,key=file,...]

--descriptions: folder with JSON files {module: {title, summary, role, ...}}
                holding plain-English descriptions of statements.
--pages:        pages built with each rule, for the switch in the header,
                e.g. plan=rh_milestones.html,absolute=rh_milestones_absolute.html
--source-url:   base URL of the Lean sources; a link to each file is shown.
--source-label: name of the source proof, shown on the page (with --source-home
                as its link).
--no-statements: do not embed the Lean text of the statements.

Layout is nested.  The coarsest level is laid out as a layered graph.  On a
finer level every coarse milestone becomes a box, and the finer milestones of
its cluster are laid out inside that box.  Edges that cross boxes are not drawn
as lines (the page shows them when a node is hovered or selected); the edges
between the boxes themselves carry that information at a glance.

Layout is computed by Graphviz (`unflatten` and `dot`); the page draws its own
SVG from the coordinates, so it needs no network access and no JS libraries.
"""
import json
import math
import os
import re
import subprocess
import sys

CARD_LARGE = (228, 86)
CARD_SMALL = (158, 42)
PAD = 14
HEADER = 22


def title_of(module):
    last = module.split('.')[-1]
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', ' ', last)


def wrap(text, width, lines):
    out, cur = [], ''
    for w in text.split():
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f'{cur} {w}'.strip()
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    out = [x for x in out if x]
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][:width - 1].rstrip() + '…'
    return [x if len(x) <= width else x[:width - 1] + '…' for x in out]


def run_dot(sizes, edges, dense, rankdir='TB'):
    """Layered layout.  sizes: {id: (w, h)} in px.  edges: (user, dependency).

    Returns (W, H, pos, paths) with pos[id] = centre and
    paths = [(user, dependency, [points], end_point)].
    """
    lines = ['digraph G {', f'rankdir={rankdir};',
             f'nodesep={0.08 if dense else 0.25}; ranksep={0.3 if dense else 0.6};',
             'node [shape=box, fixedsize=true, label=""];']
    for i, (w, h) in sizes.items():
        lines.append(f'n{i} [width={w / 72:.3f}, height={h / 72:.3f}];')
    for a, b in edges:          # a uses b: the dependency is drawn above its user
        lines.append(f'n{b} -> n{a};')
    lines.append('}')
    src = '\n'.join(lines)
    stag = subprocess.run(['unflatten', '-f', '-l', '3', '-c', '4'], input=src,
                          capture_output=True, text=True, timeout=600)
    if stag.returncode == 0 and stag.stdout.strip():
        src = stag.stdout
    res = subprocess.run(['dot', '-Tjson'], input=src, capture_output=True, text=True, timeout=1800)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[:2000])
    g = json.loads(res.stdout)
    x0, y0, x1, y1 = map(float, g['bb'].split(','))
    H = y1 - y0
    fx = lambda x: x - x0
    fy = lambda y: H - (y - y0)
    pos, gvid = {}, {}
    for o in g.get('objects', []):
        if 'pos' in o:
            x, y = map(float, o['pos'].split(','))
            nid = int(o['name'][1:])
            gvid[o['_gvid']] = nid
            pos[nid] = (fx(x), fy(y))
    paths = []
    for e in g.get('edges', []):
        pts = e['pos'].split(' ')
        end = None
        if pts[0].startswith('e,'):
            ex, ey = map(float, pts[0][2:].split(','))
            end = (fx(ex), fy(ey))
            pts = pts[1:]
        xy = [(fx(float(p.split(',')[0])), fy(float(p.split(',')[1]))) for p in pts]
        paths.append((gvid[e['head']], gvid[e['tail']], xy, end))
    return x1 - x0, H, pos, paths


def layout_box(sizes, edges, dense, rankdir='TB'):
    """Layout of the children of one box: connected part by dot, the rest in a grid."""
    linked = {x for e in edges for x in e}
    conn = {i: s for i, s in sizes.items() if i in linked}
    iso = [i for i in sizes if i not in linked]
    W = H = 0.0
    pos, paths = {}, []
    if conn:
        W, H, pos, paths = run_dot(conn, edges, dense, rankdir)
    if iso:
        gap = 6 if dense else 12
        cw = max(sizes[i][0] for i in iso) + gap
        ch = max(sizes[i][1] for i in iso) + gap
        area = len(iso) * cw * ch
        target = max(W, math.sqrt(area * 1.6))
        cols = max(1, min(len(iso), int(target // cw) or 1))
        top = H + (gap * 2 if conn else 0)
        for j, i in enumerate(iso):
            pos[i] = (cw * (j % cols) + cw / 2, top + ch * (j // cols) + ch / 2)
        rows = math.ceil(len(iso) / cols)
        W = max(W, cols * cw)
        H = top + rows * ch
    return W, H, pos, paths


def shift(paths, dx, dy):
    return [(a, b, [(x + dx, y + dy) for x, y in pts],
             (end[0] + dx, end[1] + dy) if end else None) for a, b, pts, end in paths]


def path_d(pts, end):
    r = lambda v: f'{v:.1f}'
    d = f'M{r(pts[0][0])},{r(pts[0][1])}C' + ' '.join(f'{r(x)},{r(y)}' for x, y in pts[1:])
    if end:
        d += f'L{r(end[0])},{r(end[1])}'
    return d


def nested_layout(levels, li, node_sizes):
    """Returns the layout of level `li` nested inside all coarser levels."""
    level = levels[li]
    ids_by_module = [{n['module']: n['id'] for n in lv['nodes']} for lv in levels]

    def compose(depth, parent_id):
        """Layout of the cluster of node `parent_id` of level depth-1 at level `li`.

        Returns (W, H, pos, edges, gedges, groups) in local coordinates.
        """
        lv = levels[depth]
        if depth == 0:
            members = [n['id'] for n in lv['nodes']]
        else:
            pk = str(levels[depth - 1]['k'])
            pm = levels[depth - 1]['nodes'][parent_id]['module']
            members = [n['id'] for n in lv['nodes'] if n['parents'][pk] == pm]
        mset = set(members)
        inner_edges = [(a, b) for a, b in lv['edges'] if a in mset and b in mset]
        if depth == li:
            sizes = {i: node_sizes[i] for i in members}
            W, H, pos, paths = layout_box(sizes, inner_edges, dense=(li >= 2),
                                          rankdir='LR' if li >= 2 else 'TB')
            return W, H, pos, [(a, b, pts, end) for a, b, pts, end in paths], [], []
        subs = {i: compose(depth + 1, i) for i in members}
        head = HEADER if depth + 1 < li or li - depth == 1 else HEADER
        sizes = {i: (s[0] + 2 * PAD, s[1] + PAD + head) for i, s in subs.items()}
        W, H, bpos, bpaths = layout_box(sizes, inner_edges, dense=False)
        pos, edges, gedges, groups = {}, [], [], []
        for i, s in subs.items():
            bw, bh = sizes[i]
            ox, oy = bpos[i][0] - bw / 2, bpos[i][1] - bh / 2
            groups.append({'tier': depth, 'parent': i, 'x': ox, 'y': oy, 'w': bw, 'h': bh})
            dx, dy = ox + PAD, oy + head
            for k, (x, y) in s[2].items():
                pos[k] = (x + dx, y + dy)
            edges += shift(s[3], dx, dy)
            gedges += [(t, shift([(0, 0, pts, end)], dx, dy)[0][2:]) for t, (pts, end) in s[4]]
            for g in s[5]:
                groups.append(dict(g, x=g['x'] + dx, y=g['y'] + dy))
        gedges += [(depth, (pts, end)) for _, _, pts, end in bpaths]
        return W, H, pos, edges, gedges, groups

    W, H, pos, edges, gedges, groups = compose(0, None)
    return {
        'W': round(W, 1), 'H': round(H, 1),
        'pos': {k: [round(x, 1), round(y, 1)] for k, (x, y) in pos.items()},
        'edges': [[a, b, path_d(pts, end)] for a, b, pts, end in edges],
        'gedges': [[t, path_d(pts, end)] for t, (pts, end) in gedges],
        'groups': [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in g.items()}
                   for g in groups],
    }


def option(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        value = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        return value
    return None


def load_descriptions(folder):
    out = {}
    if folder and os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(folder, f), encoding='utf-8') as fh:
                        part = json.load(fh)
                except (OSError, ValueError) as e:
                    print(f'skipping {f}: {e}')
                    continue
                for module, d in part.items():
                    if isinstance(d, dict) and d.get('title') and d.get('summary'):
                        out[module] = {k: d.get(k, '') for k in
                                       ('title', 'summary', 'role', 'statement_name', 'confidence', 'caveat')}
                        if isinstance(d.get('literature'), dict):
                            out[module]['literature'] = {'status': d['literature'].get('status', ''),
                                                         'basis': d['literature'].get('basis', '')}
    return out


def main():
    desc = load_descriptions(option('--descriptions'))
    pages = option('--pages') or ''
    source_url = option('--source-url') or ''
    source_label = option('--source-label') or ''
    source_home = option('--source-home') or ''
    no_statements = '--no-statements' in sys.argv
    if no_statements:
        sys.argv.remove('--no-statements')
    src, out = sys.argv[1], sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else 'Milestones'
    data = json.load(open(src))
    data['pages'] = [p.split('=', 1) for p in pages.split(',') if '=' in p]
    data['source_url'], data['source_label'], data['source_home'] = source_url, source_label, source_home
    if no_statements:
        for level in data['levels']:
            for n in level['nodes']:
                if n.get('key'):
                    n['key'].pop('statement', None)
                    n['key'].pop('truncated', None)
    levels = data['levels']
    described = 0
    for level in levels:
        for n in level['nodes']:
            n['title'] = title_of(n['module'])
            if n['module'] in desc:
                n['desc'] = desc[n['module']]
    data['described'] = [lv['k'] for lv in levels if all('desc' in n for n in lv['nodes'])]
    described = sum(1 for n in levels[0]['nodes'] if 'desc' in n)
    print(f'{len(desc)} descriptions loaded; {described} of {len(levels[0]["nodes"])} top-level milestones described')
    for li, level in enumerate(levels):
        kind = ['large', 'small', 'dot'][min(li, 2)]
        size_key = 'cone' if data.get('ranking') == 'plan' else 'flow'
        fmax = max(n[size_key] for n in level['nodes'] if n['module'] != data['root'])
        sizes = {}
        for n in level['nodes']:
            if kind == 'large':
                sizes[n['id']] = CARD_LARGE
            elif kind == 'small':
                sizes[n['id']] = CARD_SMALL
            else:
                r = 4 + 10 * min(1.0, n[size_key] / fmax) ** 0.5
                sizes[n['id']] = (2 * r, 2 * r)
        print(f'layout for level {level["k"]} ...', flush=True)
        level['kind'] = kind
        level['layout'] = nested_layout(levels, li, sizes)
        for n in level['nodes']:
            n['size'] = [round(v, 1) for v in sizes[n['id']]]
            shown = n['desc']['title'] if 'desc' in n else n['title']
            if kind == 'large':
                n['lines'] = wrap(shown, 27, 2)
            elif kind == 'small':
                n['lines'] = wrap(shown, 24, 2)
            if kind == 'dot' and n.get('key') and n['key'].get('statement'):
                n['key']['statement'] = n['key']['statement'][:500]
    here = os.path.dirname(os.path.abspath(__file__))
    template = open(os.path.join(here, 'template.html'), encoding='utf-8').read()
    html = template.replace('/*TITLE*/', title).replace(
        '/*DATA*/', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print(f'wrote {out} ({len(html) // 1024} KB)')


if __name__ == '__main__':
    main()
