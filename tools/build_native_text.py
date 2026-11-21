"""Turn the original two-column handouts into HTML paragraphs and display formulae.

PyMuPDF's tracing API exposes glyph IDs, including the delimiter pieces whose
PDF text mapping says 'space'. Re-map just the used math glyphs into a webfont,
and position them and the original fraction rules relative to the same baseline.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz

try:
    from fontTools import subset
except ImportError:
    # The host has fontTools in its separate system Python environment.
    from subprocess import check_output
    package = check_output(["/usr/bin/python3", "-c", "import fontTools;print(fontTools.__path__[0])"], text=True).strip()
    sys.path.append(str(Path(package).parent))
    from fontTools import subset
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from native_figures import FIGURES

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "library" / "text"
FONT_DIR = ROOT / "assets" / "native-fonts"
SOURCES = {
    "math-notes": "高数",
    "physics-notes": "物理",
    "chemistry-notes": "化学",
    "signals-notes": "信号与信息总结",
    "circuit-notes": "电路总结",
    "computing-notes": "计算机技术总结",
    "law-notes": "法律法规",
}
DET = r"\mathbf a\times\mathbf b=\begin{vmatrix}i&j&k\\a_x&a_y&a_z\\b_x&b_y&b_z\end{vmatrix}=\begin{vmatrix}a_y&a_z\\b_y&b_z\end{vmatrix}i+\begin{vmatrix}a_z&a_x\\b_z&b_x\end{vmatrix}j+\begin{vmatrix}a_x&a_y\\b_x&b_y\end{vmatrix}k"
MIXED = r"[\mathbf a,\mathbf b,\mathbf c]=(\mathbf a\times\mathbf b)\cdot\mathbf c=\begin{vmatrix}a_x&a_y&a_z\\b_x&b_y&b_z\\c_x&c_y&c_z\end{vmatrix}"
ESC = html.escape
CJK = re.compile(r"[\u3400-\u9fff]")
MATH = re.compile(r"[=≈≠≤≥≡∑∏∫→√∂×÷±∞∈≃∝]")
FONT_CACHE = {}


class NativeFont:
    def __init__(self, data):
        self.tag = "nf" + hashlib.sha256(data).hexdigest()[:12]
        self.font = TTFont(io.BytesIO(data))
        self.order = self.font.getGlyphOrder()
        self.em = self.font["head"].unitsPerEm
        if "cmap" not in self.font:
            self.font["cmap"] = newTable("cmap")
            self.font["cmap"].tableVersion = 0
            self.font["cmap"].tables = []
        self.cmap = self.font.getBestCmap() or {}
        self.reverse = {glyph: cp for cp, glyph in self.cmap.items()}
        self.used = {}
        self.shapes = {}

    def glyph(self, gid, cp):
        key = (gid, cp)
        if key in self.shapes:
            return self.shapes[key]
        glyph_name = self.order[gid]
        glyph = self.font["glyf"][glyph_name]
        if not glyph.numberOfContours:
            self.shapes[key] = None
            return None
        if (cp <= 32 or cp in self.used and self.used[cp] != glyph_name):
            cp = self.reverse.get(glyph_name, 0xF0000 + gid)
        if cp in self.used and self.used[cp] != glyph_name:
            cp = 0xF0000 + gid
        self.used[cp] = glyph_name
        bounds = tuple(v/self.em for v in (glyph.xMin,glyph.yMin,glyph.xMax,glyph.yMax))
        self.shapes[key] = chr(cp), bounds
        return self.shapes[key]

    def write(self):
        if not self.used: return ""
        table = CmapSubtable.newSubtable(12)
        table.platformID, table.platEncID, table.language = 3, 10, 0
        table.cmap = dict(self.used)
        self.font["cmap"].tables = [table]
        options = subset.Options()
        options.layout_features = []
        options.drop_tables.extend(["MATH", "BASE", "EBDT", "EBLC", "DSIG"])
        subs = subset.Subsetter(options=options)
        subs.populate(unicodes=list(self.used))
        subs.subset(self.font)
        self.font.flavor = "woff"
        self.font.save(FONT_DIR / (self.tag + ".woff"))
        return ("@font-face{font-family:"+self.tag+";src:url("+self.tag+".woff) format('woff');"
                "ascent-override:100%;descent-override:0%;line-gap-override:0%;font-display:block}")


@dataclass
class Piece:
    x: float
    y: float
    x1: float
    y1: float
    kind: str
    value: str
    size: float = 0
    base: float = 0
    family: str = ""
    origin: float = 0
    math: bool = False
    glyph: str = ""


def math_fonts(doc,page):
    result = {}
    for ref, _, _, name, *_ in page.get_fonts():
        name=name.split("+")[-1]
        data = doc.extract_font(ref)[3]
        if not data:continue
        digest = hashlib.sha256(data).digest()
        if digest not in FONT_CACHE:
            FONT_CACHE[digest] = NativeFont(data)
        result[name] = FONT_CACHE[digest]
    return result


def extract_chars(page, fonts):
    seen = set()
    for run in page.get_texttrace():
        if run["type"] == 3 or run["opacity"] < .05:continue
        size=run["size"]
        font=fonts.get(run["font"])
        for cp,gid,(x,baseline),box in run["chars"]:
            if cp < 0:continue
            identity=(round(x,2),round(baseline,2),run["font"],round(size,2),gid)
            if identity in seen:continue
            seen.add(identity)
            logical=chr(cp)
            if font and not CJK.match(logical):
                shape=font.glyph(gid,cp) if gid<len(font.order) else None
                if shape:
                    char,(xmin,ymin,xmax,ymax)=shape
                    if logical.isspace():
                        logical=char if ord(char)<0xF0000 else ""
                    yield Piece(x+xmin*size, baseline-ymax*size, x+xmax*size,
                        baseline-ymin*size, "char",logical,size,baseline,font.tag,x,"Math" in run["font"],char)
                    continue
            if logical.isspace():continue
            yield Piece(x,baseline-size*.81,box[2],baseline+size*.1,
                "char",logical,size,baseline,"nativeBody",x)



def gather_rules(page):
    for drawing in page.get_drawings():
        r = drawing["rect"]
        for item in drawing["items"]:
            if item[0]=="re":
                b=item[1]
                if b.width < .05 or b.height < .05:continue
                if b.y0 < 30 and b.width > 280:continue
                # Underlines, fraction bars and determinant rules only.
                if min(b.width,b.height)<=2 and max(b.width,b.height)<285:
                    yield Piece(*b,"rule","")
        # The law handout outlines its grouping braces with vector paths.
        # Use a textual scalable brace for each outline.
        if len(drawing["items"])>2 and r.height>r.width*3 and 1<r.width<7:
            yield Piece(*r,"brace","{")


def matches_heading(line):
    return (len(line)<70 and (re.match(r"^(第.{1,8}[章节]|[一二三四五六七八九十]+[、．]|\d+[.、．]\s*[^\d])",line)
                              or (len(line)<=10 and len(CJK.findall(line))>=2 and not re.search(r"[，。；：=（）()\d]",line))))


def plain_text(chars):
    # Keep visual word spaces for English names, while allowing CJK to wrap.
    ordered=sorted(chars,key=lambda c:c.origin)
    text=""
    prev=None
    for c in ordered:
        if prev and c.origin-prev.x1>1.5 and prev.value.isascii() and prev.value.isalnum() and c.value.isascii() and c.value.isalnum():
            text+=" "
        text+=c.value
        prev=c
    return text


def clusters(pieces):
    # A vertical interval union keeps an entire radical, fraction or matrix
    # together when its glyphs are broken over multiple PDF text blocks.
    pending=[]
    bottom=0
    for p in sorted(pieces,key=lambda e:e.y):
        if pending and p.y>bottom+2.8:
            yield pending
            pending=[]
        bottom=max(bottom if pending else p.y1,p.y1)
        pending.append(p)
    if pending:yield pending


def render_geometry(parts):
    left=min(min(p.origin,p.x) if p.kind=="char" else p.x for p in parts)
    right=max(p.x1 for p in parts)
    top=min(p.y for p in parts)
    bottom=max(p.y1 for p in parts)
    # 9 PDF points represent the nominal body-text em in these handouts.
    # Use em coordinates so browser font-size preferences affect math as well.
    scale=9
    def em(v):return f"{v/scale:.4f}em"
    out=['<div class="native-equation"><div class="native-layout" style="width:'+em(right-left+3)+';height:'+em(bottom-top+3)+'">']
    rules=[p for p in parts if p.kind!="char"]
    chars=sorted((p for p in parts if p.kind=="char"),key=lambda p:(round(p.base,1),p.x))
    for p in rules:
        pos="left:"+em(p.x-left+1)+";top:"+em(p.y-top+1)+";"
        if p.kind=="rule":
            out.append('<i class="native-rule" aria-hidden="true" style="'+pos+'width:'+em(p.x1-p.x)+';height:'+em(p.y1-p.y)+'"></i>')
        elif p.kind=="brace":
            height=p.y1-p.y
            out.append('<i class="native-brace" style="'+pos+'font-size:'+em(height)+';transform:scaleX('+f"{2*(p.x1-p.x)/height:.4f}"+')">{</i>')
    # Use an outer positioned span in document units and an inner glyph in its
    # own font size. This prevents offsets from changing with super/subscripts.
    for p in chars:
        pos="left:"+em(p.origin-left+1)+";top:"+em(p.base-top+1-p.size)
        face='font:'+em(p.size)+'/1 '+p.family
        render_as=(' class="native-variant" data-glyph="'+ESC(p.glyph)+'"' if p.glyph and p.glyph!=p.value else '')
        out.append('<span class="native-glyph" style="'+pos+'"><span'+render_as+' style="'+face+'">'+ESC(p.value)+'</span></span>')
    return ''.join(out)+'</div></div>'


def render_equations(parts):
    # Multiple independent formulae in one PDF row are separated by a wide
    # gutter. Split only when both sides contain a relation so that fractions,
    # subscripts and determinant columns stay with their parent expression.
    sections=[]
    current=[]
    right=0
    for p in sorted(parts,key=lambda v:v.x):
        if current and p.x-right>13:
            sections.append(current)
            current=[]
        current.append(p)
        right=max(right if len(current)>1 else p.x1,p.x1)
    if current:sections.append(current)
    if len(sections)>1 and all(any(c.value in ('=','≈','≤','≥','⇔','⟺','⟹','>','<') for c in sec) for sec in sections):
        return ''.join(render_geometry(sec) for sec in sections)
    return render_geometry(parts)


def render_cluster(parts):
    chars=[p for p in parts if p.kind=="char"]
    if not chars:return ''
    # Separate headings and ordinary sentences from formulae. A multi-baseline
    # expression is kept intact even if one of its rows consists solely of text.
    baselines=[p.base for p in chars]
    one_line=max(baselines)-min(baselines)<1.65
    line=plain_text(chars) if one_line else ''
    if one_line and re.match(r"^.*[.．…]{3,}\s*\d*\s*$",line):
        line=re.sub(r"[.．…]{3,}.*","",line)
        return '<p>'+ESC(line)+'</p>' if line else ''
    has_rules=len(parts)>len(chars)
    math=any(p.math for p in chars) or MATH.search(line)
    if one_line and not has_rules and not math:
        tag='h3' if matches_heading(line) and (max(p.size for p in chars)>=10.2 or re.match(r'^第.{1,8}[节章]|^\d+[.、．]',line)) else 'p'
        return f'<{tag}>{ESC(line)}</{tag}>'
    if one_line and not has_rules:
        ordered=sorted(chars,key=lambda p:p.origin)
        # e.g. “平面方程：” preceding a formula. Keep it as normal wrapping prose.
        for at, token in enumerate(ordered):
            if token.value in ('：', ':') and at+1<len(ordered):
                label=''.join(p.value for p in ordered[:at+1])
                if CJK.search(label) and not MATH.search(label):
                    return '<p>'+ESC(label)+'</p>'+render_equations(ordered[at+1:])
                break
    return render_equations(parts)


def crystal_table():
    columns=["晶体的类型","离子晶体","原子晶体","分子晶体","金属晶体"]
    rows=[
        ["晶格结点上的微粒","正、负离子","原子","分子","金属原子或金属离子"],
        ["微粒间的作用力","离子键","共价键","分子间力、氢键","金属键"],
        ["熔点、沸点","较高","高","低","一般较高"],
        ["硬度","较大","大","小","一般较大"],
        ["延展性","差","差","差","良好"],
        ["导电性","水溶液或熔融态导电性良好","绝缘体或半导体","绝缘体","良导体"],
        ["实例","NaCl、MgO、K₂SO₄","金刚石、Si、Ge、SiO₂、SiC、GaAs","CO₂、H₂O、CH₄、CCl₄、I₂、He","Na、Al、Fe、Cu、合金"],
    ]
    head=''.join('<th scope="col">'+v+'</th>' for v in columns)
    body=''.join('<tr><th scope="row">'+r[0]+'</th>'+''.join('<td>'+v+'</td>' for v in r[1:])+'</tr>' for r in rows)
    return '<div class="native-table"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def render_page(doc,page,doc_id,mathml):
    pieces=list(extract_chars(page,math_fonts(doc,page)))
    pieces.extend(gather_rules(page))
    midpoint=page.rect.width/2
    output=[]
    for col in range(2):
        column=[]
        events=[]
        def side(x):return int(x>=midpoint)
        for p in pieces:
            if side(p.origin if p.kind=="char" else p.x)!=col:continue
            # All handouts position their page numerals at the bottom centre.
            if p.kind=="char" and p.value.isdigit() and abs(p.x-midpoint)<14 and p.base>page.rect.height*.90:continue
            if doc_id=='math-notes' and page.number==1 and col==0 and (281<p.y<322 or 329<p.y<368):continue
            column.append(p)
        for cluster in clusters(column):
            events.append((min(p.y for p in cluster),render_cluster(cluster)))
        if doc_id=='math-notes' and page.number==1 and col==0:
            events.append((283,'<p>向量叉积的行列式展开</p><div class="native-equation">'+mathml[DET]+'</div>'))
            events.append((331,'<p>混合积的行列式表示</p><div class="native-equation">'+mathml[MIXED]+'</div>'))
        captions=FIGURES.get(doc_id,{}).get(page.number+1,[])
        figures=[im for im in page.get_image_info() if (im["width"],im["height"])!=(1080,1145)]
        for idx,im in enumerate(figures):
            if side(im["bbox"][0])!=col or idx>=len(captions):continue
            parts = re.split(r'\$([^$]+)\$', captions[idx])
            caption = ''.join('<div class="native-equation">'+mathml[value]+'</div>' if n % 2
                              else '<p class="native-figure-text">'+ESC(value)+'</p>'
                              for n, value in enumerate(parts) if value)
            if doc_id=='chemistry-notes' and page.number==2:
                caption=crystal_table()
            for extra in captions[len(figures):]:
                if extra.startswith('$'):caption+='<div class="native-equation">'+mathml[extra[1:-1]]+'</div>'
            events.append((im["bbox"][1],caption))
        flow=[]
        for _,content in sorted(events,key=lambda e:e[0]):
            if not content:continue
            if (flow and re.fullmatch(r"<p>[^<>]*</p>",flow[-1]) and re.fullmatch(r"<p>[^<>]*</p>",content)
                    and len(flow[-1])>27 and not re.search(r"[。；：？！:;!?]</p>$",flow[-1])
                    and not re.match(r"<p>(?:[①-⑳（(【一二三四五六七八九十第0-9]|[A-Za-z]+[：:])",content)):
                flow[-1]=flow[-1][:-4]+content[3:]
            else:
                flow.append(content)
        output.extend(flow)
    return '<section class="native-text">\n'+'\n'.join(output)+'\n</section>\n'


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    FONT_DIR.mkdir(parents=True,exist_ok=True)
    latex = [DET, MIXED] + [expr for pages in FIGURES.values() for captions in pages.values()
                            for item in captions for expr in re.findall(r'\$([^$]+)\$', item)]
    xml=json.loads(subprocess.check_output(['node',str(ROOT/'tools/mathml.cjs')], input=json.dumps(latex).encode()))
    mathml=dict(zip(latex,xml))
    for formula in (DET,MIXED):
        mathml[formula]=mathml[formula].replace('<mo fence="true">∣</mo>','').replace("<mtable ",'<mtable class="native-determinant" ')
    count=0
    for doc_id,name in SOURCES.items():
        with fitz.open(next((ROOT/'upload').rglob(name+'.pdf'))) as doc:
            for page in doc:
                result=render_page(doc,page,doc_id,mathml)
                (OUTPUT/f'{doc_id}-{page.number+1:03}.html').write_text(result)
                count+=1
        print(doc_id,len(result),flush=True)
    css=[f.write() for f in FONT_CACHE.values()]
    (FONT_DIR/'faces.css').write_text('\n'.join(css)+'\n')
    print(f'{count} pages generated')


if __name__=='__main__':
    main()
