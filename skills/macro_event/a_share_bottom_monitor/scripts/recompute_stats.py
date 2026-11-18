# -*- coding: utf-8 -*-
# Authors: Warwick
"""recompute_stats.py — 半年度全量重跑（模式B）

对每个指数重算七类统计（前六类口径与 v1.0/v1.1 完全一致，第七类为 v1.2 新增
路径分布），归档到 stats/<数据截止日>/，并与上一版归档逐信号比对，输出变更
分级建议（微调/修订/重大）。

用法：
    python3 recompute_stats.py                 # 重跑全部指数
    python3 recompute_stats.py --codes 399006.SZ
    python3 recompute_stats.py --no-compare    # 跳过新旧比对
"""
import os
import sys
import json
import shutil
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import bsl_core as core
import path_stats


def prev_stats_dir():
    """找当前数据截止日之前的最新归档目录。
    全新环境无 stats/ 目录时返回 None（首次运行无比对基线，避免 FileNotFoundError）。"""
    if not os.path.isdir(core.STATS_DIR):
        return None
    dirs = sorted(d for d in os.listdir(core.STATS_DIR)
                  if os.path.isdir(os.path.join(core.STATS_DIR, d)) and d.isdigit())
    return dirs[-1] if dirs else None


def adapt_summary(df):
    """把旧版明细归档（含 ret60 列）聚合为汇总格式，兼容列名差异。

    v1.0 基线归档为研究底稿明细格式（每次触发行），新脚本输出为汇总格式
    （每因子一行）。比对前统一转成汇总。胜率判定沿用 round(1)>0 口径。
    """
    if df is None or 'ret60' not in df.columns:
        return df
    if 'win60' in df.columns:
        return df
    rows = []
    for (code, factor), g in df.groupby(['code', 'factor'], sort=False):
        rets = g['ret60'].dropna().values
        if len(rets) == 0:
            continue
        arr = np.round(np.array(rets, dtype=float), 1)
        rows.append({'code': code, 'factor': factor, 'n': len(arr),
                     'win60': round(float((arr > 0).mean() * 100), 1),
                     'median60': round(float(np.median(arr)), 1)})
    return pd.DataFrame(rows)


def load_prev(prev_dir):
    """读取上一版归档并聚合为汇总格式。"""
    base = os.path.join(core.STATS_DIR, prev_dir)
    out = {}
    for key, fname in [('single', 'factor_test.csv'), ('layer', 'factor_layer.csv'),
                       ('combo', 'combination_test.csv')]:
        p = os.path.join(base, fname)
        if os.path.exists(p):
            out[key] = adapt_summary(pd.read_csv(p))
    return out


def run_single(df, f):
    rows = []
    for name, mask in core.single_factors(f).items():
        idx = [i for i in range(core.BASELINE_START, len(df)) if mask.iloc[i]]
        st = core.sig_stats(idx, df, gap=core.GAP_SINGLE)
        if st:
            rows.append({'factor': name, **st})
    return pd.DataFrame(rows)


def run_layer(df, f):
    rows = []
    for name, mask in core.layer_conditions(f).items():
        idx = [i for i in range(core.BASELINE_START, len(df)) if mask.iloc[i]]
        st = core.sig_stats(idx, df, gap=core.GAP_LAYER)
        if st:
            rows.append({'factor': name, **st})
    return pd.DataFrame(rows)


def run_combos(df, f):
    # 组合信号去重口径：v1.1 起统一窗口不重叠（gap=GAP_SINGLE=60）
    rows = []
    for name, mask in core.combos(f).items():
        idx = [i for i in range(core.BASELINE_START, len(df)) if mask.iloc[i]]
        st = core.sig_stats(idx, df, gap=core.GAP_SINGLE)
        if st:
            rows.append({'factor': name, **st})
    return pd.DataFrame(rows)


