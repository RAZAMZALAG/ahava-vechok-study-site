# -*- coding: utf-8 -*-
"""Look at a source PDF: probe it, render it, or clip a figure out of it.

One tool instead of the three-plus ad-hoc one-liners this pipeline otherwise
grows. Everything here exists because of one fact about the source material:
**Hebrew comes out of get_text() partially reversed**, so extracted text is fine
for locating content and useless for transcribing it. You have to render pages
and read them as images.

    py -3 render_pdf.py probe  "Tutorial 7.pdf"
    py -3 render_pdf.py sheets "Tutorial 7.pdf" ./t7g --per 4
    py -3 render_pdf.py sheets "Tutorial 7.pdf" ./t7g --per 4 --grid
    py -3 render_pdf.py pages  "Tutorial 7.pdf" ./t7 --dpi 125 --range 5-9
    py -3 render_pdf.py text   "Tutorial 7.pdf"
    py -3 render_pdf.py clip   "Tutorial 7.pdf" 12 ./fig.png --box 140,100,620,400

`probe` first, always. It tells you the page count and -- the thing that decides
your whole approach -- whether each page has a text layer at all. A page with
0 characters is a handwriting scan: no amount of text extraction will help, and
you must read it as an image.

`sheets` is the fast way to read a deck: four slides per PNG means a 30-slide
tutorial is eight images instead of thirty. It renders light by default (90 dpi,
900 px wide) because the reading pass's only cost is the size of the images the
model reads; pass `--dpi 150 --width 1150` for a sharper render when a slide is
genuinely too small to read.

`sheets --grid` overlays a faint PDF-point ruler (labelled every 100 pt) on each
slide. It costs nothing extra -- it is the *same* image you read the deck from --
but it lets you read a figure's clip rectangle straight off the slide, so your
`assets_*.py` clip() bounds are right the first time instead of after two or
three re-clip rounds. Use it whenever the page has figures to extract. The
numbers you read off are exactly the `--box`/`clip()` coordinates (PDF points,
origin top-left)."""
import io, os, sys

import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def parse_range(spec, n):
    if not spec:
        return list(range(1, n + 1))
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-')
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def cmd_probe(src):
    d = fitz.open(src)
    print(f'{os.path.basename(src)} -- {len(d)} pages')
    print(f'{"pg":>4} {"chars":>6} {"imgs":>5} {"vec":>5}  first line')
    scans = []
    for i, pg in enumerate(d):
        t = pg.get_text().strip()
        first = t.splitlines()[0][:56] if t else ''
        nimg, nvec = len(pg.get_images()), len(pg.get_drawings())
        print(f'{i+1:>4} {len(t):>6} {nimg:>5} {nvec:>5}  {first}')
        if len(t) < 15:
            scans.append(i + 1)
    if scans:
        print(f'\n!! pages with (almost) no text layer: {scans}')
        print('   These are handwriting scans or pure figures. Render and READ '
              'them as images -- text extraction will return nothing useful.')
    else:
        print('\nEvery page has a text layer. Still render before transcribing: '
              'Hebrew extracts partially reversed, and slides carry meaning in layout.')


def cmd_text(src):
    d = fitz.open(src)
    for i, pg in enumerate(d):
        print(f'\n{"="*20} PAGE {i+1} {"="*20}')
        print(pg.get_text())


def cmd_pages(src, outdir):
    dpi = int(arg('--dpi', 125))
    d = fitz.open(src)
    os.makedirs(outdir, exist_ok=True)
    for n in parse_range(arg('--range'), len(d)):
        p = os.path.join(outdir, f'p{n:03d}.png')
        d[n - 1].get_pixmap(dpi=dpi).save(p)
        print('wrote', p)


