"""Compile curated subject summaries into Mermaid mindmap markup."""
from html import escape
import json


def topic_tree(chart, key):
    tree = {}
    for path in chart['paths']:
        if len(path) < 2:
            raise ValueError(f'Incomplete topic path at {key}')
        branch = tree
        for label in path:
            if not isinstance(label, str) or not label.strip() or '\n' in label:
                raise ValueError(f'Invalid topic label at {key}')
            branch = branch.setdefault(label, {})
    if not tree:
        raise ValueError(f'Empty mind map at {key}')
    return tree


def lesson_summaries(directory, subject):
    path = directory / f'maps_{subject}.json'
    if not path.exists():
        return {}
    return {key: (chart['title'], topic_tree(chart, key))
            for key, chart in json.loads(path.read_text()).items()}


def load_law_charts(directory):
    charts = {}
    for source in sorted(directory.glob('law_flows_*.json')):
        for key, chart in json.loads(source.read_text()).items():
            if key in charts:
                raise ValueError(f'Duplicate flowchart at {key}')
            doc, point = key.split()
            page, index = map(int, point.split(':'))
            charts[key] = (doc, page, index, chart['title'], topic_tree(chart, key))
    return charts.values()


def mind_map(title, tree):
    root, topics = next(iter(tree.items())) if len(tree) == 1 else (title, tree)
    lines = ['mindmap', f'  root(({root}))']

    def add_topics(children, depth):
        for label, descendants in children.items():
            lines.append('  ' * depth + label)
            add_topics(descendants, depth + 1)

    add_topics(topics, 2)
    return ('<figure class="study-map" aria-label="' + escape(title) + '">'
            + '<figcaption>' + escape(title) + '</figcaption>'
            + '<study-mind-map class="mermaid-map"><pre>' + escape('\n'.join(lines))
            + '</pre></study-mind-map></figure>')


def apply_charts(blocks, charts):
    for doc, page, index, title, tree in charts:
        if doc not in blocks:
            continue
        items = blocks[doc][page][1]
        original = items[index]
        chart = mind_map(title, tree)
        if original.startswith('<div class="native-equation">'):
            items[index] = (chart + '<details class="law-source"><summary>查看讲义原文</summary>'
                            + original + '</details>')
        elif original.startswith('<h3>'):
            items[index] = original + chart
        else:
            raise ValueError(f'Unexpected summary source at {doc} {page}:{index}')
