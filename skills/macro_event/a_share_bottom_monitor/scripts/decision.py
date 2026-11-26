# -*- coding: utf-8 -*-
# Authors: Warwick
"""decision.py — 模式C 日常下跌决策检查表（v1.2 决策层扩展）

把「状态判断」补成「状态 + 路径 + 执行」：复用 monitor.check_index 取当前状态，
复用 path_map.json 取路径分布，逐项输出 8 问检查表，末尾给出唯一动作结论。
F/G/H 依赖实时资金流/财报/外盘，本 skill 无对应数据源，只能做
「结构化人工输入 + 缺失标注」——禁止自动抓取、禁止用模型记忆或搜索结果填数。

用法：
    python3 scripts/decision.py --code 399006.SZ
    python3 scripts/decision.py --code 399006.SZ --cost 2700 --risk-budget 5 --inputs inputs.json
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsl_core as core
import monitor

DECISION_LOG = os.path.join(core.REFS_DIR, 'decision-log.md')
LOG_HEADER = ('# 决策日志（只增不改）\n\n'
              '> 由 `scripts/decision.py` 在输出「判定失败减仓并复盘」类动作时自动追加。\n'
              '> 同一交易日 + 同一指数 + 同一动作不重复追加。人工不得修改已有行。\n\n'
              '| 日期 | 指数 | 动作 | 买点 | 理由 | 失效条件 | 复盘日 |\n'
              '| --- | --- | --- | --- | --- | --- | --- |\n')


def load_inputs(path):
    """结构化外部输入：只接受显式提供的字段，缺失一律 None（输出时标注未提供）。"""
    out = {k: None for k in core.RULES['external_fields']}
    if not path:
        return out
    if not os.path.exists(path):
        raise FileNotFoundError(f'外部输入文件不存在：{path}')
    text = open(path, encoding='utf-8').read()
    if path.lower().endswith('.json'):
        raw = json.loads(text)
    else:
        raw = {}
        for line in text.splitlines():
            line = line.strip().lstrip('-*` ')
            m = re.split(r'[:：]', line, maxsplit=1)
            if len(m) == 2:
                raw[m[0].strip()] = m[1].strip()
    for k in core.RULES['external_fields']:
        v = raw.get(k)
        if isinstance(v, dict):
            val = v.get('value')
            if val not in (None, '', '未提供'):
                out[k] = {'value': val, 'as_of': v.get('as_of'), 'source': v.get('source')}
        elif v not in (None, '', '未提供'):
            out[k] = {'value': v, 'as_of': '未提供', 'source': '未提供'}
    return out


def val(inputs, key):
    item = inputs.get(key)
    return None if item is None else item['value']


def as_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ('true', 'yes', '是', '延续', 'ok'):
            return True
        if s in ('false', 'no', '否', '断档', '恶化'):
            return False
    return None


def build_questions(r, smap, pmap, inputs, df):
    """逐项判定 8 问，返回 {序号: (状态符号, 说明)}。所有阈值读配置或 core 常量。"""
    S = core.RULES['status']
    missing = core.RULES['missing_text']
    idx = pmap.get('indices', {}).get(r['code'], {}) if pmap else {}
    # 路径分布只挂在【当前触发】的组合上；不得回退到未触发的 primary_combo，
    # 否则仓位上限 / 认错线会引用一个本轮并未成立的组合（适用范围守卫已保证非空）。
    cid = r['combo_hits'][0]
    d = idx.get('combos', {}).get(cid) or {}
    ep = r.get('episode') or {}
    st = r['state']
    tail_q = core.RULES['mae_tail_percentile']
    tail_key = f'mae_p{tail_q}'
    q = {}

    # 1 原始结论是否被证伪
    grades = core.RULES['policy_grades']
    pg, pg_prev = val(inputs, 'policy_grade'), val(inputs, 'policy_grade_prev')
    broken = False
    if pg in grades and pg_prev in grades:
        broken = grades.index(pg) > grades.index(pg_prev)
    elif pg in grades and pg == grades[-1]:
        broken = True
    if not r['combo_hits'] or broken:
        q[1] = (S['fail'], '组合信号已不再触发／政策档断档')
    elif pg is None:
        q[1] = (S['pass'], f'组合信号仍触发（{cid}）；政策档 {missing}')
    else:
        q[1] = (S['pass'], f'组合信号仍触发（{cid}）；政策档未断档（{pg}）')

    # 2 是否放量创本轮新低
    vr = ep.get('vol_ratio') if ep.get('active') else st['vol_ratio']
    new_low = bool(ep.get('active') and ep['last_close'] < ep['prior_min_close'])
    high_vol = vr is not None and vr > core.VR_HIGH
    if high_vol and new_low:
        q[2] = (S['fail'], f'量比 {vr} 且创本轮新低')
    elif high_vol or new_low:
        q[2] = (S['warn'], f'量比 {vr}，创本轮新低={"是" if new_low else "否"}（仅满足其一）')
    else:
        q[2] = (S['pass'], f'量比 {vr}，未放量创新低')

    # 3 是否触发反向信号
    rev = [h['id'] for h in r['reverse_hits'] if h.get('kind') == 'reverse']
    q[3] = ((S['fail'], '反向信号触发：' + '、'.join(rev)) if rev
            else (S['pass'], '未触发反向信号'))

    # 4 当前浮亏处于 MAE 分布哪个分位
    worst, tail, hist = ep.get('worst_drawdown_pct'), d.get(tail_key), d.get('mae_worst')
    if worst is None or tail is None or hist is None:
        q[4] = (S['missing'], missing)
    elif worst <= hist:
        q[4] = (S['fail'], f'当前最深浮亏 {worst}% 已越过历史极值 {hist}%')
    elif worst <= tail:
        q[4] = (S['warn'], f'当前最深浮亏 {worst}% 已进入 p{tail_q} 尾部（阈值 {tail}%）')
    else:
        q[4] = (S['pass'], f'当前最深浮亏 {worst}% 未进 p{tail_q} 尾部（阈值 {tail}%）')

    # 5 右侧确认是否到位
    ma5 = ep.get('ma5')
    above = bool(ep.get('active') and ma5 is not None and ep['last_close'] > ma5)
    quiet = bool(ep.get('active') and ep.get('dd_pct') is not None
                 and ep['dd_pct'] / 100 < core.DEEP25
                 and ep.get('vol_ratio') is not None
                 and ep['vol_ratio'] < core.VR_MID)
    q[5] = ((S['pass'], '收盘站回 ma5' if above else '深跌区缩量企稳') if (above or quiet)
            else (S['warn'], '收盘未站回 ma5，且深跌区未缩量企稳'))

    # 6 政策中间变量是否延续（外部输入）
    g_keys = core.RULES['external_groups']['G 资金与政策执行进度']
    provided_g = [k for k in g_keys if val(inputs, k) is not None]
    pok = as_bool(val(inputs, 'policy_execution_ok'))
    if pok is False:
        q[6] = (S['warn'], '人工输入：政策中间变量未延续')
    elif pok is True:
        q[6] = (S['pass'], '人工输入：政策中间变量延续')
    elif not provided_g:
        q[6] = (S['missing'], missing)
    else:
        q[6] = (S['missing'], f'已提供 {len(provided_g)} 项但缺自评布尔；{missing}')

    # 7 外部环境是否恶化（外部输入）
    ext = as_bool(val(inputs, 'external_deterioration'))
    if ext is True:
        q[7] = (S['warn'], '人工输入：外部环境恶化')
    elif ext is False:
        q[7] = (S['pass'], '人工输入：外部环境未恶化')
    else:
        q[7] = (S['missing'], missing)

    # 8 是否已到时间止损
    days = ep.get('consecutive_days', 0)
    q[8] = ((S['fail'], f'本轮连续 {days} 交易日，已达持有期末档') if days >= core.HOLD_DAYS[-1]
            else (S['pass'], f'本轮连续 {days} 交易日，未到时间止损'))

    return q, cid, d


def decide(q):
    """唯一动作结论。硬纪律：gate 两项未同时过关不得输出「可执行下一批」。"""
    S, A = core.RULES['status'], core.RULES['actions']
    fatal = [i for i in core.RULES['fatal_questions'] if q[i][0] == S['fail']]
    if fatal:
        return A['fail'], '第 ' + '、'.join(map(str, fatal)) + ' 项判定失败'
    gates = core.RULES['gate_questions']
    gate_ok = all(q[i][0] == S['pass'] for i in gates)
    ext_bad = [i for i in core.RULES['external_questions']
               if q[i][0] in (S['warn'], S['fail'])]
    other_warn = [i for i in q if q[i][0] == S['warn']]
    if ext_bad or any(q[i][0] == S['fail'] for i in gates):
        return A['pause'], '存在证伪/外部恶化项，暂停加仓'
    if other_warn:
        return A['hold'], '第 ' + '、'.join(map(str, other_warn)) + ' 项为警示，右侧或路径未确认'
    if gate_ok:
        return A['next_batch'], '8 问无致命项，路径与右侧确认均过关'
    return A['hold'], '未满足加仓条件'


def append_log(date, code, action, buy_point, reason, invalid_cond):
    """只增不改；同一交易日 + 同一指数 + 同一动作不重复追加。"""
    if not os.path.exists(DECISION_LOG):
        with open(DECISION_LOG, 'w', encoding='utf-8') as fp:
            fp.write(LOG_HEADER)
    text = open(DECISION_LOG, encoding='utf-8').read()
    if f'| {date} | {code} | {action} |' in text:
        return False
    review = str((datetime.strptime(date, '%Y-%m-%d')
                  + timedelta(days=core.HOLD_DAYS[-1])).date())
    with open(DECISION_LOG, 'a', encoding='utf-8') as fp:
        fp.write(f'| {date} | {code} | {action} | {buy_point} | {reason} '
                 f'| {invalid_cond} | {review}（自然日近似） |\n')
    return True


def render_not_applicable(r, smap, pmap, code, args):
    """适用范围守卫：本轮无有效组合信号触发时只输出状态层提示，不进入 8 问判定。

    见 references/decision-rules.md 第 9 节。不改动 decide() 逻辑、不写决策日志、
    不计算风险预算（路径分布必须挂在【当前触发】的组合上）。
    """
    P = core.RULES['presentation']
    NA = P['not_applicable']
    L = P['info_labels']
    today = datetime.now().strftime('%Y-%m-%d')
    lines = [
        f'# {NA["title"]} · {r["name"]}（{code}）',
        '',
        f'> **{NA["conclusion"].format(verdict=r["verdict"])}**',
        '',
        '| 项目 | 内容 |',
        '| --- | --- |',
        f'| {L["asof"]} | {today} |',
        f'| {L["daily_cutoff"]} | {r["state"]["date"]} |',
        f'| {L["signal_map"]} | v{smap["version"]} |',
        f'| {L["path_map"]} | v{pmap["version"]} |',
        f'| 状态层判断（不受本表影响） | {r["verdict"]} |',
        f'| 本轮组合 | {P["combo_none_text"]} |',
        '',
        f'> {NA["why"]}',
    ]
    if args.cost is not None or args.risk_budget is not None:
        lines += ['', '> 已提供的成本价／风险预算本轮不参与计算：路径分布须挂在'
                  '当前触发的组合上，待组合信号触发后重跑即可生效。']
    lines += [
        '',
        f'## {NA["watch_label"]}',
        '',
        NA['watch_text'],
        '',
        f'## {P["risk_title"]}',
        '',
        f'- 数据截止 {r["state"]["date"]}；信号地图 v{smap["version"]}／'
        f'路径分布 v{pmap["version"]}。',
        f'- 数据局限：{core.RULES["data_caveats"]}',
        f'- {core.RULES["disclaimer"]}',
        '',
        f'> **{P["disclaimer_head"]}**',
        '>',
        f'> {P["full_disclaimer"]}',
        '',
        NA['no_log'],
    ]
    return '\n'.join(monitor.humanize(x) for x in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True)
    ap.add_argument('--cost', type=float, default=None)
    ap.add_argument('--risk-budget', type=float, default=None)
    ap.add_argument('--inputs', default='')
    args = ap.parse_args()

    smap = monitor.load_signal_map()
    pmap = monitor.load_path_map()
    if pmap is None:
        print('[ERROR] path_map.json 缺失，请先运行 python3 scripts/path_stats.py')
        sys.exit(2)
    r = monitor.check_index(args.code, smap)
    if r is None:
        print(f'[ERROR] 无 {args.code} 日线数据')
        sys.exit(2)

    # 适用范围守卫（decision-rules.md 第 9 节）：本轮未触发有效组合信号时，
    # 不存在「可被证伪的原始结论」，不进入 8 问、不给动作、不写日志。
    if not r['combo_hits']:
        print(render_not_applicable(r, smap, pmap, args.code, args))
        return 0

    df = core.load_daily(args.code)
    inputs = load_inputs(args.inputs)
    q, cid, d = build_questions(r, smap, pmap, inputs, df)
    action, reason = decide(q)

    # 硬纪律写进代码：gates 未同时过关绝不输出「可执行下一批」
    if action == core.RULES['actions']['next_batch'] and not all(
            q[i][0] == core.RULES['status']['pass'] for i in core.RULES['gate_questions']):
        raise AssertionError('硬纪律被破坏：gate 未同时过关却输出可执行下一批')

    P = core.RULES['presentation']
    L = P['info_labels']
    tail = core.RULES['mae_tail_percentile']
    hold = core.HOLD_DAYS[-1]
    today = datetime.now().strftime('%Y-%m-%d')
    combo_disp = ('、'.join(r['combo_hits']) if r['combo_hits']
                  else P['combo_none_text'])
    lines = []

    # ---- 标题 + 结论前置 ----
    lines.append(f'# {P["decision_title"]} · {r["name"]}（{args.code}）')
    lines.append('')
    lines.append(f'> **{P["action_prefix"]}：{action}**（{reason}）')
    lines.append('')
    lines.append('| 项目 | 内容 |')
    lines.append('| --- | --- |')
    lines.append(f'| {L["asof"]} | {today} |')
    lines.append(f'| {L["daily_cutoff"]} | {r["state"]["date"]} |')
    lines.append(f'| {L["signal_map"]} | v{smap["version"]} |')
    lines.append(f'| {L["path_map"]} | v{pmap["version"]} |')
    lines.append(f'| 状态层判断（不因本表改变） | {r["verdict"]} |')
    lines.append(f'| 本轮组合 | {combo_disp} |')
    lines.append('')
    lines.append(f'> {P["decision_note"]}')
    lines.append('')

    # ---- 一、8 问检查表（状态符号与判定文案原样保留） ----
    lines.append('## 一、8 问检查表')
    lines.append('')
    lines.append('| # | 检查项 | 结果 | 判定依据 |')
    lines.append('| --- | --- | --- | --- |')
    for i, label in enumerate(core.RULES['question_labels'], start=1):
        s, why = q[i]
        lines.append(f'| {i} | {label} | {s} | {why} |')
    lines.append('')
    legend = core.RULES['presentation']['status_legend']
    lines.append('> **状态图例**：' + '　｜　'.join(f'{k} {v}' for k, v in legend.items()))
    lines.append('')

    # ---- 二、风险预算与认错线（计算不变，只换标签与呈现） ----
    lines.append('## 二、风险预算与认错线')
    lines.append('')
    lines.append('| 项目 | 结果 | 说明 |')
    lines.append('| --- | --- | --- |')
    mae_worst, mae_p50 = d.get('mae_worst'), d.get('mae_p50')
    if args.risk_budget is not None and mae_worst:
        cap = round(args.risk_budget / abs(mae_worst) * 100, 1)
        lines.append(f'| 防尾部仓位上限 | **{cap}%** | 可承受单笔回撤 '
                     f'{args.risk_budget} ÷ 历史最深浮亏 {abs(mae_worst)}；占组合比例 |')
        if mae_p50:
            cap_n = round(args.risk_budget / abs(mae_p50) * 100, 1)
            lines.append(f'| 常规版仓位上限 | {cap_n}% | 按中位最大浮亏 {mae_p50}% 计算，'
                         f'**{core.RULES["not_tail_protected"]}** |')
    else:
        lines.append(f'| 防尾部仓位上限 | {core.RULES["missing_text"]} | '
                     '需补充组合层面可承受的单笔回撤 R；或该组合无路径分布 |')
    vol = core.annualized_vol(df)
    lines.append(f'| 近端年化波动 | {vol}% | 按持有期末档窗口计算；'
                 f'**{core.RULES["no_leverage"]}** |')
    if args.cost is not None and mae_worst is not None:
        admit = round(args.cost * (1 + mae_worst / 100), 2)
        lines.append(f'| 认错线 | **{admit}** | 自身成本 {args.cost} × '
                     f'(1 + 历史最深浮亏 {mae_worst}/100)；不锚定指数点位 |')
    else:
        lines.append(f'| 认错线 | {core.RULES["missing_text"]} | '
                     '需补充用户实际成本价；不锚定指数点位 |')
    days_now = (r.get('episode') or {}).get('consecutive_days', 0)
    lines.append(f'| 时间止损 | 未到期 | 本轮连续 {days_now} 交易日，'
                 f'达到 {hold} 交易日即到期；分批节奏按批次递减 |')
    lines.append('')
    lines.append('> 仓位与认错线均为历史统计下的风险预算，不是收益承诺。')
    lines.append('')

    # ---- 三、外部输入（汇总 + 折叠清单） ----
    lines.append('## 三、外部输入（F/G/H）')
    lines.append('')
    provided = [k for k in core.RULES['external_fields'] if inputs.get(k)]
    if provided:
        lines.append(f'> 本次已提供 {len(provided)} 项外部输入（逐项列出于下表）；'
                     '其余字段一律「未提供，不参与判定」。')
    else:
        lines.append(f'> {P["missing_all"]}')
    lines.append('')
    lines.append('<details>')
    lines.append(f'<summary>展开 {len(core.RULES["external_fields"])} 项外部字段</summary>')
    lines.append('')
    lines.append('| 维度 | 字段 | 取值 | 数据时间 | 来源 |')
    lines.append('| --- | --- | --- | --- | --- |')
    labels = P['external_labels']
    for group, fields in core.RULES['external_groups'].items():
        for k in fields:
            item = inputs.get(k)
            if item:
                lines.append(f'| {group} | {labels.get(k, k)} | {item["value"]} '
                             f'| {item["as_of"]} | {item["source"]} |')
            else:
                lines.append(f'| {group} | {labels.get(k, k)} | 未提供 '
                             '| 未提供 | 未提供 |')
    lines += ['', '</details>', '']
    lines.append('- 政策档位（S/A/B/C/D）仅作为外部输入字段接入，本 skill 不实现政策打分逻辑。')
    pe_rev = [x for x in smap['indices'].get(args.code, {}).get('reverse_signals', [])
              if 'PE' in str(x.get('id'))]
    for x in pe_rev:
        w, n = x.get('win60'), x.get('n')
        stat = f'历史胜率 {w}%' if w is not None else '历史胜率 未提供'
        stat += f'／样本 {n} 次' if n is not None else '／样本 未提供'
        lines.append(f'- **F 维度提示**：`{x["id"]}` 属反向信号（{stat}），'
                     '不得作为买入依据；应看盈利增速与预期差。')
    lines.append('')

    # ---- 四、数据说明与风险提示（免责收敛一处） ----
    lines.append(f'## 四、{P["risk_title"]}')
    lines.append('')
    lines.append(f'- 数据截止 {r["state"]["date"]}；信号地图 v{smap["version"]}／'
                 f'路径分布 v{pmap["version"]}。')
    lines.append(f'- 数据局限：{core.RULES["data_caveats"]}')
    lines.append(f'- {core.RULES["disclaimer"]}')
    lines.append('')
    lines.append(f'> **{P["disclaimer_head"]}**')
    lines.append('>')
    lines.append(f'> {P["full_disclaimer"]}')
    lines.append('')
    lines += monitor.glossary_block()
    lines.append('')

    # ---- 补充 ----
    lines.append(f'## 补充 · {P["followup_title"]}')
    lines.append('')
    lines.append('成本价、风险预算与外部输入均可在命令行补齐后重跑；'
                 '外部字段需带数据时间与来源，缺失项仍标注「未提供，不参与判定」。')
    lines.append('')
    lines.append('```bash')
    lines.append('python3 scripts/decision.py --code <指数代码> --cost <实际成本价> '
                 '--risk-budget <R> --inputs <输入文件>')
    lines.append('```')

    print('\n'.join(monitor.humanize(x) for x in lines))

    # 减仓/认错动作 → 追加决策日志（只增不改、同交易日不重复）；运行提示走 stderr
    if action in (core.RULES['actions']['fail'], core.RULES['actions']['pause']):
        date = r['state']['date']
        buy_point = (f'{cid} 首触发 {r["episode"]["first_date"]}'
                     if r.get('episode') and r['episode'].get('active') and cid
                     else P['combo_none_text'])
        added = append_log(date, args.code, action, buy_point, reason,
                           '组合不再触发／越过历史最深浮亏／时间止损到期')
        print(f'[决策日志] {"已追加 1 条" if added else "同交易日同动作已存在，未重复追加"}',
              file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
