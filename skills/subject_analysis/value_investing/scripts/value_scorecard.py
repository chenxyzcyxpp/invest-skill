#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""价值投资skill — 四层加权打分卡（纯标准库、离线可跑）。

职责边界：只做标准化测算与表格输出，**不取数、不荐股、不给目标价**。
输入数据由 Agent 按 references/data-sources.md 取数后填入（或用户直接提供）。

输入 JSON 契约（也见 --example）：
{
  "as_of": "2026-11-17",
  "stocks": [{
    "code": "600519", "name": "贵州茅台",
    "macro":    {"score": 62, "evidence": ["..."]},   // 或直接写 62
    "industry": {"score": 78, "evidence": ["..."]},
    "quality":  {"score": 85, "evidence": ["..."]},
    "valuation": {
      "price": 1420.0,              // 现价，单位与 dcf_value 一致
      "pe_ttm": 22.5,               // TTM 口径；<=0 表示亏损/失真
      "pb": 7.8,
      "peg": 1.6,                   // 倍数（不是百分数）；<=0 不可用
      "ps": 10.2,                   // 仅记录，不参与自动评分
      "pe_history_percentile": 18.0,// 近3年 PE-TTM 分位，0-100（0=最便宜）
      "pe_peer_median": 25.0,       // 同行 PE-TTM 中位数，口径须与 pe_ttm 一致
      "pb_peer_median": 5.0,
      "dcf_value": 1600.0,          // DCF 情景中枢；<=0 不可用
      "dividend_yield": 3.2         // 仅记录，不参与自动评分
    }
  }]
}

硬规则（对应 SKILL.md 铁律）：
  * 缺失项保留 N/A，绝不填 0；缺失项权重按剩余项比例分摊并在 reweight_note 标注。
  * 估值层覆盖率 < 50% 或估值不可算时，禁止输出总分与「能不能买」结论。
  * 缺失层数 >= 2 时不输出总分。
  * 估值权重不得低于任何单一层级（体现「好公司≠好股票」），--weights 会校验。
  * 结论只用「值得关注 / 需等待更合理价格 / 估值偏贵 / 观察 / 数据不足」。

用法：
  python3 value_scorecard.py --example
  python3 value_scorecard.py --input data.json --out report.csv [--json-out report.json]
  python3 value_scorecard.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LAYERS = ("macro", "industry", "quality", "valuation")
DEFAULT_WEIGHTS: Dict[str, float] = {
    "macro": 0.15, "industry": 0.25, "quality": 0.30, "valuation": 0.30,
}
VAL_ITEMS: Dict[str, float] = {
    "PE历史分位": 0.35,
    "相对同行PE": 0.25,
    "相对同行PB": 0.15,
    "PEG": 0.15,
    "DCF安全边际": 0.10,
}
VAL_COVERAGE_MIN = 0.50
LAYER_LABELS = {"macro": "宏观", "industry": "行业", "quality": "质量", "valuation": "估值"}


