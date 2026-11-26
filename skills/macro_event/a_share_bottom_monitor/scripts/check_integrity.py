# -*- coding: utf-8 -*-
# Authors: Warwick
"""check_integrity.py — 数据完整性检查（每次拉取后必跑）

检查项（任一失败 → 退出码1，并提示停止后续计算）：
  1. 无重复日期、日期严格递增
  2. OHLCV 无空值、成交量 > 0
  3. high >= max(open,close) 且 low <= min(open,close)
  4. pct_chg 与 close/pre_close-1 偏差 <= 0.02 个百分点
  5. 各指数最后交易日大致同步（差异 > 3 个交易日给出警告）
  6. path_map.json 必填字段、版本号、MAE 符号、分位单调、样本量、失败日期
  7. 输出层防回流：内部纪律短语不得出现在渲染脚本的字符串常量中
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsl_core as core

PATH_MAP_JSON = os.path.join(core.REFS_DIR, 'path_map.json')
PATH_MAP_TOP_FIELDS = ('version', 'updated', 'data_cutoff', 'method', 'indices')
PATH_MAP_IDX_FIELDS = ('name', 'combos', 'deep_random_baseline',
                       'excess_vs_baseline_pp', 'excess_vs_deep_pp', 'primary_combo')
PATH_MAP_COMBO_FIELDS = (
    'n', 'win60', 'wilson_ci', 'median_ret60', 'mean_ret60', 'best_ret60',
    'worst_ret60', 'mae_worst', 'prob_under3_20d', 'mae_day_median',
    'pct_neg_ret10', 'pct_neg_ret20', 'failures', 'year_counts',
    'breakeven_rate', 'excess_vs_baseline_pp', 'excess_vs_deep_pp',
)


def check_one(code):
    df = core.load_daily(code)
    path = os.path.join(core.DATA_DIR, f'{code}.csv')
    if df is None:
        print(f'  {core.INDICES.get(code, code):6s} [缺失] 文件不存在: {path}')
        return False
    issues = []
    if not df['trade_date'].is_monotonic_increasing:
        issues.append('日期非递增')
    if df['trade_date'].duplicated().any():
        issues.append(f'重复日期{int(df["trade_date"].duplicated().sum())}个')
    if df[['close', 'open', 'high', 'low', 'vol']].isna().any().any():
        issues.append('OHLCV存在空值')
    if (df['vol'] <= 0).any():
        issues.append(f'非正成交量{int((df["vol"] <= 0).sum())}条')
    bad_hl = int(((df['high'] < df[['open', 'close']].max(axis=1) - 1e-6) |
                  (df['low'] > df[['open', 'close']].min(axis=1) + 1e-6)).sum())
    if bad_hl:
        issues.append(f'high/low越界{bad_hl}条')
    calc = (df['close'] / df['pre_close'] - 1) * 100
    n_bad = int((calc - df['pct_chg']).abs().gt(0.02).sum())
    if n_bad:
        issues.append(f'pct_chg与价格不符{n_bad}条')
    if issues:
        print(f'  {core.INDICES.get(code, code):6s} ✗ ' + '; '.join(issues))
        return False
    print(f'  {core.INDICES.get(code, code):6s} ✓ {len(df):5d}行 '
          f'{df["trade_date"].min().date()} ~ {df["trade_date"].max().date()}')
    return True


def check_path_map():
    """路径分布完整性：字段 / 版本 / MAE 符号 / 分位单调 / n≥1 / 失败日期。

    MAE 定义为「不含买入当日的持有期最低收盘 / 买入价 − 1」：若买入后全程上涨，
    该值为正（本轮无浮亏）。因此只强制 mae_worst ≤ 0 且分位值 ≥ mae_worst，
    分位数本身允许 ≥ 0；分位点与单调性由 decision-rules.md 配置块决定。
    """
    print('=== 路径分布完整性 ===')
    if not os.path.exists(PATH_MAP_JSON):
        print('  ✗ path_map.json 缺失：请先运行 python3 scripts/path_stats.py')
        return False
    try:
        with open(PATH_MAP_JSON, encoding='utf-8') as fp:
            pmap = json.load(fp)
        with open(core.SIGNAL_MAP_JSON, encoding='utf-8') as fp:
            smap = json.load(fp)
    except (OSError, ValueError) as e:
        print(f'  ✗ JSON 读取/解析失败：{e}')
        return False

    qkeys = [f'mae_p{q}' for q in core.RULES['mae_quantiles']]
    gtkeys = [f'prob_mae_gt{t}' for t in core.RULES['mae_gt_thresholds_pct']]
    required = PATH_MAP_COMBO_FIELDS + tuple(qkeys) + tuple(gtkeys)
    issues = []
    for k in PATH_MAP_TOP_FIELDS:
        if k not in pmap:
            issues.append(f'顶层缺字段 {k}')
    if pmap.get('version') != smap.get('version'):
        issues.append(f"版本号不匹配：path_map {pmap.get('version')} "
                      f"vs signal_map {smap.get('version')}")
    for code, entry in pmap.get('indices', {}).items():
        for k in PATH_MAP_IDX_FIELDS:
            if k not in entry:
                issues.append(f'{code} 缺字段 {k}')
        for cid, d in entry.get('combos', {}).items():
            tag = f'{code}/{cid}'
            for k in required:
                if k not in d:
                    issues.append(f'{tag} 缺字段 {k}')
            n = d.get('n')
            if not isinstance(n, int) or n < 1:
                issues.append(f'{tag} n<1 或非整数（{n}）')
            mw = d.get('mae_worst')
            if mw is None or mw > 0:
                issues.append(f'{tag} mae_worst 应 ≤ 0（{mw}）')
            vals = [d[k] for k in qkeys if d.get(k) is not None]
            if len(vals) == len(qkeys):
                if any(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
                    issues.append(f'{tag} MAE 分位非单调（{vals}）')
                if mw is not None and any(v < mw for v in vals):
                    issues.append(f'{tag} 分位值小于 mae_worst')
            for fail in d.get('failures', []):
                try:
                    datetime.strptime(fail['date'], '%Y-%m-%d')
                except (KeyError, ValueError, TypeError):
                    issues.append(f'{tag} failures 日期不可解析：{fail}')
        deep = entry.get('deep_random_baseline', {})
        for k in ('n', 'win60', 'wilson_ci', 'median_ret60', 'median_mae'):
            if k not in deep:
                issues.append(f'{code} deep_random_baseline 缺字段 {k}')
    if issues:
        for x in issues:
            print('  ✗ ' + x)
        return False
    n_combo = sum(len(v.get('combos', {})) for v in pmap['indices'].values())
    print(f'  ✓ version {pmap["version"]}（与 signal_map 一致）｜数据截止 {pmap["data_cutoff"]}｜'
          f'{len(pmap["indices"])} 个指数 / {n_combo} 个有效组合')
    print('  ✓ 字段齐全／n≥1／mae_worst≤0／MAE 分位单调／failures 日期可解析')
    return True


def check_output_discipline():
    """输出层防回流：渲染脚本的字符串常量里不得混入内部纪律短语。

    这些约束写在 references/decision-rules.md 第 8 节是合理的；一旦出现在脚本
    字符串常量中，就可能被直接印进给用户的报告。用 AST 只取字符串常量，
    避免把注释里的说明误判为泄漏。
    """
    import ast
    phrases = core.RULES['presentation']['internal_discipline_phrases']
    here = os.path.dirname(os.path.abspath(__file__))
    targets = ('monitor.py', 'decision.py')
    bad = []
    for fn in targets:
        with open(os.path.join(here, fn), encoding='utf-8') as fp:
            tree = ast.parse(fp.read())
        # 模块 / 函数 / 类的 docstring 是给开发者看的说明，不进入报告，排除之
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    docs.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docs):
                for ph in phrases:
                    if ph in node.value:
                        bad.append(f'{fn}:{node.lineno} 含「{ph}」')
    for item in bad:
        print(f'  ✗ {item}')
    if bad:
        print('  ✗ 输出层防回流失败：内部纪律短语不得出现在脚本字符串常量中')
        return False
    print(f'  ✓ {len(targets)} 个渲染脚本 × {len(phrases)} 条内部纪律短语，零命中')
    return True


def main():
    print('=== 日线数据完整性 ===')
    ok = True
    for code in core.INDICES:
        ok &= check_one(code)
    print('=== PE数据完整性 ===')
    for code in core.INDICES:
        if code in core.NO_PE:
            print(f'  {core.INDICES[code]:6s} - 无PE数据（已知缺失，估值维度空缺）')
            continue
        pe = core.load_pe(code)
        if pe is None:
            print(f'  {core.INDICES[code]:6s} ✗ PE文件缺失')
            ok = False
            continue
        npe = int(pe['pe_ttm'].isna().sum())
        note = f'（注意：序列自{pe["trade_date"].min().date()}起，样本期偏短）' if pe['trade_date'].min() > pd_ts(core.RULES['pe_sample_start']) else ''
        print(f'  {core.INDICES[code]:6s} ✓ {len(pe):5d}行 '
              f'{pe["trade_date"].min().date()} ~ {pe["trade_date"].max().date()} 空值{npe} {note}')
    # 日期同步
    lasts = {}
    for code in core.INDICES:
        d = core.data_cutoff(code)
        if d is not None:
            lasts[code] = d
    if lasts:
        mx, mn = max(lasts.values()), min(lasts.values())
        gap = (mx - mn).days
        print('=== 交易日同步 ===')
        if gap > 3:
            print(f'  ⚠ 各指数最后交易日差异 {gap} 天：'
                  + ', '.join(f'{core.INDICES[c]}至{d.date()}' for c, d in lasts.items())
                  + ' —— 监控报告需注明数据截止日不一致')
        else:
            print(f'  ✓ 各指数最后交易日差异 ≤3 天（最新 {mx.date()}）')
    ok &= check_path_map()
    print()
    print('=== 输出层规范（内部纪律防回流） ===')
    ok &= check_output_discipline()
    print()
    if ok:
        print('结论：数据完整性通过，可继续运行 recompute_stats.py / monitor.py')
        sys.exit(0)
    else:
        print('结论：存在问题，请先修复再继续，不得带病计算！')
        sys.exit(1)


def pd_ts(s):
    import pandas as pd
    return pd.Timestamp(s)


if __name__ == '__main__':
    main()
