"""Build the study library with PyMuPDF, Pillow, NumPy, LibreOffice and Chinese Tesseract."""
import argparse
import fcntl
import hashlib
from html import escape
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageDraw
from publish_text import standalone

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
    "高数": ("math", "math-notes", "高等数学知识梳理"),
    "物理": ("physics", "physics-notes", "大学物理知识梳理"),
    "物理高频考点公式总结": ("physics", "physics-formulas", "物理高频考点与公式"),
    "化学": ("chemistry", "chemistry-notes", "普通化学知识梳理"),
    "化学高频考点公式总结": ("chemistry", "chemistry-formulas", "化学高频考点与公式"),
    "化学元素周期表图_高清版": ("chemistry", "periodic-table", "元素周期表"),
    "理论力学总结": ("mechanics", "mechanics-notes", "理论力学考点详解"),
    "材料力学总结": ("materials", "materials-notes", "材料力学考点详解"),
    "公共基础流体力学高频公式": ("fluids", "fluids-foundations", "流体力学基础公式"),
    "流体力学高频公式总结": ("fluids", "fluids-formulas", "流体力学公式与例图"),
    "电路总结": ("circuit", "circuit-notes", "电路知识梳理"),
    "电工电子总结": ("circuit", "electrical-notes", "电工与电子技术"),
    "信号与信息总结": ("signals", "signals-notes", "信号与信息技术"),
    "计算机技术总结": ("computing", "computing-notes", "计算机技术知识梳理"),
    "计算机总结": ("computing", "computing-systems", "计算机系统与技术基础"),
    "工程经济重点总结": ("economics", "economics-focus", "工程经济重点与例题"),
    "经济自己总结": ("economics", "economics-notes", "工程经济学习笔记"),
    "法律法规": ("law", "law-notes", "工程法规知识梳理"),
    "法律法规重点总结": ("law", "law-focus", "工程法规重点与例题"),
}
BRANDED_PRINT = {"mechanics-notes", "materials-notes", "computing-systems", "electrical-notes"}
TILED_MARKS = {"mechanics-notes", "fluids-foundations"}
DECKS = {"law-focus", "economics-focus"}
FORMULA_SLIDES = {"chemistry-formulas", "physics-formulas"}
QR = (1080, 1145)
# Exact inventory of decorative images in the two presentation masters.
DECORATION = {(1919,1080), (170,174), (609,342), (1802,896), (1651,14), (258,258), (652,34)}
BRAND_WORDS = re.compile(r"老妖精|晓筑|公众号|授课老师|注册考试咨询|扫码关注|小程序|lyj\.top")


SUBJECT_WORDS = {
    "math": ("高等数学","高数","数学"),
    "physics": ("物理",),
    "chemistry": ("化学",),
    "mechanics": ("理论力学","工程静力学"),
    "materials": ("材料力学",),
    "fluids": ("流体力学","水力学"),
    "circuit": ("电路","电子","电工"),
    "signals": ("信号","信息技术"),
    "computing": ("计算机","计算技术"),
    "economics": ("工程经济","经济"),
    "law": ("法律","法规","法学"),
}


def classify(file, source):
    # Exact profiles apply only to the original file locations. Imported files
    # can use a subject directory (preferred) or an unambiguous subject name.
    path = file.relative_to(source)
    extra = {"法律法规重点总结", "电工电子总结", "流体力学高频公式总结", "物理高频考点公式总结", "计算机总结", "化学高频考点公式总结"}
    original_directory = ("笔记","其他机构总结") if file.stem in extra else ("笔记",)
    original_suffix = ".docx" if file.stem == "经济自己总结" else ".pdf"
    if path.parts[:-1] == original_directory and file.suffix.lower() == original_suffix and file.stem in CATALOG:
        return CATALOG[file.stem]
    for part in (*reversed(path.parts[:-1]), file.stem):
        matches = {subject for subject, names in SUBJECT_WORDS.items()
                   if part == subject or any(name in part for name in names)}
        if len(matches) == 1:
            subject = matches.pop()
            stable_id = hashlib.sha256(path.as_posix().encode()).hexdigest()[:16]
            return subject, "import-" + stable_id, file.stem
    raise ValueError(f"无法识别学科：{path}。请放入对应学科目录，例如 upload/高等数学/。")


