# -*- coding: utf-8 -*-
"""Fold the worked solutions on an exam page away, so it can be sat.

    py -3 foldsol.py --report                 # what would change
    py -3 foldsol.py e2026a.body.html ...     # rewrite

The three real papers were written to be read: each card shows the question and
then the full solution underneath, always open. That is the wrong shape for the
one thing the pages are for -- you cannot practise a multiple-choice exam whose
answers are already on the screen. MOCK1 and MOCK2 were written the other way
round, with every solution inside a closed <details class="sol">, and this
brings the three papers into line.

Everything from the 📖 box to the end of the card goes inside the fold, the
reference box included. Which sub-lecture a question comes from is itself a
strong hint -- seeing "5.12 Jeffreys prior" before you start tells you most of
what the item is testing -- so it belongs behind the same click, exactly as it
does in the two mock papers.

Idempotent: a card whose solution is already folded is skipped.
"""
import re, sys, glob

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SLIDE = '<div class="slide">'
REF = '<div class="note">'
MARK = '<span class="t">📖 הפניה לחומר</span>'
SOLH = '<h4>פתרון</h4>'
TAGS = re.compile(r'<div\b|</div>')


def slide_end(s, open_at):
    """Index of the </div> that closes the .slide opening at `open_at`."""
    depth, i = 1, open_at + len(SLIDE)
    while depth:
        m = TAGS.search(s, i)
        if not m:
            raise SystemExit('unbalanced .slide at %d' % open_at)
        depth += -1 if m.group(0) == '</div>' else 1
        i = m.end()
    return i - len('</div>')


def fold(path, report):
    s = open(path, encoding='utf-8').read()
    out, pos, n = [], 0, 0
    for m in re.finditer(re.escape(SLIDE), s):
        end = slide_end(s, m.start())
        card = s[m.start():end]
        if SOLH not in card or 'details class="sol"' in card:
            continue
        # start of the fold: the 📖 box if there is one, else the solution head
        k = card.find(MARK)
        if k >= 0:
            k = card.rfind(REF, 0, k)
        else:
            k = card.find(SOLH)
        if k < 0:
            continue
        start = m.start() + k
        h3 = re.search(r'<h3>(.*?)</h3>', card, re.S)
        label = 'פתרון'
        if h3:
            t = re.sub(r'<[^>]+>', '', h3.group(1))
            num = re.match(r'\s*(סעיף\s*\d+)', t)
            if num:
                label = 'פתרון ' + num.group(1)
        out.append(s[pos:start])
        out.append('<details class="sol"><summary>✅ %s</summary><div class="dbody">\n'
                   % label)
        out.append(s[start:end].rstrip())
        out.append('\n    </div></details>\n    ')
        pos = end
        n += 1
    out.append(s[pos:])
    if n and not report:
        open(path, 'w', encoding='utf-8').write(''.join(out))
    return n


def main():
    report = '--report' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    files = args or sorted(glob.glob('e2*.body.html'))
    total = 0
    for f in files:
        n = fold(f, report)
        print(f'{f}: {n} solutions folded')
        total += n
    print(f'{"would fold" if report else "folded"} {total}')


if __name__ == '__main__':
    main()
