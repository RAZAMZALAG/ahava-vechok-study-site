# -*- coding: utf-8 -*-
"""TEMPLATE -- copy to assets_<name>.py, edit the clip/embedded calls at the
bottom, run it, and it writes <name>_assets.json for build.py to inline.

    cp assets_template.py assets_t7.py
    # edit SRC and the calls
    py -3 assets_t7.py

Figures are inlined as base64 data URIs so a page keeps working with no network
and no asset folder to lose. That is the whole reason this step exists.

Two ways to get a figure out of a slide, and picking the wrong one loses content:

  clip()      renders a RECTANGLE OF THE SLIDE. Use this when the figure's axis
              labels, captions or callouts are live text in the PDF -- which is
              usually the case for charts drawn in PowerPoint. Extracting the
              raster would give you the dots without the labels.

  embedded()  pulls the stored raster. Use this for photographs and for figures
              that really are a single image. It re-applies the PDF soft mask,
              without which a transparent-background image comes out black.

clip() auto-trims the white margin afterwards, so the rectangle only has to be
a BOUND, not a fit. Be generous -- but check the left edge: labels like the red
"e = 0" often sit well outside the plot axes, and a tight box silently cuts them.
"""
import base64, io, json, os, sys

import fitz
from PIL import Image, ImageChops, ImageDraw

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SRC = r"..\..\Tutorials\Tutorial 7.pdf"      # <-- edit
NAME = os.path.basename(__file__).replace('assets_', '').replace('.py', '')

SP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SP, f'{NAME}_assets.json')
doc = fitz.open(os.path.join(SP, SRC) if not os.path.isabs(SRC) else SRC)
assets = {}
REVIEW = []   # (key, PIL image) kept so all clips can be verified in ONE montage


def _trim(im, pad=12):
    rgb = im.convert('RGB')
    box = ImageChops.difference(rgb, Image.new('RGB', rgb.size, (255, 255, 255))).getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad),
                    min(im.width, x1 + pad), min(im.height, y1 + pad)))


def _encode(key, im, max_w, fmt, quality):
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if im.mode in ('P', 'LA', 'RGBA'):
        flat = Image.new('RGB', im.size, 'white')
        flat.paste(im, mask=im.convert('RGBA').split()[-1])
        im = flat
    buf = io.BytesIO()
    if fmt == 'JPEG':
        im.convert('RGB').save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
        mime = 'image/jpeg'
    else:
        im.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=64).save(
            buf, 'PNG', optimize=True)
        mime = 'image/png'
    b = buf.getvalue()
    assets[key] = f'data:{mime};base64,' + base64.b64encode(b).decode()
    REVIEW.append((key, im.convert('RGB')))
    print(f'{key:14s} {fmt:4s} {len(b)//1024:4d} KB  {im.width}x{im.height}')


