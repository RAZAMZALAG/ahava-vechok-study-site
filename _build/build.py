# -*- coding: utf-8 -*-
"""Compose  shell_head + <body file> + shell_tail, inject the base64 images,
and fail loudly on any unresolved placeholder.

Two ways to call it:

    py -3 build.py part3                       # looks the page up in site.json
    py -3 build.py <body> <assets> <out> <title> <brand> <srcpdf> <count>

Use the first form. It reads the page entry out of site.json, so the seven
values live in one version-controlled place that make_site.py reads too --
rather than in a shell command you have to retype correctly every time. The
positional form still works for a one-off build of something not in the
manifest.

Naming convention in manifest mode: a page named `foo` is built from
`foo.body.html` with images from `foo_assets.json`. Homework and tutorial pages
usually have no figures, and a missing assets file is simply treated as empty.
"""
import hashlib, json, os, re, sys
import xml.etree.ElementTree as ET

SP = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) == 2:
    site_path = os.path.join(SP, 'site.json')
    if not os.path.exists(site_path):
        sys.exit('!! no site.json next to build.py -- use the 7-argument form, '
                 'or run init_project.py to create one')
    with open(site_path, encoding='utf-8') as fh:
        site = json.load(fh)
    name = sys.argv[1].replace('.body.html', '')
    page = next((p for p in site['pages'] if p['name'] == name), None)
    if page is None:
        known = ', '.join(p['name'] for p in site['pages'])
        sys.exit(f'!! "{name}" is not in site.json. Known pages: {known}\n'
                 f'   Add an entry for it before building.')
    body_path = os.path.join(SP, name + '.body.html')
    assets_path = os.path.join(SP, name + '_assets.json')
    out_path = os.path.join(SP, '..', page['out'])
    title, brand = page['title'], page['brand']
    # a page may be built from several sources at once -- a tutorial and the
    # homework that reuses it, say -- so srcpdf accepts a list
    srcpdf, count = page.get('srcpdf', ''), page.get('count', '')
    if isinstance(srcpdf, (list, tuple)):
        srcpdf = '</code> · <code>'.join(srcpdf)
    course = site.get('course', '')
    comments = site.get('comments') or {}
    is_index = (name == 'index')
elif len(sys.argv) == 8:
    body_path, assets_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    title, brand, srcpdf, count = sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7]
    course = os.environ.get('COURSE_NAME', '')
    comments = {}
    name = os.path.basename(body_path).replace('.body.html', '')
    is_index = os.path.basename(out_path).lower() == 'index.html'
else:
    sys.exit(__doc__)

head = open(os.path.join(SP, 'shell_head.html'), encoding='utf-8').read()
tail = open(os.path.join(SP, 'shell_tail.html'), encoding='utf-8').read()
body = open(body_path, encoding='utf-8').read()
assets = json.load(open(assets_path, encoding='utf-8')) if os.path.exists(assets_path) else {}

# A part can be built while still being written. Any TOC entry whose section is
# not in the body yet is rendered as a dead "בעבודה" label instead of a link
# that scrolls nowhere, and a banner says how far the file got. The body file
# itself keeps its real links, so this reverses automatically as sections land.
have = set(re.findall(r'<section class="lec" id="([^"]+)"', body))
pending = []


def _toc(m):
    href, label = m.group(1), m.group(2)
    if href in have:
        return m.group(0)
    pending.append(label)
    return f'<span class="todo">{label} <em>בעבודה</em></span>'


body = re.sub(r'<a href="#([^"]+)">(.*?)</a>', _toc, body, flags=re.S)

if pending:
    ndone = len(re.findall(r'<section class="lec" id="l\d+"', body))
    banner = ('<div class="warn banner"><span class="t">⚠️ הקובץ הזה עדיין בעבודה</span>'
              f'<p>הושלמו <strong>{ndone}</strong> תת-הרצאות במלואן. הפריטים המסומנים '
              '<em>בעבודה</em> בתוכן העניינים טרם נכתבו, ויתווספו לאותו קובץ.</p></div>')
    body = body.replace('<section class="lec" id="intro">',
                        banner + '\n<section class="lec" id="intro">', 1)
    print(f'PARTIAL BUILD: {ndone} sections written, {len(pending)} still pending')


def collapsible(src):
    """Turn every  <div class="note"> / <div class="warn">  into a native
    <details>/<summary> so the reader can fold our commentary away and see just
    the slide. Depth-aware: these boxes contain nested <div class="eq"> blocks,
    so matching the first </div> would cut them in half.

    Deliberately NOT applied to .def / .ex (definition / example boxes) -- those
    are the slide's own framed content, not our additions, and must stay put.
    Nor to <details class="sol">, which practice-exam pages write literally so
    their solutions start closed. The progress banner is skipped too.
    """
    open_pat = re.compile(r'<div class="(note|warn|deep)">')
    tag_pat = re.compile(r'<div\b|</div>')
    out, i, n = [], 0, 0
    while True:
        m = open_pat.search(src, i)
        if not m:
            out.append(src[i:])
            break
        out.append(src[i:m.start()])
        kind, depth, j = m.group(1), 1, m.end()
        while depth:
            t = tag_pat.search(src, j)
            if not t:
                raise SystemExit(f'!! unbalanced <div class="{kind}"> near offset {m.start()}')
            depth += -1 if t.group(0) == '</div>' else 1
            j = t.end()
        inner = src[m.end():j - len('</div>')]
        head_m = re.search(r'<span class="t">(.*?)</span>', inner, flags=re.S)
        if head_m:
            summary, rest = head_m.group(1), inner[:head_m.start()] + inner[head_m.end():]
        else:
            summary, rest = ({'note': '💡 הסבר', 'warn': '⚠️ שים לב',
                              'deep': '🔎 העמקה'}[kind]), inner
        out.append(f'<details class="{kind}" open><summary>{summary}</summary>'
                   f'<div class="dbody">{rest}</div></details>')
        n += 1
        i = j
    print(f'collapsible boxes: {n}')
    return ''.join(out)


