# -*- coding: utf-8 -*-
"""Render whole lecture slides as inline JPEG figures.

    py -3 assets_slides.py            # all pages in SPEC
    py -3 assets_slides.py t8         # one page

Writes <page>_assets.json (key -> data URI) for build.py, plus
<page>_assets_review.jpg, a montage to verify every slide in one look.
Slides are rendered whole (not clipped): most image slides here are a
title + one picture/chart, and the title is part of the meaning.
"""
import base64, glob, io, json, os, sys
import fitz
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SP, '..', '..')
SRC = {
    's1': 'src_pdf/s1.pdf', 's2': 'src_pdf/s2.pdf', 's3': 'src_pdf/s3.pdf',
    's45': 'src_pdf/s45.pdf', 's6': 'src_pdf/s6.pdf', 's7': 'src_pdf/s7.pdf',
    's8': 'src_pdf/s8.pdf', 's10y': 'src_pdf/s10y.pdf',
    'p6': glob.glob(os.path.join(ROOT, 'נושא_6', '*.pdf'))[0],
    'p8': glob.glob(os.path.join(ROOT, 'נושא_8', '*.pdf'))[0],
    'p9': glob.glob(os.path.join(ROOT, 'נושא_9', '*.pdf'))[0],
}
# page -> [(key, source, slide number)]
SPEC = {
    't1': [('cloning', 's1', 10), ('babyboom', 's1', 12), ('qualitytime', 's1', 13)],
    't2': [('famlove', 's2', 8), ('famumbrella', 's2', 11), ('sexoff', 's2', 21), ('aminchild', 's3', 29)],
    't3': [('ethicsinfo', 'p9', 41), ('adoptcartoon', 's45', 28), ('amir', 's45', 8), ('nachmani', 's45', 17), ('marriedman', 's45', 26)],
    't4': [('hamerquote', 's7', 10), ('noeuth', 's6', 10), ('wrongchild', 's7', 3), ('wrongcourt', 's7', 4)],
    't5': [('agemiscarriage', 's8', 39), ('freezing', 's8', 15)],
    't6': [('civilceremony', 'p6', 14), ('jurisrace', 'p6', 26), ('blacklist', 'p6', 51)],
    't8': [('news32', 'p8', 5), ('btl2025', 'p8', 6), ('hitech30', 'p8', 11),
           ('femprof', 'p8', 18), ('ceos35', 'p8', 32), ('knesset', 'p8', 33),
           ('edenmyth', 'p8', 38), ('motherpen', 'p8', 66), ('agegap', 'p8', 67),
           ('hourgap', 'p8', 68), ('fatherbonus', 'p8', 69), ('schoolvac', 'p8', 108),
           ('breastfeed', 'p8', 111), ('maternity', 'p8', 114)],
    't7': [('students', 's10y', 49), ('elderly', 's10y', 73), ('twowomen', 's10y', 74), ('sisters', 's10y', 81)],
    't9': [('ethicsinfo', 'p9', 41), ('sisters', 's10y', 81)],
}


def render(src, n, width=760, q=72):
    path = SRC[src] if os.path.isabs(SRC[src]) else os.path.join(SP, SRC[src])
    page = fitz.open(path)[n - 1]
    pix = page.get_pixmap(dpi=150)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=q, optimize=True)
    return im, 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode(), len(buf.getvalue())


for name in (sys.argv[1:] or SPEC):
    assets, thumbs, total = {}, [], 0
    for key, src, n in SPEC[name]:
        im, uri, size = render(src, n)
        assets[key] = uri
        total += size
        thumbs.append(im.resize((300, round(im.height * 300 / im.width))))
    json.dump(assets, open(os.path.join(SP, f'{name}_assets.json'), 'w'))
    h = max(t.height for t in thumbs)
    sheet = Image.new('RGB', (300 * min(4, len(thumbs)), h * ((len(thumbs) + 3) // 4)), 'white')
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % 4) * 300, (i // 4) * h))
    sheet.save(os.path.join(SP, f'{name}_assets_review.jpg'), quality=70)
    print(f'{name}: {len(assets)} slides, {total // 1024} KB')
