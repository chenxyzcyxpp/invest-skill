# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
market_risk.py — 舆情风险预警 skill · 模式 A：大盘研判（上证综指）
====================================================================
用「市场/个股舆情 + 量价相对特征」训练随机森林，预测下一交易日
上证综指波动率 = (最高-最低)/昨收 × 100%，并做风险分级与综合风险分。

数据流：
  1. 上证 K 线（tdx 连接器落盘 sh_index_kline.txt）→ 量价相对特征
  2. 新闻（wenda_news_query 落盘 news.json）→ TF-IDF×情感 舆情指数
  3. 市场快照（snapshot.json）→ 广度/汇率/成交额衍生特征
  4. 滚动 60 个月窗口训练 RF（sklearn 优先/numpy 回退），样本不足 200 降级
  5. 输出：下一交易日预测波动率 + 风险等级 + 综合风险分 + 特征重要性

演示模式：不传 --kline/--news，使用内置演示数据直接输出报告。

用法：
  PYTHONIOENCODING=utf-8 python3 market_risk.py \\
      --kline sh_index_kline.txt --news news.json --snapshot snapshot.json --out .
  python3 market_risk.py            # 内置演示数据
  python3 market_risk.py --months 36
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta

import numpy as np

# 共享模型层（预处理 + 随机森林）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rf_model import RandomForestRegressor, winsorize, vif_filter, zscore

# ---------------------------------------------------------------------------
# 一、内置情感词典（金融领域，无需外部依赖）
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "上涨", "大涨", "涨停", "走强", "拉升", "反弹", "突破", "创新高", "利好",
    "回暖", "企稳", "放量上攻", "牛市", "看多", "乐观", "买入", "增持", "加仓",
    "超预期", "景气", "高增长", "盈利改善", "降息", "宽松", "流动性改善",
    "龙虎榜净买", "主力抢筹", "北向流入", "强势", "领涨", "爆发",
}
NEGATIVE_WORDS = {
    "下跌", "大跌", "跌停", "走弱", "跳水", "回落", "破位", "创新低", "利空",
    "低迷", "熊市", "看空", "悲观", "卖出", "减持", "减仓", "清仓",
    "不及预期", "衰退", "亏损", "恶化", "加息", "收紧", "流动性紧张",
    "主力流出", "资金出逃", "北向流出", "弱势", "领跌", "崩盘", "恐慌",
}
NEGATION_WORDS = {"不", "没有", "未", "无", "并非", "难以", "别", "勿", "绝非", "并未"}
DEGREE_WORDS = {  # 程度副词（系数）
    "极度": 1.8, "非常": 1.6, "十分": 1.6, "明显": 1.4, "显著": 1.5,
    "大幅": 1.5, "强烈": 1.5, "较": 1.2, "较为": 1.2, "略": 0.8, "小幅": 0.8,
    "轻微": 0.8, "部分": 0.7, "有所": 0.9,
}


class _TinySegmenter:
    """轻量中文分词：词典 + 正向最大匹配。无 jieba 环境也可用。"""

    def __init__(self):
        self.vocab = set(POSITIVE_WORDS) | set(NEGATIVE_WORDS) | set(NEGATION_WORDS) | set(DEGREE_WORDS)
        self.max_len = max((len(w) for w in self.vocab), default=1)

    def segment(self, text):
        if not text:
            return []
        # 优先尝试 jieba
        try:
            import jieba
            return [w for w in jieba.lcut(text) if w.strip()]
        except Exception:
            pass
        # 正向最大匹配
        out, i, n = [], 0, len(text)
        while i < n:
            matched = None
            for L in range(min(self.max_len, n - i), 0, -1):
                w = text[i:i + L]
                if w in self.vocab:
                    matched = w
                    break
            if matched:
                out.append(matched)
                i += len(matched)
            else:
                i += 1
        return out


def _negation_aware_score(tokens):
    """对一段分词序列计算情感值：程度副词放大 + 否定词翻转。

    规则：遍历情感词，向前回溯最多 3 个词找否定词/程度副词。
    """
    score = 0.0
    for i, tok in enumerate(tokens):
        base = None
        if tok in POSITIVE_WORDS:
            base = 1.0
        elif tok in NEGATIVE_WORDS:
            base = -1.0
        if base is None:
            continue
        deg = 1.0
        neg = False
        for j in range(max(0, i - 3), i):
            prev = tokens[j]
            if prev in DEGREE_WORDS:
                deg = max(deg, DEGREE_WORDS[prev])
            if prev in NEGATION_WORDS:
                neg = not neg
        val = base * deg * (-1 if neg else 1)
        score += val
    return score