body = collapsible(body)


def stamp_cids(html, page):
    """Give every card a content-derived id, so a comment can point at one.

    A comment has to be attached to something that survives a rebuild. Numbering
    the cards in order would not: inserting one slide in the middle of Part 3
    shifts every card after it, and every comment lands on the wrong card.

    So the id is a hash of what the card *is* -- the page, the sub-lecture it
    sits under, and its heading. That survives insertion, reordering, and edits
    to the card's body. It changes only when the heading changes, and then the
    comment is not lost: the page shows it under "general", saying the card it
    was written on has since been renamed.

    Two cards under one heading (a derivation split across cards) get a counter
    appended, which is stable as long as their order between themselves is.
    """
    tok = re.compile(r'<section class="lec" id="([^"]+)">|<div class="slide">')
    out, pos, sec, seen = [], 0, '', {}
    for m in tok.finditer(html):
        if m.group(1):
            sec = m.group(1)
            continue
        head = re.search(r'<h3[^>]*>(.*?)</h3>', html[m.end():m.end() + 4000], re.S)
        label = re.sub(r'<[^>]+>', ' ', head.group(1)) if head else ''
        label = re.sub(r'\s+', ' ', label).strip()
        key = f'{page}|{sec}|{label}'
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key += f'|{seen[key]}'
        cid = hashlib.sha1(key.encode('utf-8')).hexdigest()[:8]
        out.append(html[pos:m.start()])
        out.append(f'<div class="slide" data-cid="{cid}">')
        pos = m.end()
    out.append(html[pos:])
    return ''.join(out)


body = stamp_cids(body, name)

# The comment box only exists when the manifest carries a project to talk to.
# With no config the script never runs, no request is made, and make_site.py
# leaves the strict `default-src 'none'` header untouched -- so the site works
# exactly as before until the credentials are filled in.
if comments.get('url') and comments.get('anon_key'):
    conf = ('<script>window.ST2C={url:%s,key:%s,page:%s};</script>'
            % (json.dumps(comments['url']), json.dumps(comments['anon_key']),
               json.dumps(name)))
else:
    conf = ''

# every page carries a permanent way back to index.html: a pill in the sticky
# topbar (always on screen) and a first entry in the sidebar contents.
# index.html itself is the target, so it gets neither.
home_btn = '' if is_index else (
    '<a class="home" href="index.html" title="חזרה לעמוד הראשי">'
    '🏠 עמוד הבית</a>')
if not is_index:
    body = body.replace(
        '<ol id="toclist">',
        '<ol id="toclist">\n    <li><a class="home" href="index.html">'
        '🏠 עמוד הבית</a></li>', 1)

html = (head.replace('{{TITLE}}', title).replace('{{BRAND}}', brand)
        .replace('{{COURSE}}', course).replace('{{HOME}}', home_btn)
        + body
        + tail.replace('{{SRCPDF}}', srcpdf).replace('{{NSLIDES}}', count)
                .replace('{{CONF}}', conf))

used, missing = set(), []


def sub(m):
    k = m.group(1)
    if k not in assets:
        missing.append(k)
        return m.group(0)
    used.add(k)
    return assets[k]


html = re.sub(r'\{\{([A-Za-z0-9_]+)\}\}', sub, html)

if missing:
    print('!! MISSING ASSETS:', sorted(set(missing)))
    sys.exit(1)
left = re.findall(r'\{\{[^}]{0,40}\}\}', html)
if left:
    print('!! UNREPLACED PLACEHOLDERS:', sorted(set(left)))
    sys.exit(1)
unused = sorted(set(assets) - used)
if unused:
    print('!! assets built but never referenced:', unused)

# structural sanity checks
for tag in ('section', 'div', 'math'):
    o = len(re.findall(r'<%s[\s>]' % tag, html))
    c = len(re.findall(r'</%s>' % tag, html))
    if o != c:
        print(f'!! UNBALANCED <{tag}>: {o} open vs {c} close')
        sys.exit(1)

# Counting tags is not enough for MathML. A formula like `<mover>x</mrow>`
# leaves the document totals balanced while the formula itself is malformed --
# the browser renders something subtly wrong, or nothing at all, and only a
# visual check catches it. MathML is XML, so parse each formula properly.
bad = []
for m in re.finditer(r'<math.*?</math>', html, re.S):
    try:
        ET.fromstring(m.group(0))
    except ET.ParseError as e:
        line = html[:m.start()].count(chr(10)) + 1
        text = re.sub(r'<[^>]+>', '', m.group(0))[:60]
        bad.append('  output line ~%d: %s' % (line, e))
        bad.append('      near: %s' % text)
if bad:
    print('!! MALFORMED MathML in %d formula(s):' % (len(bad) // 2))
    print(chr(10).join(bad[:24]))
    sys.exit(1)

out_path = os.path.abspath(out_path)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
open(out_path, 'w', encoding='utf-8').write(html)
print('WROTE', out_path, '|', os.path.getsize(out_path) // 1024, 'KB |', len(used), 'images')
