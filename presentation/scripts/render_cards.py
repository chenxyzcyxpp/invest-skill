"""render_cards.py — invest-skill 全库小白卡渲染器（presentation 输出层）

读 NoviceCard JSON（schema invest-novice-card/1，见 ../SKILL.md 第 1 节），
确定性渲染成自包含 HTML。同一套 nv-* 卡片类名、
同一套两层配色口径（行情数值图红=涨/绿=跌；操作信号图红=机会/绿=警示/黄=观望/灰=等待）。

用法：
    python -X utf8 presentation/scripts/render_cards.py cards.json -o cards.html          # 渲染
    python -X utf8 presentation/scripts/render_cards.py cards.json --check rendered.html  # 数字一致性校验
    python -X utf8 presentation/scripts/render_cards.py cards.json --png cards.png        # 整页 PNG（聊天宿主交付形态）

设计纪律（与 SKILL.md 红线一致）：
- 渲染器不加工数字：所有数值按 JSON 原样输出（一位小数展示为惯例舍入，--check 用原值比对）。
- 缺字段画"—"，不编造；figures 的 kind 未知时整图省略并在 evidence 标注。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── 视觉常量（改这里必须过 --check 双渲染验收）──────────
UP = '#cf2e3d'    # 红：行情=涨/正；操作=机会/赢面大
DN = '#1a8a4f'    # 绿：行情=跌/负；操作=负面警示
FL = '#98a2b3'    # 灰：等待/中性弱
ACCENT = '#1f5fd6'  # 蓝：neutral 信息卡点缀
GOLD = '#b8860b'  # 黄：观望/关注

TIER_BAR = {'red': UP, 'yellow': GOLD, 'grey': FL, 'green': DN, 'neutral': ACCENT}
TIER_LABEL = {'red': '机会', 'yellow': '观望', 'grey': '等待', 'green': '警示', 'neutral': '信息'}
TONE_COLOR = {'up': UP, 'down': DN, 'gold': GOLD, 'flat': FL}

SMALL_SAMPLE_TALK = '⚠ 这条信号历史次数少（{n} 次），只能当方向参考——仓位更要小、分批更要慢。'
DISCLAIMER = ('以上内容由开源投研技能库 invest-skill 的报告翻译生成，仅供学习参考，'
              '不构成投资建议；数字为历史样例，不代表未来表现。市场有风险，投资需谨慎。')

CARD_CSS = '''.nv-card{border:1px solid #e3e8ee;border-radius:16px;padding:18px 18px 14px;background:#fff;
position:relative;overflow:hidden;box-shadow:0 2px 8px rgba(15,36,64,.08)}
.nv-card::before{content:"";position:absolute;left:0;top:0;right:0;height:5px;
background:linear-gradient(90deg,var(--nv-bar,#1f5fd6),transparent 70%)}
.nv-grey{opacity:.92;border-style:dashed}
.nv-head{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-top:4px}
.nv-name{font-size:19px;font-weight:800;color:#0f2440}
.nv-meta{font-size:11px;color:#67748a;font-weight:500}
.nv-badge{font-size:11px;color:#67748a;white-space:nowrap}
.nv-title{font-size:15px;font-weight:800;padding:6px 14px;border-radius:99px;margin-left:auto;
background:rgba(15,36,64,.04);border:1px solid currentColor;white-space:nowrap}
.nv-say{margin:14px 2px 6px;font-size:15.5px;line-height:1.8}
.nv-tagline{display:flex;flex-wrap:wrap;gap:8px;margin:10px 2px 2px}
.nv-chip{font-weight:700;white-space:nowrap;font-size:12px;padding:4px 10px;border-radius:99px;border:1px solid currentColor;background:rgba(15,36,64,.03)}
.nv-facts{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 2px 0;font-size:12.5px;color:#33415e}
.nv-facts b{color:#0f2440}
.nv-figs{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0 4px}
.nv-fig{border:1px solid #e8ecf1;border-radius:12px;padding:10px 10px 6px;background:#fbfcfe}
.nv-fig svg{display:block;max-width:330px;margin:0 auto}
.nv-figcap{font-size:10.5px;color:#67748a;margin:0 0 4px 2px;font-weight:600}
.nv-evi{font-size:12.5px;color:#67748a;margin-top:10px}
.nv-evi summary{list-style:none;cursor:pointer}
.nv-evi div{margin-top:6px;line-height:1.7;color:#33415e}
.nv-disc{margin-top:12px;font-size:11px;color:#67748a}
@media(max-width:560px){
  .nv-card{padding:14px 12px 10px;border-radius:12px}
  .nv-head{gap:8px}
  .nv-name{font-size:17px}
  .nv-figs{grid-template-columns:1fr;gap:8px}
  .nv-fig svg{max-width:100%}
  .nv-title{font-size:13px;padding:4px 10px}
  .nv-say{font-size:14.5px;line-height:1.7;margin:10px 0 4px}
}'''

PAGE_CSS = '''*{box-sizing:border-box}body{margin:0;padding:20px;background:#f4f6f9;color:#182230;
font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.nv-wrap{max-width:760px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
h1{font-size:16px;color:#0f2440} .nv-pagehead{max-width:760px;margin:0 auto 4px;font-size:15px;color:#33415e}
@media(max-width:560px){
  body{padding:12px 10px}
  .nv-wrap{gap:12px}
}'''


def _esc(s) -> str:
    if s is None:
        return '—'
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _esc_rich(s) -> str:
    """say 字段专用：全量转义后放行 <b> 粗体（NG-C1 惯例，SKILL.md 第 4 节第 8 条）。
    其余任何标签保持转义显示，防注入。"""
    return _esc(s).replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')


def _num(v, digits=1):
    """数字展示惯例：一位小数；None → —。"""
    if v is None:
        return '—'
    if isinstance(v, (int, float)):
        return f'{round(v, digits):g}'
    return str(v)


# ── SVG 图元 ────────────────────────────────────────────────

def fig_winbar(d: dict) -> str:
    """胜率条（操作口径）：win≥60 红 / 50–60 黄 / <50 绿。"""
    win, n = d.get('win'), d.get('n')
    if win is None:
        cap = _esc(d.get('cap', '胜率'))
        return f'<div class="nv-figcap">{cap}：数据缺失</div>'
    color = UP if win >= 60 else (GOLD if win >= 50 else DN)
    w = max(2, min(100, win))
    losses = '—' if n is None else max(0, round(n * (100 - win) / 100))
    wins = '—' if n is None else round(n * win / 100)
    return f'''<div class="nv-figcap">{_esc(d.get('cap', '历史胜率（60 日口径）'))}</div>
<svg viewBox="0 0 320 46" width="100%" style="max-width:320px">
  <rect x="2" y="10" width="296" height="14" rx="7" fill="#eef1f5"/>
  <rect x="2" y="10" width="{296 * w / 100:.0f}" height="14" rx="7" fill="{color}"/>
  <text x="302" y="21" font-size="9" fill="#67748a" text-anchor="end" dy="3">{_num(win)}%</text>
  <text x="2" y="40" font-size="8.5" fill="#67748a">赢 {wins} 次 / 亏 {losses} 次{'' if n is None else f'（共 {n} 次）'}</text>
</svg>'''


def fig_meter(d: dict) -> str:
    """分级仪：levels 横排，active 高亮；可选 0–100 score 圆点。"""
    levels = d.get('levels') or []
    active = d.get('active')
    score = d.get('score')
    if not levels:
        return ''
    n = len(levels)
    cell = 300 / n
    cells = []
    for i, lv in enumerate(levels):
        on = (active is not None and i == active)
        fill = UP if on else '#eef1f5'
        tcol = '#fff' if on else '#67748a'
        cells.append(
            f'<rect x="{2 + i * cell:.0f}" y="12" width="{cell - 4:.0f}" height="20" rx="6" fill="{fill}"/>'
            f'<text x="{2 + i * cell + (cell - 4) / 2:.0f}" y="26" font-size="10.5" font-weight="700" '
            f'fill="{tcol}" text-anchor="middle">{_esc(lv)}</text>')
    extra = ''
    if score is not None:
        x = 2 + 296 * max(0, min(100, score)) / 100
        extra = (f'<circle cx="{x:.0f}" cy="44" r="4" fill="{ACCENT}"/>'
                 f'<text x="302" y="47" font-size="8.5" fill="#67748a" text-anchor="end">综合分 {_num(score)}</text>')
    return (f'<div class="nv-figcap">{_esc(d.get("cap", "分级"))}</div>'
            f'<svg viewBox="0 0 302 52" width="100%" style="max-width:320px">{"".join(cells)}{extra}</svg>')


def fig_pctl(d: dict) -> str:
    """分位胶囊（行情口径）：三段细条，圆点标当前位置。"""
    v = d.get('value')
    if v is None:
        return ''
    x = 4 + 288 * max(0, min(100, v)) / 100
    tcol = DN if v <= 25 else ('#67748a' if v <= 75 else UP)
    return f'''<div class="nv-figcap">{_esc(d.get('cap', '价格分位'))}</div>
<svg viewBox="0 0 300 34" width="100%" style="max-width:320px">
  <rect x="4" y="8" width="72" height="8" rx="4" fill="{DN}" opacity=".75"/>
  <rect x="78" y="8" width="144" height="8" rx="4" fill="#e3e8ee"/>
  <rect x="224" y="8" width="72" height="8" rx="4" fill="{UP}" opacity=".75"/>
  <circle cx="{x:.0f}" cy="12" r="5" fill="#0f2440" stroke="#fff" stroke-width="1.5"/>
  <text x="296" y="30" font-size="9" fill="{tcol}" text-anchor="end" font-weight="700">{_num(v)}%（{_esc(d.get("label", "近3年"))}）</text>
</svg>'''


def fig_trend(d: dict) -> str:
    """折线（行情口径）：可选 marks（水平参考线）。"""
    pts = d.get('points') or []
    if len(pts) < 2:
        return ''
    ys = [float(p[1]) for p in pts]
    lo, hi = min(ys), max(ys)
    if hi == lo:
        hi = lo + 1
    W, H, PAD, PH = 320, 110, 6, 84

    def xy(i, y):
        return PAD + (W - 2 * PAD) * i / (len(pts) - 1), PAD + PH * (1 - (y - lo) / (hi - lo))

    path = ' '.join(f'{"M" if i == 0 else "L"}{xy(i, ys[i])[0]:.1f},{xy(i, ys[i])[1]:.1f}' for i in range(len(pts)))
    marks = ''
    for m in (d.get('marks') or []):
        my = float(m.get('y'))
        if not (lo <= my <= hi):
            continue
        _, yy = xy(0, my)
        marks += (f'<line x1="{PAD}" y1="{yy:.1f}" x2="{W - PAD}" y2="{yy:.1f}" stroke="{DN}" '
                  f'stroke-dasharray="4 3" stroke-width="1" opacity=".7"/>'
                  f'<text x="{W - PAD}" y="{yy - 3:.1f}" font-size="8" fill="{DN}" text-anchor="end">{_esc(m.get("label", ""))}</text>')
    first, last = ys[0], ys[-1]
    up = last >= first
    return (f'<div class="nv-figcap">{_esc(d.get("cap", "走势"))}</div>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:320px">{marks}'
            f'<path d="{path}" fill="none" stroke="{UP if up else DN}" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{xy(len(pts) - 1, last)[0]:.1f}" cy="{xy(len(pts) - 1, last)[1]:.1f}" r="3" fill="{UP if up else DN}"/>'
            f'<text x="{PAD}" y="{H - 4}" font-size="8" fill="#67748a">{_esc(pts[0][0])}</text>'
            f'<text x="{W - PAD}" y="{H - 4}" font-size="8" fill="#67748a" text-anchor="end">{_esc(pts[-1][0])}</text></svg>')


def fig_bars(d: dict) -> str:
    """横条对比（行情口径：正=红、负=绿；tone 可覆盖）。"""
    items = [i for i in (d.get('items') or []) if i.get('value') is not None]
    if not items:
        return ''
    unit = _esc(d.get('unit', '%'))
    vals = [float(i['value']) for i in items]
    mx = max(abs(v) for v in vals) or 1
    rows = []
    for it in items:
        v = float(it['value'])
        tone = it.get('tone')
        color = TONE_COLOR.get(tone) if tone else (UP if v >= 0 else DN)
        w = abs(v) / mx * 130
        left = 150 if v >= 0 else 150 - w
        sign = '+' if (unit == '%' and v > 0) else ''
        y = 18 + len(rows) * 22 + 4
        if v >= 0:
            vtxt = (f'<text x="{150 + max(w, 34) + 4:.1f}" y="{y}" font-size="9.5" font-weight="700" '
                    f'fill="{color}">{sign}{_num(v)}{unit}</text>')
        else:
            vtxt = (f'<text x="{150 - max(w, 34) - 4:.1f}" y="{y}" font-size="9.5" font-weight="700" '
                    f'fill="{color}" text-anchor="end">{_num(v)}{unit}</text>')
        rows.append(
            f'<text x="148" y="{y}" font-size="9.5" fill="#33415e" text-anchor="end">{_esc(it.get("label", ""))[:8]}</text>'
            f'<rect x="{left:.1f}" y="{y - 8}" width="{w:.1f}" height="11" rx="3" fill="{color}"/>' + vtxt)
    h = 22 * len(items) + 14
    return (f'<div class="nv-figcap">{_esc(d.get("cap", "对比"))}</div>'
            f'<svg viewBox="0 0 320 {h}" width="100%" style="max-width:320px">{"".join(rows)}</svg>')


def fig_list(d: dict) -> str:
    """要点列表：圆点着色 + 标题 + 说明。"""
    items = d.get('items') or []
    if not items:
        return ''
    rows = []
    for it in items:
        tone = it.get('tone', 'flat')
        color = TONE_COLOR.get(tone, FL)
        text = _esc(it.get('text'))
        rows.append(f'<div style="display:flex;gap:8px;align-items:baseline;margin:7px 2px">'
                    f'<span style="flex:none;width:7px;height:7px;border-radius:99px;background:{color};'
                    f'position:relative;top:-1px"></span>'
                    f'<div style="font-size:12.5px;line-height:1.6;color:#33415e">'
                    f'<b style="color:#0f2440">{_esc(it.get("head", ""))}</b>'
                    + (f'　{text}' if text else '') + '</div></div>')
    return (f'<div class="nv-figcap">{_esc(d.get("cap", ""))}</div>'
            f'<div style="padding:2px 4px">{"".join(rows)}</div>')


def fig_timeline(d: dict) -> str:
    """时间线：纵向事件点。"""
    events = d.get('events') or []
    if not events:
        return ''
    rows = []
    for ev in events:
        color = TONE_COLOR.get(ev.get('tone', 'flat'), FL)
        rows.append(f'<div style="display:flex;gap:10px;margin:8px 2px;align-items:baseline">'
                    f'<span style="flex:none;font-size:11px;font-weight:700;color:{color};min-width:44px">{_esc(ev.get("time", ""))}</span>'
                    f'<span style="flex:none;width:7px;height:7px;border-radius:99px;background:{color};position:relative;top:-1px"></span>'
                    f'<span style="font-size:12.5px;color:#33415e;line-height:1.6">{_esc(ev.get("label", ""))}</span></div>')
    return (f'<div class="nv-figcap">{_esc(d.get("cap", "时间线"))}</div>'
            f'<div style="padding:2px 4px">{"".join(rows)}</div>')


FIG_RENDERERS = {'winbar': fig_winbar, 'meter': fig_meter, 'pctl': fig_pctl,
                 'trend': fig_trend, 'bars': fig_bars, 'list': fig_list, 'timeline': fig_timeline}


# ── 卡片组装 ────────────────────────────────────────────────

def render_card(c: dict) -> str:
    tier = c.get('headline', {}).get('tier', 'neutral')
    bar = TIER_BAR.get(tier, ACCENT)
    title = _esc(c.get('headline', {}).get('text', ''))

    # v2 契约：data_as_of 必填（SKILL.md 0.3）。缺失警告不阻断（兼容旧 JSON）。
    asof = str(c.get('data_as_of') or '').strip()
    if not asof:
        print(f'[warn] 卡 "{c.get("title", "?")}" 缺 data_as_of 字段（v2 契约必填，见 SKILL.md 0.3）',
              file=sys.stderr)

    head = (f'<div class="nv-head"><span class="nv-name">{_esc(c.get("title", ""))}</span>'
            f'<span class="nv-meta">{_esc(c.get("date", ""))} · {_esc(c.get("source", {}).get("skill", ""))}'
            f'{"" if not c.get("source", {}).get("version") else " v" + str(c["source"]["version"])}'
            + (f' · 截至 {_esc(asof)}' if asof else '') + '</span>'
            + (f'<span class="nv-title" style="color:{bar}">{title}</span>' if title else '') + '</div>')

    say = _esc_rich(c.get('say', ''))
    say_html = f'<div class="nv-say">{say}</div>' if say else ''

    facts = c.get('facts') or []
    facts_html = ('<div class="nv-facts">' + ' '.join(
        f'<span><b>{_esc(f.get("k", ""))}</b>：{_esc(f.get("v", ""))}</span>' for f in facts) + '</div>'
        if facts else '')

    chips = c.get('chips') or []
    chips_html = ('<div class="nv-tagline">' + ' '.join(
        f'<span class="nv-chip" style="color:{TONE_COLOR.get(ch.get("tone", "flat"), FL)}">{_esc(ch.get("text", ""))}</span>'
        for ch in chips) + '</div>' if chips else '')

    figs = []
    for fg in (c.get('figures') or []):
        r = FIG_RENDERERS.get(fg.get('kind'))
        if not r:
            continue
        html = r(fg)
        if html:
            figs.append(f'<div class="nv-fig">{html}</div>')
    figs_html = ('<div class="nv-figs">' + ''.join(figs) + '</div>'
                 if figs else '')

    ss = c.get('small_sample')
    ss_html = f'<div class="nv-say" style="font-size:13px">{_esc(SMALL_SAMPLE_TALK.format(n=ss["n"]))}</div>' if ss else ''

    evi = c.get('evidence') or []
    evi_html = ('<details class="nv-evi"><summary>▸ 为什么？点开看数据与来源</summary><div>'
                + '<br>'.join(_esc(e) for e in evi) + '</div></details>' if evi else '')

    disc = _esc(c.get('disclaimer') or DISCLAIMER)
    return (f'<div class="nv-card" style="--nv-bar:{bar}">{head}{say_html}{facts_html}{chips_html}'
            f'{figs_html}{ss_html}{evi_html}<div class="nv-disc">{disc}</div></div>')


def render_page(cards: list, title: str = 'invest-skill 小白卡') -> str:
    body = ''.join(render_card(c) for c in cards)
    return (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_esc(title)}</title><style>{PAGE_CSS}{CARD_CSS}</style></head>'
            f'<body><div class="nv-pagehead">{_esc(title)}</div>'
            f'<div class="nv-wrap">{body}</div></body></html>')


# ── --check：数字一致性（渲染前后逐数值比对）────────────────

def _numbers_of(obj, out: list):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append((k, v))
            else:
                _numbers_of(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_of(v, out)


def check(cards: list, html: str) -> int:
    """JSON 里每个数值字段都应能在 HTML 里找到其展示形式。返回缺漏数。"""
    import re
    miss = []
    for i, c in enumerate(cards):
        nums = []
        _numbers_of(c, nums)
        for k, v in nums:
            disp = _num(v)
            if disp == '—':
                continue
            if disp not in html:
                miss.append(f'卡{i + 1} 字段 {k}={v}（展示 {disp}）未见于 HTML')
    for m in miss:
        print('MISS ' + m, file=sys.stderr)
    print(f'check: {len(miss)} missing / total cards {len(cards)}')
    return len(miss)


# ---------- PNG 导出：聊天宿主（九方智投等）的最终交付形态（公共实现在 src/html2png.py） ----------
from html2png import export_png  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='invest-skill 小白卡渲染器')
    ap.add_argument('input', help='NoviceCard JSON 文件（数组或单对象）')
    ap.add_argument('-o', '--output', help='输出 HTML 路径（缺省打印到 stdout）')
    ap.add_argument('--check', metavar='HTML', help='校验已渲染 HTML 与 JSON 数字一致性')
    ap.add_argument('--png', metavar='PATH', help='额外导出整页 PNG（需本机 Chrome/Edge；聊天宿主交付形态）')
    a = ap.parse_args()

    data = json.loads(Path(a.input).read_text(encoding='utf-8'))
    cards = data if isinstance(data, list) else [data]
    for c in cards:
        if c.get('schema') != 'invest-novice-card/1':
            print(f'warn: 卡 {c.get("title", "?")} schema 不是 invest-novice-card/1', file=sys.stderr)

    if a.check:
        html = Path(a.check).read_text(encoding='utf-8')
        sys.exit(1 if check(cards, html) else 0)

    html = render_page(cards, title=Path(a.input).stem)
    if a.output:
        Path(a.output).write_text(html, encoding='utf-8')
        print(f'written {a.output} ({len(cards)} cards)')
    elif not a.png:
        sys.stdout.write(html)
    if a.png:
        export_png(html, a.png)


if __name__ == '__main__':
    main()
