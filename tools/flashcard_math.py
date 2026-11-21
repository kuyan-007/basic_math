"""Build offline MathML for formula recall cards and existing text-card expressions."""
from html import escape
from pathlib import Path
import json
import re
import subprocess

TOOLS = Path(__file__).resolve().parent
TOKENS = re.compile(r'\$([^$]+)\$')


def load_expression_markup():
    expressions = json.loads((TOOLS / 'curriculum/card_expressions.json').read_text())
    alternatives = '|'.join(re.escape(key) for key in sorted(expressions, key=len, reverse=True))
    pattern = re.compile(r'(?<![a-zA-Z0-9])(?:' + alternatives + r')(?![a-zA-Z0-9])')
    return lambda text: pattern.sub(lambda hit: '$' + expressions[hit[0]] + '$', text)


def typeset_cards(cards, *, expand_expressions=False):
    mark_existing = load_expression_markup() if expand_expressions else None
    fields = []
    formulas = {}
    for card in cards:
        for key, destination in [('q', 'questionHtml'), ('a', 'answerHtml')]:
            if card.get(destination):
                continue
            text = card[key]
            if mark_existing and '$' not in text:
                text = mark_existing(text)
            if '$' not in text:
                continue
            parts = TOKENS.split(text)
            if len(parts) == 1 or any('$' in part for part in parts[::2]):
                raise ValueError(f'Unmatched formula delimiter in {card["id"]} {key}')
            formulas.update(dict.fromkeys(parts[1::2]))
            fields.append((card, destination, parts))
    if not formulas:
        return
    result = subprocess.run(['node', str(TOOLS/'mathml.cjs')], input=json.dumps(list(formulas)),
                            text=True, capture_output=True)
    if result.returncode:
        raise ValueError('Cannot render card formula: ' + result.stderr[-4000:])
    rendered = dict(zip(formulas, json.loads(result.stdout), strict=True))
    for card, destination, parts in fields:
        card[destination] = ''.join(
            '<span class="card-formula">' + rendered[part] + '</span>' if i % 2 else escape(part)
            for i, part in enumerate(parts))
