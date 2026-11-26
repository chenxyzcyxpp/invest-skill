# -*- coding: utf-8 -*-
# Authors: Warwick
"""monitor.py — 抄底监控（模式A）

计算各指数当前状态 → 比对 references/signal_map.json 信号地图 → 输出监控报告。

用法：
    python3 monitor.py                        # 输出到终端
    python3 monitor.py --out report.md        # 写入文件
    python3 monitor.py --codes 399006.SZ,932000.CSI
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsl_core as core

HISTORY_FILE = os.path.join(core.REFS_DIR, 'history-updates.md')
STALE_DAYS = 180   # 信号地图过期阈值（天）
PATH_MAP_JSON = os.path.join(core.REFS_DIR, 'path_map.json')

# 只把「统计重跑类」条目当作过期计时基准；功能扩展（决策层扩展）不得重置计时。
# 「重大修订」纳入：本地 v1.1 台账标题为「去重口径重大修订」，属实质统计重跑。
REBUILD_RE = (r'## \[v[\d.]+\]\s*(\d{4}-\d{2}-\d{2})[^\n]*'
              r'(初版建库|半年度重跑|统计重跑|重大修订)')


def load_signal_map():
    with open(core.SIGNAL_MAP_JSON) as fp:
        return json.load(fp)


def load_path_map():
    """路径分布（v1.2 决策层）。缺失返回 None，由报告标注缺失而非猜测填数。"""
    if not os.path.exists(PATH_MAP_JSON):
        return None
    with open(PATH_MAP_JSON, encoding='utf-8') as fp:
        return json.load(fp)


def map_age_days():
    """从 history 台账解析最近一次「统计重跑」距今天数。"""
    if not os.path.exists(HISTORY_FILE):
        return None
    text = open(HISTORY_FILE, encoding='utf-8').read()
    dates = re.findall(REBUILD_RE, text)
    if not dates:
        return None
    last = datetime.strptime(dates[0][0], '%Y-%m-%d')
    return (datetime.now() - last).days


def triggered_now(mask):
    """掩码最后一日（或连跌计数）是否触发。"""
    if mask is None or len(mask) == 0:
        return False
    v = mask.iloc[-1]
    return bool(v) if hasattr(v, 'item') is False else bool(v)


def check_index(code, smap):
    df = core.load_daily(code)
    if df is None:
        return None
    f = core.build_features(df)
    st = core.current_state(df, f)
    singles = core.single_factors(f)
    layers = core.layer_conditions(f)
    combos_m = core.combos(f)
    entry = smap['indices'].get(code, {})
    name = core.INDICES.get(code, code)

    eff, rev = [], []
    for sig in entry.get('effective_signals', []):
        key = sig['key']
        hit = triggered_now(singles.get(key) if key in singles else layers.get(key))
        if hit:
            eff.append({'id': sig['id'], 'hit': True, 'win60': sig.get('win60'),
                        'n': sig.get('n'), 'median60': sig.get('median60')})
    for sig in entry.get('reverse_signals', []):
        key = sig['key']
        hit = triggered_now(singles.get(key) if key in singles else layers.get(key))
        if hit:
            rev.append({'id': sig['id'], 'win60': sig.get('win60'), 'n': sig.get('n'),
                        'kind': sig.get('kind', 'reverse')})

    combo_hits = []
    for cid in entry.get('combos_effective', []):
        key = [k for k in combos_m if k.startswith(cid + '_')]
        if key and triggered_now(combos_m[key[0]]):
            combo_hits.append(cid)
    combo_bad = []
    for cid in entry.get('combos_reverse', []):
        key = [k for k in combos_m if k.startswith(cid + '_')]
        if key and triggered_now(combos_m[key[0]]):
            combo_bad.append(cid)

    # 组合信号的历史统计（从归档CSV或signal_map快照）
    combo_stats = entry.get('combo_stats', {})

    verdict = '观察'
    if combo_hits:
        verdict = '具备左侧条件（组合信号触发）'
    elif eff:
        verdict = '观察（有效单信号已触发，组合条件未齐）'
    elif any(h['kind'] == 'reverse' for h in rev) or combo_bad:
        verdict = '不具备（反向信号触发）'
    elif rev:
        verdict = '观察（仅无效信号触发，无有效信号）'
    elif st['dd'] <= -25:
        verdict = '观察（深回撤区，条件未齐）'
    else:
        verdict = '不具备（未到门槛）'

    # v1.2 决策层：当前轮路径落点（只对触发中的有效组合计算）
    episode = None
    if combo_hits:
        cid = combo_hits[0]
        key = next((k for k in combos_m if k.startswith(cid + '_')), None)
        if key is not None:
            ep = core.episode_info(df, f, combos_m[key])
            pmap = load_path_map()
            if pmap and ep.get('active'):
                d = (pmap.get('indices', {}).get(code, {})
                     .get('combos', {}).get(cid) or {})
                mw = d.get('mae_worst')
                tail_key = f"mae_p{core.RULES['mae_tail_percentile']}"
                if mw is not None:
                    ep['mae_worst_hist'] = mw
                    ep['beyond_worst'] = bool(ep['worst_drawdown_pct'] <= mw)
                    ep['in_tail'] = bool(d.get(tail_key) is not None
                                         and ep['worst_drawdown_pct'] <= d[tail_key])
                    ep['mae_tail_value'] = d.get(tail_key)
            episode = ep

    return {'code': code, 'name': name, 'state': st, 'effective_hits': eff,
            'reverse_hits': rev, 'combo_hits': combo_hits, 'combo_bad': combo_bad,
            'combo_stats': combo_stats, 'verdict': verdict, 'episode': episode}


def humanize(text):
    """呈现层：把内部变量名/术语换成人读表述。只作用于文案，不改动任何判定或数值。

    替换按「长短语优先」进行，避免把整句拆碎产生病句；分位数字仍由配置提供，
    不在此重复定义口径常量。
    """
    P = core.RULES['presentation']
    tail = core.RULES['mae_tail_percentile']
    out = str(text)
    for a, b in P['term_replacements']:
        out = out.replace(a, b)
    out = out.replace(f'未进 p{tail} 尾部', '未进尾部风险区')
    out = out.replace(f'进入 p{tail} 尾部', '进入尾部风险区')
    out = out.replace(f'p{tail} 尾部', '尾部风险区')
    return out


def glossary_block():
    """可折叠名词说明（报告末尾）。"""
    P = core.RULES['presentation']
    rows = ['<details>', f'<summary>{P["glossary_title"]}</summary>', '',
            '| 术语 | 含义 |', '| --- | --- |']
    ctx = dict(hold=core.HOLD_DAYS[-1], tail=core.RULES['mae_tail_percentile'],
               gap=core.GAP_SINGLE)
    for term, desc in P['glossary']:
        rows.append(f'| {term} | {desc.format(**ctx)} |')
    rows += ['', '</details>']
    return rows


def render_report(results, smap, age):
    P = core.RULES['presentation']
    L = P['info_labels']
    tail = core.RULES['mae_tail_percentile']
    hold = core.HOLD_DAYS[-1]
    today = datetime.now().strftime('%Y-%m-%d')
    lines = []
    cutoffs = [r['state']['date'] for r in results if r]
    data_cutoff = max(cutoffs) if cutoffs else '无'
    pmap = load_path_map()

    # ---- 估值数据截止 ----
    pe_cutoffs = {}
    for code in core.INDICES:
        if code in core.NO_PE:
            continue
        pe = core.load_pe(code)
        if pe is not None:
            pe_cutoffs[code] = str(pe['trade_date'].max().date())
    pe_desc = '；'.join(f'{core.INDICES[c]} {d}' for c, d in pe_cutoffs.items()) or '无'
    no_pe = '、'.join(core.INDICES[c] for c in core.NO_PE) or '无'
    if no_pe != '无':
        pe_desc += f'（{no_pe} 无估值数据）'

    # ---- 一句话结论（全部由运行时结果统计，不写死） ----
    n_ready = sum(1 for r in results if r and r['verdict'].startswith('具备'))
    n_watch = sum(1 for r in results if r and r['verdict'].startswith('观察'))
    n_none = sum(1 for r in results if r and r['verdict'].startswith('不具备'))
    with_combo = [r for r in results if r and r['combo_hits']]
    with_rev = [r for r in with_combo if any(
        h.get('kind') == 'reverse' for h in r['reverse_hits'])]
    summary = f'{n_ready} 个「具备左侧条件」、{n_watch} 个「观察」'
    if n_none:
        summary += f'、{n_none} 个「不具备」'
    summary += (f'；{len(with_combo)} 个指数触发有效组合信号'
                if with_combo else '；本次无组合信号触发')
    if with_rev:
        summary += f'，其中 {len(with_rev)} 个同时伴随反向信号，须连同路径风险与证伪条件一并阅读'

    lines.append(f'# {P["monitor_title"]} · {today}')
    lines.append('')
    lines.append(f'> **一句话结论**：本次监控 {len(results)} 个指数，{summary}。')
    lines.append('')
    lines.append('| 项目 | 内容 |')
    lines.append('| --- | --- |')
    lines.append(f'| {L["asof"]} | {today} |')
    lines.append(f'| {L["daily_cutoff"]} | {data_cutoff} |')
    lines.append(f'| {L["pe_cutoff"]} | {pe_desc} |')
    lines.append(f'| {L["signal_map"]} | v{smap["version"]}（{smap["updated"]} 重跑） |')
    lines.append(f'| {L["path_map"]} | v{pmap["version"] if pmap else "缺失"}'
                 f'（数据截止 {pmap["data_cutoff"] if pmap else "缺失"}） |')
    lines.append(f'| {L["method"]} | '
                 f'{P["method_text"].format(hold=hold, gap=core.GAP_SINGLE)} |')
    lines.append('')
    if age is not None and age > STALE_DAYS:
        lines.append(f'> ⚠️ 信号地图已 {age} 天未重跑（阈值 {STALE_DAYS} 天），结论可能滞后，'
                     '建议先执行半年度重跑。')
        lines.append('')

    # ---- 结论速览（前置，不占章节编号） ----
    lines.append('## 结论速览')
    lines.append('')
    lines.append('| 指数 | 状态判断 | 触发组合 | 反向信号 |')
    lines.append('| --- | --- | --- | --- |')
    for r in results:
        if not r:
            continue
        combo = '、'.join(r['combo_hits']) if r['combo_hits'] else '未触发'
        n_rev = sum(1 for h in r['reverse_hits'] if h.get('kind') == 'reverse')
        lines.append(f'| {r["name"]} | {r["verdict"]} | {combo} | '
                     f'{str(n_rev) + " 项" if n_rev else "未触发"} |')
    lines.append('')
    lines.append('> 状态判断只回答「信号是否满足」；是否执行还需看路径风险、证伪条件'
                 '与日常下跌决策检查表。')
    lines.append('')

    # ---- 一、各指数当前状态 ----
    lines.append('## 一、各指数当前状态')
    lines.append('')
    lines.append('| 指数 | 距250日高点 | 破年线 | 连跌 | 近20日 | 20日回撤加深 | RSI14 | 量比 |')
    lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
    for r in results:
        if not r:
            continue
        s = r['state']
        lines.append(f"| {r['name']} | {s['dd']}% | {s['yl']}% | {s['consec_down']}日 "
                     f"| {s['ret20']}% | {s['dd_deepen']}% | {s['rsi14']} | {s['vol_ratio']} |")
    lines.append('')

    # ---- 二、信号比对 ----
    lines.append('## 二、信号比对')
    lines.append('')
    for r in results:
        if not r:
            continue
        s = r['state']
        base = smap['baseline'].get(r['code'])
        lines.append(f"### {r['name']}（运气线 {base}%）")
        if r['combo_hits']:
            hits = '、'.join(r['combo_hits'])
            stats = []
            for cid in r['combo_hits']:
                cs = r['combo_stats'].get(cid)
                if cs:
                    stats.append(f"{cid}: {cs.get('n')}次/胜率{cs.get('win60')}%/中位{cs.get('median60')}%")
            lines.append(f"- **组合信号触发：{hits}**" + (f"（{'；'.join(stats)}）" if stats else ''))
        if r['effective_hits']:
            hits = '；'.join(f"{h['id']}（{h['win60']}%,{h['n']}次）" for h in r['effective_hits'])
            lines.append(f"- 单因子有效信号触发：{hits}")
        if r['reverse_hits']:
            rev_hits = [h for h in r['reverse_hits'] if h.get('kind') == 'reverse']
            inv_hits = [h for h in r['reverse_hits'] if h.get('kind') != 'reverse']
            if rev_hits:
                hits = '；'.join(f"{h['id']}（{h['win60']}%,{h['n']}次）" for h in rev_hits)
                lines.append(f"- ⚠️ **反向信号触发**：{hits}")
            if inv_hits:
                hits = '；'.join(f"{h['id']}（{h['win60']}%,{h['n']}次）" for h in inv_hits)
                lines.append(f"- 无效信号触发（低于或不优于运气线）：{hits}")
        if r['combo_bad']:
            lines.append(f"- ⚠️ 反向组合触发：{'、'.join(r['combo_bad'])}")
        if not (r['combo_hits'] or r['effective_hits'] or r['reverse_hits'] or r['combo_bad']):
            lines.append('- 无信号触发')
        gaps = []
        if s['dd'] > -30:
            gaps.append(f"距深30%回撤门槛还差 {abs(-30 - s['dd']):.1f}pp")
        if s['consec_down'] < 5:
            gaps.append(f"连跌还差 {5 - s['consec_down']} 日")
        if s['dd_deepen'] is not None and s['dd_deepen'] < 15:
            gaps.append(f"恐慌快跌差 {15 - s['dd_deepen']:.1f}pp")
        if gaps:
            lines.append(f"- 距典型触发门槛：{'；'.join(gaps)}")
        lines.append('')

    # ---- 三、判断（三档措辞一字不改） ----
    lines.append('## 三、判断')
    lines.append('')
    for r in results:
        if not r:
            continue
        lines.append(f"- **{r['name']}：{r['verdict']}**")
    lines.append('')

    # ---- 四、操作纪律 ----
    lines.append('## 四、操作纪律')
    lines.append('')
    lines.append('1. 分批：前两批允许浮亏，最后一档才是胜负手（深证回撤<-35%已转反向不适用；上证/中证2000回撤<-30%为有效档）')
    lines.append('2. 左侧建仓、右侧加重：重仓须等右侧确认（收盘站回5日均线，或深跌区缩量企稳）')
    lines.append('3. 只抄指数/宽基ETF，不抄个股')
    lines.append('4. 小样本信号（触发<10次）不得单独作为重仓依据')
    lines.append('')

    # ---- 五、买点执行与当前轮次（只列有效行） ----
    lines.append('## 五、买点执行与当前轮次')
    lines.append('')
    lines.append('> 组合信号是**状态型**，会连续多个交易日为真；不同买点的持有体验差异很大。'
                 '本节只描述本轮已发生的路径落点，不构成买点建议。')
    lines.append('')
    active = [r for r in results if r and (r.get('episode') or {}).get('active')]
    if active:
        lines.append('| 指数 | 组合 | 首触发日 | 首触发收盘 | 连续交易日 | 最新收盘 | 首日买入当前浮亏 | 期间最低点买入当前收益 |')
        lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for r in active:
            ep = r['episode']
            min_buy = (round((ep['last_close'] / ep['min_close'] - 1) * 100, 2)
                       if ep.get('min_close') else None)
            lines.append(f"| {r['name']} | {'、'.join(r['combo_hits'])} | {ep['first_date']} "
                         f"| {ep['first_close']} | {ep['consecutive_days']} | {ep['last_close']} "
                         f"| {ep['current_drawdown_pct']}% | {min_buy}% |")
        lines.append('')
        if len(active) < len(results):
            lines.append(f'- 其余 {len(results) - len(active)} 个指数{P["empty_episode"]}')
        lines.append('- 「今天触发」不等于「今天才有机会」：连续天数越长，越应把本轮首触发日'
                     '作为决策锚点；首日买入与当前买入的体验差即本轮首触发至今的累计涨跌幅。')
    else:
        lines.append(f'- {P["empty_episode"]}')
    lines.append('')

    # ---- 六、路径风险 ----
    lines.append('## 六、路径风险')
    lines.append('')
    if pmap is None:
        lines.append('- **路径分布文件缺失**：路径统计未提供，不参与判定。')
    else:
        lines.append(f'> 路径分布版本 v{pmap["version"]}｜数据截止 {pmap["data_cutoff"]}｜'
                     '以下均为历史样本分布，不是确定性承诺')
        lines.append('')
        hit_any = False
        tail_key = f'mae_p{tail}'
        gt_keys = [f'prob_mae_gt{t}' for t in core.RULES['mae_gt_thresholds_pct']]
        for r in results:
            if not r or not r['combo_hits']:
                continue
            idx = pmap.get('indices', {}).get(r['code'], {})
            deep = idx.get('deep_random_baseline', {})
            for cid in r['combo_hits']:
                d = idx.get('combos', {}).get(cid)
                if not d:
                    continue
                hit_any = True
                lines.append(f"### {r['name']} · {cid} · 历史 {d['n']} 轮样本")
                lines.append('')
                lines.append(f"- **胜率与区间**：{d['win60']}%（Wilson 95% 置信区间 "
                             f"{d['wilson_ci'][0]}~{d['wilson_ci'][1]}%）；"
                             f"{hold} 日中位收益 {d['median_ret60']}%")
                quantiles = '｜'.join(
                    f"p{q} {d[f'mae_p{q}']}%" for q in core.RULES['mae_quantiles'])
                lines.append(f"- **最大浮亏**：中位 {d['mae_p50']}%／历史最深 {d['mae_worst']}%／"
                             f"尾部阈值 {d.get(tail_key)}%（最差 {tail}% 分位）")
                lines.append(f"- 最大浮亏分位分布：{quantiles}")
                lines.append(f"- 前 {core.HOLD_DAYS[1]} 日跌破买入价 "
                             f"{abs(core.SECOND_LEG) * 100:g}% 的概率 {d['prob_under3_20d']}%")
                lines.append("- 最大浮亏超过 "
                             + '／'.join(f"{t}%" for t in core.RULES['mae_gt_thresholds_pct'])
                             + " 的概率：" + '／'.join(f"{d[k]}%" for k in gt_keys)
                             + f"；回本率 {d['breakeven_rate']}%（最大浮亏中位出现在第 {d['mae_day_median']} 日）")
                fails = '、'.join(x['date'] for x in d['failures'])
                lines.append(f"- 负收益比例：{core.HOLD_DAYS[0]}日 {d['pct_neg_ret10']}%／"
                             f"{core.HOLD_DAYS[1]}日 {d['pct_neg_ret20']}%；"
                             f"失败样本 {len(d['failures'])} 例" + (f"（{fails}）" if fails else ''))
                lines.append(f"- **双基准诚实性**：全时段运气线 {smap['baseline'].get(r['code'])}%，"
                             f"深跌区随机买入 {deep.get('win60')}%（{deep.get('n')} 轮样本）；"
                             f"本组合相对前者 +{d['excess_vs_baseline_pp']}pp、"
                             f"相对后者 +{d['excess_vs_deep_pp']}pp")
                lines.append('')
        if not hit_any:
            lines.append(f'- {P["no_path_stats"]}')
    lines.append('')

    # ---- 七、证伪条件与当前落点（只列有效行） ----
    lines.append('## 七、证伪条件与当前落点')
    lines.append('')
    if active:
        lines.append('| 指数 | 组合 | 首触发日 | 连续交易日 | 当前浮亏 | 本轮最深浮亏 | '
                     '历史浮亏中位数 | 历史最深浮亏 | 最大浮亏分位 | 越过历史极值 |')
        lines.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
        fallback = P['missing_short']
        multi_notes = []
        for r in active:
            ep = r['episode']
            # 落点口径与 check_index.episode 及 decision.py 的 cid 一致：触发组合中的首个
            cid0 = r['combo_hits'][0]
            d = ((pmap or {}).get('indices', {}).get(r['code'], {})
                 .get('combos', {}).get(cid0) or {})
            med, worst = d.get('mae_p50'), d.get('mae_worst')
            med_txt = f'{med}%' if med is not None else fallback
            worst_txt = f'{worst}%' if worst is not None else fallback
            tail_txt = (f'进入最差 {tail}% 分位' if ep.get('in_tail') else '未进尾部')
            lines.append(f"| {r['name']} | {'、'.join(r['combo_hits'])} | {ep['first_date']} "
                         f"| {ep['consecutive_days']} | {ep['current_drawdown_pct']}% "
                         f"| {ep['worst_drawdown_pct']}% | {med_txt} | {worst_txt} "
                         f"| {tail_txt} | {'是' if ep.get('beyond_worst') else '否'} |")
            if len(r['combo_hits']) > 1:
                multi_notes.append(
                    f"{r['name']} 本轮同时触发 {'、'.join(r['combo_hits'])}；"
                    f"表中历史浮亏按落点口径组合 {cid0} 取值（与模式C 风险预算口径一致），"
                    '其余组合的分位分布见第六节。')
        lines.append('')
        for note in multi_notes:
            lines.append(f'- {note}')
        lines.append(f'- {P["risk_budget_hint"]}')
        if len(active) < len(results):
            lines.append(f'- 其余 {len(results) - len(active)} 个指数本轮无有效组合信号触发，'
                         '证伪落点不适用。')
    else:
        lines.append(f'- {P["empty_episode"]}')
    lines.append('')
    lines.append('- **证伪条件**（任一成立即本轮判断作废）：放量创本轮新低／浮亏越过历史最深浮亏／'
                 '反向信号触发／政策与资金执行断档／时间止损到期仍为负。详见《决策层规则》。')
    lines.append('- **认错线锚定用户自己的成本价，不锚定指数点位**；本模式不接收成本价，'
                 '执行层判定见文末补充说明。')
    lines.append(f'- 时间止损：本轮连续触发交易日达到持有期末档（{hold} 交易日）即到期；'
                 '分批节奏与仓位上限见日常下跌决策检查表。')
    lines.append('')

    # ---- 八、外部输入（汇总 + 折叠清单） ----
    lines.append('## 八、外部输入')
    lines.append('')
    lines.append(f'> {P["missing_all"]}')
    lines.append('')
    lines.append('<details>')
    lines.append(f'<summary>展开 {len(core.RULES["external_fields"])} 项外部字段清单</summary>')
    lines.append('')
    lines.append('| 维度 | 字段 | 状态 |')
    lines.append('| --- | --- | --- |')
    labels = P['external_labels']
    for group, fields in core.RULES['external_groups'].items():
        names = '、'.join(labels.get(k, k) for k in fields)
        lines.append(f'| {group} | {names} | {P["missing_group"].format(n=len(fields))} |')
    lines += ['', '</details>', '']
    lines.append('- 政策档位（S/A/B/C/D）仅作为外部输入字段接入，本 skill 不实现政策打分逻辑。')
    lines.append('')

    # ---- 九、数据说明与风险提示（免责收敛一处） ----
    lines.append(f'## 九、{P["risk_title"]}')
    lines.append('')
    lines.append(f'- 数据截止 {data_cutoff}；信号地图 v{smap["version"]}／'
                 f'路径分布 v{pmap["version"] if pmap else "缺失"}。')
    lines.append(f'- 数据局限：{core.RULES["data_caveats"]}')
    lines.append(f'- {core.RULES["disclaimer"]}')
    lines.append('')
    lines.append(f'> **{P["disclaimer_head"]}**')
    lines.append('>')
    lines.append(f'> {P["full_disclaimer"]}')
    lines.append('')
    lines += glossary_block()
    lines.append('')

    # ---- 补充：执行层结论获取方式（命令不散落在正文） ----
    lines.append(f'## 补充 · {P["followup_title"]}')
    lines.append('')
    lines.append('本模式不接收成本价与风险预算，因此不计算仓位上限与认错线。'
                 '若需完整的执行层结论（8 问检查表、唯一动作结论、风险预算、外部输入判定），'
                 '可在补齐数据后单独运行日常下跌决策检查表：')
    lines.append('')
    lines.append('```bash')
    lines.append('python3 scripts/decision.py --code <指数代码> --cost <实际成本价> --risk-budget <R>')
    lines.append('```')
    lines.append('')
    return '\n'.join(humanize(x) if isinstance(x, str) else x for x in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='')
    ap.add_argument('--codes', default='')
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(',') if c.strip()] or list(core.INDICES)

    smap = load_signal_map()
    age = map_age_days()
    results = [check_index(c, smap) for c in codes]
    results = [r for r in results if r]
    report = render_report(results, smap, age)
    if args.out:
        with open(args.out, 'w') as fp:
            fp.write(report)
        print(f'报告已写入 {args.out}')
    else:
        print(report)


if __name__ == '__main__':
    main()
