# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
sentiment.py — 个股股吧舆情情感计算
====================================
输入：按日聚合的股吧帖子列表；输出：个股舆情指数时间序列。
算法：情感词典（支持否定词、程度副词）→ 单文本情感值 → TF-IDF 加权
      Σ(TF-IDF权重 × 单文本情感值) 得到日度舆情指数。
     股吧语料稀疏（当日帖子过少）时，自动退化为情感求和（等权）。

遵循 skill 工程约束：不伪造数据；语料缺失明确返回空并以 0（中性）占位并标注。
"""

import math
from datetime import datetime


# ---------------------------------------------------------------------------
# 金融情感词典（个股语境；与大盘模式共用同一套词典口径）
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "上涨", "大涨", "涨停", "走强", "拉升", "反弹", "突破", "创新高", "利好",
    "回暖", "企稳", "放量上攻", "牛市", "看多", "乐观", "买入", "增持", "加仓",
    "超预期", "景气", "高增长", "盈利改善", "强势", "领涨", "爆发", "业绩好",
    "订单饱满", "供不应求", "回购", "增持计划", "中标", "大单",
}
NEGATIVE_WORDS = {
    "下跌", "大跌", "跌停", "走弱", "跳水", "回落", "破位", "创新低", "利空",
    "低迷", "熊市", "看空", "悲观", "卖出", "减持", "减仓", "清仓",
    "不及预期", "衰退", "亏损", "恶化", "弱势", "领跌", "崩盘", "恐慌",
    "业绩变脸", "商誉减值", "质押爆仓", "立案", "处罚", "退市风险",
    "减持计划", "解禁", "业绩暴雷",
}
NEGATION_WORDS = {"不", "没有", "未", "无", "并非", "难以", "别", "勿", "绝非", "并未"}
DEGREE_WORDS = {
    "极度": 1.8, "非常": 1.6, "十分": 1.6, "明显": 1.4, "显著": 1.5,
    "大幅": 1.5, "强烈": 1.5, "较": 1.2, "较为": 1.2, "略": 0.8, "小幅": 0.8,
    "轻微": 0.8, "部分": 0.7, "有所": 0.9, "持续": 1.3, "加速": 1.3,
}


class _TinySegmenter:
    """轻量中文分词：词典 + 正向最大匹配。无 jieba 环境也可用。"""

    def __init__(self):
        self.vocab = set(POSITIVE_WORDS) | set(NEGATIVE_WORDS) | set(NEGATION_WORDS) | set(DEGREE_WORDS)
        self.max_len = max((len(w) for w in self.vocab), default=1)

    def segment(self, text):
        if not text:
            return []
        try:
            import jieba
            return [w for w in jieba.lcut(text) if w.strip()]
        except Exception:
            pass
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


def _text_sentiment(tokens, seg=None):
    """单文本情感值：程度副词放大 + 否定词翻转，返回 (score, n_hit)。"""
    score, n_hit = 0.0, 0
    for i, tok in enumerate(tokens):
        base = None
        if tok in POSITIVE_WORDS:
            base = 1.0
        elif tok in NEGATIVE_WORDS:
            base = -1.0
        if base is None:
            continue
        deg, neg = 1.0, False
        for j in range(max(0, i - 3), i):
            prev = tokens[j]
            if prev in DEGREE_WORDS:
                deg = max(deg, DEGREE_WORDS[prev])
            if prev in NEGATION_WORDS:
                neg = not neg
        score += base * deg * (-1 if neg else 1)
        n_hit += 1
    return score, n_hit


def _normalize_date(d):
    """把各种日期格式归一为 YYYY-MM-DD；失败返回空串。"""
    if not d:
        return ""
    s = str(d).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M", "%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    # 形如 "10-08" 补当前年份
    try:
        return datetime.strptime(str(datetime.now().year) + "-" + s[:5], "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        return ""


def build_opinion_series(posts, sparse_threshold=3):
    """按日聚合股吧帖子 → 日度舆情指数。

    参数
    ----
    posts : list[dict]，每项含 {"date": ..., "text": ...} 或 {"title"/"content"}
    sparse_threshold : int，单日有效帖数低于该值时视为语料稀疏

    返回
    ----
    series : dict {date_str: {"opinion": float, "n": int, "sparse": bool}}
    detail : dict，供报告展示
    """
    seg = _TinySegmenter()
    daily = {}
    doc_sets = []
    for p in posts:
        if isinstance(p, str):
            text, d = p, ""
        else:
            text = (p.get("text") or p.get("content") or p.get("title") or "")
            d = p.get("date") or p.get("datetime") or p.get("pub_time") or ""
        d = _normalize_date(d)
        if not text.strip():
            continue
        toks = seg.segment(text)
        score, n_hit = _text_sentiment(toks, seg)
        daily.setdefault(d, []).append((score, n_hit, toks))
        doc_sets.append(set(toks))

    if not daily:
        return {}, {"count": 0, "note": "无有效股吧语料，舆情指数置 0（中性）"}

    # TF-IDF：idf = log(1 + N/df)
    N = len(doc_sets)
    df = {}
    for s in doc_sets:
        for w in s:
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log(1.0 + N / df[w]) for w in df}

    series = {}
    total_scored = 0
    sparse_days = 0
    for d in sorted(daily.keys()):
        recs = daily[d]
        n_posts = len(recs)
        sparse = n_posts < sparse_threshold
        if sparse:
            sparse_days += 1
        # 语料稀疏时退化为情感求和（等权）；否则 TF-IDF 加权
        day_sum, n_hit_total = 0.0, 0
        for score, n_hit, toks in recs:
            if n_hit == 0:
                continue
            if sparse:
                w = 1.0
            else:
                w = sum(idf.get(t, 0.0) for t in toks if t in idf)
                w = w if w > 0 else 1.0
            day_sum += score * w
            n_hit_total += n_hit
        total_scored += n_hit_total
        if n_hit_total == 0:
            opinion = 0.0
        else:
            # 除以当日命中的 idf 总和，避免帖子数放大量纲；tanh 压缩到 (-1,1)
            if not sparse:
                wsum = sum(sum(idf.get(t, 0.0) for t in toks if t in idf)
                           for _, _, toks in recs)
                opinion = math.tanh(day_sum / max(wsum, 1e-9)) if wsum > 0 else 0.0
            else:
                opinion = math.tanh(day_sum / max(n_hit_total, 1))
        series[d] = {"opinion": float(opinion), "n": n_posts,
                     "n_hit": n_hit_total, "sparse": sparse}

    detail = {
        "count": N,
        "scored_terms": total_scored,
        "sparse_days": sparse_days,
        "n_days": len(series),
        "note": "语料稀疏日退化为情感求和" if sparse_days else "TF-IDF×情感加权",
    }
    return series, detail


def merge_opinion_channels(series_list, details_list=None, weights=None):
    """合并多个舆情通道的日度序列为单一序列（逐日加权平均）。

    参数
    ----
    series_list : list[dict]，每个元素为 build_opinion_series 返回的
                  {date_str: {"opinion": float, "n": int, "sparse": bool}}
    details_list : list[dict]，各通道 detail（供报告展示），可为 None
    weights : list[float]，各通道权重；缺省等权（0.5/0.5）

    返回
    ----
    merged : dict，{date_str: {"opinion", "n", "n_hit", "sparse"}}
    detail : dict，合并口径说明（含各通道条数、权重、覆盖天数）
    """
    if weights is None:
        weights = [1.0 / len(series_list) for _ in series_list] if series_list else []
    all_days = set()
    for s in series_list:
        all_days.update(s.keys())
    merged = {}
    for d in sorted(all_days):
        vals, ns, hits = [], [], []
        for s, w in zip(series_list, weights):
            if d in s:
                vals.append(s[d]["opinion"] * w)
                ns.append(s[d].get("n", 0))
                hits.append(s[d].get("n_hit", 0))
        if not vals:
            continue
        merged[d] = {
            "opinion": float(sum(vals)),
            "n": sum(ns),
            "n_hit": sum(hits),
            "sparse": any(s.get(d, {}).get("sparse", False) for s in series_list),
        }
    counts = [sum(v.get("n", 0) for v in s.values()) for s in series_list]
    days = [len(s) for s in series_list]
    detail = {
        "channels": len(series_list),
        "counts": counts,
        "weights": [round(w, 3) for w in weights],
        "days": days,
        "n_days": len(merged),
        "note": "多通道舆情逐日加权合成（权重 %s）"
                % "/".join("%.2f" % w for w in weights),
    }
    return merged, detail


if __name__ == "__main__":
    demo = [
        {"date": "2026-10-08", "text": "业绩超预期，放量拉升，看多！"},
        {"date": "2026-10-08", "text": "主力大幅流入，明显走强，加仓。"},
        {"date": "2026-10-07", "text": "高位跳水，主力流出，警惕回调。"},
        {"date": "2026-10-07", "text": "跌破支撑，悲观情绪浓厚。"},
    ]
    s, d = build_opinion_series(demo)
    print("detail:", d)
    for k, v in s.items():
        print(k, v)
