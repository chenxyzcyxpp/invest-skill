# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
market_collect.py — 大盘舆情风险预警 · 真实数据采集器（三指数版）
=============================================================
拉取大盘模式所需全部真实数据并落盘，供 market_risk.py 使用：

  指数维度（每只指数独立拉取 60 个月 K 线 + 当日快照）：
    - 上证综指 000001.SH（兼容旧文件名 sh_index_kline.json / snapshot.json）
    - 深证成指 399001.SZ
    - 创业板指 399006.SZ
  全市场维度（三指数共用，天然同一口径）：
    - 沪深300 / 科创50 当日涨跌幅（Tushare index_daily）
    - 全市场成交额（Tushare daily_info，单位亿元，取 SH_MARKET+SZ_MARKET）
    - 涨跌家数分布（东财 push2ex getTopicZDFenBu，本机实测可用）
    - 主力资金净流入（Tushare moneyflow_mkt_dc，net_amount 单位元→亿元）
    - 新闻（东财 search-api-web，近3周；Tushare pro.news 无权限）
    - 汇率 USDCNY（Tushare fx_daily 无权限 → 7.15 中性兜底，变化率≈0）

用法：
  python3 market_collect.py --out /tmp/mr_live
然后跑单指数预测：
  PYTHONIOENCODING=utf-8 python3 market_risk.py \
      --kline <out>/kline_000001.SH.json --news <out>/news.json \
      --snapshot <out>/snapshot_000001.SH.json --out <out> --name 上证综指
或跑三指数汇总对比：
  PYTHONIOENCODING=utf-8 python3 market_risk.py --compare <out> --out <out>

