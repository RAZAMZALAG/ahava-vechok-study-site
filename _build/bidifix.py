# -*- coding: utf-8 -*-
"""Wrap inline <math> that OPENS an RTL paragraph in <span class="lt">.

SUPERSEDED, and kept because the existing body files carry its wrappers.

This script was written when the shell gave inline <math> `direction:ltr` but
deliberately NOT `unicode-bidi:isolate`, on the belief that isolating every
formula would break spacing mid-sentence. That belief was wrong, and the gap
cost real damage: without isolation a formula still takes part in the
surrounding RTL paragraph, so two formulas separated only by Hebrew can be
reordered. In Part 4 section 4.8 that displayed "estimate Var_F by Var_F-hat"
as its exact opposite while the source was correct.

The shell now sets `unicode-bidi:isolate` on `math` itself, which fixes every
formula on every page at once, so this pass no longer changes the rendering.
Running it is harmless and idempotent.

Run this on every body file after writing it, before build.py:

    py -3 bidifix.py t11.body.html

Idempotent: an already-wrapped formula no longer matches the pattern.
"""
import re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

P = sys.argv[1]
b = open(P, encoding='utf-8').read()


def span_math(s, i):
    """Index just past the </math> that closes the <math> starting at i."""
    depth = 0
    for m in re.finditer(r'<math\b|</math>', s[i:]):
        depth += 1 if m.group(0).startswith('<math') else -1
        if depth == 0:
            return i + m.end()
    raise SystemExit('unbalanced math at %d' % i)


edits = []
for m in re.finditer(r'<(p|li)>(?=<math\b(?! display))|<span class="t">[^<]*(?=<math\b)', b):
    start = m.end()
    end = span_math(b, start)
    # only if Hebrew follows the formula (i.e. it really sits in an RTL run)
    if not re.search(r'[֐-׿]', b[end:end + 120]):
        continue
    edits.append((start, end))

for start, end in reversed(edits):
    b = b[:start] + '<span class="lt">' + b[start:end] + '</span>' + b[end:]

open(P, 'w', encoding='utf-8').write(b)
print('wrapped', len(edits), 'leading inline formulas')