def run_volume(df, f):
    """深跌区放量/缩量（不去重，逐日样本）+ 二次探底率。"""
    n = len(df)
    out = {'放量': [], '缩量': []}
    for i in range(core.BASELINE_START, n):
        if f['dd'].iloc[i] >= core.DEEP25 or i + 20 >= n:
            continue
        vr = f['vol_ratio'].iloc[i]
        tag = '放量' if vr > core.VR_HIGH else ('缩量' if vr < core.VR_MID else None)
        if tag is None:
            continue
        buy = df['close'].iloc[i]
        low_after = df['close'].iloc[i + 1:i + 21].min()
        out[tag].append({
            'second_leg': bool((low_after / buy - 1) < core.SECOND_LEG),
            'ret60': (round((df['close'].iloc[i + 60] / buy - 1) * 100, 1) if i + 60 < n else None),
        })
    rows = []
    for tag, items in out.items():
        if not items:
            continue
        r60 = [x['ret60'] for x in items if x['ret60'] is not None]
        w60, n60 = core.win_rate(r60)
        rows.append({'tag': tag, 'n': len(items), 'win60': w60,
                     'second_leg_rate': round(float(np.mean([x['second_leg'] for x in items])) * 100, 0)})
    return pd.DataFrame(rows)


def run_crashes(df, f):
    """深跌谷底：peak-to-trough>=20% 的区段（merge_gap=40）。"""
    close = df['close']
    runmax = close.rolling(250, min_periods=250).max()
    dd = close / runmax - 1
    n = len(df)
    deep = (dd <= -0.20).values
    rows, i = [], 0
    while i < n:
        if deep[i]:
            j = i
            while j + 1 < n and deep[j + 1]:
                j += 1
            seg = close.iloc[i:j + 1]
            trough = seg.idxmin()
            peak = close.iloc[:i + 1].iloc[-250:].max() if i >= 250 else seg.max()
            total_dd = (seg.min() / peak - 1) * 100
            if total_dd <= -20:
                r60 = (round((df['close'].iloc[trough + 60] / df['close'].iloc[trough] - 1) * 100, 1)
                       if trough + 60 < n else None)
                rows.append({'code': '', 'peak_date': str(df['trade_date'].iloc[i].date()),
                             'trough_date': str(df['trade_date'].iloc[trough].date()),
                             'total_dd': round(total_dd, 1),
                             'fall_days': int(trough - i + 1),
                             'fut60_from_trough': r60})
            i = j + 40
        else:
            i += 1
    return pd.DataFrame(rows)


def classify(old_st, new_st):
    """变更分级：比较同因子旧新统计。"""
    if old_st is None or new_st is None:
        return None
    dw = abs((new_st['win60'] or 0) - (old_st['win60'] or 0))
    dn = abs(new_st['n'] - old_st['n'])
    if dw > 15 or (old_st['n'] and (dn / old_st['n'] > 0.5)):
        return '重大'
    if dw >= 5:
        return '修订'
    return '微调'


def build_path_rows(pmap):
    """把 path_map.json 展开为可归档的扁平表（每个组合一行 + 深跌区随机基准一行）。"""
    qkeys = [f'mae_p{q}' for q in core.RULES['mae_quantiles']]
    rows = []
    for code, entry in pmap['indices'].items():
        for cid, d in entry.get('combos', {}).items():
            row = {
                'code': code, 'combo': cid, 'n': d['n'], 'win60': d['win60'],
                'wilson_lo': d['wilson_ci'][0], 'wilson_hi': d['wilson_ci'][1],
                'median_ret60': d['median_ret60'], 'mae_worst': d['mae_worst'],
                'median_mae': None,
                'prob_under3_20d': d['prob_under3_20d'],
                'mae_day_median': d['mae_day_median'],
                'pct_neg_ret10': d['pct_neg_ret10'], 'pct_neg_ret20': d['pct_neg_ret20'],
                'failures_n': len(d['failures']),
                'year_counts': json.dumps(d['year_counts'], ensure_ascii=False),
                'breakeven_rate': d['breakeven_rate'],
                'excess_vs_baseline_pp': d['excess_vs_baseline_pp'],
                'excess_vs_deep_pp': d['excess_vs_deep_pp'],
            }
            row.update({k: d[k] for k in qkeys})
            rows.append(row)
        deep = entry.get('deep_random_baseline', {})
        ci = deep.get('wilson_ci') or [None, None]
        rows.append({
            'code': code, 'combo': 'deep_random_baseline', 'n': deep.get('n'),
            'win60': deep.get('win60'), 'wilson_lo': ci[0], 'wilson_hi': ci[1],
            'median_ret60': deep.get('median_ret60'), 'mae_worst': None,
            'median_mae': deep.get('median_mae'),
        })
    return pd.DataFrame(rows)


