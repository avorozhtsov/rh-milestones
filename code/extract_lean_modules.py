"""Extract the module-level import graph of a Lean source tree.

Usage: python3 -I extract_lean_modules.py <src_dir> <out.json>

Output format (shared by all graph tools in this folder):
  nodes  - list of node names
  deps   - deps[i] = indices of nodes that node i depends on (imports)
  weight - weight[i] = amount of work in node i (non-blank lines)
  info   - per-node extra data (counts of theorems and definitions)
"""
import json, os, re, sys, collections

IMPORT = re.compile(r'^\s*(?:public\s+|private\s+|meta\s+)*import\s+(?:all\s+)?([\w.«»\']+)', re.M)
DECL = re.compile(
    r'^\s*(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)\s+)*'
    r'(theorem|lemma|def|abbrev|structure|class|instance|inductive)\b', re.M)

def main(src, out):
    paths = {}
    for dp, _, fn in os.walk(src):
        for f in fn:
            if f.endswith('.lean'):
                p = os.path.join(dp, f)
                paths[os.path.relpath(p, src)[:-5].replace(os.sep, '.')] = p
    nodes = sorted(paths)
    idx = {m: i for i, m in enumerate(nodes)}
    deps, weight, info = [], [], []
    for m in nodes:
        with open(paths[m], encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        deps.append(sorted({idx[x] for x in IMPORT.findall(text) if x in idx}))
        weight.append(sum(1 for line in text.splitlines() if line.strip()))
        c = collections.Counter(DECL.findall(text))
        thm = c['theorem'] + c['lemma']
        info.append({'thm': thm, 'def': sum(c.values()) - thm})
    with open(out, 'w') as fh:
        json.dump({'nodes': nodes, 'deps': deps, 'weight': weight, 'info': info}, fh)
    print(f'{len(nodes)} modules, {sum(map(len, deps))} edges, {sum(weight)} non-blank lines -> {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