def compute_opinion_index(news_items, window_days=30):
    """大盘舆情指数：近 window_days 天新闻 TF-IDF 权重 × 情感值 的合成。

    返回 (opinion_index, detail)：
      opinion_index : float，正看多、负看空；无新闻返回 0.0
      detail        : dict，供报告展示
    """
    if not news_items:
        return 0.0, {"count": 0, "note": "无新闻输入，舆情指数置 0（中性）"}

    seg = _TinySegmenter()
    cutoff = datetime.now() - timedelta(days=window_days)
    items = []
    for it in news_items:
        try:
            dt = datetime.strptime(str(it.get("date", "")), "%Y-%m-%d")
        except Exception:
            dt = datetime.now()
        if dt >= cutoff or not it.get("date"):
            items.append(it)
    if not items:
        items = news_items[-window_days:]

    # TF-IDF 简化版：df（出现该词的新闻数）、idf = log(1 + N/df)
    N = len(items)
    doc_words = []
    df = {}
    for it in items:
        text = "%s %s" % (it.get("title", ""), it.get("content", "") or it.get("summary", ""))
        toks = seg.segment(text)
        doc_words.append(set(toks))
        for w in set(toks):
            df[w] = df.get(w, 0) + 1

    total = 0.0
    n_scored = 0
    for toks_set in doc_words:
        for w in toks_set:
            if w in df and df[w] > 0:
                idf = math.log(1.0 + N / df[w])
            else:
                idf = 0.0
            # 该词若为情感词，其情感贡献 = idf × 该词在全文中的情感极性
            if w in POSITIVE_WORDS:
                total += idf * 1.0
                n_scored += 1
            elif w in NEGATIVE_WORDS:
                total += idf * (-1.0)
                n_scored += 1
    # 归一化到 [-1, 1] 附近
    if n_scored == 0:
        opinion = 0.0
    else:
        opinion = math.tanh(total / max(1, math.sqrt(N)))
    return opinion, {
        "count": N,
        "scored_terms": n_scored,
        "raw_sum": round(total, 4),
        "window_days": window_days,
    }


# ---------------------------------------------------------------------------
# 二、演示数据（确定性，覆盖约 60 个月）
# ---------------------------------------------------------------------------

