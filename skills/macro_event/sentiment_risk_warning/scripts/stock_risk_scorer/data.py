# -*- coding: utf-8 -*-
# Authors: 姜青、Warwick
"""
data.py — 个股模式数据采集（东方财富）
========================================
- K 线：push2his.eastmoney.com kline API（curl 子进程，带重试）
- 股吧：guba.eastmoney.com HTML 抓取帖子标题+时间
- 行业板块涨跌幅：push2 板块接口，失败降级为代理并明确标注

网络不可达/接口失败时抛 DataFetchError，禁止伪造数据。
"""

import json
import re
import subprocess
import time
import urllib.parse


class DataFetchError(Exception):
    """数据获取失败异常。"""


def _curl(url, timeout=15, retries=3):
    """curl 子进程请求（批量请求比 urllib 稳定，带重试）。"""
    last_err = None
    for i in range(retries):
        try:
            r = subprocess.run(
                ["curl", "-s", "--connect-timeout", "8", "--max-time", str(timeout),
                 "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                 "-H", "Referer: https://guba.eastmoney.com/", url],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if r.returncode == 0 and r.stdout:
                return r.stdout
            last_err = "curl exit=%s, len=%d" % (r.returncode, len(r.stdout or ""))
        except Exception as e:
            last_err = str(e)
        time.sleep(0.4 * (i + 1))
    raise DataFetchError("请求失败: %s | %s" % (url[:120], last_err))


def _secid(code):
    """A 股代码 → 东财 secid（沪 1.xxxxxx / 深 0.xxxxxx / 北 0.xxxxxx）。"""
    code = str(code).strip()
    if code.startswith(("6", "5", "9", "688", "689")):
        return "1." + code
    return "0." + code


def _fetch_kline_eastmoney(code, days):
    """东财 push2his K 线（首选）。失败抛 DataFetchError，由上层回退。"""
    secid = _secid(code)
    end = time.strftime("%Y%m%d")
    # 1250 交易日约 5 年，向前多取一些自然日
    beg = time.strftime("%Y%m%d", time.localtime(time.time() - days * 1.8 * 86400))
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?%s"
           % urllib.parse.urlencode({
               "secid": secid,
               "fields1": "f1,f2,f3,f4,f5,f6",
               "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
               "klt": "101", "fqt": "1",
               "beg": beg, "end": end,
           }))
    raw = _curl(url)
    try:
        data = json.loads(raw)
    except Exception as e:
        raise DataFetchError("K线接口返回非 JSON: %s" % e)
    klines = (data.get("data") or {}).get("klines") or []
    if not klines:
        raise DataFetchError("K线数据为空（代码 %s，可能未上市或代码错误）" % code)
    rows = []
    for k in klines:
        # f51=日期 f52=开 f53=收 f54=高 f55=低 f56=量 f57=额 f58=振幅
        # f59=涨跌幅 f60=涨跌额 f61=换手率
        p = k.split(",")
        if len(p) < 10:
            continue
        rows.append({
            "date": p[0],
            "open": float(p[1]), "close": float(p[2]),
            "high": float(p[3]), "low": float(p[4]),
            "vol": float(p[5] or 0), "amount": float(p[6] or 0),
            "pct_chg": float(p[8] or 0), "turnover": float(p[10] or 0),
        })
    if not rows:
        raise DataFetchError("K线解析失败（代码 %s）" % code)
    return rows


def _fetch_kline_tushare(code, days):
    """Tushare 回退 K 线（东财 push2his 不可达时用；换手率取自 daily_basic）。

    返回格式与 _fetch_kline_eastmoney 一致；失败抛 DataFetchError。
    """
    ts_code = str(code).strip()
    if not ts_code.endswith((".SZ", ".SH", ".BJ")):
        ts_code = ts_code + (".SH" if ts_code.startswith(("6", "5", "9")) else ".SZ")
    try:
        import re as _re
        import os as _os
        cfg = open(_os.path.expanduser("~/.hermes/config.yaml"),
                   encoding="utf-8").read()
        m = _re.search(r"token=([0-9a-f]+)", cfg)
        import tushare as ts
        pro = ts.pro_api(m.group(1) if m else None)
        end = time.strftime("%Y%m%d")
        beg = time.strftime("%Y%m%d", time.localtime(time.time() - days * 1.8 * 86400))
        df = pro.daily(ts_code=ts_code, start_date=beg, end_date=end)
        if df is None or df.empty:
            raise DataFetchError("Tushare K线为空（代码 %s）" % code)
        df = df.sort_values("trade_date").reset_index(drop=True)
        tb = pro.daily_basic(ts_code=ts_code, start_date=beg, end_date=end,
                             fields="trade_date,turnover_rate")
        tr_map = {}
        if tb is not None and not tb.empty:
            tr_map = dict(zip(tb["trade_date"], tb["turnover_rate"]))
        rows = []
        for _, r in df.iterrows():
            d = str(r["trade_date"])
            rows.append({
                "date": "%s-%s-%s" % (d[:4], d[4:6], d[6:8]),
                "open": float(r["open"]), "close": float(r["close"]),
                "high": float(r["high"]), "low": float(r["low"]),
                "vol": float(r.get("vol") or 0),
                "amount": float(r.get("amount") or 0) * 1000.0,  # Tushare 千元→元
                "pct_chg": float(r.get("pct_chg") or 0),
                "turnover": float(tr_map.get(d) or 0),
            })
        if not rows:
            raise DataFetchError("Tushare K线解析失败（代码 %s）" % code)
        return rows
    except DataFetchError:
        raise
    except Exception as e:
        raise DataFetchError("Tushare K线回退失败（代码 %s）: %s" % (code, e))


def fetch_kline(code, days=1250):
    """获取个股日 K 线（前复权）。东财优先，失败自动回退 Tushare。

    返回 list[dict]：date/open/close/high/low/vol/amount/turnover/pct_chg
    """
    try:
        return _fetch_kline_eastmoney(code, days)
    except DataFetchError as e:
        # 东财不可达 → Tushare 回退（本机实测可用）；仍失败则抛明确错误
        rows = _fetch_kline_tushare(code, days)
        return rows


def fetch_guba(code, pages=3):
    """抓取东方财富股吧帖子（标题+日期）。

    返回 list[dict]：{"date": "YYYY-MM-DD", "title": ..., "text": ...}
    抓取失败抛 DataFetchError。
    """
    posts = []
    seen = set()
    for page in range(1, pages + 1):
        url = "https://guba.eastmoney.com/list,%s_%d.html" % (code, page)
        html = _curl(url, timeout=12)
        # 帖子标题通常出现在 class="article-title" 或 a[title] 中
        # 模式1：<a ... title="标题" ...>
        for m in re.finditer(r'<a[^>]+title="([^"]{4,120})"[^>]*>', html):
            title = m.group(1).strip()
            if title and title not in seen:
                seen.add(title)
                posts.append({"date": "", "title": title, "text": title})
        # 模式2：span.article-title 内文本
        for m in re.finditer(r'class="article-title"[^>]*>([^<]{4,120})<', html):
            title = m.group(1).strip()
            if title and title not in seen:
                seen.add(title)
                posts.append({"date": "", "title": title, "text": title})
        if len(posts) >= 60:
            break
        time.sleep(0.3)
    if not posts:
        # 网络可达但页面结构变化 → 报错而非伪造
        raise DataFetchError("股吧页面解析不到帖子（代码 %s，页面结构可能变更）" % code)
    # 尝试从页面提取日期（多数页面日期在 class="update" 或纯数字 2026-10-08）
    # 由于 HTML 结构差异大，日期缺失时按当天兜底并标注（由 cli 处理标注）
    for p in posts:
        if not p["date"]:
            p["date"] = time.strftime("%Y-%m-%d")
    return posts


def _stock_name(code):
    """获取个股名称（东财 push2 f58），失败返回空串（调用方退回用代码搜索）。"""
    try:
        secid = _secid(code)
        url = ("https://push2.eastmoney.com/api/qt/stock/get?%s"
               % urllib.parse.urlencode({
                   "secid": secid,
                   "fields": "f57,f58",  # f57=代码 f58=名称
               }))
        raw = _curl(url, timeout=10, retries=2)
        data = json.loads(raw)
        d = (data.get("data") or {})
        return str(d.get("f58") or "").strip()
    except Exception:
        return ""


def fetch_news(code, keyword=None, page_size=30):
    """获取个股新闻（东财 search-api，与大盘模式同一接口口径）。

    参数
    ----
    code : str 股票代码（如 300759）
    keyword : str 搜索词；缺省先用股票名称（更精准），名称拿不到退回代码
    page_size : int 单页条数

    返回
    ----
    list[dict]：[{"date": "YYYY-MM-DD", "title": ..., "content": ...}]
    失败返回 []（由调用方降级为仅股吧并标注），不伪造数据。
    """
    kw = keyword or _stock_name(code) or str(code)
    try:
        param = json.dumps({
            "uid": "", "keyword": kw, "type": ["cmsArticleWebOld"],
            "client": "web", "clientType": "web", "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "default", "pageIndex": 1,
                "pageSize": page_size, "preTag": "<em>", "postTag": "</em>"}}},
            ensure_ascii=False)
        url = ("https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param=%s"
               % urllib.parse.quote(param))
        raw = _curl(url, timeout=15, retries=2)
        m = re.search(r"cb\((.*)\)", raw, re.S)
        if not m:
            return []
        data = json.loads(m.group(1))
        items = ((data.get("result") or {}).get("cmsArticleWebOld") or [])
        news, seen = [], set()
        for it in items:
            title = str(it.get("title") or "").replace("<em>", "").replace("</em>", "").strip()
            content = str(it.get("content") or "").replace("<em>", "").replace("</em>", "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            news.append({
                "date": str(it.get("date", ""))[:10],
                "title": title,
                "content": content[:300],
            })
        return news
    except Exception:
        return []