Tushare token 自动从 ~/.hermes/config.yaml 的 tushareMcp.url 提取；
若提取失败可手工 python3 -c "import tushare; tushare.set_token('<token>')"。
"""

import argparse
import json
import os
import re
import subprocess
import urllib.parse

import tushare as ts

# 指数清单：code / name / 落盘文件名
INDEXES = [
    {"code": "000001.SH", "name": "上证综指",
     "kline_file": "kline_000001.SH.json", "snapshot_file": "snapshot_000001.SH.json"},
    {"code": "399001.SZ", "name": "深证成指",
     "kline_file": "kline_399001.SZ.json", "snapshot_file": "snapshot_399001.SZ.json"},
    {"code": "399006.SZ", "name": "创业板指",
     "kline_file": "kline_399006.SZ.json", "snapshot_file": "snapshot_399006.SZ.json"},
]


def get_tushare_token():
    """从 ~/.hermes/config.yaml 的 tushareMcp.url 提取 token。"""
    import yaml
    cfg_path = os.path.expanduser("~/.hermes/config.yaml")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        url = (cfg.get("mcp", {}) or {}).get("tushareMcp", {}).get("url", "")
        m = re.search(r"[?&]token=([0-9a-f]+)", url)
        if m:
            return m.group(1)
    return None


def curl_json(url, timeout=15):
    r = subprocess.run(
        ["curl", "-s", "--connect-timeout", "8", "--max-time", str(timeout),
         "-H", "User-Agent: Mozilla/5.0", url],
        capture_output=True, text=True, timeout=timeout + 5)
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def fetch_index_kline(pro, code, start_ymd, end_ymd):
    """拉单只指数 60 个月 K 线，返回 list[dict]。"""
    df = pro.index_daily(ts_code=code, start_date=start_ymd, end_date=end_ymd)
    df = df.sort_values("trade_date").reset_index(drop=True)
    rows = [{
        "date": r["trade_date"], "open": float(r["open"]),
        "high": float(r["high"]), "low": float(r["low"]),
        "close": float(r["close"]), "volume": float(r["vol"]),
        "amount": float(r["amount"]),
    } for _, r in df.iterrows()]
    return rows, (float(df.iloc[-1]["pct_chg"]) if len(df) else None)


def collect(out_dir, days=1250, start_ymd="20210901", end_ymd=None):
    import datetime
    if end_ymd is None:
        end_ymd = datetime.date.today().strftime("%Y%m%d")
    os.makedirs(out_dir, exist_ok=True)

    token = get_tushare_token()
    if token:
        ts.set_token(token)
    else:
        print("⚠️ 未从 config.yaml 提取到 Tushare token，接口将失败")
    pro = ts.pro_api()

    # ---------- 1. 三指数 K 线 + 当日快照 ----------
    snapshots = {}
    last_date = None
    for idx in INDEXES:
        code = idx["code"]
        rows, last_pct = fetch_index_kline(pro, code, start_ymd, end_ymd)
        kpath = os.path.join(out_dir, idx["kline_file"])
        with open(kpath, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        last = rows[-1]
        if last_date is None:
            last_date = last["date"]
        # 上证额外写兼容旧名文件
        if code == "000001.SH":
            with open(os.path.join(out_dir, "sh_index_kline.json"), "w",
                      encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
        print("%s(%s) K线行数: %d | 最新: %s 收盘 %.2f" % (
            idx["name"], code, len(rows), last["date"], last["close"]))
        snapshots[code] = {
            "date": last["date"], "code": code, "name": idx["name"],
            "close": last["close"], "pct": last_pct,
            # 兼容旧字段名（render 会优先读 close/pct）
            "sh_close": last["close"], "sh_pct": last_pct,
        }

    # ---------- 2. 涨跌分布（东财 push2ex，本机可用） ----------
    up_total = down_total = 0
    zd = curl_json("https://push2ex.eastmoney.com/getTopicZDFenBu"
                   "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt")
    if zd and zd.get("data", {}).get("fenbu"):
        for item in zd["data"]["fenbu"]:
            for k, v in item.items():
                if int(k) > 0:
                    up_total += v
                elif int(k) < 0:
                    down_total += v
    print("涨跌分布: 上涨", up_total, "下跌", down_total)

    # ---------- 3. 沪深300 / 科创50 当日涨跌幅 ----------
    hs300_pct = kch50_pct = None
    try:
        hs300 = pro.index_daily(ts_code="399300.SZ", start_date="20260101",
                                end_date=end_ymd)
        kch50 = pro.index_daily(ts_code="000688.SH", start_date="20260101",
                                end_date=end_ymd)
        hs300_pct = float(hs300.iloc[0]["pct_chg"]) if len(hs300) else None
        kch50_pct = float(kch50.iloc[0]["pct_chg"]) if len(kch50) else None
    except Exception as e:
        print("沪深300/科创50 失败:", e)

    # ---------- 4. 全市场成交额（亿元；daily_info amount 已是亿元） ----------
    amt_total_yi = None
    try:
        di = pro.daily_info(trade_date=last_date)
        a = di[di["ts_code"].isin(["SH_MARKET", "SZ_MARKET"])]
        amt_total_yi = float(a["amount"].sum())
    except Exception as e:
        print("daily_info 失败:", e)

    # ---------- 5. 主力资金（亿元；net_amount 单位元） ----------
    main_net = None
    try:
        mf = pro.moneyflow_mkt_dc(trade_date=last_date)
        if len(mf):
            main_net = round(float(mf.iloc[0]["net_amount"]) / 1e8, 1)
    except Exception as e:
        print("资金接口失败:", e)

    # ---------- 6. 汇率（Tushare fx_daily 无权限 → 7.15 中性兜底） ----------
    usdcny = 7.15
    try:
        fx = pro.fx_daily(ts_code="USDCNY.FXCM", start_date="20260101",
                          end_date=end_ymd)
        if len(fx):
            usdcny = float(fx.iloc[0]["bid_close"])
    except Exception:
        pass

    # ---------- 7. 新闻（东财 search-api，Tushare pro.news 无权限） ----------
    news = []
    try:
        param = json.dumps({
            "uid": "", "keyword": "A股 大盘", "type": ["cmsArticleWebOld"],
            "client": "web", "clientType": "web", "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "default", "pageIndex": 1,
                "pageSize": 20, "preTag": "<em>", "postTag": "</em>"}}},
            ensure_ascii=False)
        url = ("https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param=%s"
               % urllib.parse.quote(param))
        raw = subprocess.run(
            ["curl", "-s", "--connect-timeout", "8", "--max-time", "15",
             "-H", "User-Agent: Mozilla/5.0", url],
            capture_output=True, text=True, timeout=20)
        m = re.search(r"cb\((.*)\)", raw.stdout, re.S)
        if m:
            data = json.loads(m.group(1))
            for it in (data.get("result", {}) or {}).get("cmsArticleWebOld", []) or []:
                news.append({"date": str(it.get("date", ""))[:10],
                             "title": it.get("title", ""),
                             "content": it.get("content", "")[:200]})
    except Exception as e:
        print("东财新闻失败:", e)
    with open(os.path.join(out_dir, "news.json"), "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False)
    print("新闻条数:", len(news))

    # ---------- 8. 组装三份 snapshot（全市场字段共用） ----------
    for code, snap in snapshots.items():
        snap.update({
            "hs300_pct": hs300_pct, "kch50_pct": kch50_pct,
            "amount_yi": round(amt_total_yi, 0) if amt_total_yi else None,
            "up_total": up_total, "down_total": down_total,
            "usdcny": usdcny, "main_net_sh": main_net,
            "main_net_sz": None, "main_net_cyb": None,
            "strong": "", "weak": "", "view": "",
        })
        idx = next(i for i in INDEXES if i["code"] == code)
        spath = os.path.join(out_dir, idx["snapshot_file"])
        with open(spath, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        # 上证额外写兼容旧名 snapshot.json
        if code == "000001.SH":
            with open(os.path.join(out_dir, "snapshot.json"), "w",
                      encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        print("%s snapshot 已写盘: close=%.2f pct=%s" % (
            idx["name"], snap["close"], snap["pct"]))
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="大盘舆情风险预警 · 真实数据采集（三指数）")
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--days", type=int, default=1250,
                    help="K线取数天数（默认1250交易日≈60个月，自动换算起始日期）")
    args = ap.parse_args()
    import datetime as _dt
    start = (_dt.date.today() - _dt.timedelta(days=int(args.days * 1.8))).strftime("%Y%m%d")
    collect(args.out, start_ymd=start)
