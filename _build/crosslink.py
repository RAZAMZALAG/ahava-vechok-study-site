# -*- coding: utf-8 -*-
"""Give every sub-lecture in Part 1-6 a strip of links to the places it is
practised, and keep those strips in sync with the rest of the site.

    py -3 crosslink.py            # rewrite the strips in part*.body.html
    py -3 crosslink.py --report   # print the mapping, change nothing

Why this is generated rather than hand-written: the mapping already exists in
the repository, only backwards. Every tutorial, homework and exam question
opens with a 📖 box naming the sub-lecture it comes from, so inverting those
links yields, for each sub-lecture, the exact list of questions that drill it --
derived from the material instead of from memory, and correct again the moment
a new page is added. What no inversion can produce is what the lectures never
say about each other (4.5 simulation and 5.13 Monte Carlo are one idea under
two names), so those live in EXTRA below and are merged in.

The strip is a <div class="prac">, not a .note/.warn/.deep: build.py folds
those into <details>, and this has to be visible the moment you land on the
anchor. Rerunning replaces the strips it wrote before, so it is idempotent.
"""
import os, re, sys, collections

SP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SP)

PARTS = [f'part{i}' for i in range(1, 7)]
# every page the strips may point at, and the label it gets in a chip. The
# first letter picks the colour family below, so keep the T / HW / E / M
# prefixes even if the course calls them something else.
BRAND = {**{f'T{i}': f'tutorial {i}' for i in range(1, 13)},
         **{f'HW{i}': f'HW{i}' for i in range(1, 8)}}
# the order the families appear in the strip: tutorials first, because that is
# where the worked example closest to an exam question lives
FAMILY = {'T': (0, ''), 'H': (1, 'hw'), 'E': (2, 'ex'), 'M': (3, 'ex')}
# a strip that lists everything lists nothing: past four chips of one colour the
# reader stops reading them. The most-drilled sub-lectures (2.4 MLE, 2.6 Fisher)
# genuinely appear a dozen times, so the cap is what keeps those strips legible.
CAP = 4
# sections whose heading does not shorten into a usable chip label
LABEL = {
    # 'T12|ipw': 'IPW',   # sections whose heading does not shorten well
}

# ---- the links no inversion can produce. Two kinds live here: one part
# pointing at another (the course teaches the same idea twice under two names),
# and the handful of sub-lectures that no 📖 box happens to cite even though a
# question clearly drills them. Sub-lecture id -> [(target, label), ...];
# the chip's colour comes from the target, so both kinds are written the same.
EXTRA = {
    # Empty on a fresh course. Fill it as you notice the two things inversion
    # cannot find: a part that teaches the same idea as another part under a
    # different name, and a sub-lecture no 📖 box happens to cite.
    # 'l45': [('Part 5.html#l513', 'Monte Carlo -- 5.13')],
}

SECRE = re.compile(r'<section class="lec" id="([^"]+)">')


def sections(html):
    """(id, start, end) for every lecture section, in document order."""
    hits = [(m.group(1), m.start()) for m in SECRE.finditer(html)]
    return [(sid, a, hits[i + 1][1] if i + 1 < len(hits) else len(html))
            for i, (sid, a) in enumerate(hits)]


def load_titles():
    """(page, section id) -> heading text, for the pages the strips point at."""
    out, pat = {}, re.compile(
        r'<section class="lec" id="([^"]+)">(.{0,400}?)</h2>', re.S)
    for page in BRAND:
        path = os.path.join(ROOT, page + '.html')
        if not os.path.exists(path):
            continue
        for m in pat.finditer(open(path, encoding='utf-8').read()):
            txt = re.sub(r'<[^>]+>', ' ', m.group(2))
            out[(page, m.group(1))] = re.sub(r'\s+', ' ', txt).strip()
    return out


def seclabel(page, sid, titles):
    """Short human label for one target section."""
    m = re.fullmatch(r'q(\d+)', sid)
    if m:
        return 'ש׳ ' + m.group(1)
    if re.fullmatch(r'th\d+', sid):
        return 'תיאוריה'
    if page + '|' + sid in LABEL:
        return LABEL[page + '|' + sid]
    title = re.sub(r'^[⭐\s]+', '', titles.get((page, sid), sid))
    if ' · ' in title:
        title = title.split(' · ')[-1]
    title = re.sub(r'\s*[—-]\s.*$', '', title)
    return title[:24].strip()


