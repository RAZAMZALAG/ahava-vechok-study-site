# -*- coding: utf-8 -*-
"""Report <span class="t"> box titles that will render badly.

build.py turns `.note` / `.warn` boxes into <details>/<summary>, and the title
span becomes the <summary>. Chrome wraps <math>, <em> and stray </strong>
inside a <summary> badly under RTL — the fix is always to reword the title as
plain Hebrew text, never to keep the markup.

    py -3 checkheadings.py t11.body.html
"""
import re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

s = open(sys.argv[1], encoding='utf-8').read()
bad = [t for t in re.findall(r'<span class="t">(.*?)</span>', s, re.S)
       if re.search(r'<math|<em|</strong>', t)]

print('bad headings:', len(bad))
for b in bad:
    print('  ', b[:140])
sys.exit(1 if bad else 0)