def repeated_margins(doc):
    if len(doc) < 3:
        return set()
    counts = Counter()
    for page in doc:
        found = set()
        for block in page.get_text("dict", flags=0)["blocks"]:
            for line in block.get("lines", []):
                y = line["bbox"][1] / page.rect.height
                if y < .07 or y > .93:
                    txt = "".join(s["text"] for s in line["spans"]).strip()
                    if txt:
                        found.add((round(y, 2), re.sub(r"\d+", "#", txt)))
        counts.update(found)
    return {k for k, count in counts.items() if count >= max(3, len(doc)*.65)}


def render(page, scale):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def box(coords, scale):
    return tuple(round(c * scale) for c in coords)


def remove_objects(doc, key):
    refs = set()
    for page in doc:
        for ref, _, w, h, *_ in page.get_images():
            if ((w, h) == QR and not key.startswith("import-")) or (key in DECKS | FORMULA_SLIDES and (w,h) in DECORATION):
                refs.add(ref)
    for ref in refs:
        doc.update_object(ref, "<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Resources <<>> >>")
        doc.update_stream(ref, b" ")


def watermark_background(doc, scale):
    # Common light pixels across many pages recover the repeated printed backdrop.
    reference = None
    for p in doc:
        sample = np.asarray(render(p, scale))
        reference = sample.copy() if reference is None else np.maximum(reference, sample)
    return np.maximum(reference, 185)


def clean_page(page, key, scale, backdrop, margins=()):
    n = page.number + 1
    im = render(page, scale)
    if backdrop is not None:
        data = np.asarray(im).astype(np.float32)
        corrected = np.minimum(255, np.rint(data * 255 / backdrop)).astype("uint8")
        # Flat, near-white residuals in these scans are the printed master.
        # Only whiten light neutral pixels, retaining hues and darker linework.
        light = np.min(corrected, axis=2) > 217
        neutral = np.ptp(corrected, axis=2) < 15
        corrected[light & neutral] = 255
        im = Image.fromarray(corrected)
    draw = ImageDraw.Draw(im)
    rect = page.rect
    crop = (0, 0, rect.width, rect.height)
    if key in BRANDED_PRINT:
        crop = (29, 96 if n == 1 else 53, 574, 779)
        draw.rectangle(box((553,414,574,428), scale), fill="white")
    elif key == "fluids-foundations":
        crop = (25, 45, 565, 766)
    elif key == "periodic-table":
        crop = (27, 53, 811, 567)
        draw.rectangle(box((709,505,811,523),scale), fill="white")
    elif key in DECKS:
        if page.get_text().lstrip().startswith("课堂总结"):
            crop = (197,117,769,445)
        else:
            crop = (16, 0, 946, 509)
            draw.rectangle(box((875,467,938,530),scale), fill="white")
            draw.rectangle(box((888,0,941,45),scale), fill="white")
    elif key in FORMULA_SLIDES:
        draw.rectangle(box((902,516,947,539),scale),fill=im.getpixel(box((900,514),scale)))
    # TOC leaders and their original folios no longer serve as navigation.
    toc = page.get_text().count("......") >= 4
    if toc:
        for block in page.get_text("rawdict", flags=0)["blocks"]:
            for line in block.get("lines", []):
                chars = [c for span in line["spans"] for c in span["chars"]]
                match = re.search(r"[.．·]{3,}\s*\d*\s*$", "".join(c["c"] for c in chars))
                if match:
                    x = chars[match.start()]["bbox"][0]
                    _,y,x1,y1 = line["bbox"]
                    draw.rectangle(box((x,y,x1+1,y1),scale),fill="white")
    lines = []
    for block in page.get_text("dict", flags=0)["blocks"]:
        for line in block.get("lines", []):
            txt = "".join(span["text"] for span in line["spans"]).strip()
            x,y,x1,y1 = line["bbox"]
            if not txt: continue
            footer = txt == str(n) and (key in DECKS and y>500 or abs(x-300)<12 and y>760)
            generic_margin = (round(y / rect.height, 2), re.sub(r"\d+", "#", txt)) in margins
            generic_folio = key.startswith("import-") and (y / rect.height > .90 or y1 / rect.height < .08) and re.fullmatch(r"[-— ]*(?:第\s*)?\d+\s*(?:页)?(?:\s*/\s*\d+)?[-— ]*",txt)
            if footer or generic_margin or generic_folio or BRAND_WORDS.search(txt):
                draw.rectangle(box((x-1,y-1,x1+1,y1+1),scale),fill="white")
                continue
            if key in FORMULA_SLIDES and re.fullmatch(r"\d+/\d+", txt): continue
            if y1 < crop[1] or y > crop[3]: continue
            if toc:
                txt = re.sub(r"[.．·]{3,}\s*\d*\s*$", "",txt).strip()
            if txt:
                lines.append(txt)
    if toc:
        lines.insert(0, "知识目录")
    return strip_referrals(im.crop(box(crop, scale)),key,n), "\n".join(lines)


