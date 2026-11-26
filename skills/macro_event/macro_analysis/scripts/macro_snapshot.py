# -*- coding: utf-8 -*-
# Authors: 姜青
"""
宏观快照抓取脚本（akshare 数据源，离线兜底）
============================================
用途：
  拉取股票投资所需的宏观关键指标最新值，输出为 JSON（默认打印到 stdout，
  也可 --out 写入文件），供「宏观—权益投资分析」skill 直接消费。

为什么需要它（数据口径说明）：
  akshare 中多数宏观"历史序列"接口已停更（部分停在 2008 年），而 *_yearly /
  报告型接口更新到最近月份。本脚本优先采用**更新更及时**的接口，并对每个
  指标做"新鲜度"标注（stale）。若 akshare 数据滞后，请优先用 MCP 实时源
  （mx-ds-mcp 东方财富妙想 / tdx-connector 通达信）交叉验证。

设计原则：
  - 每个指标独立 try/except，单点失败不影响整体；缺失项标注 "unavailable"。
  - 报告型接口最后一行常为"未发布"(NaN)，自动回落到上一个有效值并记录真实日期。
  - 输出保证 JSON 可序列化（numpy/pandas/日期类型统一兜底为原生类型或字符串）。

用法：
  python macro_snapshot.py                # 打印 JSON 到 stdout
  python macro_snapshot.py --out snap.json
  python macro_snapshot.py --pretty
"""
import argparse, json, sys, re, datetime as dt

try:
    import akshare as ak
except Exception as e:
    print(json.dumps({"error": "akshare unavailable: %s" % e}, ensure_ascii=False))
    sys.exit(1)

try:
    import numpy as _np
except Exception:
    _np = None
try:
    import pandas as _pd
except Exception:
    _pd = None


def _json_default(o):
    if isinstance(o, (dt.datetime, dt.date)):
        return o.isoformat()
    if _pd is not None and isinstance(o, _pd.Timestamp):
        return str(o)
    if _np is not None:
        if isinstance(o, _np.integer):
            return int(o)
        if isinstance(o, _np.floating):
            return (None if o != o else float(o))
        if isinstance(o, _np.bool_):
            return bool(o)
    return str(o)


def _num(v):
    try:
        if v is None:
            return None
        if hasattr(v, "item"):
            try:
                v = v.item()
            except Exception:
                pass
        if isinstance(v, str):
            v = v.strip().replace(",", "")
        f = float(v)
        return None if f != f else f
    except Exception:
        return None


def _parse_yearmonth(date_str):
    """从 '2025-09-10' / '2025年09月份' / 202609 / '2026-09-20' 提取 (year, month)。"""
    if date_str is None:
        return (None, None)
    s = str(date_str)
    m = re.search(r"(\d{4})", s)
    if not m:
        return (None, None)
    y = int(m.group(1))
    mm = re.search(r"[年-](\d{1,2})", s)
    month = int(mm.group(1)) if mm else None
    return (y, month)


def _is_stale(date_str, months_tolerance=9):
    """数据日期距今天数/月数是否超阈值。环境数据快照较旧时会标 stale。"""
    y, m = _parse_yearmonth(date_str)
    if y is None:
        return None
    try:
        if m:
            d = dt.date(y, m, 1)
        else:
            d = dt.date(y, 12, 1)
        now = dt.date.today()
        delta_months = (now.year - d.year) * 12 + (now.month - d.month)
        return delta_months > months_tolerance
    except Exception:
        return None


