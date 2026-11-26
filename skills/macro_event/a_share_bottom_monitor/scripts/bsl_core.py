# -*- coding: utf-8 -*-
# Authors: Warwick
"""bsl_core.py — A股底部信号监控 skill 公共库

集中管理：路径解析、数据加载、指标计算、统计口径、信号特征构建。
所有脚本（fetch/check/recompute/monitor）共享本模块，确保口径唯一来源。
"""
import os
import numpy as np
import pandas as pd

# ---------------- 路径 ----------------
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_ROOT, 'data')
STATS_DIR = os.path.join(SKILL_ROOT, 'stats')
REFS_DIR = os.path.join(SKILL_ROOT, 'references')
SIGNAL_MAP_JSON = os.path.join(REFS_DIR, 'signal_map.json')

# ---------------- 口径常量（v1.1：2026-10-28 去重口径修订） ----------------
BASELINE_START = 260        # 全时段起点：第260个交易日（250日滚动指标就绪）
GAP_SINGLE = 60             # v1.1 起统一为窗口不重叠：相邻触发间隔≥60个交易日合并（保留首个）
                            # 依据 stats/20261026_dedup_sensitivity/ 去重敏感度底稿：
                            # 旧口径 5/3 天把同一轮行情重复计数，胜率/样本量双双失真
GAP_LAYER = 60              # v1.1 起深跌区叠加与单因子统一（原 3 天）
HOLD_DAYS = (10, 20, 60)    # 持有期
DEEP25, DEEP30 = -0.25, -0.30   # 深跌区阈值
YL15, YL20 = -0.15, -0.20       # 破年线档位
VR_LOW, VR_MID, VR_HIGH = 0.7, 0.8, 1.5   # 量比阈值（全时段0.7 / 深跌区0.8 / 放量1.5）
FAST_DD = 0.15              # 恐慌快跌：20个交易日回撤加深≥15个百分点
SECOND_LEG = -0.03          # 二次探底：信号后20日内收盘再跌3%

# 默认监控指数（代码 → 名称）；PE 数据中证2000缺失
INDICES = {
    '000001.SH': '上证指数',
    '399001.SZ': '深证成指',
    '399006.SZ': '创业板指',
    '932000.CSI': '中证2000',
}
NO_PE = ['932000.CSI']          # 无交易所PE数据
BACKTRACK = ['932000.CSI']      # 2023-08发布，此前为回溯序列


# ---------------- 数据加载 ----------------
def load_daily(code, data_dir=DATA_DIR):
    """加载日线CSV，按日期排序。文件不存在返回 None。"""
    path = os.path.join(data_dir, f'{code}.csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['trade_date'])
    return df.sort_values('trade_date').reset_index(drop=True)


def load_pe(code, data_dir=DATA_DIR):
    """加载PE数据；不存在返回 None。"""
    path = os.path.join(data_dir, f'pe_{code}.csv')
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=['trade_date'])
    return df.sort_values('trade_date').reset_index(drop=True)


def data_cutoff(code, data_dir=DATA_DIR):
    df = load_daily(code, data_dir)
    return None if df is None else df['trade_date'].max()


# ---------------- 指标计算 ----------------
def rsi14(close, n=14):
    """14日RSI，简单移动平均口径（ru/rd 均值比，非Wilder平滑）。"""
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ru = up.rolling(n).mean()
    rd = down.rolling(n).mean()
    return 100 - 100 / (1 + ru / rd.replace(0, np.nan))


