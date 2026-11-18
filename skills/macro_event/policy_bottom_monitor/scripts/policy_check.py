# -*- coding: utf-8 -*-
"""policy_check.py — 底部政策信号助手运行时位置计算
用法: python3 policy_check.py [--date YYYYMMDD] [--json]
输出: 当前市场位置(距250日高点/近20日跌幅/位置档) + 最近政策事件(组合进度)
"""
import json, csv, sys, os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "a_share_bottom_monitor", "data")
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references")

def load_csv(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = row["trade_date"].replace("-", "")
            out[d] = {"close": float(row["close"]),
                      "pct_chg": float(row["pct_chg"]) if row["pct_chg"] else None}
    return out

def calc_position(code, target):
    d = load_csv(os.path.join(BASE, f"{code}.csv"))
    dates = sorted(d.keys())
    if target not in dates:
        # 找<=target的最近交易日
        prev = [x for x in dates if x <= target]
        if not prev:
            return None
        target = prev[-1]
    idx = dates.index(target)
    if idx < 250:
        return {"date": target, "close": d[target]["close"], "pos_level": "N/A",
                "note": "数据不足250日，位置档N/A"}
    closes = [d[dates[i]]["close"] for i in range(idx-249, idx+1)]
    high250 = max(closes)
    ma250 = sum(closes) / 250
    c = closes[-1]
    c20 = d[dates[idx-20]]["close"] if idx >= 20 else None
    dd = c / high250 - 1
    r20 = (c / c20 - 1) if c20 else None
    # 位置档
    if dd <= -0.15 or (r20 is not None and r20 <= -0.10):
        level = "深跌区"
    elif dd >= -0.05:
        level = "浅跌区"
    else:
        level = "中性区"
    return {
        "date": target, "close": round(c, 2),
        "dd_from_250high": round(dd * 100, 1),
        "vs_ma250": round((c / ma250 - 1) * 100, 1),
        "ret20d": round(r20 * 100, 1) if r20 else None,
        "pos_level": level,
    }

def recent_policy_events(target, days=15):
    """找target前days天内的政策事件(判断组合进度)"""
    from datetime import datetime
    ev = json.load(open(os.path.join(REF, "policy-events.json"), encoding="utf-8"))
    t0 = datetime.strptime(str(target), "%Y%m%d")
    out = []
    for e in ev["events"]:
        d0 = datetime.strptime(e["date"], "%Y-%m-%d")
        if d0 <= t0 and (t0 - d0).days <= days:
            out.append({"date": e["date"], "name": e["name"], "category": e["category"],
                        "combo": e["combo"]})
    out.sort(key=lambda x: x["date"])
    return out

def main():
    target = None
    as_json = False
    for a in sys.argv[1:]:
        if a.startswith("--date"):
            target = a.split("=")[1] if "=" in a else sys.argv[sys.argv.index(a)+1]
        if a == "--json":
            as_json = True
    if not target:
        # 默认用数据最后一天
        d = load_csv(os.path.join(BASE, "000001.SH.csv"))
        target = max(d.keys())
    result = {"index": "000001.SH"}
    pos = calc_position("000001.SH", target)
    result["position"] = pos
    # 补充其他指数(有数据则输出)
    others = {}
    for code, name in [("399001.SZ", "深成指"), ("399006.SZ", "创业板指"), ("932000.CSI", "中证2000")]:
        try:
            p = calc_position(code, target)
            if p and p.get("pos_level") != "N/A":
                others[name] = p
        except Exception:
            pass
    result["others"] = others
    result["recent_policy_events"] = recent_policy_events(target)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        p = pos
        print(f"当前点位({p['date']}): {p['close']}")
        print(f"距250日高点: {p['dd_from_250high']:+.1f}%  距MA250: {p['vs_ma250']:+.1f}%  近20日: {p['ret20d']:+.1f}%")
        print(f"位置档: {p['pos_level']}")
        for name, op in others.items():
            print(f"  {name}: 距250高{op['dd_from_250high']:+.1f}% 近20日{op['ret20d']:+.1f}% {op['pos_level']}")
        rp = result["recent_policy_events"]
        if rp:
            print("\n近15日政策事件(组合进度):")
            for e in rp:
                print(f"  {e['date']} [{e['category']}] {e['name'][:30]} combo={e['combo']}")
        else:
            print("\n近15日无政策事件")

if __name__ == "__main__":
    main()