def build_index():
    """sub-lecture id -> {page: [ids of the sections that link to it]}."""
    rev = collections.defaultdict(lambda: collections.defaultdict(list))
    lower = {p.lower(): p for p in BRAND}
    for f in sorted(os.listdir(SP)):
        if not f.endswith('.body.html'):
            continue
        page = lower.get(f[:-len('.body.html')])
        if page is None:
            continue
        html = open(os.path.join(SP, f), encoding='utf-8').read()
        for sid, a, b in sections(html):
            for frag in set(re.findall(r'href="Part \d\.html#(l\d+)"', html[a:b])):
                if sid not in rev[frag][page]:
                    rev[frag][page].append(sid)
    return rev


def ranked(score):
    """Counter.most_common leaves ties in insertion order, and insertion order
    here comes from iterating a set of strings -- which Python hashes with a
    per-process seed, so two runs could disagree about which of two equally
    good tutorials to name. Break the tie on the page and section instead."""
    return sorted(score.items(),
                  key=lambda kv: (-kv[1],
                                  FAMILY[kv[0][0][0]][0],
                                  int(re.sub(r'\D', '', kv[0][0]) or 0),
                                  kv[0][0], kv[0][1]))


def cls_of(href):
    """The colour a chip gets, from the page it points at."""
    return 'pt' if href.startswith('Part') else FAMILY[href[0]][1]


def chips(lec, rev, titles):
    """(href, label, css class) for one sub-lecture, capped and in family order."""
    by_family = collections.defaultdict(list)
    for page in sorted(rev.get(lec, {}),
                       key=lambda p: (FAMILY[p[0]][0],
                                      int(re.sub(r'\D', '', p) or 0), p)):
        cls = FAMILY[page[0]][1]
        real = [s for s in rev[lec][page] if s not in ('map', 'intro')]
        if not real:                     # only the summary table mentions it
            by_family[cls].append((f'{page}.html', BRAND[page], cls))
            continue
        for sid in real[:2]:
            by_family[cls].append((f'{page}.html#{sid}',
                                   f'{BRAND[page]} · {seclabel(page, sid, titles)}',
                                   cls))
    for href, label in EXTRA.get(lec, []):
        c = cls_of(href)
        by_family[c].append((href, label, c))
    out, seen = [], set()
    for cls in ('', 'hw', 'ex', 'pt'):
        for chip in by_family[cls][:CAP]:
            if chip[0] not in seen:
                seen.add(chip[0]); out.append(chip)
    return out


def strip(lec, rev, titles):
    cs = chips(lec, rev, titles)
    if not cs:
        return ''
    rows = '\n'.join(
        '    <a href="%s"%s>%s</a>' % (h, f' class="{c}"' if c else '', t)
        for h, t, c in cs)
    return ('  <div class="prac">\n'
            '    <span class="t">🎯 איפה מתרגלים את זה</span>\n'
            + rows + '\n  </div>')


OLD = re.compile(r'\n[ \t]*<div class="prac">.*?</div>', re.S)

# ---- the same idea pointed the other way: an exam or homework question whose
# 📖 box names its sub-lectures but not the tutorial that works the identical
# example. The sub-lectures it already cites are the query -- whichever tutorial
# section cites the most of the same ones is the closest worked example there
# is, which is exactly what someone stuck on the question wants next.
# which pages get a hint, what family the hint points at, and how it opens.
# A question page wants the tutorial that works the same example; a tutorial
# wants the exam parts that turned out to test it, which is the one thing a
# tutorial cannot tell you about itself.
BOXES = (
    [(n, 'T', 'התרגול הקרוב ביותר') for n in
     ('e2024a', 'e2025a', 'e2026a', 'mock1',
      'hw1', 'hw2', 'hw3', 'hw4', 'hw5', 'hw6', 'hw7')]
    + [(f't{i}', 'EM', 'נבחן במועדים') for i in range(1, 13)]
)
HINT = re.compile(r'\n?[ \t]*<p class="prachint">.*?</p>', re.S)
MARK = '<span class="t">📖 הפניה לחומר</span>'
TAG = re.compile(r'<div\b|</div>')