def build_features(df):
    """从日线DataFrame构建全部信号特征。

    口径（methodology.md）：
      回撤   = close / 过去250个交易日最高收盘价 - 1
      破年线 = close / 250日简单移动平均 - 1
      连跌   = 当日跌幅<0计1天，收涨即中断重新计
      量比   = 当日成交量 / 过去20日平均成交量
    """
    close, high, low, open_ = df['close'], df['high'], df['low'], df['open']
    vol = df['vol']
    runmax250 = close.rolling(250, min_periods=250).max()
    ma250 = close.rolling(250).mean()
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    dd = close / runmax250 - 1                      # 距250日高点回撤
    yl = close / ma250 - 1                          # 破年线
    r = rsi14(close)
    vol_ratio = vol / vol.rolling(20).mean()        # 量比
    rng = (high - low).replace(0, np.nan)
    lower_shadow = (np.minimum(open_, close) - low) / rng
    pct = df['pct_chg']
    down = (pct < 0).astype(int)
    consec = down * (down.groupby((down != down.shift()).cumsum()).cumcount() + 1)
    # 20个交易日前的回撤（用于恐慌快跌判定）
    dd20ago = dd.shift(20)
    feats = pd.DataFrame({
        'date': df['trade_date'], 'close': close, 'dd': dd, 'yl': yl,
        'rsi': r, 'vol_ratio': vol_ratio, 'lower_shadow': lower_shadow,
        'pct': pct, 'consec_down': consec, 'ma5': ma5, 'ma20': ma20,
        'ma250': ma250, 'dd20ago': dd20ago,
    })
    return feats


# ---------------- 事件与统计 ----------------
def dedup(events, gap=GAP_SINGLE):
    """事件去重：相邻触发间隔 < gap 天的合并为一次（保留首个）。"""
    out = []
    for i in sorted(set(events)):
        if not out or i - out[-1] >= gap:
            out.append(i)
    return out


def forward_returns(df, i):
    """触发日 i 的后10/20/60日收益（%），不足窗口返回 None。"""
    buy = df['close'].iloc[i]
    res = {}
    for h in HOLD_DAYS:
        if i + h < len(df):
            res[f'ret{h}'] = round((df['close'].iloc[i + h] / buy - 1) * 100, 1)
        else:
            res[f'ret{h}'] = None
    return res


def win_rate(rets):
    """胜率：收益率先四舍五入到1位小数再判 >0（复现原流程口径）。"""
    arr = np.array([r for r in rets if r is not None], dtype=float)
    if len(arr) == 0:
        return None, 0
    return round(float((np.round(arr, 1) > 0).mean() * 100), 1), len(arr)


def sig_stats(events, df, gap=GAP_SINGLE):
    """对触发事件列表统计 后20/60日胜率与中位/均值。已按 gap 去重。"""
    ev = [i for i in dedup(events, gap) if i + 60 < len(df)]
    if not ev:
        return None
    rets60 = [forward_returns(df, i)['ret60'] for i in ev]
    rets20 = [forward_returns(df, i)['ret20'] for i in ev]
    w60, n = win_rate(rets60)
    w20, _ = win_rate(rets20)
    arr = np.array([r for r in rets60 if r is not None], dtype=float)
    return {
        'n': n,
        'win20': w20,
        'win60': w60,
        'median60': round(float(np.median(arr)), 1) if n else None,
        'mean60': round(float(arr.mean()), 1) if n else None,
    }


# ---------------- 信号条件（供 recompute / monitor 共用） ----------------
def single_factors(f):
    """全时段单因子触发掩码字典。"""
    return {
        'RSI<20': f['rsi'] < 20,
        'RSI<25': f['rsi'] < 25,
        'RSI<30': f['rsi'] < 30,
        '回撤<-20%': f['dd'] < -0.20,
        '回撤<-25%': f['dd'] < DEEP25,
        '回撤<-30%': f['dd'] < DEEP30,
        '回撤<-35%': f['dd'] < -0.35,
        '缩量(量比<0.7)': f['vol_ratio'] < VR_LOW,
        '放量(量比>1.5)': f['vol_ratio'] > VR_HIGH,
        '长下影>0.5': f['lower_shadow'] > 0.5,
        '单日跌>3%': f['pct'] < -3,
        '单日跌>5%': f['pct'] < -5,
        '连跌>=5日': f['consec_down'] >= 5,
        '连跌>=8日': f['consec_down'] >= 8,
        '破年线>10%': f['yl'] < -0.10,
        '破年线>15%': f['yl'] < YL15,
        '破年线>20%': f['yl'] < YL20,
    }


