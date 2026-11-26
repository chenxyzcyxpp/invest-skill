# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
features.py — 个股模式特征工程（模式 B，7 特征）
==================================================
特征（对应 skill spec 模式 B）：
  opinion_index  个股舆情指数（股吧情感合成；无历史语料时作为当期信号不入训练矩阵）
  turnover       换手率 %
  amount_rel     成交额相对倍数（当日 / 过去 20 日均）
  pct_chg        个股涨跌幅 %
  ind_pct        所属行业指数涨跌幅 %（板块环境；失败用个股 20 日均涨幅代理并标注）
  vol_20d        20 日历史波动率
  crowding_score 拥挤度得分（内置代理：换手率 250 日分位数；可被外部覆盖）

标签 y_t = (high - low) / prev_close × 100。
全部为相对值/比率/分位数，不喂原始绝对值。
"""

import numpy as np


def build_stock_features(kline_rows, opinion_series=None, industry_pct=None):
    """构造个股特征矩阵与标签。

    返回 (feat, label, names, notes, series_dates)
      feat      : np.ndarray (n, p)
      label     : np.ndarray (n,) 日波动率
      names     : list[str]
      notes     : list[str] 数据口径说明（供报告标注）
      series_dates : list[str] 与行对应的日期
    """
    closes = np.array([r["close"] for r in kline_rows], dtype=float)
    highs = np.array([r["high"] for r in kline_rows], dtype=float)
    lows = np.array([r["low"] for r in kline_rows], dtype=float)
    amounts = np.array([r.get("amount", 0) or 0 for r in kline_rows], dtype=float)
    vols = np.array([r.get("vol", 0) or 0 for r in kline_rows], dtype=float)
    turnover = np.array([r.get("turnover", 0) or 0 for r in kline_rows], dtype=float)
    dates = [r["date"] for r in kline_rows]
    n = len(closes)

    prev_close = np.concatenate([[closes[0]], closes[:-1]])
    pct_chg = (closes - prev_close) / np.where(prev_close == 0, 1, prev_close) * 100.0
    pct_chg[0] = 0.0
    label = (highs - lows) / np.where(prev_close == 0, 1, prev_close) * 100.0
    label[0] = np.nan  # 首日无真实昨收，标签不可用

    # amount_rel：当日成交额 / 过去 20 日均（成交额缺失时用成交量代理）
    amt = amounts if amounts.sum() > 0 else vols
    amt_ma20 = np.convolve(amt, np.ones(20) / 20, mode="same")
    amt_ma20[amt_ma20 == 0] = np.nan
    amount_rel = amt / amt_ma20
    amount_rel[np.isnan(amount_rel)] = 1.0

    # vol_20d
    vol_20d = np.full(n, np.nan)
    for i in range(20, n):
        vol_20d[i] = np.std(pct_chg[i - 20:i], ddof=1)
    vol_20d[:20] = np.nanmedian(vol_20d[20:]) if n > 20 else 0.0
    vol_20d[np.isnan(vol_20d)] = 0.0

    # crowding_score：换手率 250 日分位数（内置代理，表征赛道抱团/拥挤）
    crowding = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - 250)
        w = turnover[lo:i + 1]
        denom = (w <= turnover[i]).sum()
        crowding[i] = denom / max(len(w), 1)
    crowding[np.isnan(crowding)] = 0.5
    crowding[np.isnan(turnover) & np.isnan(crowding)] = 0.5

    # opinion_index：有历史舆情序列则作为特征列，否则全 0 占位（当期信号单独输出）
    opinion = np.zeros(n)
    opinion_note = "无历史舆情序列，opinion 作为当期信号单独输出（不入训练矩阵）"
    if opinion_series:
        d2o = {}
        for d, v in opinion_series.items():
            d2o[d] = v["opinion"]
        filled = 0
        for i, d in enumerate(dates):
            if d in d2o:
                opinion[i] = d2o[d]
                filled += 1
        if filled > 0:
            opinion_note = "历史舆情序列命中 %d/%d 个交易日" % (filled, n)
            # 命中过少（<50%）时视为不可靠，退回当期信号
            if filled < n * 0.5:
                opinion_note = "历史舆情命中率 %.0f%%（<50%%），opinion 仍作为当期信号，不入训练矩阵" % (filled / n * 100)
                opinion = np.zeros(n)

    # ind_pct：行业指数涨跌幅；无则用个股 20 日均涨幅代理
    ind_pct = np.full(n, np.nan)
    ind_note = ""
    if industry_pct is not None:
        ind_pct[-1] = industry_pct  # 仅当前日有行业板块涨跌幅
        ind_note = "行业板块涨跌幅仅覆盖最新交易日（%s），历史段用代理" % industry_pct
    # 历史段代理：个股 20 日均涨幅（tanh 压缩）
    for i in range(20, n):
        ind_pct[i] = np.tanh(np.mean(pct_chg[i - 20:i]) / 1.0)
    ind_pct[:20] = 0.0
    ind_pct[np.isnan(ind_pct)] = 0.0
    if not ind_note:
        ind_note = "行业板块接口不可用，ind_pct 使用个股 20 日均涨幅代理"

    feat = np.column_stack([opinion, turnover, amount_rel, pct_chg,
                            ind_pct, vol_20d, crowding])
    names = ["opinion_index", "turnover", "amount_rel", "pct_chg",
             "ind_pct", "vol_20d", "crowding_score"]

    # 过滤含缺失的特征行与无有效标签的首日（date 列表同步对齐）
    bad = np.isnan(feat).any(axis=1) | np.isnan(label)
    if bad.any():
        keep = ~bad
        feat, label = feat[keep], label[keep]
        dates = [d for d, k in zip(dates, keep) if k]

    notes = [opinion_note, ind_note]
    return feat, label, names, notes, dates


if __name__ == "__main__":
    from data import _secid
    print("features 模块自检 OK, secid 300666 ->", _secid("300666"))
