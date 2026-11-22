#!/bin/sh
# Rebuild the milestone levels and the three pages.
#
#   sh code/build.sh /path/to/riemann-hypothesis
#
# The argument is a checkout of the source proof (see README). Needs Python 3
# and Graphviz (dot, unflatten). Takes about five minutes and 4 GB of memory.
set -e
SRC="${1:?usage: sh code/build.sh /path/to/riemann-hypothesis}"
COMMIT=7cce738ba719a32964ca3822d0994f4c6952c7ae
REPO=https://github.com/leanprover-community/riemann-hypothesis
TITLE="Riemann Hypothesis proof: milestones"
PAGES="plan=index.html,relative=relative.html,absolute=absolute.html"

mkdir -p build
[ -f build/modules.json ] || python3 -I code/extract_lean_modules.py "$SRC/src" build/modules.json
for rule in plan relative absolute; do
  page=docs/$rule.html
  [ "$rule" = plan ] && page=docs/index.html
  python3 -I code/build_levels.py build/modules.json Main "$SRC/src" "data/levels_$rule.json" \
    --rule "$rule" --no-statements 20 100 1000
  python3 -I code/render_html.py "data/levels_$rule.json" "$page" "$TITLE" \
    --descriptions data/descriptions --pages "$PAGES" --no-statements \
    --source-url "$REPO/blob/$COMMIT/src/" \
    --archive-url "https://archive.softwareheritage.org/browse/revision/$COMMIT/?path=src/" \
    --source-home "$REPO/tree/$COMMIT" \
    --source-label "leanprover-community/riemann-hypothesis at commit 7cce738"
done
