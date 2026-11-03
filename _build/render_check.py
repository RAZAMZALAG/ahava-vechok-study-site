# -*- coding: utf-8 -*-
"""Render a built page through headless Chrome and rasterise sample pages,
so you can actually LOOK at what you produced.

    py -3 render_check.py "..\\T7.html"
    py -3 render_check.py "..\\MOCK1.html" --open-solutions
    py -3 render_check.py "..\\Part 3.html" --no-print-css --pages 5,9,14,20

There is no way to know a page is right except to look at it. A normal
screenshot only captures the first viewport and will not travel to an anchor,
so --print-to-pdf is the only way to see a whole page.

Three traps this exists to remove, each of which cost real time:

1. **Chrome returns before it has written the PDF.** Fire-and-forget and then
   rasterise, and you will silently read the PREVIOUS run's file and draw
   confident conclusions from a stale render. This waits for the process AND
   checks the file's mtime is newer than the moment we started.

2. **The URL must be an absolute file:/// URL with forward slashes and %20 for
   spaces.** Course folders have spaces in their names; a relative or unencoded
   URL renders a blank page without complaining.

3. Chrome prints unrelated USB / GCM / app-install errors to stderr. They are
   noise; the line that matters is "bytes written to file".

For a mock exam pass --open-solutions: <details class="sol"> is closed by
design, so a plain render shows only the summary bars and you never see the
solutions. For a lecture part pass --no-print-css: the print stylesheet hides
the topbar and contents, which is right for printing and wrong for checking.
"""
import os, re, shutil, subprocess, sys, tempfile, time, urllib.parse

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium',
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    found = shutil.which('chrome') or shutil.which('google-chrome') or shutil.which('chromium')
    if found:
        return found
    sys.exit('!! Chrome not found. Add its path to CHROME_CANDIDATES in render_check.py.')


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def file_url(path):
    """Absolute file:/// URL, forward slashes, %20 for spaces (see trap 2)."""
    p = os.path.abspath(path).replace('\\', '/')
    if not p.startswith('/'):
        p = '/' + p
    return 'file://' + urllib.parse.quote(p)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    html = os.path.abspath(sys.argv[1])
    if not os.path.exists(html):
        sys.exit(f'!! no such file: {html}')

    work = tempfile.mkdtemp(prefix='rendercheck_')
    target = html

    # Variants are written to a temp copy so the real page is never touched.
    src = open(html, encoding='utf-8').read()
    if '--open-solutions' in sys.argv:
        src = src.replace('<details class="sol">', '<details class="sol" open>')
        print('variant: solutions forced open')
    if '--no-print-css' in sys.argv:
        src = src.replace('@media print{', '@media prtoff{')
        print('variant: print stylesheet neutralised')
    if '--dark' in sys.argv:
        # Chrome's headless print always renders light, and the theme toggle
        # writes to localStorage, which a fresh --print-to-pdf run never has.
        # Stamping the attribute the toggle would have set is the only way to
        # see what half the readers see.
        src = src.replace('<html lang="he" dir="rtl">',
                          '<html lang="he" dir="rtl" data-theme="dark">', 1)
        print('variant: dark theme forced')
    if src != open(html, encoding='utf-8').read():
        target = os.path.join(work, 'variant.html')
        open(target, 'w', encoding='utf-8').write(src)

    pdf = os.path.join(work, 'out.pdf')
    started = time.time()
    proc = subprocess.run(
        [find_chrome(), '--headless', '--disable-gpu', '--no-pdf-header-footer',
         f'--user-data-dir={os.path.join(work, "profile")}',
         f'--print-to-pdf={pdf}', file_url(target)],
        capture_output=True, text=True, timeout=300)

    # trap 1: do not trust the exit code, check the artefact
    for _ in range(60):
        if os.path.exists(pdf) and os.path.getmtime(pdf) >= started - 1:
            break
        time.sleep(0.5)
    else:
        print(proc.stderr[-2000:])
        sys.exit('!! Chrome produced no fresh PDF. See stderr above.')

    import fitz
    doc = fitz.open(pdf)
    n = len(doc)
    print(f'rendered {n} pages')

    spec = arg('--pages')
    if spec:
        # accepts  4  |  2,7,11  |  2-5  |  1,4-6
        want = []
        for part in spec.split(','):
            if '-' in part.strip('-'):
                a, b = part.split('-', 1)
                want += list(range(int(a), int(b) + 1))
            else:
                want.append(int(part))
        want = sorted(set(want))
    else:
        # spread the sample across the file rather than clustering at the front
        want = sorted({max(1, round(n * f)) for f in (0.15, 0.35, 0.55, 0.8)})
    want = [p for p in want if 1 <= p <= n]

    outdir = arg('--out', os.path.join(work, 'png'))
    os.makedirs(outdir, exist_ok=True)
    for p in want:
        png = os.path.join(outdir, f'page{p:03d}.png')
        doc[p - 1].get_pixmap(dpi=int(arg('--dpi', 105))).save(png)
        print('  ', png)

    print(f'\nNow READ those PNGs. Sample deliberately: include one heavy-formula '
          f'page and one table page.\nLooking for: formulas that did not render, '
          f'Latin runs flipped inside Hebrew sentences,\nbox titles that wrapped '
          f'onto a second line, figures overflowing their card.')


if __name__ == '__main__':
    main()
