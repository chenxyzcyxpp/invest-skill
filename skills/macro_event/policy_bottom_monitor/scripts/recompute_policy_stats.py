# -*- coding: utf-8 -*-
"""recompute_policy_stats.py — 模式B自更新：重跑政策回测并归档
用法: python3 recompute_policy_stats.py
输出: stats/YYYYMMDD/ 归档（policy_stats.md + backtest.json），供人工比对结论

早期指数数据（可选）：由环境变量 POLICY_EARLY_DATA_DIR 指定目录，
目录内按 <指数代码>.json 命名（如 000001.SH.json / 399001.SZ.json），
格式与 load_early() 兼容。未配置或文件不存在时跳过该指数的早期数据补充，
回测仅使用 data/*.csv 覆盖区间——这是允许的，但结论须注明样本区间与缺口。
"""
import json, csv, re, os, sys, datetime

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "a_share_bottom_monitor", "data")
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")
STATS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stats")
EARLY_DIR = os.environ.get("POLICY_EARLY_DATA_DIR", "").strip()
EARLY_CODES = ("000001.SH", "399001.SZ")


def early_path(code):
    """返回该指数可选的早期数据文件路径；未配置/不存在则返回 None。"""
    if code not in EARLY_CODES or not EARLY_DIR:
        return None
    p = os.path.join(EARLY_DIR, f"{code}.json")
    return p if os.path.isfile(p) else None

def load_csv(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = row["trade_date"].replace("-", "")
            out[d] = {"close": float(row["close"]), "pct_chg": float(row["pct_chg"]) if row["pct_chg"] else None}
    return out

def load_early(path):
    raw = open(path, encoding="utf-8").read()
    try:
        outer = json.loads(raw)
        inner = outer["result"]
    except Exception:
        m = re.search(r'"result":\s*"(\[.*?\])"', raw, re.S)
        inner = m.group(1)
    arr = json.loads(inner)
    return {str(r["trade_date"]): {"close": r["close"], "pct_chg": r.get("pct_chg")} for r in arr}

def load_kline(code):
    d = {}
    p = early_path(code)
    if p:
        d.update(load_early(p))
    d.update(load_csv(os.path.join(BASE, f"{code}.csv")))
    return d

def next_trade_day(dates, target):
    for d in dates:
        if d >= target:
            return d
    return None

def ret_after(dates, kl, target, days):
    t = next_trade_day(dates, target)
    if t is None:
        return None
    idx = dates.index(t)
    if idx + days >= len(dates):
        return None
    return kl[dates[idx+days]]["close"] / kl[t]["close"] - 1

def main():
    kl = load_kline("000001.SH")
    dates = sorted(kl.keys())
    ev = json.load(open(os.path.join(REF, "policy-events.json"), encoding="utf-8"))
    rows = []
    for e in ev["events"]:
        t = e["date"].replace("-", "")
        rows.append({"id": e["id"], "name": e["name"], "date": e["date"],
                     "category": e["category"],
                     "r5": ret_after(dates, kl, t, 5),
                     "r20": ret_after(dates, kl, t, 20),
                     "r60": ret_after(dates, kl, t, 60)})
    today = datetime.date.today().strftime("%Y%m%d")
    outdir = os.path.join(STATS, today)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "backtest.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, default=str)
    lines = ["# 政策回测重跑归档 " + today, "", "| 事件 | 日期 | 工具 | T+5 | T+20 | T+60 |", "|------|------|------|-----|------|------|"]
    for r in rows:
        fmt = lambda x: f"{x*100:+.1f}%" if x is not None else "N/A"
        lines.append(f"| {r['name'][:30]} | {r['date']} | {r['category']} | {fmt(r['r5'])} | {fmt(r['r20'])} | {fmt(r['r60'])} |")
    with open(os.path.join(outdir, "policy_stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"归档完成: {outdir}")
    print("注意：结论修订须人工比对 policy-map.md，未经记录不得改知识库。")

if __name__ == "__main__":
    main()
