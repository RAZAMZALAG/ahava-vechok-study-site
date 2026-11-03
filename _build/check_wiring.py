# -*- coding: utf-8 -*-
"""Check that every built page is wired in everywhere it needs to be, and that
no link inside it points at an anchor that does not exist.

    py -3 check_wiring.py

A finished page has to appear in four places, and forgetting one is the single
most common slip in this pipeline -- the page builds fine, looks fine, and is
simply unreachable. site.json and _redirects are handled by the manifest, so
this checks the two that stay hand-written (the index nav and the README) plus
the thing no manifest can catch: dead anchors.

Dead anchors matter more than they sound. Every question carries a 📖 box
linking to the sub-lecture that teaches it, and those links are a large part of
why the files are useful. A typo turns one into a link that scrolls nowhere,
and nothing else in the pipeline notices.

Exit code is 1 if anything is missing, so it can gate a commit.
"""
import json, os, re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SP)

with open(os.path.join(SP, 'site.json'), encoding='utf-8') as fh:
    SITE = json.load(fh)

problems = []


def read(path):
    return open(path, encoding='utf-8').read() if os.path.exists(path) else ''


index_body = read(os.path.join(SP, 'index.body.html'))
readme = read(os.path.join(ROOT, 'README.md'))

# ---- 1. every manifest page is built, linked from the index, listed in README
built = {}
for page in SITE['pages']:
    name, out = page['name'], page['out']
    if name == 'index':
        continue
    path = os.path.join(ROOT, out)
    if not os.path.exists(path):
        problems.append(f'{name}: not built yet ({out} missing)')
        continue
    built[out] = read(path)
    if f'href="{out}"' not in index_body:
        problems.append(f'{name}: no link to {out} in index.body.html '
                        f'(needs a <li> in the nav AND a card in <main>)')
    elif index_body.count(f'href="{out}"') < 2:
        problems.append(f'{name}: only one link to {out} in index.body.html '
                        f'-- there should be two, the nav <li> and the card')
    if out not in readme and f'`{out}`' not in readme:
        problems.append(f'{name}: no row for {out} in README.md')

# ---- 2. every built page is in the manifest
declared = {p['out'] for p in SITE['pages']}
for f in sorted(os.listdir(ROOT)):
    if f.endswith('.html') and f not in declared:
        problems.append(f'{f}: built but absent from site.json '
                        f'-- it will not be published by make_site.py')

# ---- 2b. the index does not promise a page that does not exist.
# build.py's "בעבודה" mechanism only covers in-page #anchors; a nav entry
# pointing at an unbuilt FILE renders as a live link straight to a 404.
for target in sorted(set(re.findall(r'href="([^":#/]+\.html)"', index_body))):
    if not os.path.exists(os.path.join(ROOT, target)):
        problems.append(f'index.body.html: links to {target}, which is not built '
                        f'-- that renders as a live link to nothing')

# ---- 3. no link points at an anchor that does not exist
# The scan is over markup, so the inline <script> has to come out first. The
# comment box builds links as strings -- `'<a href="#cid-' + cid + '">'` -- and
# read as HTML those are 31 dead anchors that are not there.
SCRIPT = re.compile(r'<script[^>]*>.*?</script>', re.S)
built = {out: SCRIPT.sub('', html) for out, html in built.items()}
anchors = {out: set(re.findall(r'id="([^"]+)"', html)) for out, html in built.items()}
anchors['index.html'] = set(re.findall(r'id="([^"]+)"', read(os.path.join(ROOT, 'index.html'))))
for out, html in built.items():
    for target, frag in re.findall(r'href="([^"#]*\.html)#([^"]+)"', html):
        if target in anchors and frag not in anchors[target]:
            problems.append(f'{out}: link to {target}#{frag} -- no such anchor')
    for frag in re.findall(r'href="#([^"]+)"', html):
        if frag not in anchors[out]:
            problems.append(f'{out}: in-page link #{frag} -- no such anchor')

# ---- 4. no link out of the site at all.
# These used to be allowed as long as the file existed on disk, and that was
# the wrong test: make_site.py publishes the manifest's HTML pages and nothing
# else, so ../Tutorials/Tutorial 7.pdf resolves perfectly while you are reading
# off disk and 404s for everyone you send the link to. The check has to be that
# the target is published, which for a path leaving the folder it never is --
# name the file in a <span class="src" title="..."> instead, or point at the
# page that now covers it.
for out, html in built.items():
    for rel in sorted(set(re.findall(r'href="(\.\./[^"#]+)"', html))):
        problems.append(f'{out}: link to {rel} -- outside sections-he, so '
                        f'make_site.py does not publish it and the link 404s. '
                        f'Use <span class="src" title="..."> or link the page '
                        f'that covers it.')

if problems:
    print(f'{len(problems)} problem(s):\n')
    for p in problems:
        print('  !!', p)
    sys.exit(1)
print(f'wiring OK -- {len(built)} pages, all links resolve')