def write_review(path, cols=3, thumb=360, pad=10, label_h=20):
    """Tile every clip into one montage, each labelled with its key, so the whole
    set is verified in a SINGLE image read instead of one read per clip (and one
    more per clip after every fix). This is the cheapest place to catch a cropped
    figure -- read it once, adjust the bounds that are wrong, re-run, read once
    more. A green frame just marks each tile's edge so a clip that lost content to
    a tight bound is obvious against it."""
    if not REVIEW:
        return
    cell_w = thumb + pad
    scaled = []
    for key, im in REVIEW:
        s = im.copy()
        if s.width > thumb:
            s = s.resize((thumb, round(s.height * thumb / s.width)), Image.LANCZOS)
        scaled.append((key, s))
    rows = (len(scaled) + cols - 1) // cols
    row_h = [0] * rows
    for i, (_, s) in enumerate(scaled):
        r = i // cols
        row_h[r] = max(row_h[r], s.height + label_h + pad)
    W = cols * cell_w + pad
    H = sum(row_h) + pad
    sheet = Image.new('RGB', (W, H), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    y0 = pad
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if i >= len(scaled):
                break
            key, s = scaled[i]
            x = pad + c * cell_w
            draw.text((x, y0), key, fill=(180, 20, 20))
            sheet.paste(s, (x, y0 + label_h))
            draw.rectangle([x, y0 + label_h, x + s.width, y0 + label_h + s.height],
                           outline=(60, 170, 90), width=1)
        y0 += row_h[r]
    sheet.save(path)
    print(f'REVIEW montage: {len(scaled)} clips -> {os.path.basename(path)}  '
          f'(read this ONE image to verify them all)')


def _warn_if_cut(key, page, x0, y0, x1, y1, dpi, margin=12):
    """Warn only when real ink sits in the MARGIN RING just OUTSIDE the requested
    box -- the actual signature of a cut (content spilled past the boundary). This
    is the distinction that matters: a graph node sitting right against the box
    edge is fully captured (fill), whereas ink a few points beyond it is lost
    (cut). Checking the trimmed image edge cannot tell those apart and cries wolf
    on every full-bleed figure; probing the ring can. A side whose box already
    coincides with the page edge is skipped -- nothing lies beyond it to recover.

    Turns finding a cropped figure from a visual hunt in the montage into a line
    in the console naming the exact side to widen."""
    pr = page.rect
    ex0, ey0 = max(pr.x0, x0 - margin), max(pr.y0, y0 - margin)
    ex1, ey1 = min(pr.x1, x1 + margin), min(pr.y1, y1 + margin)
    im = Image.open(io.BytesIO(page.get_pixmap(dpi=dpi, clip=fitz.Rect(ex0, ey0, ex1, ey1)).tobytes('png'))).convert('RGB')
    g = im.convert('L')
    s = dpi / 72.0
    lb, tb = round((x0 - ex0) * s), round((y0 - ey0) * s)      # ring widths, px
    rb, bb = round((ex1 - x1) * s), round((ey1 - y1) * s)
    W, H = g.width, g.height

    def frac(region):
        # fraction of the ring that is real ink. `< 200` ignores the soft grey
        # drop-shadows PowerPoint puts on nodes (which read ~210-235) so a figure
        # merely filling its box is not mistaken for one spilling past it; only
        # genuine content -- text, a coloured node, a black line -- trips it.
        px = list(region.getdata())
        return sum(v < 200 for v in px) / len(px) if px else 0.0

    sides = []
    if lb > 1 and frac(g.crop((0, 0, lb, H))) > 0.005:      sides.append('left')
    if tb > 1 and frac(g.crop((0, 0, W, tb))) > 0.005:      sides.append('top')
    if rb > 1 and frac(g.crop((W - rb, 0, W, H))) > 0.005:  sides.append('right')
    if bb > 1 and frac(g.crop((0, H - bb, W, H))) > 0.005:  sides.append('bottom')
    if sides:
        print(f'   !! {key}: ink just OUTSIDE the {"/".join(sides)} edge -- widen, '
              f'OR it is prose you meant to exclude (check the montage)')


def clip(key, page_no, x0, y0, x1, y1, dpi=200, max_w=980, fmt='PNG', quality=85):
    """Render a rectangle of a slide (points), auto-trim to its ink, inline it.

    Err LARGE when in doubt: _trim removes white margin afterwards, so a loose box
    costs nothing, but no trim can recover ink the box cut off. The only reason to
    tighten a side is to exclude neighbouring TEXT you are transcribing anyway --
    and a plot's legend or a graph's parameter box (θ, weights) is figure content,
    not prose, so keep it in. _warn_if_cut flags a side that spilled."""
    page = doc[page_no - 1]
    _warn_if_cut(key, page, x0, y0, x1, y1, dpi)
    im = Image.open(io.BytesIO(page.get_pixmap(dpi=dpi, clip=fitz.Rect(x0, y0, x1, y1)).tobytes('png'))).convert('RGB')
    _encode(key, _trim(im), max_w, fmt, quality)


def embedded(key, page_no, idx, max_w=900, fmt='JPEG', quality=85):
    """Pull image `idx` off a page, re-applying its soft mask if it has one."""
    info = doc[page_no - 1].get_images(full=True)[idx]
    xref, smask = info[0], info[1]
    pix = fitz.Pixmap(doc, xref)
    if not pix.alpha and smask:
        pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
        print(f'   ({key}: applied SMask xref {smask})')
    if pix.colorspace and pix.colorspace.n == 4:          # CMYK -> RGB
        pix = fitz.Pixmap(fitz.csRGB, pix)
    _encode(key, Image.open(io.BytesIO(pix.tobytes('png'))), max_w, fmt, quality)


# ---------------------------------------------------------------- edit below
# Read the clip rectangles straight off `render_pdf.py sheets <deck> <dir> --grid`
# -- the ruler is in PDF points, the same units clip() takes, so no guessing and
# no re-clip rounds. A 16:9 slide is ~960 x 540 pt (or ~803 x 453 for 4:3).
# After running this script, read the ONE `<name>_assets_review.png` montage to
# verify every clip at once; fix any bounds that cropped, re-run, read it once
# more. Reference each figure from the body as
#   <img class="fig" src="{{key}}" alt="...">   (add class="fig wide" for room).

clip('example_plot', 17, 140, 100, 620, 400)
# embedded('photo', 3, 0, 380)

# ---------------------------------------------------------------------------

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(assets, fh)
write_review(os.path.join(SP, f'{NAME}_assets_review.png'))
print('TOTAL data-uri:', sum(len(v) for v in assets.values()) // 1024, 'KB ->', OUT)
