"""Prepare standalone reading pages and update the existing library search index."""
import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = '<article class="study-text" data-reading-page>'
END = '</article>\n</body></html>'
BLOCKS = {'p', 'h2', 'h3', 'h4', 'li', 'tr', 'div', 'aside', 'section', 'dt', 'dd'}
DISALLOWED = {'script', 'img', 'picture', 'svg', 'canvas', 'iframe', 'embed', 'object', 'video',
              'audio', 'link', 'style', 'form', 'base', 'meta', 'input', 'button'}

class ReadingText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.words = []
        self.annotation = False

    def handle_starttag(self, tag, attrs):
        if tag in DISALLOWED:
            raise ValueError(f'Unexpected media or active element: {tag}')
        for name, value in attrs:
            if name.startswith('on') or name in ('src', 'href', 'srcdoc') or (
                    name == 'style' and 'url(' in value.lower()):
                raise ValueError(f'Unexpected attribute: {name}')
        if tag == 'annotation':
            self.annotation = True
        if tag in BLOCKS:
            self.words.append('\n')

    def handle_endtag(self, tag):
        if tag == 'annotation':
            self.annotation = False
        if tag in BLOCKS:
            self.words.append('\n')
        elif tag in ('th', 'td', 'mtd'):
            self.words.append(' ')

    def handle_data(self, data):
        if not self.annotation:
            self.words.append(data)

    def result(self):
        return '\n'.join(line.strip() for line in ''.join(self.words).splitlines() if line.strip())

def standalone(fragment, title):
    map_script = '<script defer src="../../assets/mind-map.js?v=adaptive2"></script>' if '<study-mind-map ' in fragment else ''
    return ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(title)}</title><link rel="stylesheet" href="../../assets/reading.css">'
            f'<link rel="stylesheet" href="../../assets/native-text.css">{map_script}</head>\n'
            '<body class="standalone-reading">\n' + START + '\n' + fragment.strip() + '\n' + END + '\n')

def publish(library, source):
    catalog = library / 'documents.js'
    docs = json.loads(catalog.read_text().split('=', 1)[1].strip().removesuffix(';'))
    inputs = {}
    for file in source.rglob("*"):
        if file.is_file():
            inputs.setdefault(file.name, []).append(file)
    prepared = []
    for doc in docs:
        matches = inputs.get(doc['source'], [])
        if len(matches) == 1:
            doc['sourceSha256'] = hashlib.sha256(matches[0].read_bytes()).hexdigest()
        for page in doc['pages']:
            path = library / 'text' / f"{doc['id']}-{page['sourcePage']:03}.html"
            source = path.read_text()
            fragment = source.split(START, 1)[1].rsplit(END, 1)[0] if source.startswith('<!doctype html>\n') else source
            parser = ReadingText()
            parser.feed(fragment)
            text = parser.result()
            if not text:
                raise ValueError(f'Empty reading page: {path}')
            page['text'] = text
            page['html'] = 'library/text/' + path.name
            prepared.append((path, standalone(fragment, page['title'])))
    for path, html in prepared:
        tmp = path.with_suffix('.html.tmp')
        tmp.write_text(html)
        tmp.replace(path)
    tmp = catalog.with_suffix('.js.tmp')
    tmp.write_text('window.DOCUMENTS=' + json.dumps(docs, ensure_ascii=False, separators=(',', ':')) + ';\n')
    tmp.replace(catalog)
    from build_chapters import compile_library
    compile_library(library)
    print(f'{len(docs)} documents, {len(prepared)} searchable HTML pages')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT / 'library')
    parser.add_argument('--source', type=Path, default=ROOT / 'upload')
    args = parser.parse_args()
    publish(args.library, args.source)