# Localized course referrals share lines with technical prose. These rectangles
# are in the 570-by-759 inspection view of the printed body, not page edges.
REFERRALS = {
    ("electrical-notes",22): [(241,7,565,25),(8,28,110,48)],
    ("electrical-notes",23): [(155,633,554,655)],
    ("materials-notes",24): [(82,365,275,386)],
    ("mechanics-notes",6): [(504,556,556,577),(7,577,224,599)],
}


def strip_referrals(im, key, n):
    draw = ImageDraw.Draw(im)
    for x,y,x1,y1 in REFERRALS.get((key,n),[]):
        draw.rectangle((x*im.width/570,y*im.height/759,x1*im.width/570,y1*im.height/759),fill="white")
    return im


def recognize(path):
    with Image.open(path) as im:
        im.thumbnail((1450,1900))
        with tempfile.NamedTemporaryFile(suffix=".png") as input_file:
            im.save(input_file.name)
            res = subprocess.run(["tesseract",input_file.name,"stdout","-l","chi_sim+eng","--psm","6"],
                                 capture_output=True,check=True,env={**os.environ,"OMP_THREAD_LIMIT":"1"})
    lines = [re.sub(r"(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])","",l.strip())
             for l in res.stdout.decode().splitlines() if l.strip() and not BRAND_WORDS.search(l)]
    return "\n".join(lines)