def as_number(value: Any) -> Optional[float]:
    """把输入转成有限浮点数；None / N/A / 非数字一律返回 None（不降级为 0）。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        text = value.strip().replace("%", "").replace(",", "")
        if not text or text.lower() in ("n/a", "na", "none", "null", "-", "—", "未知"):
            return None
        try:
            result = float(text)
        except ValueError:
            return None
    else:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def relative_score(ratio: float) -> float:
    """相对同行倍数→分数：1.0x=60、0.7x≈78、1.5x=30、2.0x=0。"""
    return clamp(60.0 + (1.0 - ratio) * 60.0)


def valuation_score(val: Any) -> Tuple[Optional[float], float, List[str], str]:
    """返回 (估值分 0-100 / None, 覆盖率, 缺口清单, 权重重分配说明)。"""
    if not isinstance(val, dict):
        return None, 0.0, ["估值数据整块缺失"], ""

    parts: List[Tuple[str, float, float]] = []
    gaps: List[str] = []

    pct = as_number(val.get("pe_history_percentile"))
    if pct is not None:
        parts.append(("PE历史分位", VAL_ITEMS["PE历史分位"], clamp(100.0 - pct)))
    else:
        gaps.append("PE历史分位")

    price = as_number(val.get("price"))
    pe = as_number(val.get("pe_ttm"))
    pe_peer = as_number(val.get("pe_peer_median"))
    if pe is not None and pe > 0 and pe_peer is not None and pe_peer > 0:
        parts.append(("相对同行PE", VAL_ITEMS["相对同行PE"], relative_score(pe / pe_peer)))
    elif pe is not None and pe <= 0:
        gaps.append("相对同行PE（亏损/PE失真，该项不参与）")
    else:
        gaps.append("相对同行PE")

    pb = as_number(val.get("pb"))
    pb_peer = as_number(val.get("pb_peer_median"))
    if pb is not None and pb > 0 and pb_peer is not None and pb_peer > 0:
        parts.append(("相对同行PB", VAL_ITEMS["相对同行PB"], relative_score(pb / pb_peer)))
    else:
        gaps.append("相对同行PB")

    peg = as_number(val.get("peg"))
    if peg is not None and peg > 0:
        parts.append(("PEG", VAL_ITEMS["PEG"], clamp(100.0 - (peg - 0.5) * 50.0)))
    elif peg is not None and peg <= 0:
        gaps.append("PEG（增速为负/失真，该项不参与）")
    else:
        gaps.append("PEG")

    dcf = as_number(val.get("dcf_value"))
    if dcf is not None and dcf > 0 and price is not None and price > 0:
        margin = (dcf - price) / price
        parts.append(("DCF安全边际", VAL_ITEMS["DCF安全边际"], clamp(50.0 + margin * 100.0)))
    else:
        gaps.append("DCF安全边际")

    covered = sum(weight for _, weight, _ in parts)
    total_possible = sum(VAL_ITEMS.values())
    coverage = covered / total_possible if total_possible else 0.0
    if covered <= 0:
        return None, 0.0, gaps, ""

    score = sum(weight * value for _, weight, value in parts) / covered
    note = ""
    if len(parts) < len(VAL_ITEMS):
        note = "估值层权重已重分配（缺失 {} 项）".format(len(VAL_ITEMS) - len(parts))
    if coverage < VAL_COVERAGE_MIN:
        return None, coverage, gaps, note
    return round(score, 1), round(coverage, 3), gaps, note


def layer_score(raw: Any, label: str, gaps: List[str]) -> Optional[float]:
    """读取定性层分数；校验 0-100 范围，记录依据缺失告警。"""
    evidence: Any = []
    if isinstance(raw, dict):
        value = as_number(raw.get("score"))
        evidence = raw.get("evidence") or []
    else:
        value = as_number(raw)
    if value is None:
        gaps.append("{}层数据缺失".format(label))
        return None
    if value < 0 or value > 100:
        gaps.append("{}层分数越界({})，按缺失处理".format(label, value))
        return None
    if not evidence:
        gaps.append("{}层未提供可核验依据".format(label))
    return value


def evaluate(stock: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    gaps: List[str] = []
    scores: Dict[str, Optional[float]] = {}
    for layer in LAYERS[:3]:
        scores[layer] = layer_score(stock.get(layer), LAYER_LABELS[layer], gaps)

    val_score, coverage, val_gaps, val_note = valuation_score(stock.get("valuation"))
    gaps.extend(val_gaps)
    scores["valuation"] = val_score

    total: Optional[float] = None
    verdict = "数据不足 · 不做价格判断"
    notes: List[str] = []
    if val_note:
        notes.append(val_note)

    if val_score is None:
        notes.append("估值层数据不足，禁止输出总分与价格判断")
    missing_layers = [layer for layer in LAYERS if scores[layer] is None]
    if len(missing_layers) >= 2:
        total = None
        verdict = "数据不足 · 不做结论"
        notes.append("缺失层级≥2（{}），不输出总分".format("、".join(LAYER_LABELS[x] for x in missing_layers)))
    elif val_score is not None:
        available_weight = sum(weights[layer] for layer in LAYERS if scores[layer] is not None)
        total = round(
            sum(weights[layer] * scores[layer] for layer in LAYERS if scores[layer] is not None)
            / available_weight, 1
        )
        if len(missing_layers) == 1:
            notes.append("层级权重已重分配（缺失{}层）".format(LAYER_LABELS[missing_layers[0]]))
        if val_score < 45:
            verdict = "估值偏贵 · 暂不介入价格判断"
        elif total >= 75 and val_score >= 60:
            verdict = "值得关注 · 价格相对合理"
        elif total >= 60 and val_score >= 45:
            verdict = "值得关注 · 需等待更合理价格"
        else:
            verdict = "观察 · 基本面或性价比不足"

    return {
        "code": str(stock.get("code") or "—"),
        "name": str(stock.get("name") or "—"),
        "macro": scores["macro"],
        "industry": scores["industry"],
        "quality": scores["quality"],
        "valuation": scores["valuation"],
        "total": total,
        "valuation_coverage": coverage,
        "verdict": verdict,
        "gaps": "；".join(gaps) if gaps else "无",
        "notes": "；".join(notes) if notes else "—",
    }


def display(value: Any) -> str:
    return "—" if value is None else str(value)


def to_markdown(rows: List[Dict[str, Any]], as_of: str) -> str:
    headers = ["代码", "名称", "宏观", "行业", "质量", "估值", "总分", "估值覆盖", "参考结论", "数据缺口 / 说明"]
    lines = [
        "### 价值投资四层打分卡｜基准日 {}".format(as_of or "未提供"),
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        cells = [
            row["code"], row["name"],
            display(row["macro"]), display(row["industry"]), display(row["quality"]),
            display(row["valuation"]), display(row["total"]),
            "{:.0%}".format(row["valuation_coverage"]) if row["valuation_coverage"] else "—",
            row["verdict"],
            row["gaps"] + (("；" + row["notes"]) if row["notes"] != "—" else ""),
        ]
        lines.append("| " + " | ".join(str(c).replace("|", "/") for c in cells) + " |")
    lines += [
        "",
        "> 评分仅为框架辅助：宏观/行业/质量分须有可核验依据；估值数据不足时不下「能不能买」结论。",
        "> 结论仅供参考，不构成投资建议。",
    ]
    return "\n".join(lines)


CSV_FIELDS = ["code", "name", "macro", "industry", "quality", "valuation",
              "total", "valuation_coverage", "verdict", "gaps", "notes"]


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: ("" if row.get(key) is None else row.get(key)) for key in CSV_FIELDS})


def parse_weights(text: Optional[str]) -> Dict[str, float]:
    if not text:
        return dict(DEFAULT_WEIGHTS)
    try:
        numbers = [float(part.strip()) for part in text.split(",")]
    except ValueError as exc:
        raise SystemExit("--weights 需为 4 个数字，如 15,25,30,30：{}".format(exc))
    if len(numbers) != 4 or any(number < 0 for number in numbers) or abs(sum(numbers) - 100) > 1e-6:
        raise SystemExit("--weights 需为 4 个非负数字且合计 100（顺序：宏观,行业,质量,估值）")
    weights = dict(zip(LAYERS, [number / 100.0 for number in numbers]))
    if weights["valuation"] < max(weights["macro"], weights["industry"], weights["quality"]):
        raise SystemExit("估值权重不得低于任何单一层级（好公司≠好股票），请调整 --weights")
    return weights


def load_stocks(data: Any) -> Tuple[str, List[Dict[str, Any]]]:
    if isinstance(data, list):
        return "", data
    if isinstance(data, dict):
        as_of = str(data.get("as_of") or "")
        stocks = data.get("stocks")
        if isinstance(stocks, list):
            return as_of, stocks
        return as_of, [data]
    raise SystemExit("输入 JSON 需为对象、{stocks:[...]} 或数组")


EXAMPLE = {
    "as_of": "2026-11-17",
    "stocks": [
        {
            "code": "600519", "name": "示例A（字段齐全）",
            "macro": {"score": 62, "evidence": ["货币政策偏宽松", "消费刺激政策落地"]},
            "industry": {"score": 78, "evidence": ["行业处于成熟期", "五力中购买者议价能力弱"]},
            "quality": {"score": 85, "evidence": ["市占率领先", "毛利率高于同行"]},
            "valuation": {
                "price": 1420.0, "pe_ttm": 22.5, "pb": 7.8, "peg": 1.1, "ps": 10.2,
                "pe_history_percentile": 18.0, "pe_peer_median": 25.0,
                "pb_peer_median": 6.0, "dcf_value": 1650.0, "dividend_yield": 3.2,
            },
        },
        {
            "code": "000001", "name": "示例B（含缺失与亏损PE）",
            "macro": {"score": 50, "evidence": ["宏观中性"]},
            "industry": {"score": 55, "evidence": ["行业增速平缓"]},
            "quality": {"score": 60, "evidence": ["区域龙头"]},
            "valuation": {
                "price": 11.0, "pe_ttm": -8.0, "pb": 0.6, "pb_peer_median": 0.8,
                "dcf_value": 12.5,
            },
        },
    ],
}


def selftest() -> None:
    """校验：缺失不填0、负PE不参与、估值不足不下结论、权重重分配。"""
    base = json.loads(json.dumps(EXAMPLE["stocks"][0], ensure_ascii=False))

    full = evaluate(base, DEFAULT_WEIGHTS)
    assert full["valuation"] is not None and full["valuation"] > 60, full
    assert full["total"] is not None and "值得关注" in full["verdict"], full

    poor = {"code": "T2", "name": "亏损且数据稀薄", "macro": 50,
            "valuation": {"price": 10.0, "pe_ttm": -5.0}}
    row_poor = evaluate(poor, DEFAULT_WEIGHTS)
    assert row_poor["valuation"] is None, row_poor
    assert row_poor["total"] is None and "数据不足" in row_poor["verdict"], row_poor
    assert any("失真" in gap for gap in row_poor["gaps"].split("；")), row_poor

    missing = json.loads(json.dumps(base, ensure_ascii=False))
    del missing["valuation"]["pe_history_percentile"]
    del missing["valuation"]["peg"]
    row_missing = evaluate(missing, DEFAULT_WEIGHTS)
    assert row_missing["valuation_coverage"] < 1.0, row_missing
    assert row_missing["valuation"] > 0, row_missing
    assert "权重已重分配" in row_missing["notes"], row_missing

    zero_filled = json.loads(json.dumps(missing, ensure_ascii=False))
    zero_filled["valuation"]["pe_history_percentile"] = 0.0  # 真实分位0 = 最便宜
    row_zero = evaluate(zero_filled, DEFAULT_WEIGHTS)
    assert row_zero["valuation"] > row_missing["valuation"], (row_zero, row_missing)

    print("PASS 1/4 字段齐全：估值分 {} > 60，输出参考结论".format(full["valuation"]))
    print("PASS 2/4 亏损PE + 估值稀薄：不输出总分，结论= {}".format(row_poor["verdict"]))
    print("PASS 3/4 缺失项按权重分摊（覆盖 {:.0%}），未填 0".format(row_missing["valuation_coverage"]))
    print("PASS 4/4 缺失(≠填0)可区分：N/A={} vs 真实分位0={}".format(
        row_missing["valuation"], row_zero["valuation"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="价值投资skill 四层加权打分卡")
    parser.add_argument("--input", help="输入 JSON 文件路径")
    parser.add_argument("--out", help="输出 CSV 路径（UTF-8 BOM，Excel 可直开）")
    parser.add_argument("--json-out", help="可选：输出结构化结果 JSON 路径")
    parser.add_argument("--weights", help="层级权重百分数，顺序 宏观,行业,质量,估值，合计100")
    parser.add_argument("--example", action="store_true", help="打印输入 JSON 样例")
    parser.add_argument("--selftest", action="store_true", help="运行内置规则自检")
    args = parser.parse_args()

    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return
    if args.selftest:
        selftest()
        return
    if not args.input:
        parser.error("需提供 --input，或使用 --example / --selftest")

    weights = parse_weights(args.weights)
    with open(args.input, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    as_of, stocks = load_stocks(data)
    rows = [evaluate(stock, weights) for stock in stocks if isinstance(stock, dict)]
    print(to_markdown(rows, as_of))
    if args.out:
        write_csv(args.out, rows)
        print("\nCSV 已写出：{}".format(args.out))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump({"as_of": as_of, "weights": weights, "rows": rows},
                      handle, ensure_ascii=False, indent=2)
        print("JSON 已写出：{}".format(args.json_out))


if __name__ == "__main__":
    main()
