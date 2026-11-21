"""Read proofread prose and display equations for the two mechanics handouts.

A numbered page header matches an original source page. An @ line references
the existing formula detection indices; an = line adds a transcribed equation.
"""
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("scan_data")


@lru_cache(maxsize=2)
def _pages(document):
    result = {}
    path = DATA / f"{document}.proof.txt"
    if not path.is_file():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("::"):
            page = line[2:].strip()
            blocks = result.setdefault(page, [])
        elif line.startswith("@"):
            blocks.extend(("f", index) for index in line[1:].split())
        elif line.startswith("="):
            blocks.append(("math", line[1:].strip()))
        elif line.startswith("#"):
            blocks.append(("h", line[1:].strip()))
        else:
            blocks.append(("p", line))
    return result


def correct(stem, blocks):
    document, _, page = stem.rpartition("-")
    if document not in {"materials-notes", "mechanics-notes"}:
        return blocks
    revised = _pages(document).get(page)
    if revised is None:
        return blocks
    expected = Counter((t, str(v)) for t, v in blocks if t in {"f", "table"})
    actual = Counter((t, v) for t, v in revised if t in {"f", "table"})
    if actual != expected:
        raise ValueError(f"Changed formula or table anchors on {stem}: {expected-actual}, {actual-expected}")
    return [list(item) for item in revised]