# Teacher-authored running text often starts mid-equation. Supply descriptive
# section headings for documents whose page boundaries cross topics.
PAGE_TITLES = {
    "math-notes": "知识目录|向量代数与空间直线|空间曲面与函数极限|连续性、导数与中值定理|函数性态与偏导数|积分公式与换元积分|定积分应用与重积分|曲线积分与常数项级数|幂级数与泰勒级数|傅里叶级数与微分方程|可降阶方程与线性微分方程",
    "physics-notes": "知识目录|理想气体与热力学过程|热力循环与机械波|波动、干涉与驻波|多普勒效应与光的干涉|牛顿环、薄膜干涉与衍射|衍射光栅与偏振光|双折射现象",
    "chemistry-notes": "知识目录|原子结构与元素周期律|晶体、杂化轨道与溶液|溶度积与电化学|反应速率与化学热力学|化学平衡与有机物|有机高分子与塑料|橡胶与合成纤维",
    "signals-notes": "知识目录|信号的分类、频谱与放大|放大器失真与数字逻辑",
    "circuit-notes": "知识目录|理想电路元件与互感|变压器与电路定律|等效电路与交流参数|三相电路与用电安全|暂态分析与频率特性|滤波电路",
    "computing-notes": "计算机组成与系统软件|操作系统、程序语言与数据库|数据表示、编码与多媒体|信息安全与操作系统管理|网络层次结构与通信协议|互联网服务与网络安全",
    "economics-notes": "资金的时间价值与项目投资|成本费用与资金筹措|财务分析与偿债能力|经济评价、方案比选与价值工程|价值系数与功能改进",
    "fluids-foundations": "流体特性与常用物性参数|牛顿内摩擦定律与静水压强|连续性方程、伯努利方程与动量方程|雷诺数与流动阻力损失|孔口出流与管路计算|明渠均匀流与断面单位能量",
    "fluids-formulas": "流体物性与黏性|静水压力与能量方程|流动阻力与管道计算|过流断面与明渠流动|集水廊道与相似准则",
    "mechanics-notes": "力与静力学公理|二力平衡与力的分解|约束与约束力|支座约束与力矩|力偶与力系|力系平衡条件|点的运动学|抛体运动与圆周运动|角速度与角加速度|刚体定轴转动的速度与加速度|动力学定律与质点运动|惯性力与转动惯量|转动惯量与质点振动|弹簧刚度与固有频率|动量与动量定理|转动惯量与动量矩|动量矩定理与动能|势能与机械能守恒",
    "materials-notes": "拉压试验与材料性能|屈服、强化与变形|卸载、应力集中与轴向拉压|截面法与轴力|轴力图、应力与应变|剪切与切应力|挤压及其强度计算|圆轴扭转与扭矩|扭转切应力|截面几何性质|形心、静矩与惯性矩|惯性矩与平行轴定理|惯性矩叠加与惯性积|梁的剪力与弯矩|弯曲内力的正负号|剪力图与弯矩图|荷载、内力图与弯曲正应力|正应力与中性轴|弯曲切应力|转角与挠度|点的应力状态|主应力与极值切应力|强度理论与应力圆|组合变形|拉伸与弯曲的组合|偏心拉伸与压缩|压杆稳定|欧拉公式与临界压力|不同约束下的压杆计算长度",
    "electrical-notes": "库仑定律与电磁场|磁场、电磁感应与欧姆定律|电阻串并联与电流定律|回路电压与支路电流法|戴维宁定理与诺顿定理|储能元件与暂态|正弦交流量|相量表示与交流电路|电抗与正弦交流电路计算|三相负载|功率因数的改善|变压器的工作原理|三相异步电动机|异步电动机的启动、反转与调速|电气控制器件|连续与离散信号|信号放大与失真|谐波与傅里叶级数|滤波器分类|二极管与模拟电子技术|运算放大器与电压比较器|运算放大器的运算电路|数字信号与逻辑函数|BCD 码与基本门电路|逻辑门与 D 触发器|触发器与时序逻辑电路",
    "computing-systems": "计算机系统与硬件组成|控制器、运算器与存储器|总线、转换器与软件系统|操作系统与计算机语言|高级语言、编译和解释||信息数量单位与字符编码|汉字编码与图形信息|进位计数制与数制转换|多媒体信息|操作系统概述与进程|进程、线程与处理器管理|设备与文件管理|计算机网络概述|网络结构与组成|传输介质与通信协议|网络协议与网络安全",
    "economics-focus": "|工程经济复习范围|现金流量图与资金等值公式|权益资本成本与资本资产定价模型|实际利率与计息周期|现金流量图与年金|设备更新的资金等值计算|财务收益与财务费用|建设投资的构成|建设期利息|经营成本的构成|总成本费用的估算|资本金与债务资金|固定增长股利与资金成本|资本资产定价模型|债务资金成本|盈利能力与偿债能力指标|盈利能力的评价指标|总投资收益率|内部收益率|静态投资回收期|利息备付率与偿债备付率|资产负债率|影子价格|盈亏平衡分析|敏感性分析|价格敏感度计算|方案比选与价值工程概览|效益比选方法|差额内部收益率与净现值|费用现值法与费用年值法|设备方案费用比较|费用年值比较例题|计算期不同的互斥方案|改扩建项目的经济评价|价值工程概念|价值工程分析方法|功能评价例题|功能成本改进的期望值",
    "periodic-table": "元素周期表",
}