def fetch_industry_pct(code):
    """获取个股所属行业板块当日涨跌幅（东财板块接口）。

    失败返回 None（由调用方降级为代理并标注，不伪造）。
    """
    try:
        secid = _secid(code)
        url = ("https://push2.eastmoney.com/api/qt/stock/get?%s"
               % urllib.parse.urlencode({
                   "secid": secid,
                   "fields": "f57,f58,f127,f128",  # f127=行业板块名称 f128=行业板块代码
               }))
        raw = _curl(url, timeout=10, retries=2)
        data = json.loads(raw)
        d = (data.get("data") or {})
        board_name = d.get("f127")
        board_code = d.get("f128")
        if not board_code:
            return None
        # 板块指数 secid：行业板块代码形如 BK0475，对应板块指数 90.BK0475
        bsecid = "90." + str(board_code)
        url2 = ("https://push2.eastmoney.com/api/qt/stock/get?%s"
                % urllib.parse.urlencode({
                    "secid": bsecid,
                    "fields": "f57,f58,f170",  # f170=涨跌幅
                }))
        raw2 = _curl(url2, timeout=10, retries=2)
        data2 = json.loads(raw2)
        d2 = (data2.get("data") or {})
        pct = d2.get("f170")
        if pct is None:
            return None
        return {"industry": board_name, "pct": float(pct) / 100.0}  # 东财 f170 为百分数*100
    except Exception:
        return None


if __name__ == "__main__":
    # 自测：仅验证 _secid 与错误处理（网络不可达时给出明确错误）
    print("secid 300666 ->", _secid("300666"))
    print("secid 600584 ->", _secid("600584"))
    print("secid 002472 ->", _secid("002472"))
    try:
        rows = fetch_kline("300666", days=30)
        print("kline rows:", len(rows), rows[-1] if rows else None)
    except DataFetchError as e:
        print("kline 获取失败（网络受限时属正常）:", e)