# ---------- 报告型接口统一解析（商品/日期/今值/预测值/前值） ----------
def fetch_report(fn_name, label):
    df = getattr(ak, fn_name)()
    tail = df.tail(3)
    val = None
    date = None
    used_prev = False
    # 1) 优先最近一个有效的"今值"
    for i in range(len(tail) - 1, -1, -1):
        v = _num(tail.iloc[i].get("今值"))
        if v is not None:
            val = v
            date = tail.iloc[i].get("日期")
            break
    # 2) 今值全空（未发布）则回落到"前值"
    if val is None:
        for i in range(len(tail) - 1, -1, -1):
            v = _num(tail.iloc[i].get("前值"))
            if v is not None:
                val = v
                date = tail.iloc[i].get("日期")
                used_prev = True
                break
    return {
        "date": str(date),
        label: val,
        "stale": _is_stale(date),
        "used_prev": used_prev,
    }


def fetch_pmi():
    out = fetch_report("macro_china_pmi_yearly", "manufacturing_pmi")
    out2 = fetch_report("macro_china_non_man_pmi", "non_manufacturing_pmi")
    out.update({k: v for k, v in out2.items() if k not in out})
    return out


def fetch_cpi():
    return fetch_report("macro_china_cpi_yearly", "cpi_yoy")


def fetch_ppi():
    return fetch_report("macro_china_ppi_yearly", "ppi_yoy")


def fetch_money():
    m2 = fetch_report("macro_china_m2_yearly", "m2_yoy")
    # M1 无 yearly 接口，用历史序列接口兜底（可能较旧，stale 自行标注）
    try:
        df = ak.macro_china_money_supply()
        r = df.iloc[-1]
        m1 = _num(r.get("货币(M1)-同比增长"))
        m1_date = r.get("月份")
        m2["m1_yoy"] = m1
        m2["m1_date"] = str(m1_date)
        m2["m1_stale"] = _is_stale(m1_date)
        # 剪刀差（仅当 M1 非严重滞后时计算；M1 老接口停在 2008，不可与近期 M2 比较）
        if m2.get("m2_yoy") is not None and m1 is not None and not m2.get("m1_stale"):
            m2["m1_minus_m2"] = round(m1 - m2["m2_yoy"], 2)
        else:
            m2["m1_minus_m2"] = None
            m2["m1_minus_m2_note"] = "M1 数据源严重滞后(2008)，暂不计算 M1-M2 剪刀差，建议用实时源"
    except Exception as e:
        m2["m1_error"] = "%s: %s" % (type(e).__name__, str(e)[:100])
    return m2


def fetch_gdp():
    return fetch_report("macro_china_gdp_yearly", "gdp_yoy")


def fetch_shrzgm():
    df = ak.macro_china_shrzgm()
    r = df.iloc[-1]
    return {
        "date": str(r.get("月份")),
        "social_financing_increment": _num(r.get("社会融资规模增量")),
        "rmb_loan": _num(r.get("其中-人民币贷款")),
        "stale": _is_stale(str(r.get("月份"))),
    }


def fetch_lpr():
    df = ak.macro_china_lpr()
    r = df.iloc[-1]
    return {
        "date": str(r.get("TRADE_DATE")),
        "lpr_1y": _num(r.get("LPR1Y")),
        "lpr_5y": _num(r.get("LPR5Y")),
        "stale": _is_stale(str(r.get("TRADE_DATE"))),
    }


def fetch_unemployment():
    df = ak.macro_china_urban_unemployment()
    out = {"date": None, "survey_unemployment": None, "local_hukou": None, "external_hukou": None}
    # 用"包含匹配"避免空格/口径差异导致匹配失败
    for _, row in df.iterrows():
        item = str(row.get("item", ""))
        val = _num(row.get("value"))
        d = str(row.get("date"))
        if "调查失业率" in item and "本地" not in item and "外来" not in item:
            out["survey_unemployment"] = val
            out["date"] = d
        elif "本地户籍" in item:
            out["local_hukou"] = val
        elif "外来户籍" in item:
            out["external_hukou"] = val
    out["stale"] = _is_stale(out["date"])
    return out


def fetch_industrial():
    df = ak.macro_china_gyzjz()
    r = df.iloc[-1]
    return {"date": str(r.get("月份")), "industrial_value_added_yoy": _num(r.get("同比增长")),
            "stale": _is_stale(str(r.get("月份")))}