def apply_page_titles(library):
    for doc in library:
        titles = PAGE_TITLES.get(doc["id"], "").split("|")
        for page in doc["pages"]:
            idx = page["sourcePage"] - 1
            if doc["id"] == "law-focus" and page["sourcePage"] in (13,15):
                page["title"] = {13:"要约邀请的识别",15:"要约的撤回与撤销"}[page["sourcePage"]]
            if idx < len(titles) and titles[idx]:
                page["title"] = titles[idx]


def page_title(text, fallback):
    if re.search(r"\.{6,}",text): return "知识目录"
    for line in text.splitlines():
        if len(re.findall(r"[\u3400-\u9fff]",line)) < 2: continue
        clean = re.sub(r"^(?:\s*\d+[.、．)]\s*|[ .、．-]+)","",line).strip()
        if 2<=len(clean)<=40: return clean
    return fallback


def convert_docx(file, temp):
    output = temp / hashlib.sha256(str(file).encode()).hexdigest()[:12]
    output.mkdir()
    subprocess.run(["libreoffice","-env:UserInstallation="+(temp/"profile").as_uri(),"--headless",
                    "--convert-to","pdf","--outdir",str(output),str(file)], check=True, stdout=subprocess.DEVNULL)
    return output/(file.stem+".pdf")


