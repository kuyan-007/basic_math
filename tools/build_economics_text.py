"""Convert the engineering economics Word notes and their 19 embedded figures to HTML."""
from html import escape
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
# Transcriptions follow the original word/media numbering. Each equation gets its own block.
FIGURES = {
    1: [('outline', [
        '资金的时间价值：利息、实际与名义利率、现金流量图、资金等值计算。',
        '经济效益与费用估算：项目计算期、财务效益与费用。',
        '资金来源与融资方案：筹措方式、资金成本、债务资金偿还方式。',
        '财务分析：现金流量表与财务分析指标、盈利能力、偿债能力及财务生存能力。',
        '经济费用效益分析：影子价格、经济效益与费用比。',
        '不确定性分析：盈亏平衡分析、敏感性分析。',
        '方案经济比选：效益比选、费用比选、最低价格法及不同计算期的方案比选。',
        '改扩建项目经济分析：改扩建项目的财务分析。',
        '价值工程：概念、应用程序与常用方法、功能评价。',
    ])],
    2: [('math', r'F=P(1+in)')],
    3: [('math', r'F=P(1+i)^n')],
    4: [('math', r'i=\frac{I}{P}=\left(1+\frac{r}{m}\right)^m-1')],
    5: [('math', r'F=A\frac{(1+i)^n-1}{i}')],
    6: [('math', r'P=A\frac{(1+i)^n-1}{i(1+i)^n}')],
    7: [('math', r'\text{经营成本}=\text{外购原材料、燃料和动力费}+\text{工资及福利费}+\text{修理费}+\text{其他费用}')],
    8: [('text', '其他费用是指从制造费用、管理费用和营业费用中扣除了折旧费、摊销费、修理费、工资及福利费以后的其他部分。')],
    9: [('math', r'\text{生产成本}=\text{直接材料费}+\text{直接燃料和动力费}+\text{直接工资}+\text{其他直接支出}+\text{制造费用}'),
        ('math', r'\text{期间费用}=\text{管理费用}+\text{营业费用}+\text{财务费用}')],
    10: [('math', r'\text{资金成本率}=\frac{\text{筹资使用费}}{\text{筹资净额}}=\frac{\text{筹资使用费}}{\text{筹资额}-\text{筹资费用}}')],
    11: [('math', r'K_d=\frac{I(1-T)}{P_0(1-F)}=\frac{\text{每年付息额}\,(1-25\%)}{\text{债务现值}\,(1-\text{债务资金筹集费率})}')],
    12: [('math', r'K_s=\frac{D}{P_0(1-F)}')],
    13: [('math', r'K_s=\frac{D_1}{P_0(1-F)}+G')],
    14: [('math', r'K_s=R_f+\beta(R_m-R_f)'),
         ('text', '其中，Rₘ 与无风险报酬率 Rf 的差额为市场风险溢价，Rₘ 为市场投资组合报酬率，β 为股票贝塔系数。')],
    15: [('math', r'A_t=\frac{I_c}{n}+I_c\left(1-\frac{t-1}{n}\right)i')],
    16: [('math', r'P_t=\text{累计净现金流量开始出现正值的年份数}-1+\frac{\lvert\text{上年累计净现金流量}\rvert}{\text{当年净现金流量}}')],
    17: [('math', r'\text{出口产品影子价格（出厂价）}=\text{离岸价（FOB）}\times\text{影子汇率}-\text{出口费用}'),
         ('math', r'\text{进口投入物影子价格（到厂价）}=\text{到岸价（CIF）}\times\text{影子汇率}+\text{进口费用}')],
    18: [('math', r'\text{影子汇率}=\text{外币牌价}\times\text{影子汇率折算系数}')],
    19: [('math', r'\text{投入物影子价格（到厂价）}=\text{市场价格}+\text{国内运杂费}'),
         ('math', r'\text{产出物影子价格（出厂价）}=\text{市场价格}-\text{国内运杂费}')],
}

def build():
    with ZipFile(next((ROOT / 'upload').rglob('经济自己总结.docx'))) as file:
        body = ET.fromstring(file.read('word/document.xml'))[0]
        rels = {el.get('Id'): el.get('Target') for el in
                ET.fromstring(file.read('word/_rels/document.xml.rels'))}
    eqs = [v for parts in FIGURES.values() for k, v in parts if k == 'math'] + ['V=F/C']
    process = subprocess.run(['node', str(ROOT / 'tools/mathml.cjs')], input=json.dumps(eqs),
                             text=True, capture_output=True, check=True)
    equations = dict(zip(eqs, json.loads(process.stdout)))
    pages = {n: [] for n in range(1, 6)}
    def paragraph(value):
        return '<p>' + escape(value.strip()) + '</p>' if value.strip() else ''
    def formula(value):
        return '<div class="formula">' + equations[value] + '</div>'

    for number, p in enumerate(body):
        # The library's page anchors follow the converted Word pagination.
        page = 1 if number < 17 else 2 if number < 41 else 3 if number < 72 else 4 if number < 103 else 5
        parts = pages[page]
        text = ''
        for node in p.iter():
            if node.tag.endswith('}t'):
                text += node.text or ''
            if node.tag.endswith('}blip'):
                parts.append(paragraph(text))
                text = ''
                target = rels[next(iter(node.attrib.values()))]
                figure = int(Path(target).stem.removeprefix('image'))
                for kind, value in FIGURES[figure]:
                    if kind == 'math':
                        parts.append(formula(value))
                    elif kind == 'outline':
                        parts.append('<ul>' + ''.join('<li>'+escape(t)+'</li>' for t in value) + '</ul>')
                    else:
                        parts.append(paragraph(value))
        if number == 103:
            # This paragraph crosses the page break after the word “剩余功能”.
            first, after = text.split('或者成本偏低', 1)
            pages[4].append(paragraph(first))
            text = '或者成本偏低' + after
        if 'V=F/C' in text:
            parts.extend([paragraph(text.split('V=F/C')[0]), formula('V=F/C')])
        else:
            parts.append(paragraph(text))
    output = ROOT / 'library/text'
    output.mkdir(parents=True, exist_ok=True)
    for page, parts in pages.items():
        (output / f'economics-notes-{page:03}.html').write_text('\n'.join(filter(None, parts)))

if __name__ == '__main__':
    build()
