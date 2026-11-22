#!/bin/sh
# Rebuild the milestone levels and the pages.
#
#   sh code/build.sh /path/to/riemann-hypothesis
#
# The argument is a checkout of the source proof (see README). Needs Python 3
# with numpy and Graphviz (dot, unflatten). Takes about ten minutes and 6 GB of
# memory.
#
# The declaration-level map is built from data/decl_graph/, which is shipped with
# this repository; code/decl-graph/ has the scripts that produced it.
set -e
SRC="${1:?usage: sh code/build.sh /path/to/riemann-hypothesis}"
REPO=https://github.com/leanprover-community/riemann-hypothesis
TITLE="Riemann Hypothesis proof: milestones"
PAGES="plan=index.html,relative=relative.html,absolute=absolute.html"
VARIANTS="Files=index.html,Declarations=declarations.html"

# 1. Maps built on the import graph of files, at the commit below.
COMMIT=7cce738ba719a32964ca3822d0994f4c6952c7ae
mkdir -p build
[ -f build/modules.json ] || python3 -I code/extract_lean_modules.py "$SRC/src" build/modules.json
for rule in plan relative absolute; do
  page=docs/$rule.html
  [ "$rule" = plan ] && page=docs/index.html
  python3 -I code/build_levels.py build/modules.json Main "$SRC/src" "data/levels_$rule.json" \
    --rule "$rule" --no-statements 20 100 1000
  python3 -I code/render_html.py "data/levels_$rule.json" "$page" "$TITLE" \
    --descriptions data/descriptions --pages "$PAGES" --variants "$VARIANTS" --no-statements \
    --source-url "$REPO/blob/$COMMIT/src/" \
    --archive-url "https://archive.softwareheritage.org/browse/revision/$COMMIT/?path=src/" \
    --source-home "$REPO/tree/$COMMIT" \
    --source-label "leanprover-community/riemann-hypothesis at commit 7cce738"
done

# 2. Map built on the graph of declarations, which comes from the compiled proof
#    at the commit below (the proof as published, plus one added file).
COMMIT=e50d09817ad81469f737e8f637561e6ccf86c670
python3 -I code/build_levels.py data/decl_graph/rh_decls.npz Main "$SRC/src" data/levels_declarations.json 20 100 1000
python3 -I code/render_html.py data/levels_declarations.json docs/declarations.html "$TITLE" \
  --descriptions data/descriptions --pages "plan=declarations.html" --variants "$VARIANTS" \
  --source-url "$REPO/blob/$COMMIT/src/" \
  --archive-url "https://archive.softwareheritage.org/browse/revision/$COMMIT/?path=src/" \
  --source-home "$REPO/tree/$COMMIT" \
  --source-label "leanprover-community/riemann-hypothesis at commit e50d098"
