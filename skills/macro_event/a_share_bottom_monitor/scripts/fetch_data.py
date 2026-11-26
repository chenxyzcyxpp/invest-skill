# -*- coding: utf-8 -*-
# Authors: Warwick
"""fetch_data.py — Tushare 增量拉取日线与PE数据

用法：
    export TUSHARE_TOKEN=你的token
    python3 fetch_data.py                 # 拉取全部默认指数
    python3 fetch_data.py --codes 000001.SH,399006.SZ
    python3 fetch_data.py --start 20240101 --end 20261231

行为：
  - 只拉取本地最大日期之后的交易日，追加写入 data/<code>.csv（去重排序）；
  - 无 TUSHARE_TOKEN 时退出并提示，绝不静默使用陈旧数据冒充最新；
  - 中证2000（932000.CSI）无 index_dailybasic PE 记录，自动跳过PE。
"""
import os
import sys
import time
import argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsl_core as core


def get_pro():
    token = os.environ.get('TUSHARE_TOKEN', '').strip()
    if not token:
        print('[ERROR] 未找到环境变量 TUSHARE_TOKEN。')
        print('        请先执行: export TUSHARE_TOKEN=<你的Tushare Pro Token>')
        print('        未获取Token前无法增量更新；可先用现有 data/ 数据跑监控。')
        sys.exit(2)
    try:
        import tushare as ts
    except ImportError:
        print('[ERROR] 未安装 tushare。请先: pip install tushare')
        sys.exit(2)
    ts.set_token(token)
    return ts.pro_api()


def fetch_daily(pro, code, start=None, end=None):
    """增量拉取日线；返回新增行数。"""
    df0 = core.load_daily(code)
    path = os.path.join(core.DATA_DIR, f'{code}.csv')
    if start is None:
        if df0 is not None and len(df0):
            start = (df0['trade_date'].max() + pd.Timedelta(days=1)).strftime('%Y%m%d')
        else:
            start = '20140101'   # 与 v1.0 研究起点对齐
    if end is None:
        end = pd.Timestamp.today().strftime('%Y%m%d')
    if start > end:
        print(f'  {code}: 已是最新（本地截至 {df0["trade_date"].max().date()}）')
        return 0
    print(f'  {code}: 拉取 {start} ~ {end} ...')
    try:
        # 注意：指数必须用 index_daily，pro.daily 只返回股票数据（实测对指数返回空）
        df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
    except Exception as e:
        print(f'  [ERROR] {code} daily 接口失败: {e}')
        return 0
    if df is None or len(df) == 0:
        print(f'  {code}: 无新数据（可能节假日/停更）')
        return 0
    df = df[['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
             'pre_close', 'pct_chg', 'vol']].copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    if df0 is not None and len(df0):
        out = pd.concat([df0, df], ignore_index=True)
    else:
        out = df
    out = out.drop_duplicates(subset=['trade_date']).sort_values('trade_date').reset_index(drop=True)
    out.to_csv(path, index=False)
    print(f'  {code}: +{len(df)} 行 → 共 {len(out)} 行（截至 {out["trade_date"].max().date()}）')
    return len(df)


def fetch_pe(pro, code):
    """增量拉取指数PE-TTM；无数据的指数跳过。"""
    if code in core.NO_PE:
        print(f'  pe_{code}: 跳过（该指数无交易所PE数据，已知缺失）')
        return 0
    pe0 = core.load_pe(code)
    path = os.path.join(core.DATA_DIR, f'pe_{code}.csv')
    start = '20140101'
    if pe0 is not None and len(pe0):
        start = (pe0['trade_date'].max() + pd.Timedelta(days=1)).strftime('%Y%m%d')
    end = pd.Timestamp.today().strftime('%Y%m%d')
    if start > end:
        print(f'  pe_{code}: 已是最新')
        return 0
    print(f'  pe_{code}: 拉取 {start} ~ {end} ...')
    try:
        df = pro.index_dailybasic(ts_code=code, start_date=start, end_date=end,
                                  fields='trade_date,ts_code,pe_ttm')
    except Exception as e:
        print(f'  [ERROR] {code} index_dailybasic 失败: {e}')
        return 0
    if df is None or len(df) == 0:
        print(f'  pe_{code}: 无新数据')
        return 0
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    out = pd.concat([pe0, df], ignore_index=True) if pe0 is not None and len(pe0) else df
    out = out.drop_duplicates(subset=['trade_date']).sort_values('trade_date').reset_index(drop=True)
    out.to_csv(path, index=False)
    print(f'  pe_{code}: +{len(df)} 行 → 共 {len(out)} 行')
    return len(df)


def main():
    ap = argparse.ArgumentParser(description='Tushare 增量拉取')
    ap.add_argument('--codes', default='', help='逗号分隔指数代码，默认全部')
    ap.add_argument('--start', default=None, help='强制起始日 YYYYMMDD')
    ap.add_argument('--end', default=None, help='强制截止日 YYYYMMDD')
    ap.add_argument('--skip-pe', action='store_true', help='跳过PE拉取')
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()] or list(core.INDICES)
    pro = get_pro()
    print('=== 拉取日线 ===')
    for c in codes:
        fetch_daily(pro, c, args.start, args.end)
        time.sleep(0.4)   # 限频保护
    if not args.skip_pe:
        print('=== 拉取PE ===')
        for c in codes:
            fetch_pe(pro, c)
            time.sleep(0.4)
    print('完成。建议接着运行: python3 check_integrity.py')


if __name__ == '__main__':
    main()
