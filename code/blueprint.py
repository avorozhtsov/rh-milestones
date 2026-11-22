"""Parse a Lean Blueprint (LaTeX sources) into the human-written milestone graph.

Usage: python3 -I blueprint.py <blueprint/src dir> [label of the main theorem]

A blueprint statement is a definition, lemma, proposition, theorem or
corollary with a \\label.  \\lean{...} names the Lean declarations that
formalise it, and \\uses{...} (in the statement or in its proof) lists the
labels it depends on.
"""
import os
import re
import sys

STATEMENT = re.compile(
    r'\\begin\{(definition|lemma|proposition|theorem|corollary)\}(.*?)\\end\{\1\}', re.S)
PROOF = re.compile(r'\s*\\begin\{proof\}(.*?)\\end\{proof\}', re.S)
ARG = lambda cmd: re.compile(r'\\' + cmd + r'\{([^}]*)\}')
LABEL, LEAN, USES = ARG('label'), ARG('lean'), ARG('uses')
TITLE = re.compile(r'^\s*\[([^\]]*)\]')


def split_list(items):
    return [x.strip() for chunk in items for x in chunk.split(',') if x.strip()]


def parse(src_dir):
    """Returns {label: {kind, title, lean: [names], uses: [labels], file}}."""
    nodes = {}
    for dp, _, files in os.walk(src_dir):
        for f in sorted(files):
            if not f.endswith('.tex'):
                continue
            with open(os.path.join(dp, f), encoding='utf-8', errors='replace') as fh:
                text = re.sub(r'(?<!\\)%.*', '', fh.read())      # drop comments
            for m in STATEMENT.finditer(text):
                body = m.group(2)
                label = LABEL.search(body)
                if not label:
                    continue
                uses = USES.findall(body)
                proof = PROOF.match(text, m.end())
                if proof:
                    uses += USES.findall(proof.group(1))
                title = TITLE.match(body)
                nodes[label.group(1).strip()] = {
                    'kind': m.group(1),
                    'title': title.group(1) if title else '',
                    'lean': split_list(LEAN.findall(body)),
                    'uses': split_list(uses),
                    'file': f,
                }
    for n in nodes.values():
        n['uses'] = [u for u in dict.fromkeys(n['uses']) if u in nodes]
    return nodes


def cone(nodes, label):
    seen, stack = {label}, [label]
    while stack:
        for u in nodes[stack.pop()]['uses']:
            if u not in seen:
                seen.add(u)
                stack.append(u)
    return seen


def main():
    nodes = parse(sys.argv[1])
    print(f'{len(nodes)} statements, {sum(1 for n in nodes.values() if n["lean"])} with \\lean, '
          f'{sum(len(n["uses"]) for n in nodes.values())} \\uses edges')
    if len(sys.argv) > 2:
        c = cone(nodes, sys.argv[2])
        print(f'cone of {sys.argv[2]}: {len(c)} statements')
        for label in sorted(c):
            n = nodes[label]
            print(f'  {n["kind"]:11s} {label:28s} {", ".join(n["lean"])}')


if __name__ == '__main__':
    main()