def _draw_grid(im, page_rect, step=100):
    """Overlay a faint PDF-point ruler on a rendered slide. `im` is the (already
    resized) slide image; `page_rect` is the source page's rect in points. Lines
    and labels are in POINTS -- the same units clip()/--box take -- so a rect
    read off this image needs no conversion."""
    from PIL import ImageDraw
    draw = ImageDraw.Draw(im)
    sx, sy = im.width / page_rect.width, im.height / page_rect.height
    x = 0
    while x <= page_rect.width:
        px = round(x * sx)
        draw.line([(px, 0), (px, im.height)], fill=(120, 170, 255), width=1)
        draw.text((px + 2, 2), str(x), fill=(40, 80, 200))
        draw.text((px + 2, im.height - 12), str(x), fill=(40, 80, 200))
        x += step
    y = 0
    while y <= page_rect.height:
        py = round(y * sy)
        draw.line([(0, py), (im.width, py)], fill=(120, 170, 255), width=1)
        draw.text((2, py + 1), str(y), fill=(40, 80, 200))
        draw.text((im.width - 26, py + 1), str(y), fill=(40, 80, 200))
        y += step
    return im


def cmd_sheets(src, outdir):
    """Stack `per` consecutive pages into one tall PNG, with a page-number strip
    above each so you can always tell which slide you are looking at.

    This is the READING pass, and its whole cost to you is the size of the images
    the model then reads. So the defaults are deliberately light -- 90 dpi, capped
    at 900 px wide -- which is plenty to read slide text and layout, and about
    half the pixels (so roughly half the tokens) of a 150 dpi / 1150 px render.
    Reach for a heavier render only when something is genuinely too small to read:

        --dpi 150 --width 1150     # sharper, ~2x the tokens; use sparingly

    --width is the real token lever (it caps the output size); --dpi only changes
    sharpness, and below ~75 dpi it also shrinks the image under the cap. Slides
    are never upscaled past their natural size.

    --grid overlays a PDF-point ruler on each slide (see _draw_grid): the same
    image you read the deck from also gives you clip() coordinates."""
    from PIL import Image, ImageDraw
    per, width = int(arg('--per', 4)), int(arg('--width', 900))
    dpi = int(arg('--dpi', 90))
    grid = '--grid' in sys.argv
    step = int(arg('--step', 100))
    d = fitz.open(src)
    os.makedirs(outdir, exist_ok=True)
    pages = parse_range(arg('--range'), len(d))
    for g in range(0, len(pages), per):
        group = pages[g:g + per]
        tiles = []
        for n in group:
            pm = d[n - 1].get_pixmap(dpi=dpi)
            im = Image.open(io.BytesIO(pm.tobytes('png'))).convert('RGB')
            if im.width > width:          # downscale only -- never blow a slide up
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            if grid:
                _draw_grid(im, d[n - 1].rect, step)
            strip = Image.new('RGB', (width, 18), (28, 100, 242))
            label = f'PAGE {n}' + ('  (grid in PDF points)' if grid else '')
            ImageDraw.Draw(strip).text((6, 4), label, fill='white')
            tiles.append((strip, im))
        total = sum(s.height + i.height for s, i in tiles)
        sheet = Image.new('RGB', (width, total), 'white')
        y = 0
        for s, i in tiles:
            sheet.paste(s, (0, y)); y += s.height
            sheet.paste(i, (0, y)); y += i.height
        name = f'g{group[0]:03d}-{group[-1]:03d}.png'
        sheet.save(os.path.join(outdir, name))
        print(name)
    print('groups:', (len(pages) + per - 1) // per)


def cmd_clip(src, page_no, out):
    """Render one rectangle of one page. Coordinates are PDF points; `probe`
    prints the page size, and a 16:9 slide is usually about 803 x 453."""
    box = [float(v) for v in arg('--box', '0,0,0,0').split(',')]
    dpi = int(arg('--dpi', 200))
    d = fitz.open(src)
    pg = d[int(page_no) - 1]
    r = fitz.Rect(*box) if any(box) else pg.rect
    pg.get_pixmap(dpi=dpi, clip=r).save(out)
    print('wrote', out, '| page rect was', pg.rect)


if len(sys.argv) < 3:
    sys.exit(__doc__)

cmd, src = sys.argv[1], sys.argv[2]
if cmd == 'probe':
    cmd_probe(src)
elif cmd == 'text':
    cmd_text(src)
elif cmd == 'pages':
    cmd_pages(src, sys.argv[3])
elif cmd == 'sheets':
    cmd_sheets(src, sys.argv[3])
elif cmd == 'clip':
    cmd_clip(src, sys.argv[3], sys.argv[4])
else:
    sys.exit(__doc__)