def _gen_demo_kline(n=1250, seed=2026):
    rng = np.random.default_rng(seed)
    dates = []
    d = datetime(2021, 9, 1)
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    # 随机游走 + 缓慢上行趋势，含若干波动放大段
    ret = rng.normal(0.0003, 0.011, n)
    for i in range(n // 3, n // 3 + 40):
        ret[i] += rng.normal(-0.002, 0.006)  # 一段调整
    close = 3200 * np.cumprod(1 + ret)
    open_ = close * (1 + rng.normal(0, 0.004, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol = rng.integers(2_000_000, 4_500_000, n)
    rows = []
    for i in range(n):
        rows.append({
            "date": dates[i],
            "open": round(float(open_[i]), 2),
            "high": round(float(high[i]), 2),
            "low": round(float(low[i]), 2),
            "close": round(float(close[i]), 2),
            "volume": int(vol[i]),
        })
    return rows


def _gen_demo_news():
    texts = [
        ("2026-10-06", "政策面释放积极信号 市场情绪回暖", "多部门联合发布稳增长政策，投资者信心明显回升，A股放量上涨。"),
        ("2026-10-07", "北向资金大幅流入 权重股走强", "今日北向资金明显流入，银行券商等权重板块领涨，大盘企稳。"),
        ("2026-10-08", "央行表态维持流动性宽松", "央行表示将保持流动性合理充裕，利好成长板块，市场看多情绪升温。"),
        ("2026-10-01", "海外市场波动 短期情绪谨慎", "受外围市场影响，部分资金选择观望，短线或有所回落。"),
        ("2026-09-28", "成交量萎缩 市场分化加剧", "两市成交低迷，热点散乱，资金观望情绪浓厚，赚钱效应减弱。"),
        ("2026-09-25", "部分高位股跳水 警惕回调风险", "前期强势股集体跳水，主力资金流出明显，市场风险偏好下降。"),
    ]
    return [{"date": d, "title": t, "content": c} for d, t, c in texts]


def _gen_demo_snapshot():
    return {
        "date": "2026-10-08",
        "sh_close": 3280.5,
        "sh_pct": 0.85,
        "hs300_pct": 0.92,
        "kch50_pct": 1.10,
        "amount_yi": 10520.0,
        "up_total": 3100,
        "down_total": 1800,
        "usdcny": 7.18,
        "main_net_sh": 42.5,
        "main_net_sz": 18.3,
        "main_net_cyb": 6.2,
        "strong": "银行、券商、半导体",
        "weak": "煤炭、地产",
        "view": "机构认为短期震荡上行，关注量能配合",
    }


# ---------------------------------------------------------------------------
# 三、数据加载
# ---------------------------------------------------------------------------

def load_kline(path=None):
    """加载上证 K 线。支持 CSV（date,open,high,low,close[,volume,amount]）
    或 JSON（list[dict]）。path 为空返回演示数据。"""
    if not path:
        return _gen_demo_kline()
    # 按首字符探测格式（tdx 落盘为 .txt，内容可能是 CSV 或 JSON）
    with open(path, "r", encoding="utf-8") as f:
        head = f.read(1).strip()
    if head in ("[", "{"):
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
    else:  # CSV
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        header = lines[0].lower().split(",")
        rows = []
        for ln in lines[1:]:
            parts = ln.split(",")
            if len(parts) < 5:
                continue
            rec = dict(zip(header, parts))
            rows.append({
                "date": rec["date"].strip(),
                "open": float(rec["open"]),
                "high": float(rec["high"]),
                "low": float(rec["low"]),
                "close": float(rec["close"]),
                "volume": float(rec.get("volume", 0) or 0),
                "amount": float(rec.get("amount", 0) or 0),
            })
    if len(rows) < 60:
        raise ValueError("K线样本过少（%d 行），至少需要 60 行" % len(rows))
    rows.sort(key=lambda r: r["date"])
    return rows


def load_news(path=None):
    """加载新闻。path 为空返回演示数据。支持 JSON list[dict] 或简单文本行。"""
    if not path:
        return _gen_demo_news()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("data", data.get("news", []))
    items = []
    for it in data:
        if isinstance(it, str):
            items.append({"title": it, "content": it, "date": ""})
        else:
            items.append({
                "date": str(it.get("date") or it.get("datetime") or ""),
                "title": it.get("title", ""),
                "content": it.get("content", it.get("summary", "")),
            })
    return items


def load_snapshot(path=None):
    if not path:
        return _gen_demo_snapshot()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 四、特征工程（大盘模式，7 特征，全部相对值/比率/分位数）
# ---------------------------------------------------------------------------

def build_market_features(kline_rows, snapshot):
    """由 K 线历史 + 当日快照构造特征矩阵（含标签 volatility_t）。

    特征（对应 spec 模式 A 特征表）：
      sh_quantile  : 上证收盘 60 个月窗口分位数（替代原始点位）
      turnover     : 流动性代理 = 成交额/指数点位（无成交额用 volume 代理）
      amount_rel   : 当日成交额 / 过去 20 日均值
      pct_chg      : 涨跌幅 %
      usdcny_pct   : 汇率涨跌幅 %（无历史汇率用 0，当前用 snapshot 提供）
      vol_20d      : 20 日历史波动率
      breadth      : 涨跌家数占比（无历史用 pct_chg 符号滚动代理，当前用 snapshot）
    标签 y_t = 当日 (high-low)/prev_close × 100（t 日波动率）
    """
    closes = np.array([r["close"] for r in kline_rows], dtype=float)
    highs = np.array([r["high"] for r in kline_rows], dtype=float)
    lows = np.array([r["low"] for r in kline_rows], dtype=float)
    opens = np.array([r["open"] for r in kline_rows], dtype=float)
    amounts = np.array([r.get("amount", 0) or 0 for r in kline_rows], dtype=float)
    vols = np.array([r.get("volume", 0) or 0 for r in kline_rows], dtype=float)
    n = len(closes)

    prev_close = np.concatenate([[closes[0]], closes[:-1]])
    pct_chg = (closes - prev_close) / np.where(prev_close == 0, 1, prev_close) * 100.0
    pct_chg[0] = 0.0
    # 日波动率标签（spec：1.1 预测目标）
    label = (highs - lows) / np.where(prev_close == 0, 1, prev_close) * 100.0
    label[0] = np.nan  # 首日无真实昨收，标签不可用（后续过滤剔除）

    # 成交额代理：优先真实成交额，缺失用 vol
    amt = amounts if amounts.sum() > 0 else vols
    # turnover = 成交额/点位（用当日点位近似，规避量级漂移）
    turnover = amt / np.where(closes == 0, 1, closes)
    # amount_rel = 当日 / 20 日均
    amt_ma20 = np.convolve(amt, np.ones(20) / 20, mode="same")
    amt_ma20[amt_ma20 == 0] = np.nan
    amount_rel = amt / amt_ma20
    amount_rel[np.isnan(amount_rel)] = 1.0

    # 60 个月窗口分位数（约 1250 交易日，取 min(len,1250) 窗口，滚动）
    sh_quantile = np.full(n, 0.5)
    win = min(n, 1250)
    for i in range(n):
        lo = max(0, i - win)
        w = closes[lo:i + 1]
        sh_quantile[i] = (w <= closes[i]).mean()

    # 20 日历史波动率（已实现波动率，年化换算为日 %，保持量纲直观）
    vol_20d = np.full(n, np.nan)
    for i in range(20, n):
        vol_20d[i] = np.std(pct_chg[i - 20:i], ddof=1)
    vol_20d[:20] = np.nanmedian(vol_20d[20:]) if n > 20 else 0.0
    vol_20d[np.isnan(vol_20d)] = 0.0

    # 汇率涨跌幅：无历史序列时，历史段 0，当前日取 snapshot 中相对 7.15 基线的变化
    usdcny_now = float(snapshot.get("usdcny") or 7.15)
    usdcny_pct = np.full(n, 0.0)
    if n > 0:
        usdcny_pct[-1] = (usdcny_now - 7.15) / 7.15 * 100.0

    # 广度：无历史涨跌家数 → 用 pct_chg 的 20 日均值方向代理（单调近似市场热度）
    breadth = np.full(n, np.nan)
    for i in range(20, n):
        breadth[i] = np.tanh(np.mean(pct_chg[i - 20:i]) / 1.0)
    breadth[:20] = 0.0
    breadth[np.isnan(breadth)] = 0.0
    # 当日快照真实广度覆盖最后一行
    up = float(snapshot.get("up_total") or 0)
    down = float(snapshot.get("down_total") or 0)
    if up + down > 0:
        breadth[-1] = (up - down) / (up + down)

    feat = np.column_stack([sh_quantile, turnover, amount_rel, pct_chg,
                            usdcny_pct, vol_20d, breadth])
    names = ["sh_quantile", "turnover", "amount_rel", "pct_chg",
             "usdcny_pct", "vol_20d", "breadth"]
    bad = np.isnan(feat).any(axis=1) | np.isnan(label)
    feat, label = feat[~bad], label[~bad]
    return feat, label, names


# ---------------------------------------------------------------------------
# 五、训练 / 预测 / 分级
# ---------------------------------------------------------------------------

def train_predict(feat, label, names, months=60, use_opinion=None):
    """滚动时序窗口训练 + 预测下一交易日波动率。

    窗口：months 对应约 months*21 个交易日；样本不足 200 自动降级为
    简易统计模型（近 20 日波动率分位数 + 当前波动率）。
    """
    win = months * 21
    n = len(label)
    hist_n = min(n - 1, win)  # 训练用最近 win 天（不含待预测日）
    if hist_n < 200:
        # 降级：简易统计模型
        recent = label[-min(20, n):]
        pred = float(np.percentile(recent, 70)) if len(recent) else 0.0
        return {
            "backend": "statistical_fallback",
            "pred_vol": pred,
            "grade": grade_risk(pred),
            "score": risk_score(pred),
            "hist_n": hist_n,
            "note": "有效样本 %d < 200，已降级为简易统计模型（近20日波动率70分位）" % hist_n,
            "importances": {name: None for name in names},
            "fit_mae": None,
            "fit_r": None,
        }

    X = feat[n - hist_n:]
    y = label[n - hist_n:]
    # 若提供舆情特征列（可选），追加为第 8 个特征
    if use_opinion is not None:
        X = np.column_stack([X, np.full(len(X), use_opinion)])
        names = names + ["opinion_index"]

    # 预处理流水线：Winsor → VIF → Z-score（仅在训练集拟合，避免泄露）
    Xw = np.column_stack([winsorize(X[:, j]) for j in range(X.shape[1])])
    kept, removed = vif_filter(Xw, names, threshold=10.0)
    Xf = Xw[:, kept]
    Xs, mu, sigma = zscore(Xf)
    names_kept = [names[j] for j in kept]

    # 严格前向验证：用窗口内前 85% 训练一次，预测后 15% 每一天的波动率。
    # 训练段与验证段严格时序不重叠，无未来数据泄露；相比逐日滚动重训
    # 大大降低计算量（仅 2 次训练），口径上属于"固定模型前向验证"。
    m = len(y)
    split = int(m * 0.85)
    oos_preds, oos_trues = [], []
    if split >= 200 and m - split >= 5:
        rf_val = RandomForestRegressor(n_estimators=103, min_samples_split=3,
                                       min_samples_leaf=2, max_depth=10,
                                       random_state=42)
        rf_val.fit(Xs[:split], y[:split])
        oos_preds = [float(p) for p in rf_val.predict(Xs[split:])]
        oos_trues = [float(v) for v in y[split:]]

    # 最终模型：用全部历史训练，预测下一个交易日
    rf_final = RandomForestRegressor(n_estimators=103, min_samples_split=3,
                                     min_samples_leaf=2, max_depth=10,
                                     random_state=42)
    rf_final.fit(Xs, y)
    pred_vol = float(rf_final.predict(Xs[-1:])[0])

    importances = {}
    fi = rf_final.feature_importances_
    for j, nm in enumerate(names_kept):
        importances[nm] = float(fi[j])
    for rm in removed:
        importances[rm] = 0.0

    fit_mae = fit_r = None
    if len(oos_preds) >= 5:
        arr_p, arr_t = np.array(oos_preds), np.array(oos_trues)
        fit_mae = float(np.mean(np.abs(arr_p - arr_t)))
        if arr_t.std() > 1e-9 and arr_p.std() > 1e-9:
            fit_r = float(np.corrcoef(arr_p, arr_t)[0, 1])
        else:
            fit_r = None

    return {
        "backend": rf_final.backend,
        "pred_vol": pred_vol,
        "grade": grade_risk(pred_vol),
        "score": risk_score(pred_vol),
        "hist_n": hist_n,
        "note": "",
        "importances": importances,
        "fit_mae": fit_mae,
        "fit_r": fit_r,
        "removed_vif": removed,
        "names_kept": names_kept,
        "mu": mu, "sigma": sigma,
    }


def grade_risk(pred_vol):
    """风险分级：>4% 高 / 2~4% 中 / <2% 低。"""
    if pred_vol > 4.0:
        return "高"
    if pred_vol >= 2.0:
        return "中"
    return "低"


def risk_score(pred_vol):
    """映射综合风险分 0-100（封顶）。分段线性：0%(0分)→2%(50分)→4%(80分)→6%+(100分)。"""
    v = pred_vol
    if v <= 0:
        s = 0.0
    elif v < 2.0:
        s = v / 2.0 * 50
    elif v < 4.0:
        s = 50 + (v - 2.0) / 2.0 * 30
    elif v < 6.0:
        s = 80 + (v - 4.0) / 2.0 * 20
    else:
        s = 100.0
    return int(round(min(max(s, 0), 100)))


# ---------------------------------------------------------------------------
# 六、报告输出
# ---------------------------------------------------------------------------

def render_market_report(result, snapshot, opinion, news_detail, out_dir=".",
                         name="上证综指", code=None):
    """渲染单指数报告。name/code 用于标题与文件名区分；code 缺省时用旧文件名。"""
    lines = []
    lines.append("=" * 60)
    lines.append("舆情风险预警 · 大盘模式（%s）" % name)
    lines.append("=" * 60)
    lines.append("数据日期      : %s" % snapshot.get("date", ""))
    # 兼容新旧字段：新采集用 close/pct，旧文件用 sh_close/sh_pct
    close_v = snapshot.get("close", snapshot.get("sh_close", 0))
    pct_v = snapshot.get("pct", snapshot.get("sh_pct", 0))
    lines.append("%s收盘   : %.2f（%+.2f%%）" % (name, close_v, pct_v))
    lines.append("成交额        : %.0f 亿元" % snapshot.get("amount_yi", 0))
    lines.append("上涨/下跌     : %s / %s" % (snapshot.get("up_total"), snapshot.get("down_total")))
    lines.append("-" * 60)
    lines.append("【下一交易日预测】")
    lines.append("  预测波动率    : %.2f%%" % result["pred_vol"])
    lines.append("  风险等级      : %s" % result["grade"])
    lines.append("  综合风险分    : %d / 100" % result["score"])
    lines.append("  模型后端      : %s" % result.get("backend", ""))
    if result.get("note"):
        lines.append("  ⚠️  %s" % result["note"])
    lines.append("-" * 60)
    lines.append("【舆情维度】")
    lines.append("  舆情指数      : %+.3f（%s）" % (
        opinion, "看多" if opinion > 0.05 else ("看空" if opinion < -0.05 else "中性")))
    lines.append("  文本样本      : %d 条（近 %d 天）" % (
        news_detail.get("count", 0), news_detail.get("window_days", 30)))
    breadth = (float(snapshot.get("up_total", 0)) - float(snapshot.get("down_total", 0))) / (
        float(snapshot.get("up_total", 0)) + float(snapshot.get("down_total", 0)) or 1)
    lines.append("  市场广度      : %+.2f（上涨占比 %.1f%%）" % (
        breadth, float(snapshot.get("up_total", 0)) /
        (float(snapshot.get("up_total", 0)) + float(snapshot.get("down_total", 0)) or 1) * 100))
    # 舆情 + 广度共振预警
    if opinion < -0.05 and breadth < -0.1:
        lines.append("  ⚠️  舆情与广度同步转负：即使预测波动率不高，也要警惕短线 risk-off")
    elif opinion > 0.05 and breadth > 0.1:
        lines.append("  ✅  舆情与广度同步转正：情绪面支撑，短线风险偏好回暖")
    lines.append("-" * 60)
    lines.append("【特征重要性】")
    imp = result.get("importances", {})
    ranked = sorted(imp.items(), key=lambda kv: (kv[1] if kv[1] is not None else -1), reverse=True)
    for nm, v in ranked:
        if v is None:
            lines.append("  %-16s  —（降级模型无此输出）" % nm)
        else:
            bars = int(round(v * 30))
            lines.append("  %-16s %5.1f%%  %s" % (nm, v * 100, "#" * bars))
    if result.get("removed_vif"):
        lines.append("  （VIF 剔除：%s）" % ", ".join(result["removed_vif"]))
    lines.append("-" * 60)
    lines.append("【模型拟合质量（最近 OOS）】")
    if result.get("fit_mae") is not None:
        lines.append("  MAE = %.3f%%  相关系数 r = %s" % (
            result["fit_mae"], "%.3f" % result["fit_r"] if result.get("fit_r") is not None else "N/A"))
    else:
        lines.append("  样本不足，未做 OOS 拟合评估")
    lines.append("-" * 60)
    lines.append("【解读要点】")
    lines.append("  1. 指数天然波动率低于个股，优先看综合风险分与舆情方向，"
                 "勿只看绝对波动率阈值。")
    lines.append("  2. 大盘/个股数据源口径不一致，风险分不可横向对比。")
    lines.append("  3. 样本外 R²≈0.52，对黑天鹅预测能力有限，重大事件需人工二次研判。")
    lines.append("  4. 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。")
    lines.append("=" * 60)

    text = "\n".join(lines)
    os.makedirs(out_dir, exist_ok=True)
    # 文件名：传了 code 则带后缀区分，否则沿用旧名（上证默认）
    if code:
        txt_name = "risk_report_market_%s.txt" % code
        json_name = "risk_report_market_%s.json" % code
    else:
        txt_name, json_name = "risk_report_market.txt", "risk_report_market.json"
    with open(os.path.join(out_dir, txt_name), "w", encoding="utf-8") as f:
        f.write(text)
    payload = {
        "mode": "market",
        "index_code": code,
        "index_name": name,
        "data_date": snapshot.get("date", ""),
        "pred_vol": result["pred_vol"],
        "grade": result["grade"],
        "score": result["score"],
        "backend": result.get("backend", ""),
        "opinion_index": opinion,
        "news_detail": news_detail,
        "breadth": breadth,
        "importances": result.get("importances", {}),
        "fit_mae": result.get("fit_mae"),
        "fit_r": result.get("fit_r"),
        "note": result.get("note", ""),
        "risk_off_warning": bool(opinion < -0.05 and breadth < -0.1),
    }
    with open(os.path.join(out_dir, json_name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return text


# ---------------------------------------------------------------------------
# 七、三指数对比报告（模式 A 扩展）
# ---------------------------------------------------------------------------

def render_compare_report(results, news_detail, out_dir="."):
    """汇总三指数预测结果，输出并列对比报告。

    results: list[dict]，每项含 code/name/result/snapshot/opinion。
    舆情（opinion）三指数共用同一新闻源，仅输出一次。
    """
    lines = []
    lines.append("=" * 70)
    lines.append("舆情风险预警 · 大盘对比（上证综指 / 深证成指 / 创业板指）")
    lines.append("=" * 70)
    lines.append("数据日期      : %s" % (results[0]["snapshot"].get("date", "") if results else ""))
    lines.append("舆情指数      : %+.3f（%s）  文本样本 %d 条" % (
        results[0]["opinion"],
        "看多" if results[0]["opinion"] > 0.05 else ("看空" if results[0]["opinion"] < -0.05 else "中性"),
        news_detail.get("count", 0)))
    lines.append("-" * 70)
    lines.append("%-12s %10s %8s %10s %10s" % (
        "指数", "预测波动率", "风险等级", "综合风险分", "模型后端"))
    lines.append("-" * 70)
    for r in results:
        res = r["result"]
        lines.append("%-12s %8.2f%% %8s %8d/100 %10s" % (
            r["name"], res["pred_vol"], res["grade"], res["score"],
            res.get("backend", "")))
        if res.get("note"):
            lines.append("  ⚠️  %s" % res["note"])
    lines.append("-" * 70)
    lines.append("【风险梯度】")
    scores = sorted(results, key=lambda r: r["result"]["score"], reverse=True)
    lines.append("  风险最高  → %s（%d/100，预测波动率 %.2f%%）" % (
        scores[0]["name"], scores[0]["result"]["score"], scores[0]["result"]["pred_vol"]))
    lines.append("  风险最低  → %s（%d/100，预测波动率 %.2f%%）" % (
        scores[-1]["name"], scores[-1]["result"]["score"], scores[-1]["result"]["pred_vol"]))
    if scores[0]["result"]["score"] - scores[-1]["result"]["score"] >= 20:
        lines.append("  ⚠️  三指数风险分化明显，结构行情概率大，重指数轻大盘。")
    lines.append("-" * 70)
    lines.append("【解读要点】")
    lines.append("  1. 舆情口径为全市场（新闻+涨跌分布），三指数共用；差异体现在各自量价特征。")
    lines.append("  2. 指数天然波动率低于个股，优先看综合风险分与舆情方向，勿只看绝对波动率。")
    lines.append("  3. 三指数风险分同源可比，可横向对比强弱；大盘/个股口径仍不可比。")
    lines.append("  4. 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。")
    lines.append("=" * 70)

    text = "\n".join(lines)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "risk_report_market_compare.txt"), "w",
              encoding="utf-8") as f:
        f.write(text)
    payload = {
        "mode": "market_compare",
        "data_date": results[0]["snapshot"].get("date", "") if results else "",
        "opinion_index": results[0]["opinion"] if results else 0.0,
        "news_detail": news_detail,
        "indexes": [{
            "index_code": r["code"], "index_name": r["name"],
            "pred_vol": r["result"]["pred_vol"], "grade": r["result"]["grade"],
            "score": r["result"]["score"], "backend": r["result"].get("backend", ""),
            "note": r["result"].get("note", ""),
            "fit_mae": r["result"].get("fit_mae"),
            "fit_r": r["result"].get("fit_r"),
        } for r in results],
    }
    with open(os.path.join(out_dir, "risk_report_market_compare.json"), "w",
              encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return text


# ---------------------------------------------------------------------------
# 八、主入口
# ---------------------------------------------------------------------------

# 内置三指数清单（与 market_collect.py 保持一致）
DEFAULT_INDEXES = [
    {"code": "000001.SH", "name": "上证综指"},
    {"code": "399001.SZ", "name": "深证成指"},
    {"code": "399006.SZ", "name": "创业板指"},
]


def run_compare(data_dir, news_path="", out_dir=".", months=60, news_window=30):
    """三指数对比模式：扫描 data_dir 下的 kline_<code>.json + snapshot_<code>.json。

    新闻共用 data_dir/news.json（或 news_path 指定）。返回对比报告文本。
    """
    import glob
    results = []
    news_detail = {"count": 0, "window_days": news_window}
    for idx in DEFAULT_INDEXES:
        code, name = idx["code"], idx["name"]
        kpath = os.path.join(data_dir, "kline_%s.json" % code)
        spath = os.path.join(data_dir, "snapshot_%s.json" % code)
        if not (os.path.exists(kpath) and os.path.exists(spath)):
            print("⚠️ 跳过 %s：缺 %s 或 %s" % (name, kpath, spath))
            continue
        try:
            kline = load_kline(kpath)
            snapshot = load_snapshot(spath)
        except Exception as e:
            print("⚠️ %s 数据加载失败：%s" % (name, e))
            continue
        feat, label, names = build_market_features(kline, snapshot)
        news_path_eff = news_path or os.path.join(data_dir, "news.json")
        news = load_news(news_path_eff if os.path.exists(news_path_eff) else None)
        opinion, nd = compute_opinion_index(news, news_window)
        news_detail = nd
        result = train_predict(feat, label, names, months=months, use_opinion=None)
        results.append({"code": code, "name": name, "result": result,
                        "snapshot": snapshot, "opinion": opinion})
    if not results:
        raise RuntimeError("data_dir 下未找到任何可用的 kline_<code>.json + snapshot_<code>.json")
    report = render_compare_report(results, news_detail, out_dir)
    return report, results


def main():
    ap = argparse.ArgumentParser(description="舆情风险预警 · 大盘模式（三指数可选）")
    ap.add_argument("--kline", default="", help="指数 K 线文件（CSV/JSON），缺省用演示数据")
    ap.add_argument("--news", default="", help="新闻 JSON 文件，缺省用演示数据")
    ap.add_argument("--snapshot", default="", help="市场快照 JSON 文件，缺省用演示数据")
    ap.add_argument("--code", default="", help="指数代码（如 000001.SH），用于报告文件名区分")
    ap.add_argument("--name", default="上证综指", help="指数名称，用于报告标题")
    ap.add_argument("--out", default=".", help="报告输出目录")
    ap.add_argument("--months", type=int, default=60, choices=[36, 60],
                    help="滚动训练窗口月数（36/60），默认 60")
    ap.add_argument("--news-window", type=int, default=30, help="舆情文本采集窗口天数")
    ap.add_argument("--compare", default="", metavar="DATA_DIR",
                    help="三指数对比模式：传入采集数据目录，扫描 kline_<code>.json + snapshot_<code>.json 批量研判")
    args = ap.parse_args()

    # 三指数对比模式
    if args.compare:
        try:
            report, _ = run_compare(args.compare, args.news, args.out,
                                    args.months, args.news_window)
            print(report)
            return
        except Exception as e:
            print("错误：三指数对比失败 → %s" % e, file=sys.stderr)
            sys.exit(1)

    try:
        kline = load_kline(args.kline or None)
        news = load_news(args.news or None)
        snapshot = load_snapshot(args.snapshot or None)
    except Exception as e:
        print("错误：数据加载失败 → %s" % e, file=sys.stderr)
        sys.exit(1)

    try:
        feat, label, names = build_market_features(kline, snapshot)
    except Exception as e:
        print("错误：特征工程失败 → %s" % e, file=sys.stderr)
        sys.exit(1)

    opinion, news_detail = compute_opinion_index(news, args.news_window)
    # 训练期舆情列用当前舆情填充（大盘历史舆情通常不可得；当前值影响小）
    result = train_predict(feat, label, names, months=args.months, use_opinion=None)

    report = render_market_report(result, snapshot, opinion, news_detail,
                                  args.out, name=args.name, code=args.code or None)
    print(report)


if __name__ == "__main__":
    main()
