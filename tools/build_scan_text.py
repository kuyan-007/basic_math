"""Render the reviewed transcription of the seven scanned workbooks as HTML and MathML."""
from html import escape
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DATA = TOOLS / "scan_data"
DEST = ROOT / "library" / "text"

# Both formula handouts cover much of the same material, but use different page breaks.
FLUID_PAGES = {
    "fluids-foundations": [
        "gas visc", "visc2 hydro pressure", "forcefull force balance",
        "loss", "orifice resist parallel parallelratio trapezoid circle open", "manning energy darcy gallery",
    ],
    "fluids-formulas": [
        "gas visc visc2 hydro", "pressure force balance", "loss orifice parallel",
        "parallelratio trapezoid open manning darcy", "gallery sim",
    ],
}


def read_sections(path):
    sections = {}
    for line in path.read_text().splitlines():
        if not line:
            continue
        if line.startswith("@"):
            section = sections[line[1:]] = []
        elif line.startswith("= "):
            section.append(("math", line[2:]))
        elif line.startswith("$"):
            section.append(("insert", line[1:]))
        elif line.startswith("## "):
            section.append(("h",line[3:]))
        elif line.startswith("# "):
            section.append(("h", line[2:]))
        else:
            section.append(("p", line))
    return sections


def table(headers, rows):
    head = "".join(f'<th scope="col">{escape(str(v))}</th>' for v in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def periodic():
    elements = [tuple(line.split()) for line in (DATA/"elements.tsv").read_text().splitlines()]
    if len(elements) != 112:
        raise ValueError("Expected 112 entries from the source chart")
    periods = [(1,2), (3,10), (11,18), (19,36), (37,54), (55,86), (87,112)]
    overview = []
    for period, (first,last) in enumerate(periods,1):
        ids = list(range(first,last+1))
        if len(ids)==2:
            columns = [ids[0]] + [None]*16 + [ids[-1]]
        elif len(ids)==8:
            columns = ids[:2] + [None]*10 + ids[2:]
        elif len(ids) in (26,32):
            columns = ids[:2] + [("镧系" if first==55 else "锕系")] + ids[17:]
        else:
            columns = ids
        columns += [None]*(18-len(columns))
        row=[period]
        for z in columns:
            if isinstance(z,int):
                symbol, name, *_ = elements[z-1]
                row.append(f"{z} {symbol if z!=112 else 'Uub'} {name if z!=112 else ''}".rstrip())
            else:
                row.append(z or "")
        overview.append(row)
    html=["<h3>周期与族</h3>", table(["周期／族", *range(1,19)],overview),
          "<p>镧系位于第六周期（57–71），锕系位于第七周期（89–103）。下表保留资料采用的 2001 年相对原子质量数据，方括号中的数字为原表所列同位素的质量数。</p>",
          "<p>原表至 112 号，使用当时的暂定符号 Uub。现行符号为 Cn。第七周期末尾按原表留空。电子排布沿用资料中的写法，圆括号表示原表给出的可能排布，破折号表示原表未给出该项。</p>"]
    sup=str.maketrans("0123456789","⁰¹²³⁴⁵⁶⁷⁸⁹")
    for period,(first,last) in enumerate(periods,1):
        rows=[]
        for z in range(first,last+1):
            s,n,m,config=elements[z-1]
            config = re.sub(r"([spdf])(\d+)",lambda match:match[1]+match[2].translate(sup),config).replace("-"," ")
            nonmetals={1,2,*range(5,11),*range(14,19),*range(33,37),*range(52,55),85,86}
            classification="非金属" if z in nonmetals else "金属"
            if 21<=z<=30 or 39<=z<=48 or 57<=z<=80 or 89<=z<=112:
                classification+="、原表过渡元素区"
            if z in (43,61) or z>=84:
                classification+="、放射性"
            if z>=95:
                classification+="、原表标记为人造"
            rows.append((z, s if z!=112 else "Uub（现 Cn）", n if z!=112 else "原表未列", config, m, classification))
        html += [f"<h3>第{period}周期</h3>",table(["原子序数","符号","名称","外围电子排布","相对原子质量或质量数","原表标记"],rows)]
    html += ["<h3>稀有气体的电子层排布</h3>",table(["元素","K","L","M","N","O","P"],
             [("He",2,"","","","",""),("Ne",2,8,"","","",""),("Ar",2,8,8,"","",""),
              ("Kr",2,8,18,8,"",""),("Xe",2,8,18,18,8,""),("Rn",2,8,18,32,18,8)])]
    return "\n".join(html)


COMPUTER_TABLES = {
    (1,0): table(["发展","年代","电子器件"],[
        ("第一代","1946–1958","电子管"),("第二代","1958–1964","晶体管"),
        ("第三代","1964–1970","集成电路"),("第四代","1971 年起","大规模集成电路")]),
    (3,0): table(["总线类型","功能","传输方向"],[
        ("地址总线（AB）","传送主存储器地址码或外围设备码","单向"),
        ("数据总线（DB）","传送程序或数据信息","双向"),("控制总线（CB）","传送控制信息","一般为双向")]),
    (7,0): table(["容量单位（教材按二进制换算）","换算关系"],[
        ("bit","一个二进制位"),("B","8 bit = 1 B"),("KB","2¹⁰ B = 1024 B"),
        ("MB","2²⁰ B = 1024 KB"),("GB","2³⁰ B = 1024 MB"),("TB","2⁴⁰ B = 1024 GB")]),
    (7,1): table(["十进制数字","8421 BCD 码"],[(i,f"{i:04b}") for i in range(10)]),
}


def lookup_equations():
    return {path.stem:dict(line.split(maxsplit=1) for line in path.read_text().splitlines() if line.strip())
            for path in [DATA/(name+".txt") for name in ("mechanics-notes","materials-notes","electrical-notes","computing-systems")]}


def get_pages():
    output={}
    sections=read_sections(DATA/"fluids.txt")
    for doc,pages in FLUID_PAGES.items():
        for number,sequence in enumerate(pages,1):
            blocks=[block for section in sequence.split() for block in sections[section]]
            if doc=="fluids-foundations" and number==5:
                idx=blocks.index(("math",r"\chi=b+2h\sqrt{1+m^2}"))
                blocks.insert(idx+1,("p","原页湿周式第一项印为大写 B；按同页水面宽 B、底宽 b 的定义，湿周第一项应取底宽 b。"))
            if (doc,number) in {("fluids-foundations",5),("fluids-formulas",3)}:
                where=next(i for i,v in enumerate(blocks) if v[1].startswith("μ 为流量系数"))
                value="0.62" if doc=="fluids-foundations" else "0.82"
                blocks.insert(where+1,("p",f"本份资料列的小孔流量系数为 0.62，管嘴流量系数为 {value}。"))
            output[f"{doc}-{number:03}"]=blocks
    output["periodic-table-001"]=[("html",periodic())]
    equations=lookup_equations()
    corpus=json.loads((DATA/"transcription.json").read_text())
    figure_notes={}
    for name in ("scan_figure_notes.json","scan_other_figures.json"):
        figure_notes.update(json.loads((TOOLS/name).read_text()))
    source_notes = {
        "materials-notes-023": "原页关于夹角倍数的等式次序颠倒。按莫尔圆的角度关系，圆心角为相应物理转角的两倍。",
        "materials-notes-025": "原页部分化简式误把 Δy 写成 Δz；此处按弯矩 Mz 的定义使用 Δy。",
        "electrical-notes-009": "按相量除法，电容电流的直角坐标实部为负、虚部为正，与原页末尾所列 135° 一致。",
        "electrical-notes-010": "原页第三相电压的相量式漏印模值，此处按对称三相电压补上相电压有效值。",
        "electrical-notes-011": "原页电容支路的式子混用了瞬时值和相量记号，此处分列两种表示。",
        "electrical-notes-018": "原页的幅相展开漏列或混用了直流项，此处按同一傅里叶级数约定保留直流项，用 Aₙ 表示第 n 次谐波的幅值。",
    }
    for page,source in corpus.items():
        doc,number=page.rsplit("-",1)
        if doc in {"materials-notes","mechanics-notes"}:
            proof_name="scan_proof_mechanics"
        else:
            proof_name="scan_proof_electrical"
        proof_path=TOOLS/(proof_name+".py")
        if proof_path.exists():
            from importlib import import_module
            source=import_module(proof_name).correct(page,source)
        blocks=[]
        for kind,value in source:
            if kind=="f":
                expression=equations[doc][number+"."+value]
                if expression!="-":
                    blocks.extend(("math",line) for line in expression.split(" ; "))
            elif kind=="table":
                if doc=="computing-systems":
                    blocks.append(("html",COMPUTER_TABLES[int(number),int(value)]))
                elif page=="electrical-notes-003":
                    blocks.extend([("p","两个电阻串联、并联时的等效电阻分别为"),
                                   ("math",r"R_{\rm 串}=R_1+R_2"),
                                   ("math",r"\frac{1}{R_{\rm 并}}=\frac{1}{R_1}+\frac{1}{R_2}"),
                                   ("math",r"R_{\rm 并}=\frac{R_1R_2}{R_1+R_2}")])
            else:
                blocks.append((kind,value))
        if page in source_notes:
            blocks.append(("p",source_notes[page]))
        if page in figure_notes:
            blocks.append(("html",figure_notes[page]))
        output[page]=blocks
    for n,source in read_sections(DATA/"computing-sections.txt").items():
        blocks=[]
        for k,v in source:
            if k!="insert":
                blocks.append((k,v))
            elif v=="codes":
                blocks.append(("html",table(["真值","原码","反码","补码"],[
                    ("+91","01011011","01011011","01011011"),("−91","11011011","10100100","10100101"),
                    ("−92","11011100","10100011","10100100")])))
            else:
                blocks.append(("html",COMPUTER_TABLES[int(n),int(v[-1])]))
        output["computing-systems-"+n]=blocks
    return output


def main():
    pages=get_pages()
    formulas=sorted({s for page in pages.values() for kind,s in page if kind=="math"})
    rendered=json.loads(subprocess.run(["node",str(TOOLS/"mathml.cjs")],cwd=ROOT,input=json.dumps(formulas),
                                      capture_output=True,check=True,text=True).stdout)
    maths=dict(zip(formulas, rendered,strict=True))
    DEST.mkdir(parents=True,exist_ok=True)
    for name, blocks in pages.items():
        contents=[]
        for kind,value in blocks:
            if kind=="math":
                contents.append('<div class="formula">'+maths[value]+'</div>')
            elif kind=="html":
                contents.append(value)
            else:
                tag="h3" if kind=="h" else "p"
                contents.append(f"<{tag}>{escape(value)}</{tag}>")
        target=DEST/(name+".html")
        temp=target.with_suffix(".html.tmp")
        temp.write_text("\n".join(contents)+"\n")
        temp.replace(target)
    print(f"{len(pages)} scanned pages rendered, {len(formulas)} distinct transcribed expressions.")

if __name__=="__main__":
    main()