def generic_html(text):
    """Keep explicit math markup and bracketed row structure in new imports."""
    delimiters = re.compile(
        r"\$\$(.*?)\$\$|\\\[(.*?)\\\]|\\\((.*?)\\\)|"
        r"(\\begin\{(?P<env>[pbvVB]?matrix|cases|aligned)\}.*?\\end\{(?P=env)\})",
        re.DOTALL,
    )
    expressions = []
    sections = []
    start = 0
    for match in delimiters.finditer(text):
        sections.append(('text', text[start:match.start()]))
        expression = next(group for group in match.groups()[:4] if group is not None)
        sections.append(('math', len(expressions)))
        expressions.append(expression)
        start = match.end()
    sections.append(('text', text[start:]))

    converted = []
    if expressions:
        process = subprocess.run(
            ['node', str(ROOT / 'tools' / 'mathml.cjs')],
            input=json.dumps(expressions), text=True, capture_output=True,
        )
        # A literal but malformed TeX expression may occur in imported text.
        # Keeping its source on a separate line makes it available for correction.
        converted = json.loads(process.stdout) if process.returncode == 0 else [
            '<code>' + escape(value) + '</code>' for value in expressions
        ]
    blocks = []
    for kind, value in sections:
        if kind == 'math':
            blocks.append('<div class="formula">' + converted[value] + '</div>')
            continue
        for line in value.splitlines():
            if not line.strip():
                continue
            content = escape(line.strip())
            if re.search(r"[=≈≠≤≥∫∑√→]", line):
                blocks.append('<div class="formula">' + content + '</div>')
            else:
                blocks.append('<p>' + content + '</p>')
    return '\n'.join(blocks) or '<p>此页没有可提取的文字。</p>'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=ROOT/"upload")
    parser.add_argument("--output",type=Path,default=ROOT/"library")
    args=parser.parse_args()
    pages_dir=args.output/"pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    if not args.source.is_dir():
        raise SystemExit(f"资料目录不存在：{args.source}")
    files=sorted(p for p in args.source.rglob("*") if p.is_file() and not p.name.startswith("."))
    profiles={}
    issues=[]
    for file in files:
        if file.suffix.lower() not in (".pdf",".docx"):
            issues.append(f"不支持此文件格式：{file}")
            continue
        try:
            profiles[file] = classify(file, args.source)
        except ValueError as error:
            issues.append(str(error))
    if issues:
        raise SystemExit("\n".join(issues))
    previous = {}
    catalog = args.output / "documents.js"
    if catalog.is_file():
        documents = json.loads(catalog.read_text().split("=", 1)[1].strip().removesuffix(";"))
        previous = {document["id"]: document for document in documents}
    reference = ROOT / "library"
    curated = {}
    if reference.resolve() != args.output.resolve() and (reference / "documents.js").is_file():
        raw = (reference / "documents.js").read_text().split("=", 1)[1].strip().removesuffix(";")
        curated = {document["id"]: document for document in json.loads(raw)}
    library=[]; pending=[]
    with tempfile.TemporaryDirectory(dir=args.output) as tmp, ThreadPoolExecutor(max_workers=3) as pool:
        staged=Path(tmp).resolve()
        generated=staged/"pages"
        generated.mkdir()
        reading_dir = staged / "text"
        reading_dir.mkdir()
        for file in files:
            subject,key,title=profiles[file]
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            existing = previous.get(key)
            if existing and existing.get("sourceSha256") == digest and all(
                    p.get("html") and (args.output / "text" / Path(p["html"]).name).is_file()
                    for p in existing["pages"]):
                library.append(existing)
                continue
            original = curated.get(key)
            if original and original.get("sourceSha256") == digest:
                for item in original["pages"]:
                    page_name = Path(item["html"]).name
                    shutil.copyfile(reference / "text" / page_name, reading_dir / page_name)
                    if item.get("image"):
                        filename = Path(item["image"]).name
                        shutil.copyfile(reference / "pages" / filename, generated / filename)
                library.append(original)
                continue
            src=convert_docx(file, staged) if file.suffix.lower()==".docx" else file
            with fitz.open(src) as doc:
                remove_objects(doc,key)
                scale = 2.6 if key=="periodic-table" else (2.25 if doc[0].rect.width<700 else 1.7)
                bg=watermark_background(doc,scale) if key in TILED_MARKS else None
                margins=repeated_margins(doc) if key.startswith("import-") else set()
                content=[]
                for page in doc:
                    source_page=page.number+1
                    # The printed masters contain two promotional covers and
                    # two pages with just a running header, watermark and folio.
                    if key in DECKS and source_page == 1 or (key, source_page) in {
                        ("computing-systems", 6), ("mechanics-notes", 19)
                    }:
                        continue
                    im,text=clean_page(page,key,scale,bg,margins)
                    filename=f"{key}-{source_page:03}.webp"
                    out=generated/filename
                    im.save(out,quality=90,method=3)
                    item=dict(image="library/pages/"+filename,title=page_title(text,title),
                              text=text,sourcePage=source_page)
                    if len(re.findall(r"[\u3400-\u9fff]",text))<8:
                        pending.append((item,pool.submit(recognize,out),title))
                    content.append(item)
                library.append(dict(id=key,subject=subject,title=title,source=file.name,sourceSha256=digest,pages=content))
                print(file.name,len(content),flush=True)
        for item,job,title in pending:
            item["text"]=job.result() or item["text"]
            item["title"]=page_title(item["text"],title)
        apply_page_titles(library)
        for document in library:
            for item in document["pages"]:
                if item.get("html"):
                    continue
                name = f"{document['id']}-{item['sourcePage']:03}.html"
                (reading_dir / name).write_text(standalone(generic_html(item['text']), item['title']))
                item['html'] = 'library/text/' + name
        manifest = staged / "documents.js"
        manifest.write_text("window.DOCUMENTS="+json.dumps(library,ensure_ascii=False,separators=(",",":"))+";\n")
        # Install complete page files before exposing their new manifest. A
        # failed conversion leaves the last successful library available.
        directory_fd = os.open(args.output, os.O_RDONLY)
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            for image in generated.iterdir():
                image.replace(pages_dir / image.name)
            target = args.output / "text"
            target.mkdir(exist_ok=True)
            for page in reading_dir.iterdir():
                page.replace(target / page.name)
            manifest.replace(args.output / "documents.js")
            from build_chapters import compile_library
            compile_library(args.output)
        finally:
            os.close(directory_fd)
    print(f"{len(library)} documents; {sum(len(d['pages']) for d in library)} pages")


if __name__=="__main__":
    main()