def fetch_retail():
    # 优先报告型（若存在）；这里用历史序列兜底并标 stale
    try:
        df = ak.macro_china_consumer_goods_retail()
        r = df.iloc[-1]
        return {"date": str(r.get("月份")), "retail_sales_yoy": _num(r.get("同比增长")),
                "stale": _is_stale(str(r.get("月份"))), "note": "历史序列接口，可能滞后"}
    except Exception as e:
        return {"unavailable": "retail: %s" % str(e)[:120]}


def fetch_trade():
    ex = fetch_report("macro_china_exports_yoy", "export_yoy")
    im = fetch_report("macro_china_imports_yoy", "import_yoy")
    ex.update({k: v for k, v in im.items() if k not in ex})
    return ex


def fetch_usa_cpi():
    return fetch_report("macro_usa_cpi_monthly", "us_cpi_mom")


def fetch_usa_unemployment():
    return fetch_report("macro_usa_unemployment_rate", "us_unemployment")


def fetch_usa_ism():
    return fetch_report("macro_usa_ism_pmi", "us_ism_pmi")


def fetch_usa_pce():
    return fetch_report("macro_usa_core_pce_price", "us_core_pce_yoy")


def fetch_rates():
    df = ak.bond_zh_us_rate()
    r = df.iloc[-1]
    return {
        "date": str(r.get("日期")),
        "cn_10y": _num(r.get("中国国债收益率10年")),
        "us_10y": _num(r.get("美国国债收益率10年")),
        "cn_2y": _num(r.get("中国国债收益率2年")),
        "us_2y": _num(r.get("美国国债收益率2年")),
        "cn_10y_2y_spread": _num(r.get("中国国债收益率10年-2年")),
        "us_10y_2y_spread": _num(r.get("美国国债收益率10年-2年")),
        "stale": _is_stale(str(r.get("日期"))),
    }


FETCHERS = [
    ("china_pmi", fetch_pmi),
    ("china_cpi", fetch_cpi),
    ("china_ppi", fetch_ppi),
    ("china_money", fetch_money),
    ("china_gdp", fetch_gdp),
    ("china_social_financing", fetch_shrzgm),
    ("china_lpr", fetch_lpr),
    ("china_unemployment", fetch_unemployment),
    ("china_industrial", fetch_industrial),
    ("china_retail", fetch_retail),
    ("china_trade", fetch_trade),
    ("usa_cpi", fetch_usa_cpi),
    ("usa_unemployment", fetch_usa_unemployment),
    ("usa_ism_pmi", fetch_usa_ism),
    ("usa_core_pce", fetch_usa_pce),
    ("rates_cn_us", fetch_rates),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="输出 JSON 文件路径")
    ap.add_argument("--pretty", action="store_true", help="美化输出")
    args = ap.parse_args()

    snapshot = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare",
        "indicators": {},
    }
    ok, fail, stale_list = [], [], []
    for key, fn in FETCHERS:
        try:
            val = fn()
            snapshot["indicators"][key] = val
            ok.append(key)
            if isinstance(val, dict) and val.get("stale") is True:
                stale_list.append(key)
        except Exception as e:
            snapshot["indicators"][key] = {"unavailable": "%s: %s" % (type(e).__name__, str(e)[:120])}
            fail.append(key)

    snapshot["meta"] = {"ok": ok, "fail": fail, "stale": stale_list,
                        "note": "stale 指标数据可能滞后，建议用 mx-ds-mcp / tdx-connector 实时源交叉验证"}
    text = json.dumps(snapshot, ensure_ascii=False, indent=2 if args.pretty else None, default=_json_default)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("written -> %s  (ok=%d fail=%d stale=%d)" % (args.out, len(ok), len(fail), len(stale_list)))
    else:
        print(text)


if __name__ == "__main__":
    main()