def layer_conditions(f):
    """深跌区叠加条件（深25/深30 前提下）。"""
    d25, d30 = f['dd'] < DEEP25, f['dd'] < DEEP30
    return {
        '深25+缩量(量比<0.8)': d25 & (f['vol_ratio'] < VR_MID),
        '深25+放量(量比>1.5)': d25 & (f['vol_ratio'] > VR_HIGH),
        '深25+长下影>0.4': d25 & (f['lower_shadow'] > 0.4),
        '深25+连跌>=5日': d25 & (f['consec_down'] >= 5),
        '深25+破年线20%+': d25 & (f['yl'] < YL20),
        '深25+RSI<25': d25 & (f['rsi'] < 25),
        '深30+缩量': d30 & (f['vol_ratio'] < VR_MID),
        '深30+放量': d30 & (f['vol_ratio'] > VR_HIGH),
        '深30+连跌>=5日': d30 & (f['consec_down'] >= 5),
        '深30+破年线20%+': d30 & (f['yl'] < YL20),
        '深30+RSI<25': d30 & (f['rsi'] < 25),
    }


def combos(f):
    """组合信号 C1-C8（定义与 v1.0 一致）。"""
    dd, yl, cd = f['dd'], f['yl'], f['consec_down']
    vr = f['vol_ratio']
    fast = (f['dd20ago'] - dd >= FAST_DD)
    return {
        'C1_深25+破年线20%+连跌5': (dd < DEEP25) & (yl < YL20) & (cd >= 5),
        'C2_深25+破年线15%+连跌5': (dd < DEEP25) & (yl < YL15) & (cd >= 5),
        'C3_深30+破年线15%+连跌5': (dd < DEEP30) & (yl < YL15) & (cd >= 5),
        'C4_深25+破年线20%': (dd < DEEP25) & (yl < YL20),
        'C5_快跌+深25+破年线15%': fast & (dd < DEEP25) & (yl < YL15),
        'C6_快跌+深25+破年线15%+连跌4': fast & (dd < DEEP25) & (yl < YL15) & (cd >= 4),
        'C7_C2+缩量': (dd < DEEP25) & (yl < YL15) & (cd >= 5) & (vr < 0.9),
        'C8_C2+放量': (dd < DEEP25) & (yl < YL15) & (cd >= 5) & (vr > VR_HIGH),
    }


def baseline_rate(df, f, step=5):
    """运气线：全时段每 step 个交易日取1个买入点的后60日胜率。
    v1.1 起主对照用 step=60（窗口不重叠，与信号同口径），step=5 作为随机基准参考。"""
    idx = list(range(BASELINE_START, len(df) - 60, step))
    rets = [forward_returns(df, i)['ret60'] for i in idx]
    w, n = win_rate(rets)
    arr = np.array([r for r in rets if r is not None], dtype=float)
    return {'n': n, 'win60': w,
            'median60': round(float(np.median(arr)), 1),
            'mean60': round(float(arr.mean()), 1)}


def current_state(df, f):
    """截至数据最后一日的当前状态（供 monitor.py 使用）。"""
    i = len(df) - 1
    close = df['close'].iloc[i]
    st = {
        'date': str(df['trade_date'].iloc[i].date()),
        'close': round(float(close), 2),
        'dd': round(float(f['dd'].iloc[i]) * 100, 1),          # 距250日高点
        'yl': round(float(f['yl'].iloc[i]) * 100, 1),          # 破年线
        'consec_down': int(f['consec_down'].iloc[i]),
        'ret20': round(float(close / df['close'].iloc[i - 20] - 1) * 100, 1) if i >= 20 else None,
        'dd_deepen': (round(float((f['dd20ago'].iloc[i] - f['dd'].iloc[i]) * 100), 1)
                      if not pd.isna(f['dd20ago'].iloc[i]) else None),
        'rsi14': round(float(f['rsi'].iloc[i]), 1) if not pd.isna(f['rsi'].iloc[i]) else None,
        'vol_ratio': round(float(f['vol_ratio'].iloc[i]), 2),
    }
    return st


