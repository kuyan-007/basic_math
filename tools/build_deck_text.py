"""Rebuild four slide decks as text and native MathML.

Run this with the project’s PyMuPDF-enabled Python. Technical source files are
UTF-8 transcriptions of individual slides. Tables, headings and formula lines
are marked explicitly, so a rebuild never needs OCR to interpret their layout.
"""
from html import escape
import json
from pathlib import Path
import re
import subprocess

import fitz

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SOURCES = TOOLS / "deck_sources"
PAGE_RANGES = {
    "chemistry-formulas": range(1, 10),
    "physics-formulas": range(1, 9),
    "economics-focus": range(2, 40),
    "law-focus": range(2, 35),
}
NUMBERED = re.compile(r"^(?:[（(]?[0-9]{1,2}[）).、-]|[①-⑩]|[（(][ABCD][）)]|[ABCD][.、]|【|例题|解析|答案)")
END = re.compile(r"[。？！；：:）)]$")


def technical_pages(doc_id):
    pages = {}
    for line in (SOURCES / f"{doc_id}.txt").read_text().splitlines():
        if line.startswith("@"):
            number = int(line[1:])
            if number in pages:
                raise ValueError(f"Duplicate page {doc_id}-{number}")
            pages[number] = []
        elif line.strip():
            pages[number].append(line)
    return pages


def law_paragraphs(block):
    paragraphs = []
    for line in block.strip().splitlines():
        line = re.sub(r"(?<=[\u4e00-\u9fff]) +(?=[\u4e00-\u9fff])", "", line.strip())
        line = re.sub(r"\s{2,}", "　", line)
        if not line:
            continue
        if not paragraphs or NUMBERED.match(line) or END.search(paragraphs[-1]):
            paragraphs.append(line)
        else:
            paragraphs[-1] += line
    return paragraphs


def law_pages():
    path, = (ROOT / "upload").rglob("法律法规重点总结.pdf")
    pages = {}
    with fitz.open(path) as pdf:
        for number in PAGE_RANGES["law-focus"]:
            blocks = [b for b in pdf[number - 1].get_text("blocks") if b[1] < 510 and b[4].strip()]
            if number == 16:
                # This slide has two separate columns of related legal definitions.
                blocks.sort(key=lambda b: (b[1] > 52, b[0] >= 440, b[1], b[0]))
            else:
                blocks.sort(key=lambda b: (round(b[1] / 3), b[0]))
            content = []
            for block in blocks:
                text = block[4].strip()
                if number == 11 and block[1] > 240:
                    if "要约人发出要约" not in "".join(content):
                        content.append("要约人发出要约，受要约人向要约人作出承诺。")
                    continue
                if number == 27 and all(s.strip() in {"国家标准、行业标准","地方标准","企业标准","＞","＜","严于"} for s in text.splitlines()):
                    if "图中将地方标准" not in "".join(content):
                        content.append("图中将地方标准、企业标准分别与国家标准和行业标准比较，标示地方标准、企业标准可以更严。")
                    continue
                paragraphs = law_paragraphs(text)
                if block[1] < 45 or text == "课堂总结":
                    paragraphs[0] = "# " + paragraphs[0]
                content.extend(paragraphs)
            pages[number] = content
    return pages


def table_html(rows):
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Table rows with inconsistent widths")
    heads = "".join(f'<th scope="col">{escape(cell)}</th>' for cell in rows[0])
    body = []
    for row in rows[1:]:
        cells = "".join(f"<td>{escape(cell)}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return '<div class="table-scroll"><table><thead><tr>' + heads + '</tr></thead><tbody>' + "".join(body) + '</tbody></table></div>'


def render_page(lines, maths):
    output = []
    rows = []
    for line in [*lines, ""]:
        is_row = line.startswith("|")
        if is_row:
            cells = [s.strip() for s in line.strip("|").split("|")]
            if rows and len(rows[0]) != len(cells):
                output.append(table_html(rows))
                rows = []
            rows.append(cells)
            continue
        if rows:
            output.append(table_html(rows))
            rows = []
        if line.startswith("# "):
            output.append(f"<h3>{escape(line[2:])}</h3>")
        elif line.startswith("= "):
            output.append('<div class="formula">' + maths[line[2:]] + '</div>')
        elif line:
            output.append(f"<p>{escape(line)}</p>")
    return "\n".join(output) + "\n"


def build():
    decks = {doc: technical_pages(doc) for doc in PAGE_RANGES if doc != "law-focus"}
    decks["law-focus"] = law_pages()
    equations = list(dict.fromkeys(
        line[2:] for pages in decks.values() for lines in pages.values()
        for line in lines if line.startswith("= ")
    ))
    rendered = subprocess.run(
        ["node", str(TOOLS / "mathml.cjs")], cwd=ROOT,
        input=json.dumps(equations), capture_output=True, text=True,
    )
    if rendered.returncode:
        raise RuntimeError(rendered.stderr)
    maths = dict(zip(equations, json.loads(rendered.stdout), strict=True))
    out = ROOT / "library" / "text"
    out.mkdir(exist_ok=True, parents=True)
    for doc, pages in decks.items():
        if set(pages) != set(PAGE_RANGES[doc]):
            raise ValueError(f"Incomplete page sequence in {doc}")
        for n, lines in pages.items():
            target = out / f"{doc}-{n:03}.html"
            target.write_text(render_page(lines, maths))
    print(f"Built {sum(map(len, decks.values()))} HTML pages with {len(equations)} distinct equations.")


if __name__ == "__main__":
    build()
