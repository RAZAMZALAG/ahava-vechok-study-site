# -*- coding: utf-8 -*-
"""Take Hebrew sentences out of <math>, so they read right to left.

    py -3 fixmixed.py --report          # list what would change, touch nothing
    py -3 fixmixed.py part4.body.html   # rewrite one file
    py -3 fixmixed.py --all             # rewrite every body file

MathML lays its children out along the `direction` of the <math> element, which
is ltr. A formula whose children are

    <mtext>נייצר מדגם</mtext> X ∼ F <mtext>ונחשב</mtext> T

therefore puts "נייצר מדגם" at the LEFT end, and a Hebrew reader gets the
sentence backwards. In Part 4 §4.8 the bootstrap algorithm read from the wrong
end for exactly this reason.

The fix is not a CSS property -- `direction:rtl` on <math> would reverse the
formulas too. The Hebrew has to leave the formula: the line becomes ordinary
RTL HTML with the mathematics as separate <math> islands, each of which is
isolated by the shell and so keeps its place.

    <span class="mixed">נייצר מדגם <math>X ∼ F</math> ונחשב <math>T</math></span>

Only Hebrew that is a DIRECT child of <math> (or of its single top-level
<mrow>) is moved. Hebrew nested deeper -- a label under an <munder> brace, a
cell in an <mtable> -- is left alone: it cannot be lifted out without
destroying the construct, and it renders correctly anyway, because there the
Hebrew is a label attached to one term rather than a word in a sentence.
"""
import re, sys, glob, os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HEB = re.compile(r'[֐-׿]|&#x05')
TAG = re.compile(r'<(/?)([a-z]+)\b[^>]*?(/?)>')
MATH = re.compile(r'<math\b([^>]*)>(.*?)</math>', re.S)


def children(inner):
    """(tag, source) for each top-level child of a MathML fragment."""
    out, depth, start, tag = [], 0, None, None
    for m in TAG.finditer(inner):
        closing, name, selfclose = m.group(1), m.group(2), m.group(3)
        if closing:
            depth -= 1
            if depth == 0:
                out.append((tag, inner[start:m.end()]))
        elif selfclose:
            if depth == 0:
                out.append((name, m.group(0)))
        else:
            if depth == 0:
                start, tag = m.start(), name
            depth += 1
    return out


def convert(m):
    """Rewrite one <math> as a mixed RTL line, or return it unchanged."""
    attrs, inner = m.group(1), m.group(2)
    if not HEB.search(m.group(0)):
        return None
    kids = children(inner)
    # a formula often wraps everything in one <mrow>; look inside it
    if len(kids) == 1 and kids[0][0] == 'mrow':
        body = kids[0][1]
        kids = children(body[body.index('>') + 1:body.rindex('</mrow>')])
    if not any(t == 'mtext' and HEB.search(src) for t, src in kids):
        return None

    parts, run = [], []

    def flush():
        if run:
            parts.append(('math', ''.join(run)))
            run.clear()

    for tag, src in kids:
        if tag == 'mtext' and HEB.search(src):
            flush()
            text = re.sub(r'</?mtext[^>]*>', '', src)
            text = text.replace('&#xA0;', ' ').replace('&#160;', ' ')
            text = text.replace(' ', ' ').strip()
            if text:
                parts.append(('text', text))
        else:
            run.append(src)
    flush()

    # Refuse to split inside a bracketed group. `Gamma(α ידוע, λ)` has its
    # Hebrew between the parentheses, and lifting it out would leave `Gamma(α`
    # on one side and `, λ)` on the other -- two halves of an expression with
    # an unmatched bracket each. A formula only splits cleanly when every piece
    # that stays behind is balanced on its own.
    for kind, val in parts:
        if kind != 'math':
            continue
        depth = {'(': 0, '[': 0, '{': 0}
        close = {')': '(', ']': '[', '}': '{'}
        for tok in re.findall(r'<mo[^>]*>(.*?)</mo>', val):
            t = tok.strip()
            if t in depth:
                depth[t] += 1
            elif t in close:
                depth[close[t]] -= 1
        if any(v != 0 for v in depth.values()):
            return None

    out = []
    for kind, val in parts:
        out.append(val if kind == 'text' else f'<math>{val}</math>')
    return '<span class="mixed">' + ' '.join(out) + '</span>'


def run(path, report):
    src = open(path, encoding='utf-8').read()
    hits, out, pos = [], [], 0
    for m in MATH.finditer(src):
        new = convert(m)
        if new is None:
            continue
        hits.append((re.sub(r'<[^>]+>', ' ', new), ))
        out.append(src[pos:m.start()]); out.append(new); pos = m.end()
    out.append(src[pos:])
    if hits and not report:
        open(path, 'w', encoding='utf-8').write(''.join(out))
    return hits


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    report = '--report' in sys.argv
    files = sorted(glob.glob('*.body.html')) if ('--all' in sys.argv or report) else args
    total = 0
    for f in files:
        hits = run(f, report)
        if hits:
            print(f'{f}: {len(hits)}')
            if report:
                for (t,) in hits:
                    print('    ' + re.sub(r'\s+', ' ', t).strip()[:110])
        total += len(hits)
    print(f'{"would rewrite" if report else "rewrote"} {total} formulas')


if __name__ == '__main__':
    main()