# ---------------- 决策层口径配置（v1.2 新增；唯一定义处见 references/decision-rules.md） ----------------
# 模块级装载，不新增函数。scripts/ 下脚本统一通过 core.RULES 读阈值，保证口径常量只定义一次。
# 配置文件缺失或配置块损坏时立即报错，不带病运行（沿用红线「不得跳过完整性检查」）。
import json as _json
import re as _re

_RULES_PATH = os.path.join(REFS_DIR, 'decision-rules.md')
if not os.path.exists(_RULES_PATH):
    raise FileNotFoundError(f'决策层规则文件缺失：{_RULES_PATH}')
_RULES_TEXT = open(_RULES_PATH, encoding='utf-8').read()
_RULES_MATCH = _re.search(
    r'<!--\s*MACHINE_CONFIG_BEGIN\s*-->.*?```json\s*(.*?)\s*```.*?<!--\s*MACHINE_CONFIG_END\s*-->',
    _RULES_TEXT, _re.S)
if not _RULES_MATCH:
    raise ValueError(f'决策层规则文件缺少 MACHINE_CONFIG 配置块：{_RULES_PATH}')
RULES = _json.loads(_RULES_MATCH.group(1))


# ---------------- v1.2 新增函数（仅两个，不改任何既有函数与常量） ----------------
def episode_info(df, f, mask):
    """回溯「本轮连续为真」的区间（状态型组合信号），只依赖日线。

    返回首触发日/收盘、连续天数、当前浮亏、期间最低收盘与最深浮亏，以及
    prior_min_close（本轮内截至前一交易日的最低收盘，供「放量创新低」判定）。
    当日未触发时返回 {'active': False}。
    """
    if mask is None or len(mask) == 0 or not bool(pd.Series(mask).iloc[-1]):
        return {'active': False}
    vals = pd.Series(mask).fillna(False).astype(bool).values
    j = len(vals) - 1
    i = j
    while i > 0 and vals[i - 1]:
        i -= 1
    first_close = float(df['close'].iloc[i])
    seg = df['close'].iloc[i:j + 1]
    min_close = float(seg.min())
    last_close = float(df['close'].iloc[j])
    prior = df['close'].iloc[i:j] if j > i else df['close'].iloc[i:i + 1]
    return {
        'active': True,
        'first_date': str(df['trade_date'].iloc[i].date()),
        'first_close': round(first_close, 2),
        'consecutive_days': int(j - i + 1),
        'last_date': str(df['trade_date'].iloc[j].date()),
        'last_close': round(last_close, 2),
        'current_drawdown_pct': round((last_close / first_close - 1) * 100, 2),
        'min_close': round(min_close, 2),
        'worst_drawdown_pct': round((min_close / first_close - 1) * 100, 2),
        'prior_min_close': round(float(prior.min()), 2),
        'ma5': round(float(f['ma5'].iloc[j]), 2) if not pd.isna(f['ma5'].iloc[j]) else None,
        'dd_pct': round(float(f['dd'].iloc[j]) * 100, 2) if not pd.isna(f['dd'].iloc[j]) else None,
        'vol_ratio': round(float(f['vol_ratio'].iloc[j]), 2) if not pd.isna(f['vol_ratio'].iloc[j]) else None,
    }


def annualized_vol(df, n=None):
    """近 n 个交易日年化波动（%）；n 缺省取持有期末档，年化因子读 core.RULES。"""
    if n is None:
        n = HOLD_DAYS[-1]
    close = df['close'].tail(n + 1).astype(float).values
    if len(close) < 2:
        return None
    return round(float(np.std(np.diff(np.log(close))) * np.sqrt(RULES['annual_trading_days']) * 100), 1)