def compare_path_stats(path_df, prev, out_dir):
    """新旧路径分布比对：中位 MAE 分位与最深浮亏变化（无任何硬编码阈值）。"""
    old_csv = os.path.join(core.STATS_DIR, prev, 'path_stats.csv')
    if not os.path.exists(old_csv):
        print(f'=== 路径分布比对：上一版归档 {prev} 无 path_stats.csv，跳过（v1.2 前无此统计）===')
        return
    old = pd.read_csv(old_csv).set_index(['code', 'combo'])
    q_mid = core.RULES['mae_quantiles'][len(core.RULES['mae_quantiles']) // 2]
    p_mid = f'mae_p{q_mid}'
    print(f'=== 路径分布比对（vs {prev}）===')
    for _, row in path_df.iterrows():
        if row['combo'] == 'deep_random_baseline':
            continue
        key = (row['code'], row['combo'])
        if key not in old.index:
            continue
        o = old.loc[key]
        if isinstance(o, pd.DataFrame):
            o = o.iloc[0]
        d_mid = (round(float(row[p_mid] - o[p_mid]), 2)
                 if pd.notna(o.get(p_mid)) else None)
        d_worst = (round(float(row['mae_worst'] - o['mae_worst']), 2)
                   if pd.notna(o.get('mae_worst')) else None)
        print(f"  {core.INDICES.get(row['code'], row['code'])} {row['combo']}: "
              f"{p_mid} {o.get(p_mid)} → {row[p_mid]}（Δ {d_mid}）｜"
              f"mae_worst {o.get('mae_worst')} → {row['mae_worst']}（Δ {d_worst}）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--codes', default='')
    ap.add_argument('--no-compare', action='store_true')
    args = ap.parse_args()
    codes = [c.strip() for c in args.codes.split(',') if c.strip()] or list(core.INDICES)

    # 数据截止日
    cutoffs = [core.data_cutoff(c) for c in codes]
    cutoffs = [d for d in cutoffs if d is not None]
    if not cutoffs:
        print('[ERROR] 无可用数据，请先运行 fetch_data.py 或检查 data/ 目录')
        sys.exit(2)
    cutoff = max(cutoffs).strftime('%Y%m%d')
    out_dir = os.path.join(core.STATS_DIR, cutoff)
    if os.path.exists(out_dir):   # 防覆盖：同日重跑追加序号
        k = 2
        while os.path.exists(f'{out_dir}_{k}'):
            k += 1
        out_dir = f'{out_dir}_{k}'
        print(f'[提示] stats/{cutoff}/ 已存在，本次归档至 {os.path.basename(out_dir)}/')
    prev = None if args.no_compare else prev_stats_dir()
    prev_data = load_prev(prev) if prev else {}
    os.makedirs(out_dir, exist_ok=True)
    print(f'=== 全量重跑（数据截止 {cutoff}）===  上一版归档: {prev or "无"}')

    all_single, all_layer, all_combo, all_vol, all_crash = [], [], [], [], []
    baselines, states = {}, {}
    changes = []
    for code in codes:
        df = core.load_daily(code)
        if df is None:
            print(f'  {core.INDICES.get(code, code)}: 数据缺失，跳过')
            continue
        f = core.build_features(df)
        name = core.INDICES.get(code, code)
        print(f'  [{name}] 重算中... ({len(df)}行)')
        s, l, c = run_single(df, f), run_layer(df, f), run_combos(df, f)
        for t in (s, l, c):
            t.insert(0, 'code', code)
        all_single.append(s); all_layer.append(l); all_combo.append(c)
        v = run_volume(df, f); v.insert(0, 'code', code); all_vol.append(v)
        cr = run_crashes(df, f); cr['code'] = code; all_crash.append(cr)
        baselines[code] = {'step5': core.baseline_rate(df, f, step=5),
                           'step60': core.baseline_rate(df, f, step=60)}
        states[code] = core.current_state(df, f)

        # 新旧比对
        if prev_data.get('single') is not None:
            p = prev_data['single']
            for _, r in s.iterrows():
                old = p[(p['code'] == code) & (p['factor'] == r['factor'])]
                if len(old):
                    old_st = old.iloc[0].to_dict()
                    lvl = classify(old_st, r.to_dict())
                    if lvl:
                        changes.append({'code': code, 'factor': r['factor'], 'level': lvl,
                                        'old_win': old_st.get('win60'), 'new_win': r['win60'],
                                        'old_n': old_st.get('n'), 'new_n': r['n']})
        if prev_data.get('combo') is not None:
            p = prev_data['combo']
            for _, r in c.iterrows():
                old = p[(p['code'] == code) & (p['factor'] == r['factor'])]
                if len(old):
                    old_st = old.iloc[0].to_dict()
                    lvl = classify(old_st, r.to_dict())
                    if lvl:
                        changes.append({'code': code, 'factor': r['factor'], 'level': lvl,
                                        'old_win': old_st.get('win60'), 'new_win': r['win60'],
                                        'old_n': old_st.get('n'), 'new_n': r['n']})

    # 归档前六类统计
    pd.concat(all_single).to_csv(os.path.join(out_dir, 'factor_test.csv'), index=False)
    pd.concat(all_layer).to_csv(os.path.join(out_dir, 'factor_layer.csv'), index=False)
    pd.concat(all_combo).to_csv(os.path.join(out_dir, 'combination_test.csv'), index=False)
    pd.concat(all_vol).to_csv(os.path.join(out_dir, 'volume_trap.csv'), index=False)
    pd.concat(all_crash).to_csv(os.path.join(out_dir, 'crashes_detail.csv'), index=False)
    summary = {'data_cutoff': cutoff, 'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
               'baselines': baselines, 'current_states': states}
    with open(os.path.join(out_dir, 'summary.json'), 'w') as fp:
        json.dump(summary, fp, ensure_ascii=False, indent=2, default=str)

    # ---------- 第 7 类统计：路径分布（v1.2 决策层） ----------
    # 全量调用 build_path_map；同时在归档目录保存 path_stats.csv 与 path_map.json
    # 快照，保证每次重跑可追溯、旧归档不被覆盖。
    dc_iso = datetime.strptime(cutoff, '%Y%m%d').strftime('%Y-%m-%d')
    pmap = path_stats.build_path_map(dc_iso)
    path_df = build_path_rows(pmap)
    path_df.to_csv(os.path.join(out_dir, 'path_stats.csv'), index=False)
    with open(os.path.join(out_dir, 'path_map.json'), 'w', encoding='utf-8') as fp:
        json.dump(pmap, fp, ensure_ascii=False, indent=2)

    print('=== 已归档至 ' + os.path.relpath(out_dir, core.SKILL_ROOT) + '/ ===')
    print('  （含第 7 类路径统计 path_stats.csv / path_map.json 快照）')
    print('运气线（窗口不重叠·每60天采样 为 v1.1 主对照）:')
    for code, b in baselines.items():
        s5, s60 = b['step5'], b['step60']
        print(f"  {core.INDICES[code]:6s}  step5 {s5['win60']}% (n={s5['n']}) | "
              f"step60 {s60['win60']}% (n={s60['n']}, 中位{s60['median60']:+.1f}%)")

    # 变更报告
    if changes:
        print(f'=== 变更比对（vs {prev}）===')
        lv_order = {'重大': 0, '修订': 1, '微调': 2}
        changes.sort(key=lambda x: lv_order[x['level']])
        for ch in changes:
            print(f"  [{ch['level']}] {core.INDICES.get(ch['code'], ch['code'])} {ch['factor']}: "
                  f"胜率 {ch['old_win']}% → {ch['new_win']}%  次数 {ch['old_n']} → {ch['new_n']}")
        worst = changes[0]['level']
        print(f'=== 变更分级结论：{worst} ===')
        if worst == '重大':
            print('  ⚠️ 存在重大变更：暂停依赖旧结论的监控输出，标记"知识库待人工复核"，')
            print('     经用户确认后再按协议修订 references/signal_map.json 并追加 history 台账。')
        elif worst == '修订':
            print('  ⚠️ 存在修订级变更：需更新 signal_map.json 数字与结论文字，并追加 history 台账。')
        else:
            print('  ✓ 仅微调：更新 signal_map.json 数字即可，结论文字不变；仍须记录 history。')
    else:
        print('=== 无变更或无比对基线 ===')

    # 第 7 类统计的新旧比对
    if prev and not args.no_compare:
        compare_path_stats(path_df, prev, out_dir)

    print('完成。按 SKILL.md 模式B协议执行落库动作（更新知识库 → 追加 history → 归档旧版）。')


if __name__ == '__main__':
    main()
