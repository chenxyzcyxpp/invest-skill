# -*- coding: utf-8 -*-
# Authors: Warwick
"""path_stats.py — 路径统计库（v1.2 决策层扩展）

从历史日线计算「信号触发之后怎么走」：最大浮亏分布、回本天数、二次探底概率、
失败案例、深跌区随机买入基准与双基准超额。结果写入 references/path_map.json，
**独立于 signal_map.json**（不污染 v1.1 的胜率/有效判定结论）。

口径纪律：
  - MAE 一律用收盘价、不含买入当日；收益判定沿用 core.win_rate（round(1)>0）
  - 事件去重复用 core.dedup + core.GAP_SINGLE（methodology.md 为唯一口径来源）
  - 所有阈值读 core.RULES（decision-rules.md 配置块），源码不内联数字
  - 回测结果值一律由数据算出，禁止写进源码

用法：
    python3 path_stats.py                                  # 全量生成 path_map.json
    python3 path_stats.py --code 399006.SZ --combo C4      # 打印单个组合分布
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import bsl_core as core

PATH_MAP_JSON = os.path.join(core.REFS_DIR, 'path_map.json')


def _hold():
    """持有期末档（=时间止损长度），取自 bsl_core 口径常量。"""
    return core.HOLD_DAYS[-1]


def event_indices(mask, gap=None):
    """触发日索引：复用 core.dedup，只保留完整持有窗口的事件。"""
    if gap is None:
        gap = core.GAP_SINGLE
    vals = pd.Series(mask).fillna(False).astype(bool).values
    raw = [i for i, v in enumerate(vals) if v]
    return [i for i in core.dedup(raw, gap) if i + _hold() < len(vals)]


def path_profile(df, i, hold=None):
    """单次事件的路径切片：买入价、MAE、回本天数、二次探底、各档收益。"""
    if hold is None:
        hold = _hold()
    closes = df['close'].astype(float).values
    n = len(df)
    buy = float(closes[i])
    window = closes[i + 1: min(i + 1 + hold, n)]
    mae = round(float((window.min() / buy - 1) * 100), 2) if len(window) else None
    mae_day = int(np.argmin(window)) + 1 if len(window) else None
    min_close = round(float(window.min()), 2) if len(window) else None

    rets = {}
    for h in core.HOLD_DAYS:
        rets[f'ret{h}'] = (round(float((closes[i + h] / buy - 1) * 100), 1)
                           if i + h < n else None)

    seg = closes[i + 1: min(i + 1 + core.HOLD_DAYS[1], n)]
    under3_20d = bool(np.any(seg / buy - 1 < core.SECOND_LEG)) if len(seg) else False

    breakeven_day = None
    for d in range(1, min(hold, n - i - 1) + 1):
        if closes[i + d] > buy:
            breakeven_day = d
            break

    return {
        'date': str(df['trade_date'].iloc[i].date()),
        'buy': round(buy, 2),
        'mae': mae,
        'mae_day': mae_day,
        'ret10': rets.get('ret10'),
        'ret20': rets.get('ret20'),
        'ret60': rets.get('ret60'),
        'under3_20d': under3_20d,
        'breakeven_day': breakeven_day,
        'min_close': min_close,
    }


def wilson(k, n, z=None):
    """Wilson score 置信区间（百分数，1 位小数）；z 读配置块。"""
    if z is None:
        z = core.RULES['wilson_z']
    if not n:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(float((centre - half) * 100), 1),
            round(float((centre + half) * 100), 1))


def distribution(profiles):
    """把路径切片汇总为分布字典（path_map.json 中单个组合的内容）。"""
    if not profiles:
        return None
    r60 = [p['ret60'] for p in profiles]
    win60, n = core.win_rate(r60)
    k = sum(1 for r in r60 if r is not None and round(float(r), 1) > 0)
    lo, hi = wilson(k, n)

    maes = np.array([p['mae'] for p in profiles if p['mae'] is not None], dtype=float)
    arr60 = np.array([r for r in r60 if r is not None], dtype=float)
    q = {}
    for qq in core.RULES['mae_quantiles']:
        q[f'mae_p{qq}'] = round(float(np.percentile(maes, qq)), 2)
    gt = {}
    for t in core.RULES['mae_gt_thresholds_pct']:
        gt[f'prob_mae_gt{t}'] = round(float((maes <= -t).mean() * 100), 1)

    r10 = np.array([p['ret10'] for p in profiles if p['ret10'] is not None], dtype=float)
    r20 = np.array([p['ret20'] for p in profiles if p['ret20'] is not None], dtype=float)
    mae_days = [p['mae_day'] for p in profiles if p['mae_day'] is not None]

    failures = [{'date': p['date'], 'ret60': p['ret60'], 'mae': p['mae']}
                for p in profiles if p['ret60'] is not None
                and round(float(p['ret60']), 1) <= 0]
    year_counts = {}
    for p in profiles:
        y = p['date'][:4]
        year_counts[y] = year_counts.get(y, 0) + 1

    out = {
        'n': n,
        'win60': win60,
        'wilson_ci': [lo, hi],
        'median_ret60': round(float(np.median(arr60)), 1),
        'mean_ret60': round(float(arr60.mean()), 1),
        'best_ret60': round(float(arr60.max()), 1),
        'worst_ret60': round(float(arr60.min()), 1),
        'mae_worst': round(float(maes.min()), 2),
        'prob_under3_20d': round(float(np.mean([p['under3_20d'] for p in profiles]) * 100), 1),
        'mae_day_median': round(float(np.median(mae_days)), 1) if mae_days else None,
        'pct_neg_ret10': round(float((np.round(r10, 1) < 0).mean() * 100), 1) if len(r10) else None,
        'pct_neg_ret20': round(float((np.round(r20, 1) < 0).mean() * 100), 1) if len(r20) else None,
        'failures': failures,
        'year_counts': dict(sorted(year_counts.items())),
        'breakeven_rate': round(float(np.mean([p['breakeven_day'] is not None
                                               for p in profiles]) * 100), 1),
    }
    out.update(q)
    out.update(gt)
    return out


def deep_random_baseline(df, f, threshold=None, step=None):
    """深跌区随机买入基准：深跌区内按采样步长取点，要求完整持有窗口。"""
    if threshold is None:
        threshold = core.DEEP25
    if step is None:
        step = core.RULES['deep_baseline_sample_step']
    n = len(df)
    dd = f['dd'].values
    idx = [i for i in range(core.BASELINE_START, n)
           if i + _hold() < n and not pd.isna(dd[i]) and dd[i] < threshold]
    idx = idx[::step]
    profs = [path_profile(df, i) for i in idx]
    r60 = [p['ret60'] for p in profs]
    win60, cnt = core.win_rate(r60)
    k = sum(1 for r in r60 if r is not None and round(float(r), 1) > 0)
    lo, hi = wilson(k, cnt)
    arr = np.array([r for r in r60 if r is not None], dtype=float)
    maes = [p['mae'] for p in profs if p['mae'] is not None]
    return {
        'n': cnt,
        'win60': win60,
        'wilson_ci': [lo, hi],
        'median_ret60': round(float(np.median(arr)), 1) if len(arr) else None,
        'median_mae': round(float(np.median(maes)), 2) if maes else None,
    }


def current_episode(df, f, mask, profiles=None):
    """当前这一轮（连续为真）的路径落点：复用 core.episode_info，补 MAE 分位。"""
    ep = core.episode_info(df, f, mask)
    if not ep.get('active') or not profiles:
        return ep
    maes = np.array([p['mae'] for p in profiles if p['mae'] is not None], dtype=float)
    if not len(maes):
        return ep
    worse = int((maes < ep['worst_drawdown_pct']).sum())
    ep.update({
        'mae_percentile': round(worse / len(maes) * 100, 1),
        'worse_count': worse,
        'mae_worst_hist': round(float(maes.min()), 2),
        'beyond_worst': bool(ep['worst_drawdown_pct'] <= maes.min()),
    })
    return ep


def build_path_map(data_cutoff):
    """对四指数 × 各指数 combos_effective 全量生成路径分布并写入 path_map.json。

    version 与 signal_map 对齐；updated 与 data_cutoff 保持一致，以保证删除文件后
    重跑可确定性重建（数字全部由 data/ 算出，不含任何抄写值）。
    """
    with open(core.SIGNAL_MAP_JSON, encoding='utf-8') as fp:
        smap = json.load(fp)
    out = {
        'version': smap['version'],
        'updated': data_cutoff,
        'data_cutoff': data_cutoff,
        'method': (
            '事件去重复用 core.dedup + core.GAP_SINGLE；持有期取 core.HOLD_DAYS 末档；'
            'MAE 用收盘价且不含买入当日；收益判定沿用 core.win_rate；'
            'Wilson z / 年化交易日 / MAE 分位点 / 深跌区采样步长读 decision-rules.md 配置块；'
            '深跌区阈值取 core.DEEP25；updated 与 data_cutoff 一致以保证确定性重建'
        ),
        'indices': {},
    }
    for code in core.INDICES:
        df = core.load_daily(code)
        if df is None:
            continue
        f = core.build_features(df)
        cm = core.combos(f)
        entry = smap['indices'].get(code, {})
        deep = deep_random_baseline(df, f)
        combos_out = {}
        for cid in entry.get('combos_effective', []):
            key = next((k for k in cm if k.startswith(cid + '_')), None)
            if key is None:
                continue
            profs = [path_profile(df, i) for i in event_indices(cm[key])]
            dist = distribution(profs)
            if dist is None:
                continue
            dist['excess_vs_baseline_pp'] = round(dist['win60'] - smap['baseline'][code], 1)
            dist['excess_vs_deep_pp'] = (round(dist['win60'] - deep['win60'], 1)
                                         if deep['win60'] is not None else None)
            combos_out[cid] = dist
        primary = (entry.get('combos_effective') or [None])[0]
        p = combos_out.get(primary, {})
        out['indices'][code] = {
            'name': core.INDICES[code],
            'combos': combos_out,
            'deep_random_baseline': deep,
            'excess_vs_baseline_pp': p.get('excess_vs_baseline_pp'),
            'excess_vs_deep_pp': p.get('excess_vs_deep_pp'),
            'primary_combo': primary,
        }
    with open(PATH_MAP_JSON, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='')
    ap.add_argument('--combo', default='')
    args = ap.parse_args()
    cutoffs = [core.data_cutoff(c) for c in core.INDICES]
    cutoffs = [d for d in cutoffs if d is not None]
    if not cutoffs:
        print('[ERROR] 无可用日线数据')
        sys.exit(2)
    dc = max(cutoffs).strftime('%Y-%m-%d')
    pmap = build_path_map(dc)
    if args.code:
        idx = pmap['indices'].get(args.code)
        if idx is None:
            print(f'[ERROR] 未知指数代码 {args.code}')
            sys.exit(2)
        if args.combo:
            d = idx['combos'].get(args.combo)
            if d is None:
                print(f'[ERROR] {args.code} 无有效组合 {args.combo}')
                sys.exit(2)
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({'combos': idx['combos'],
                              'deep_random_baseline': idx['deep_random_baseline'],
                              'excess_vs_baseline_pp': idx['excess_vs_baseline_pp'],
                              'excess_vs_deep_pp': idx['excess_vs_deep_pp']},
                             ensure_ascii=False, indent=2))
    else:
        total = sum(len(v['combos']) for v in pmap['indices'].values())
        print(f'path_map.json 已生成：数据截止 {dc}，'
              f'{len(pmap["indices"])} 个指数 / {total} 个有效组合，'
              f'version {pmap["version"]}')


if __name__ == '__main__':
    main()
