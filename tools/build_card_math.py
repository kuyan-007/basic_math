"""Mark up equations in the existing flashcards without changing their progress IDs."""
from html import escape
from pathlib import Path
import json
import re
from flashcard_math import typeset_cards

ROOT = Path(__file__).resolve().parents[1]
# Only overrides with display math are included. Each $...$ becomes a separate MathML block.
CONTENT = {
    'math-527a0452038c': (None, r'$A(x-x_0)+B(y-y_0)+C(z-z_0)=0$从已知点指向平面内任意一点的向量均与法向量垂直。'),
    'math-d0ba4b9485b6': (r'下列方程在三维空间中描述什么曲面？$x^2+y^2=R^2,\quad R>0$', None),
    'math-df90d4395278': (r'下列曲线与 x 轴之间从 a 到 b 的区域绕 x 轴旋转，怎样求体积？$y=f(x)$', r'垂直于 x 轴的截面是圆盘，半径为函数值的绝对值。$V=\pi\int_a^b [f(x)]^2\,dx$'),
    'math-91e2f7af400c': (None, r'坐标变换为$x=r\cos\theta,\quad y=r\sin\theta$面积微元为$dA=r\,dr\,d\theta$因子 r 来自坐标变换。'),
    'math-a60368cada16': (r'下面的 p 级数在什么条件下收敛？$\sum_{n=1}^{\infty}\frac{1}{n^p},\qquad p>0$', r'收敛条件为$p>1$发散范围为$0<p\leq1$其中 p 等于 1 时是调和级数。'),
    'math-5d22873889ef': (r'下面的二阶方程不显含 y，如何降阶？$y^{\prime\prime}=f(x,y^\prime)$', r'引入新未知函数$p=y^\prime$得到一阶方程$p^\prime=f(x,p)$求出 p 后对 x 积分即可得到 y。'),
    'physics-38c3ec0a5636': (None, r'$\eta=1-\frac{T_{\text{冷}}}{T_{\text{热}}}=1-\frac{300}{600}=50\%$温度使用绝对温度。'),
    'physics-7b9e8ed0c2f2': (None, r'$\lambda=\frac{u}{f}=\frac{340}{170}\,\mathrm{m}=2\,\mathrm{m}$一个周期内，确定相位的波形向前传播一个波长。'),
    'physics-046cd598091f': (None, r'条纹间距减半。小角度条件下，条纹间距为$\Delta x=\frac{\lambda D}{d}$其中 D 为双缝到屏的距离。'),
    'physics-ac1844ff1a10': (None, r'由马吕斯定律，$I=I_0\cos^2 60^\circ=\frac{I_0}{4}$其中 I₀ 是入射线偏振光的强度。'),
    'chemistry-47a0395b181a': (None, r'过饱和，有析出沉淀的趋势：$Q>K_{\rm sp}$饱和：$Q=K_{\rm sp}$未饱和，已有固体可继续溶解：$Q<K_{\rm sp}$'),
    'chemistry-c871592af843': ('当角量子数为 2 时，磁量子数有哪些可能的取值？', r'磁量子数从角量子数的负值到其正值取整数。$m\in\{-2,-1,0,1,2\}$这一 d 亚层共有五个轨道。'),
    'chemistry-3683a04faa4a': ('25 ℃ 的稀水溶液中，pH 为 3，pOH 约为多少？', r'$\mathrm{pH}+\mathrm{pOH}\approx14$$\mathrm{pOH}\approx11$两者之和取决于水的离子积，随温度变化。'),
    'chemistry-39cf3f95ce0b': (None, r'大于 1。标准反应吉布斯自由能变与标准平衡常数满足$\Delta_\mathrm{r} G^\circ=-RT\ln K^\circ$因此$\Delta_\mathrm{r} G^\circ<0\quad\Longrightarrow\quad\ln K^\circ>0$'),
    'signals-50a06d699ab2': (None, r'基频为$f_1=\frac{1}{T}$第 k 次谐波的频率为$f_k=\frac{k}{T}$相邻谐波的频率差等于基频。'),
    'signals-7e9f4289bbd5': (None, r'$\neg(A\land B)=(\neg A)\lor(\neg B)$只要 A、B 中至少一个为假，原来的合取命题就为假。'),
    'economics-614a2940ddd2': (None, r'按给定基准收益率折现各期净现金流量。满足以下条件，方案即达到或超过该收益率要求：$\mathrm{FNPV}\geq0$'),
    'economics-c2aac7f96540': (None, r'它是使项目计算期内各期净现金流量的现值之和等于零的折现率，满足$\mathrm{FNPV}(\mathrm{FIRR})=0$'),
    'economics-65952af3cebd': (None, r'用功能 F 除以成本 C 得到价值 V：$V=\frac{F}{C}$成本不变时，提高所需功能可提高价值。'),
    'mechanics-7399d21cf2dd': (r'怎样消去下面运动方程中的时间参数，得到轨迹？$x=2t,\qquad y=t^2,\qquad t\geq0$', r'由第一式解出时间：$t=\frac{x}{2}$代入第二式：$y=\frac{x^2}{4},\qquad x\geq0$参数范围决定实际经过哪一段曲线。'),
    'mechanics-f79dafa2a4ae': (None, r'线速度大小之比为 1∶2。两点角速度相同，速度均沿各自圆轨迹的切线，其大小为$v=\lvert\omega\rvert r$'),
    'mechanics-e26f94d412ea': (None, r'引入惯性力$\boldsymbol F_{\text{惯}}=-m\boldsymbol a$实际力与惯性力之和为零，从而将动力学方程写成平衡形式。'),
    'mechanics-dfd50953c5a9': (None, r'平行轴定理给出$J=J_c+md^2$其中 m 为质量，d 为两平行轴之间的垂直距离。'),
    'materials-712063fab454': (None, r'工程应力为$\sigma=\frac{F}{A_0}$工程应变为$\varepsilon=\frac{\Delta L}{L_0}$分母分别取试件的初始截面积与初始长度。'),
    'materials-0e9cc9450f85': (None, r'若横轴为应变、纵轴为应力，线弹性段的斜率为弹性模量 E。这一段满足$\sigma=E\varepsilon$'),
    'materials-f1c5c412a465': (None, r'$\Delta L=\frac{NL}{EA}$材料和轴力相同时，长度加倍则伸长量加倍，截面积加倍则伸长量减半。'),
    'materials-204e6d481238': (None, r'$I=\frac{bh^3}{12}$与该轴垂直的尺寸 h 取三次方。'),
    'fluids-f81c7f5eda20': (None, r'由动力黏度和垂直于流层的速度梯度决定：$\lvert\tau\rvert=\mu\left\lvert\frac{du}{dy}\right\rvert$速度梯度相同时，黏度越大，剪应力越大。'),
    'fluids-8dbeb00fb58a': (None, r'$p_{\text{绝对}}=p_{\text{大气}}+p_{\text{表}}=130\,\mathrm{kPa}$表压以当地大气压为零点。'),
    'fluids-500080b91e4f': ('充分发展的圆管层流中，雷诺数为 1600 时，达西沿程阻力系数是多少？', r'$\lambda=\frac{64}{\mathrm{Re}}=0.04$这里使用达西阻力系数。'),
    'circuit-0adb24cf5652': (None, r'初始偏差还剩约 36.8%。时间常数为$\tau=R_{\text{等效}}C$偏差相对初值按下式衰减：$e^{-t/\tau}$'),
    'computing-d5c3419359a3': (None, r'8 位的取值总数为$2^8=256$最小值为 0，最大值为 255。'),
    'computing-332d730444f6': (None, r'标准 ASCII 使用 7 个有效位，可表示的编码数为$2^7=128$其中包含控制字符和可打印字符。'),
}

def build():
    file = ROOT / 'library/cards.js'
    raw = file.read_text().split('=', 1)[1].strip().removesuffix(';')
    cards = json.loads(re.sub(r',\s*\]$', ']', raw))
    # Format curated TeX versions without changing the original wording or progress keys.
    display_cards = []
    for card in cards:
        display = dict(card)
        for key, html_key, text in zip(('q', 'a'), ('questionHtml', 'answerHtml'),
                                       CONTENT.get(card['id'], (None, None))):
            if text is not None:
                display[key] = text
                display.pop(html_key, None)
                if '$' not in text:
                    display[html_key] = escape(text)
        display_cards.append(display)
    typeset_cards(display_cards, expand_expressions=True)
    for card, display in zip(cards, display_cards, strict=True):
        for key in ('questionHtml', 'answerHtml'):
            if key in display:
                card[key] = display[key]
    file.write_text('window.CARDS = [\n' + ',\n'.join('  '+json.dumps(c, ensure_ascii=False)
                                                      for c in cards) + '\n];\n')

if __name__ == '__main__':
    build()