def boxes_in(html):
    """(content start, content end) of every 📖 box body. Walks div depth
    rather than matching the first </div>, because a box may hold a nested
    <div class="eq"> and cutting at the first close would land inside it."""
    out, i = [], 0
    while True:
        k = html.find(MARK, i)
        if k < 0:
            return out
        # rewind to the <div class="note"> that opens this box
        start = html.rfind('<div', 0, k)
        depth, j = 1, k + len(MARK)
        while depth:
            t = TAG.search(html, j)
            if not t:
                return out
            depth += -1 if t.group(0) == '</div>' else 1
            j = t.end()
        out.append((k + len(MARK), j - len('</div>')))
        i = j


def hint(box_html, rev, titles, self_page, want, lead):
    """Links to append to one 📖 box, as HTML (or '').

    The sub-lectures the box already cites are the query. Whichever section of
    the wanted family cites the most of the same ones is the closest thing in
    the course to what this box is about -- computed from the material rather
    than guessed, and the one direction the box's author could not have known.
    """
    cited = set(re.findall(r'href="Part \d\.html#(l\d+)"', box_html))
    if not cited:
        return ''
    score = collections.Counter()
    for lec in sorted(cited):
        for page, sids in rev.get(lec, {}).items():
            if page[0] not in want or page == self_page:
                continue
            for sid in sids:
                if sid not in ('map', 'intro'):
                    score[(page, sid)] += 1
    have = set(re.findall(r'href="([A-Z0-9]+\.html[^"]*)"', box_html))
    picks = []
    for (page, sid), n in ranked(score):
        # one shared sub-lecture is not evidence of anything -- 4.13 gets a
        # passing mention in the tutorial on drawing histograms, and suggesting
        # that as "the closest worked example" to a permutation-test question
        # is worse than suggesting nothing. Two shared sub-lectures means the
        # tutorial section is about the same thing, not adjacent to it.
        if n < 2:
            break
        href = f'{page}.html#{sid}'
        if href in have or f'{page}.html' in have:
            continue
        picks.append((href, f'{BRAND[page]} · {seclabel(page, sid, titles)}'))
        have.add(href)
        if len(picks) == 2:
            break
    if not picks:
        return ''
    links = ' · '.join(f'<a href="{h}">{t}</a>' for h, t in picks)
    return f'\n      <p class="prachint">{lead}: {links}.</p>'


def do_boxes(rev, titles, report):
    n = 0
    for name, want, lead in BOXES:
        path = os.path.join(SP, name + '.body.html')
        if not os.path.exists(path):
            continue
        html = HINT.sub('', open(path, encoding='utf-8').read())
        self_page = name.upper()
        added, pieces, cursor = 0, [], 0
        for a, b in boxes_in(html):
            h = hint(html[a:b], rev, titles, self_page, want, lead)
            if not h:
                continue
            pieces.append(html[cursor:b]); pieces.append(h)
            cursor = b
            added += 1
        pieces.append(html[cursor:])
        if not report:
            open(path, 'w', encoding='utf-8').write(''.join(pieces))
        print(f'{name}: {added} boxes gained a tutorial link')
        n += added
    print(f'{n} 📖 boxes enriched')


# ---- the index's topic map. The site is organised by source file -- part,
# tutorial, homework, exam -- which is the wrong axis the week before an exam,
# when the question is "I need to revise odds ratios, what have I got?". Each
# row is one examinable topic and the sub-lectures that make it up; the other
# four columns are read out of the same reverse index the strips use.
TOPICS = [
    # ('Part 2 -- inference', [('maximum likelihood', 'l24 l25'), ...]),
]
MAPMARK = re.compile(r'<!-- topicmap -->.*?<!-- /topicmap -->', re.S)


def cell(lecs, rev, titles, want, limit=4):
    """One table cell: the sections of `want` that teach any of `lecs`."""
    score = collections.Counter()
    for lec in lecs:
        for page, sids in rev.get(lec, {}).items():
            if page[0] not in want:
                continue
            for sid in sids:
                score[(page, sid if sid not in ('map', 'intro') else '')] += 1
    picks, seen = [], set()
    for (page, sid), _ in ranked(score):
        if page in seen:
            continue
        seen.add(page)
        href = f'{page}.html' + (f'#{sid}' if sid else '')
        label = BRAND[page] + (f' · {seclabel(page, sid, titles)}' if sid else '')
        picks.append(f'<a href="{href}">{label}</a>')
        if len(picks) == limit:
            break
    return ' · '.join(picks) or '—'


