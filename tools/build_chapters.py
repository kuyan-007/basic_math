"""Compile topic boundaries into standalone HTML lessons and a searchable curriculum."""
from collections import defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import argparse
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from flashcard_math import typeset_cards
from mind_maps import apply_charts, load_law_charts, lesson_summaries, mind_map
from publish_text import START, END, ReadingText, standalone

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / 'tools/curriculum'
VOID = {'br', 'hr', 'wbr', 'col', 'input', 'img', 'source', 'area', 'base', 'embed',
        'link', 'meta', 'param', 'track'}

class BlockBoundaries(HTMLParser):
    """Locate whole top-level elements without reserializing MathML or font geometry."""
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.offsets = []
        self.lines = [0, *(m.end() for m in re.finditer('\n', source))]
        self.depth = 0
        self.feed(source)
        self.close()
        if self.depth:
            raise ValueError('Unbalanced HTML in a source lesson')

    def handle_starttag(self, tag, attrs):
        if not self.depth:
            line, col = self.getpos()
            self.offsets.append(self.lines[line - 1] + col)
        if tag not in VOID:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag not in VOID:
            self.depth -= 1

def source_blocks(path):
    source = path.read_text()
    fragment = source.split(START, 1)[-1].rsplit(END, 1)[0].strip()
    native = fragment.startswith('<section class="native-text">')
    if native:
        fragment = fragment.split('>', 1)[1].rsplit('</section>', 1)[0].strip()
    offsets = BlockBoundaries(fragment).offsets
    return native, [fragment[a:b].strip() for a, b in zip(offsets, offsets[1:] + [len(fragment)])]

def plain(source):
    parser = ReadingText()
    parser.feed(source)
    return parser.result()

@dataclass
class Lesson:
    chapter: str
    title: str
    starts: list = field(default_factory=list)

def definitions(subject, documents):
    result = []
    path = RULES / (subject + '.txt')
    chapter = ''
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line.startswith('# '):
                chapter = line[2:]
            elif line.startswith('## '):
                if not chapter:
                    raise ValueError(f'Missing chapter before {line}')
                result.append(Lesson(chapter, line[3:]))
            elif line:
                doc, coordinate = line.split()
                page, block = map(int, coordinate.split(':'))
                if doc in documents:
                    result[-1].starts.append((doc, page, block))
    return [lesson for lesson in result if lesson.starts]

def fallback_lessons(doc, blocks):
    """Imported material can contribute new sections through its structural headings."""
    result = []
    titles = {}
    for page, (_, items) in blocks.items():
        for index, item in enumerate(items):
            heading = re.match(r'<h[234][ >]', item)
            if not result or heading:
                title = plain(item) if heading else doc['title']
                if title in titles:
                    titles[title].starts.append((doc['id'], page, index))
                else:
                    titles[title] = Lesson(doc['title'], title, [(doc['id'], page, index)])
                    result.append(titles[title])
    return result

