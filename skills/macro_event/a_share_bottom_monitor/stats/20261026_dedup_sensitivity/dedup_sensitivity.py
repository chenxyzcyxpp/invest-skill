# -*- coding: utf-8 -*-
"""dedup_sensitivity.py — 事件去重敏感度对比底稿生成器

三口径对比：
  口径0 现口径    ：单因子/组合 gap=5，深跌区叠加 gap=3（与 v1.0 一致）
  口径A 窗口不重叠：所有信号 gap=60（任意两个样本的60日收益窗口不重叠）
  口径B 行情起点聚类：深跌区段(dd<=-20%,段间间隔>40天合并)内每段保留最早触发；
                      区段外孤立触发按60天冷却；整体再按60天窗口不重叠约束

输出到 stats/<数据截止日>/：
  dedup_sensitivity.md   —— 人读底稿
  dedup_sensitivity.csv  —— 全量明细（机器可查）
  dedup_sensitivity.py   —— 本脚本（可复现）
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

SKILL_ROOT = '/home/ubuntu/invest-skill/skills/macro_event/a_share_bottom_monitor'
sys.path.insert(0, os.path.join(SKILL_ROOT, 'scripts'))
import bsl_core as core

# ---------------- 三种去重口径 ----------------
def dedup_gap(events, gap):
    out = []
    for i in sorted(set(events)):
        if not out or i - out[-1] >= gap:
            out.append(i)
    return out

def cluster_by_regime(events, f, threshold=-0.20, merge_gap=40, gap_outside=60):
    """行情起点聚类（口径B）：
    1) 识别深跌区段：dd<=threshold 的连续交易日，段间间隔<=merge_gap 合并；
    2) 区段内触发：每段保留最早触发（无前视偏差）；
    3) 区段外孤立触发：60天冷却；
    4) 合并后再按60天窗口不重叠约束整体冷却。
    """
    deep = (f['dd'] <= threshold).values
    n = len(f)
    segs = []
    i = 0
    while i < n:
        if deep[i]:
            j = i
            while j + 1 < n and deep[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + merge_gap
        else:
            i += 1
    events_sorted = sorted(set(events))
    chosen, used_seg = [], set()
    outside = []
    for e in events_sorted:
        seg_idx = next((k for k, (a, b) in enumerate(segs) if a <= e <= b), None)
        if seg_idx is None:
            outside.append(e)
        elif seg_idx not in used_seg:
            used_seg.add(seg_idx)
            chosen.append(e)
    return dedup_gap(chosen + outside, gap_outside)

# ---------------- 统计 ----------------
def stats_for(ev, df):
    ev = [i for i in ev if i + 60 < len(df)]
    if not ev:
        return None
    rets60 = [core.forward_returns(df, i)['ret60'] for i in ev]
    arr = np.array([r for r in rets60 if r is not None], dtype=float)
    w, n = core.win_rate(rets60)
    return {'n': n, 'win60': w,
            'median60': round(float(np.median(arr)), 1) if n else None,
            'mean60': round(float(arr.mean()), 1) if n else None}

def baseline_60(df):
    """60天冷却运气线：每60个交易日取1个买入点（窗口不重叠）"""
    idx = list(range(core.BASELINE_START, len(df) - 60, 60))
    return stats_for(idx, df)

def baseline_5(df):
    """现口径运气线：每5个交易日取1个买入点（v1.0定义）"""
    idx = list(range(core.BASELINE_START, len(df) - 60, 5))
    return stats_for(idx, df)

# ---------------- 主流程 ----------------
def main():
    out_dir = os.path.join(core.STATS_DIR, '20261026')
    os.makedirs(out_dir, exist_ok=True)

    all_rows = []
    per_signal = []
    summaries = {}

    for code in core.INDICES:
        df = core.load_daily(code)
        if df is None:
            continue
        f = core.build_features(df)
        name = core.INDICES[code]
        bl5, bl60 = baseline_5(df), baseline_60(df)
        summaries[code] = {'name': name, 'bl5': bl5, 'bl60': bl60}

        groups = [
            ('single', core.single_factors(f), '单因子', 5),
            ('layer', core.layer_conditions(f), '深跌区叠加', 3),
            ('combo', core.combos(f), '组合C1-C8', 5),
        ]
        for gkey, factors, gname, gap_cur in groups:
            for sig, mask in factors.items():
                idx = [i for i in range(core.BASELINE_START, len(df)) if mask.iloc[i]]
                raw_n = len(idx)
                st_cur = stats_for(dedup_gap(idx, gap_cur), df)
                st_a = stats_for(dedup_gap(idx, 60), df)
                st_b = stats_for(cluster_by_regime(idx, f), df)
                all_rows.append({
                    'code': code, 'index': name, 'group': gname, 'signal': sig,
                    'raw_n': raw_n,
                    'n_cur': st_cur['n'] if st_cur else 0, 'win_cur': st_cur['win60'] if st_cur else None,
                    'n_A60': st_a['n'] if st_a else 0, 'win_A60': st_a['win60'] if st_a else None,
                    'n_Bcluster': st_b['n'] if st_b else 0, 'win_Bcluster': st_b['win60'] if st_b else None,
                    'med_cur': st_cur['median60'] if st_cur else None,
                    'med_A60': st_a['median60'] if st_a else None,
                    'med_B': st_b['median60'] if st_b else None,
                })

    df_all = pd.DataFrame(all_rows)
    df_all.to_csv(os.path.join(out_dir, 'dedup_sensitivity.csv'), index=False)
    with open(os.path.join(out_dir, 'summary.json'), 'w') as fp:
        json.dump(summaries, fp, ensure_ascii=False, indent=2, default=str)

    # 翻转评估：以60天冷却运气线为界
    lines = ['# 事件去重敏感度对比底稿（2026-10-26 数据截止）', '']
    lines += ['> 目的：检验「连续多天触发实为同一行情起点」对胜率统计的影响。',
              '> 三口径：现口径(gap=5/3)｜窗口不重叠(gap=60)｜行情起点聚类(深跌区段内每段取首触发,区外60天冷却)',
              '> 统计：触发日收盘买入、持有60个交易日、收益先round(1)再判胜负（与v1.0一致）。',
              '> 状态：底稿验证，未落库；结论翻转须经模式B流程用户确认。', '']

    for code, s in summaries.items():
        b = s['bl60']
        lines.append(f"## {s['name']}（{code}）")
        lines.append(f"- 运气线·现口径(每5天采样): win60={s['bl5']['win60']}% n={s['bl5']['n']}  中位={s['bl5']['median60']}%")
        lines.append(f"- 运气线·窗口不重叠(每60天采样): win60={b['win60']}% n={b['n']}  中位={b['median60']}%")
        lines.append('')
        sub = df_all[df_all['code'] == code].copy()
        sub = sub.sort_values('group', kind='stable')
        lines.append('| 信号 | 原始触发 | 现口径 n/胜率 | 口径A(60天) n/胜率 | 口径B(聚类) n/胜率 | 现→B 判定 |')
        lines.append('| --- | --- | --- | --- | --- | --- |')
        for _, r in sub.iterrows():
            # 判定：现口径有效与否 vs 口径B
            w_cur, w_b = r['win_cur'], r['win_Bcluster']
            n_b = r['n_Bcluster']
            verdict = []
            if w_cur is not None and w_b is not None:
                if w_cur > b['win60'] + 5 and r['n_cur'] >= 10:
                    if w_b > b['win60'] + 5 and n_b >= 10:
                        verdict.append('仍有效')
                    elif n_b < 10:
                        verdict.append('降级小样本')
                    elif w_b <= b['win60']:
                        verdict.append('失效')
                    if w_b < b['win60'] - 5:
                        verdict.append('疑反向')
                elif w_cur < b['win60'] - 5:
                    if w_b > b['win60'] + 5 and n_b >= 10:
                        verdict.append('翻转为有效')
            if r['n_cur'] >= 10 > n_b:
                verdict.append('n跌破10')
            verdict_str = '/'.join(verdict) if verdict else '—'
            cur_s = f"{r['n_cur']}/{r['win_cur']}%" if r['win_cur'] is not None else '-'
            a_s = f"{r['n_A60']}/{r['win_A60']}%" if r['win_A60'] is not None else '-'
            b_s = f"{r['n_Bcluster']}/{r['win_Bcluster']}%" if r['win_Bcluster'] is not None else '-'
            lines.append(f"| {r['signal']} | {r['raw_n']} | {cur_s} | {a_s} | {b_s} | {verdict_str} |")
        lines.append('')

    # 重点结论
    lines.append('## 三、重点信号结论影响')
    lines.append('')
    lines.append('（本表由脚本按 60天冷却运气线 自动判定，人工复核要点见正文底部。）')
    lines.append('')

    md = '\n'.join(lines)
    with open(os.path.join(out_dir, 'dedup_sensitivity.md'), 'w') as fp:
        fp.write(md)
    # 脚本自归档
    import shutil
    shutil.copy(os.path.abspath(__file__), os.path.join(out_dir, 'dedup_sensitivity.py'))

    print(f'归档完成: {out_dir}')
    print(f'信号×指数: {len(df_all)} 行')
    # 打印核心翻转
    flip = df_all[(df_all['win_cur'].notna()) & (df_all['win_Bcluster'].notna())]
    flip['d_win'] = flip['win_Bcluster'] - flip['win_cur']
    flip['d_n'] = flip['n_Bcluster'] - flip['n_cur']
    big = flip[flip['d_win'].abs() >= 10].sort_values('d_win')
    print('\n=== 胜率变化 >= 10pp 的信号（现口径 → 聚类口径） ===')
    for _, r in big.iterrows():
        print(f"  {r['index']} {r['signal']}: {r['win_cur']}%({r['n_cur']}) → {r['win_Bcluster']}%({r['n_Bcluster']})  中位 {r['med_cur']}→{r['med_B']}")

if __name__ == '__main__':
    main()