def do_map(rev, titles, report):
    rows = []
    for part, topics in TOPICS:
        rows.append(f'      <tr><th colspan="5">{part}</th></tr>')
        for label, lecspec in topics:
            lecs = lecspec.split()
            partno = lecs[0][1]
            # one link for the whole run rather than one per sub-lecture: the
            # cell is a destination, not an inventory, and six numbered links
            # side by side made the topic column break a word per line
            num = lambda l: f'{l[1]}.{l[2:]}'
            span = num(lecs[0]) + (f'–{num(lecs[-1])}' if len(lecs) > 1 else '')
            rows.append(
                '      <tr>'
                f'<td><a href="Part {partno}.html#{lecs[0]}">{label}</a></td>'
                f'<td class="c"><span class="lt">{span}</span></td>'
                f'<td class="lnk">{cell(lecs, rev, titles, "T", 3)}</td>'
                f'<td class="lnk">{cell(lecs, rev, titles, "H", 3)}</td>'
                f'<td class="lnk">{cell(lecs, rev, titles, "EM", 4)}</td>'
                '</tr>')
    section = (
        '<!-- topicmap -->\n'
        '<section class="lec" id="topics">\n'
        '  <h2>מפת הנושאים</h2>\n'
        '  <div class="slide">\n'
        '    <h3>כל נושא, וכל מקום שבו הוא מופיע</h3>\n'
        '    <p>האתר מסודר לפי קובץ מקור — חלק, תרגול, תרגיל, מבחן. שבוע לפני '
        'המבחן זה הציר הלא נכון: השאלה היא ״אני צריך לחזור על יחס סיכויים, מה יש '
        'לי?״. הטבלה הזאת היא אותו חומר בחתך של נושא. היא <strong>נבנית '
        'אוטומטית</strong> מתוך תיבות ה-📖 של כל השאלות, ולכן היא מתעדכנת לבד '
        'כשנוסף דף.</p>\n'
        '    <div class="scrollx">\n'
        '    <table class="map topics">\n'
        '      <col class="topic"><col class="lec"><col><col><col>\n'
        '      <tr><th>נושא</th><th>בהרצאה</th><th>תרגול</th><th>תרגיל בית</th>'
        '<th>סעיפי מבחן</th></tr>\n'
        + '\n'.join(rows) + '\n'
        '    </table>\n'
        '    </div>\n'
        '  </div>\n'
        '</section>\n'
        '<!-- /topicmap -->')
    path = os.path.join(SP, 'index.body.html')
    html = open(path, encoding='utf-8').read()
    if not MAPMARK.search(html):
        sys.exit('!! no <!-- topicmap --> markers in index.body.html')
    if not report:
        open(path, 'w', encoding='utf-8').write(MAPMARK.sub(lambda _: section, html))
    print(f'topic map: {sum(len(t) for _, t in TOPICS)} rows')


def main():
    report = '--report' in sys.argv
    rev, titles = build_index(), load_titles()
    total = 0
    for part in PARTS:
        path = os.path.join(SP, part + '.body.html')
        html = OLD.sub('', open(path, encoding='utf-8').read())
        cuts = []
        for sid, a, b in sections(html):
            if not re.fullmatch(r'l\d+', sid):
                continue
            s = strip(sid, rev, titles)
            if s:
                cuts.append((html.index('</h2>', a) + len('</h2>'), s))
        out, cursor = [], 0
        for at, s in cuts:
            out.append(html[cursor:at]); out.append('\n' + s); cursor = at
        out.append(html[cursor:])
        if not report:
            open(path, 'w', encoding='utf-8').write(''.join(out))
        print(f'{part}: {len(cuts)} strips')
        total += len(cuts)
    print(f'{total} strips over {len(PARTS)} parts')
    do_boxes(rev, titles, report)
    do_map(rev, titles, report)
    if report:
        for lec in sorted(rev, key=lambda s: (len(s), s)):
            print(lec, ' | '.join(t for _, t, _ in chips(lec, rev, titles)))


if __name__ == '__main__':
    main()
