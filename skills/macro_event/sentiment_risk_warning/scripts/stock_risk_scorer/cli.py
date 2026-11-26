# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
cli.py — 舆情风险预警 · 个股模式命令行入口
============================================
用法（在 scripts/ 目录下，以模块方式运行保证 import 路径正确）：
  python3 -m stock_risk_scorer.cli --code 300666 --days 1250      # 真实行情+股吧
  python3 -m stock_risk_scorer.cli --code 300666 --self-test      # 离线自测（演示数据）
  python3 -m stock_risk_scorer.cli --code 300666 --posts guba.csv # 自备股吧语料
  python3 -m stock_risk_scorer.cli --code 300666,600584,002472    # 批量

输出：控制台结论 + risk_report_<code>.html + risk_report_<code>.json
"""

import argparse
import csv
import os
import re
import sys
import time

import numpy as np

# 保证从 scripts/ 直接 python 文件运行时也能 import 同级模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rf_model import RandomForestRegressor, winsorize, vif_filter, zscore

from . import data, sentiment
from .features import build_stock_features
from .report import render_stock_report


def _grade_risk(v):
    return "高" if v > 4.0 else ("中" if v >= 2.0 else "低")


def _risk_score(v):
    if v <= 0:
        return 0
    if v < 2.0:
        s = v / 2.0 * 50
    elif v < 4.0:
        s = 50 + (v - 2.0) / 2.0 * 30
    elif v < 6.0:
        s = 80 + (v - 4.0) / 2.0 * 20
    else:
        s = 100.0
    return int(round(min(max(s, 0), 100)))  # 封顶 0-100


def load_posts_file(path):
    """加载自备股吧语料 CSV（列：date,title/text/content）。"""
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(2048)
        f.seek(0)
        if "\t" in sample and "," not in sample:
            reader = csv.reader(f, delimiter="\t")
        else:
            reader = csv.DictReader(f)
        for line in reader:
            if isinstance(line, dict):
                d = line.get("date") or line.get("日期") or ""
                t = (line.get("text") or line.get("title") or line.get("content")
                     or line.get("帖子") or "")
            else:
                if len(line) < 2:
                    continue
                d, t = line[0], line[1]
            if t:
                rows.append({"date": d, "text": t})
    if not rows:
        raise ValueError("语料文件 %s 未解析到有效帖子" % path)
    return rows


def _demo_posts(code):
    """离线自测用演示股吧语料（确定性）。"""
    return [
        {"date": "2026-10-08", "text": "业绩超预期，放量拉升，主力大幅流入，看多！"},
        {"date": "2026-10-08", "text": "明显走强，突破前高，加仓。"},
        {"date": "2026-10-07", "text": "高位跳水，主力流出，警惕回调风险。"},
        {"date": "2026-10-07", "text": "跌破支撑，悲观情绪，减仓离场。"},
        {"date": "2026-10-06", "text": "订单饱满，供不应求，业绩好，持续看多。"},
        {"date": "2026-10-05", "text": "缩量整理，观望为主。"},
        {"date": "2026-10-04", "text": "减持计划公告，利空，注意风险。"},
        {"date": "2026-10-03", "text": "行业景气度高，景气，买入。"},
    ]


def _demo_kline(code, days=1250):
    """离线自测用确定性演示 K 线（种子由代码数字派生，保证可复现）。"""
    num = int(re.sub(r"\D", "", str(code)) or "0") % (2 ** 31)
    rng = np.random.default_rng(num)
    n = days
    dates = []
    d = time.strptime("2021-09-01", "%Y-%m-%d")
    import datetime as _dt
    cur = _dt.datetime(2021, 9, 1)
    while len(dates) < n:
        if cur.weekday() < 5:
            dates.append(cur.strftime("%Y-%m-%d"))
        cur += _dt.timedelta(days=1)
    ret = rng.normal(0.0002, 0.022, n)
    close = 20 * np.cumprod(1 + ret)
    prev = np.concatenate([[close[0]], close[:-1]])
    open_ = prev * (1 + rng.normal(0, 0.006, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
    vol = rng.integers(50_000, 300_000, n)
    amount = vol * close * 100
    rows = []
    for i in range(n):
        pct = (close[i] - prev[i]) / prev[i] * 100 if prev[i] else 0.0
        rows.append({
            "date": dates[i], "open": float(open_[i]), "close": float(close[i]),
            "high": float(high[i]), "low": float(low[i]),
            "vol": float(vol[i]), "amount": float(amount[i]),
            "pct_chg": float(pct),
            "turnover": float(2.0 + 3.0 * abs(rng.normal())),
        })
    return rows


def run_single(code, days=1250, posts=None, self_test=False, months=60, out=".",
               use_news=True):
    """对单只标的执行完整流程，返回报告文本与产物路径。"""
    use_demo = self_test
    news_posts = None  # 新闻通道（个股新闻，东财 search-api）
    notes0 = []
    if use_demo:
        kline = _demo_kline(code, days)
        guba_posts = posts if posts else _demo_posts(code)
        industry_pct = None
        industry_name = None
    else:
        from .data import fetch_kline, fetch_guba, fetch_news, fetch_industry_pct
        kline = fetch_kline(code, days)
        guba_posts = posts if posts else fetch_guba(code, pages=3)
        if use_news:
            news_posts = fetch_news(code)
            if not news_posts:
                notes0 = ["新闻通道不可用（东财 search-api 无返回），本次仅用股吧通道"]
            else:
                notes0 = []
        else:
            news_posts = None
            notes0 = ["新闻通道已关闭（--no-news），本次仅用股吧通道"]
        ind = fetch_industry_pct(code)
        industry_pct = ind["pct"] if ind else None
        industry_name = ind["industry"] if ind else None

    # 舆情序列：股吧通道 + 新闻通道（如启用）→ 逐日加权合成
    guba_series, guba_detail = sentiment.build_opinion_series(guba_posts)
    channels_meta = [{"name": "股吧", "detail": guba_detail}]
    if news_posts:
        news_series, news_detail = sentiment.build_opinion_series(news_posts)
        channels_meta.append({"name": "新闻", "detail": news_detail})
        op_series, op_detail = sentiment.merge_opinion_channels(
            [guba_series, news_series], weights=[0.5, 0.5])
    else:
        op_series, op_detail = guba_series, guba_detail

    # 特征
    feat, label, names, notes, dates = build_stock_features(
        kline, opinion_series=op_series, industry_pct=industry_pct)
    notes = notes0 + notes
    if industry_name:
        notes.append("所属行业：%s" % industry_name)

    # 当期舆情指数（报告展示用）：最近一日
    opinion_now = 0.0
    if op_series:
        last_key = sorted(op_series.keys())[-1]
        opinion_now = op_series[last_key]["opinion"]

    # 预处理流水线 + 训练
    win = months * 21
    n = len(label)
    hist_n = min(n - 1, win)
    result = {}
    if hist_n < 200:
        recent = label[-min(20, n):]
        pred = float(np.percentile(recent, 70)) if len(recent) else 0.0
        result = {
            "backend": "statistical_fallback",
            "pred_vol": pred,
            "grade": _grade_risk(pred),
            "score": _risk_score(pred),
            "hist_n": hist_n,
            "note": "有效样本 %d < 200，降级为简易统计模型（近20日波动率70分位）" % hist_n,
            "importances": {nm: None for nm in names},
            "fit_mae": None, "fit_r": None,
        }
    else:
        X = feat[n - hist_n:]
        y = label[n - hist_n:]
        Xw = np.column_stack([winsorize(X[:, j]) for j in range(X.shape[1])])
        kept, removed = vif_filter(Xw, names, threshold=10.0)
        Xs, mu, sigma = zscore(Xw[:, kept])
        names_kept = [names[j] for j in kept]

        m = len(y)
        split = int(m * 0.85)
        oos_p, oos_t = [], []
        if split >= 200 and m - split >= 5:
            rfv = RandomForestRegressor(n_estimators=103, min_samples_split=3,
                                        min_samples_leaf=2, max_depth=10,
                                        random_state=42)
            rfv.fit(Xs[:split], y[:split])
            oos_p = [float(p) for p in rfv.predict(Xs[split:])]
            oos_t = [float(v) for v in y[split:]]

        rf = RandomForestRegressor(n_estimators=103, min_samples_split=3,
                                   min_samples_leaf=2, max_depth=10,
                                   random_state=42)
        rf.fit(Xs, y)
        pred_vol = float(rf.predict(Xs[-1:])[0])

        importances = {}
        fi = rf.feature_importances_
        for j, nm in enumerate(names_kept):
            importances[nm] = float(fi[j])
        for rm in removed:
            importances[rm] = 0.0

        fit_mae = fit_r = None
        if len(oos_p) >= 5:
            ap, at = np.array(oos_p), np.array(oos_t)
            fit_mae = float(np.mean(np.abs(ap - at)))
            if at.std() > 1e-9 and ap.std() > 1e-9:
                fit_r = float(np.corrcoef(ap, at)[0, 1])
        result = {
            "backend": rf.backend,
            "pred_vol": pred_vol,
            "grade": _grade_risk(pred_vol),
            "score": _risk_score(pred_vol),
            "hist_n": hist_n,
            "note": "",
            "importances": importances,
            "removed_vif": removed,
            "fit_mae": fit_mae,
            "fit_r": fit_r,
        }

    meta = {
        "code": str(code),
        "name": ("演示标的" if use_demo else ""),
        "data_date": dates[-1] if dates else "",
        "months": months,
        "opinion": opinion_now,
        "opinion_detail": op_detail,
        "channels_meta": channels_meta,
        "news_titles": [p.get("title", "") for p in (news_posts or [])][:8],
        "notes": notes,
        "ind_industry": industry_name if not use_demo else None,
        "ind_pct_used": industry_pct if not use_demo else None,
    }
    text, jp, hp = render_stock_report(result, meta, out_dir=out)
    return text, jp, hp, {"demo": use_demo}


def main(argv=None):
    ap = argparse.ArgumentParser(description="舆情风险预警 · 个股模式")
    ap.add_argument("--code", required=True,
                    help="股票代码，逗号分隔支持批量，如 300666 或 300666,600584")
    ap.add_argument("--days", type=int, default=1250,
                    help="K线取数天数（默认 1250 交易日≈60 个月）")
    ap.add_argument("--posts", default="", help="自备股吧语料 CSV（date,text）")
    ap.add_argument("--no-news", action="store_true",
                    help="关闭新闻通道（仅用股吧；默认开启新闻+股吧双通道）")
    ap.add_argument("--self-test", action="store_true", help="离线自测（内置演示数据）")
    ap.add_argument("--months", type=int, default=60, choices=[36, 60],
                    help="滚动训练窗口月数（36/60），默认 60")
    ap.add_argument("--out", default=".", help="报告输出目录")
    args = ap.parse_args(argv)

    codes = [c.strip() for c in str(args.code).split(",") if c.strip()]
    if not codes:
        print("错误：--code 不能为空", file=sys.stderr)
        sys.exit(1)

    posts = None
    if args.posts:
        try:
            posts = load_posts_file(args.posts)
            print("已加载自备语料 %d 条" % len(posts))
        except Exception as e:
            print("错误：语料加载失败 → %s" % e, file=sys.stderr)
            sys.exit(1)

    all_ok = True
    for code in codes:
        try:
            text, jp, hp, info = run_single(
                code, days=args.days, posts=posts,
                self_test=args.self_test, months=args.months, out=args.out,
                use_news=not args.no_news)
            print(text)
            if not info["demo"]:
                print("产物：%s\n      %s" % (jp, hp))
        except Exception as e:
            all_ok = False
            print("错误：标的 %s 处理失败 → %s" % (code, e), file=sys.stderr)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