def compile_library(library):
    library = Path(library)
    docs = json.loads((library/'documents.js').read_text().split('=', 1)[1].strip().removesuffix(';'))
    catalog = {'subjects': {}, 'documents': {}, 'cards': {}, 'lessonCards': []}
    locations = defaultdict(list)
    lesson_titles = {}
    destination = library/'lessons'
    destination.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=library) as work:
        staged = Path(work)
        for subject in dict.fromkeys(d['subject'] for d in docs):
            sources = {d['id']: d for d in docs if d['subject'] == subject}
            blocks = {}
            for doc_id, d in sources.items():
                blocks[doc_id] = {p['sourcePage']: source_blocks(library/'text'/Path(p['html']).name)
                                  for p in d['pages'] if p['title'] != '知识目录'}
            if subject == "law":
                apply_charts(blocks, load_law_charts(RULES))
            lessons = definitions(subject, sources)
            mapped = {a[0] for lesson in lessons for a in lesson.starts}
            for doc_id in sources:
                if doc_id in mapped:
                    continue
                lessons.extend(fallback_lessons(sources[doc_id], blocks[doc_id]))
            boundaries = defaultdict(dict)
            for lesson in lessons:
                for doc, page, block in lesson.starts:
                    if ((page, block) in boundaries[doc] or page not in blocks[doc]
                            or not 0 <= block < len(blocks[doc][page][1])):
                        raise ValueError(f'Invalid or duplicate boundary: {doc} {page}:{block}')
                    boundaries[doc][page, block] = lesson
            # Divide each source in its own reading order, then gather the pieces in curriculum order.
            ranges = defaultdict(list)
            for doc, pages in blocks.items():
                active = None
                for page, (native, elements) in pages.items():
                    span = []
                    for index, element in enumerate(elements):
                        if (page, index) in boundaries[doc]:
                            if span:
                                ranges[active].append((page, native, span))
                            active = (doc, page, index)
                            span = []
                        if active is None:
                            raise ValueError(f'Unassigned opening content: {doc} {page}:{index}')
                        span.append(element)
                    if span:
                        ranges[active].append((page, native, span))
            summaries = lesson_summaries(RULES, subject)
            card_file = RULES / f'cards_{subject}.json'
            lesson_cards = json.loads(card_file.read_text()) if card_file.exists() else {}
            formula_file = RULES / f'formulas_{subject}.json'
            formula_cards = json.loads(formula_file.read_text()) if formula_file.exists() else {}
            chapters = {}
            for lesson in lessons:
                identity = '\0'.join((subject, lesson.chapter, lesson.title))
                slug = subject + '-' + sha256(identity.encode()).hexdigest()[:12]
                if slug in lesson_titles:
                    raise ValueError(f'Duplicate lesson: {identity}')
                lesson_titles[slug] = lesson.title
                for question, answer in lesson_cards.get(lesson.title, []):
                    key = sha256((slug + '\0' + question).encode()).hexdigest()[:16]
                    catalog['lessonCards'].append({'id': 'study-' + key, 'subject': subject,
                                                   'lesson': slug, 'q': question, 'a': answer})
                for entry in formula_cards.get(lesson.title, []):
                    key = sha256((slug + '\0' + entry['q']).encode()).hexdigest()[:16]
                    catalog['lessonCards'].append({'id': 'formula-' + key, 'subject': subject,
                                                   'lesson': slug, 'kind': 'formula', **entry})
                parts, body = [], []
                summary = summaries.get(lesson.title)
                if summary:
                    body.append(mind_map(*summary))
                previous_doc = None
                for start in lesson.starts:
                    doc, _, _ = start
                    if previous_doc != doc:
                        if previous_doc is not None or len({key[0] for key in lesson.starts}) > 1:
                            body.append('<p class="source-label">'+escape(sources[doc]['title'])+'</p>')
                        previous_doc = doc
                    for page, native, elements in ranges[start]:
                        anchor = 'part-' + str(len(parts) + 1)
                        text = '\n'.join(elements)
                        wrapper = ' class="native-text"' if native else ''
                        body.append(f'<section id="{anchor}"{wrapper}>\n{text}\n</section>')
                        segment = {'anchor': anchor, 'text': plain(text)}
                        parts.append(segment)
                        locations[doc, page].append((slug, anchor, segment['text']))
                if summary and parts:
                    parts[0]['text'] += '\n' + plain(body[0])
                chapters.setdefault(lesson.chapter, []).append({'id':slug,'title':lesson.title,'parts':parts})
                (staged/(slug+'.html')).write_text(standalone('\n'.join(body), lesson.title))
            catalog['subjects'][subject] = [{'title': title, 'lessons': items} for title, items in chapters.items()]
            for doc,d in sources.items():
                links = []
                for p in d['pages']:
                    entries = locations[doc, p['sourcePage']]
                    links.append(list(entries[0][:2]) if entries else None)
                catalog['documents'][doc] = {'subject':subject, 'title':d['title'], 'source':d['source'], 'links':links}
        card_path = library/'cards.js'
        if card_path.exists():
            cards = json.loads(card_path.read_text().split('=',1)[1].strip().removesuffix(';'))
            overrides_path = RULES/'card_anchors.json'
            overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
            for c in cards:
                doc = next((d['id'] for d in docs if d['source']==c['source'] and d['subject']==c['subject']),None)
                if doc is None:
                    continue
                candidates = locations[doc,c['sourcePage']]
                if not candidates:
                    raise ValueError(f'No source location for card {c["id"]}')
                terms = grams(c['q']+' '+c['a'])
                if c['id'] in overrides:
                    match = overrides[c['id']]
                    candidates = [entry for entry in candidates if lesson_titles[entry[0]] == match]
                    if not candidates:
                        raise ValueError(f'Invalid card topic {match} for {c["id"]}')
                best = max(candidates, key=lambda entry: len(terms & grams(entry[2])) +
                           3*len(terms & grams(lesson_titles[entry[0]])))
                catalog['cards'][c['id']] = list(best[:2])
        typeset_cards(catalog['lessonCards'], expand_expressions=True)
        for f in staged.glob('*.html'):
            f.replace(destination/f.name)
        manifest = staged/'chapters.js'
        manifest.write_text('window.CURRICULUM='+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n')
        manifest.replace(library/'chapters.js')
    return catalog

def grams(s):
    words = re.findall(r'[\u3400-\u9fff]+|[a-z0-9]+',s.lower())
    return {word[i:i+2] for word in words for i in range(max(len(word)-1,1))}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT/'library')
    compile_library(parser.parse_args().library)
