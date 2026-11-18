#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Authors: Warwick
"""
market_review.py — 股市每日收评 · 可运行主脚本（script_based 形态，开源版）
====================================================================
自动生成 A 股 / 港股每个交易日的收盘点评报告：大盘指数、涨跌统计、板块表现、
个股异动、资金流向、龙虎榜、重要资讯、技术面、盘面综述，覆盖全部市场或单市场，
所有数据带数据来源标记与降级标记。

用法：
  # 演示模式（沙箱可直接跑，无需 token / 外部库）
  python3 market_review.py --demo --output-format markdown
  python3 market_review.py --demo --output-format json

  # 真实模式（需本机可访问 Tushare / Akshare / 公开网页源；未接入时如实报错，不伪造）
  python3 market_review.py --trade-date 2026-10-22 --market A股 --output-format markdown
  python3 market_review.py --trade-date 2026-10-22 --market 全部 --top-n 10 --out files/report

  # 仅落盘 files/report/{trade_date}_股市每日收评.md / .html
  python3 market_review.py --demo --out files/report

  # 重要资讯：由 agent 经 WebSearch 检索后整理成 JSON 注入（离线源无新闻接口）
  python3 market_review.py --trade-date 2026-10-27 --news-file news.json --out files/report

数据源（四级可降级，详见 references/data-sources.md）：
  Tushare（优先，需 token）> Akshare（次级，开源主源）>
  腾讯财经 / 东方财富 Push API 网页兜底 > 演示数据（--demo）
  * 行情四类数据源（指数 / 涨跌统计 / 板块 / 个股 / 资金流）全部失败 → 抛 MKT_REVIEW_001 退出，不输出伪造报告。
  * 龙虎榜 / 公开资讯在开源体系中覆盖较弱，缺口按「数据待补充」标注，不编造。

约束（与框架铁律一致）：
  * 禁止编造数据：任何数值必须来自脚本计算或真实接口；数据源失败报错退出或标注缺失。
  * 信号必带 evidence 证据链；演示数据仅验管线（报告标 degraded=demo）。
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ===========================================================================
# 一、配置（阈值集中，便于运营调参）
# ===========================================================================
SKILL_NAME = "market_daily_review"
SKILL_VERSION = "1.0.0"

# 开源可降级网关数据源优先级（全局约定的降级顺序）
GATEWAY_PRIORITY: List[str] = ["tushare", "akshare", "web"]

ERROR_CODES = {
    "MKT_REVIEW_001": "行情核心数据源（指数/涨跌统计/板块/个股/资金流）全部失败",
    "MKT_REVIEW_002": "龙虎榜 / 公开资讯源全部失败但行情可用",
}

DISCLAIMER = (
    "本服务内容来源于公开及第三方数据源，仅自动化加工展示，"
    "不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，"
    "内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。"
    "市场有风险，投资需谨慎。"
)

# A 股核心指数（名称，用于 sina/em 接口筛选）
A_INDEX_NAMES = ["上证指数", "深证成指", "创业板指", "沪深300", "科创50", "上证50"]
# 港股核心指数
HK_INDEX_NAMES = ["恒生指数", "恒生科技"]
# 东方财富 push2 指数 secid 映射（市场前缀.代码）
EASTMONEY_INDEX_SECID = {
    "上证指数": "1.000001", "深证成指": "0.399001", "创业板指": "0.399006",
    "沪深300": "1.000300", "科创50": "1.000688", "上证50": "1.000016",
    "恒生指数": "100.HSI", "恒生科技": "105.HSTECH",
}


@dataclass
class ReviewThresholds:
    """初版阈值，集中配置可运营调参。"""
    top_n: int = 10                       # 板块 / 个股榜单默认前 N
    breadth_limit_up_note: bool = True    # 涨跌停家数提示
    extreme_move_abs: float = 9.5         # 个股单日涨跌幅(绝对值) > 该值 => 极端波动(涨停/跌停附近)
    rsi_overbought: float = 70.0          # 技术面 RSI 超买
    rsi_oversold: float = 30.0            # 技术面 RSI 超卖
    ma_golden_cross_days: int = 5         # 短期均线上穿长期均线提示
    leading_stocks: int = 3               # 领涨 / 领跌个股展示数量


DEFAULT_THRESHOLDS = ReviewThresholds()


# ===========================================================================
# 二、演示数据（无需任何 token / 外部库即可跑通完整 SOP）
# ===========================================================================
TRADE_DATE = "2026-10-22"

# 大盘指数（A 股 + 港股）
DEMO_INDICES = {
    "A股": [
        {"name": "上证指数", "close": 3325.40, "pct": 0.62, "amount_yi": 4210.5},
        {"name": "深证成指", "close": 10860.12, "pct": 0.85, "amount_yi": 5380.1},
        {"name": "创业板指", "close": 2268.55, "pct": 1.12, "amount_yi": 2410.3},
        {"name": "沪深300", "close": 3980.20, "pct": 0.55, "amount_yi": 3120.8},
        {"name": "科创50", "close": 985.30, "pct": 1.45, "amount_yi": 720.6},
    ],
    "港股": [
        {"name": "恒生指数", "close": 21580.30, "pct": -0.35, "amount_yi": 980.0},
        {"name": "恒生科技", "close": 4820.15, "pct": -0.78, "amount_yi": 410.0},
    ],
}

# 涨跌统计
DEMO_BREADTH = {"up": 3120, "down": 1680, "flat": 210, "limit_up": 86, "limit_down": 12, "total": 5010}

# 板块表现（同花顺口径，约 90 个；演示取部分）
DEMO_SECTORS = [
    {"name": "半导体", "pct1d": 3.85, "amount_yi": 1283.4, "net_yi": 45.2},
    {"name": "计算机", "pct1d": 2.98, "amount_yi": 980.1, "net_yi": 38.5},
    {"name": "通信", "pct1d": 1.85, "amount_yi": 410.3, "net_yi": 12.0},
    {"name": "国防军工", "pct1d": 1.45, "amount_yi": 360.2, "net_yi": 9.8},
    {"name": "银行", "pct1d": 0.30, "amount_yi": 300.1, "net_yi": 5.0},
    {"name": "医药生物", "pct1d": -0.75, "amount_yi": 610.5, "net_yi": -9.4},
    {"name": "食品饮料", "pct1d": -1.10, "amount_yi": 540.2, "net_yi": -18.6},
    {"name": "有色金属", "pct1d": -1.55, "amount_yi": 520.0, "net_yi": -11.5},
    {"name": "汽车", "pct1d": -2.10, "amount_yi": 690.0, "net_yi": -34.0},
    {"name": "房地产", "pct1d": -2.65, "amount_yi": 280.4, "net_yi": -15.2},
]

# 个股异动（涨 / 跌 / 换手 TOP）
DEMO_MOVERS = {
    "up": [
        {"code": "688981", "name": "中芯国际", "pct": 12.3, "turnover": 8.5},
        {"code": "300750", "name": "宁德时代", "pct": 9.8, "turnover": 5.2},
        {"code": "002371", "name": "北方华创", "pct": 9.1, "turnover": 6.1},
        {"code": "688256", "name": "寒武纪", "pct": 8.7, "turnover": 7.9},
        {"code": "603501", "name": "韦尔股份", "pct": 7.9, "turnover": 4.3},
    ],
    "down": [
        {"code": "601127", "name": "赛力斯", "pct": -9.6, "turnover": 6.8},
        {"code": "600519", "name": "贵州茅台", "pct": -3.2, "turnover": 0.9},
        {"code": "002594", "name": "比亚迪", "pct": -4.1, "turnover": 3.2},
        {"code": "000858", "name": "五粮液", "pct": -3.8, "turnover": 1.5},
        {"code": "601318", "name": "中国平安", "pct": -2.4, "turnover": 1.1},
    ],
    "turnover": [
        {"code": "688981", "name": "中芯国际", "pct": 12.3, "turnover": 8.5},
        {"code": "688256", "name": "寒武纪", "pct": 8.7, "turnover": 7.9},
        {"code": "601127", "name": "赛力斯", "pct": -9.6, "turnover": 6.8},
        {"code": "002371", "name": "北方华创", "pct": 9.1, "turnover": 6.1},
        {"code": "300750", "name": "宁德时代", "pct": 9.8, "turnover": 5.2},
    ],
}

# 资金流向（市场 + 行业）
DEMO_FUND_FLOW = {
    "market_main_net_yi": 128.5,          # 全市场主力净流入
    "north_south": None,                  # 沪深港通（开源覆盖弱，演示标缺）
    "industry_top_in": [("半导体", 45.2), ("计算机", 38.5), ("通信", 12.0)],
    "industry_top_out": [("汽车", -34.0), ("食品饮料", -18.6), ("房地产", -15.2)],
}

# 龙虎榜（演示）
DEMO_DRAGON = [
    {"code": "688981", "name": "中芯国际", "net_yi": 6.8, "reason": "日涨幅偏离值达7%"},
    {"code": "300750", "name": "宁德时代", "net_yi": 4.2, "reason": "日涨幅偏离值达7%"},
    {"code": "601127", "name": "赛力斯", "net_yi": -3.5, "reason": "日跌幅偏离值达7%"},
]

# 重要资讯（演示；开源环境通常经 WebSearch 补充）
DEMO_NEWS = [
    {"title": "半导体国产化替代政策再加码，设备招标提速", "source": "公开资讯", "time": "2026-10-22 14:20"},
    {"title": "国产算力需求旺盛，服务器订单能见度延长", "source": "公开资讯", "time": "2026-10-22 10:30"},
    {"title": "网传海外光伏组件关税上调，尚未官方确认", "source": "公开资讯", "time": "2026-10-22 13:50", "rumor": True},
]

# 技术面（各主要指数）
DEMO_TECH = {
    "上证指数": {"rsi14": 58.3, "ma5": 3301.2, "ma20": 3275.8, "ma60": 3210.5, "close": 3325.40},
    "深证成指": {"rsi14": 55.1, "ma5": 10860.1, "ma20": 10720.4, "ma60": 10500.2, "close": 10860.12},
    "创业板指": {"rsi14": 61.2, "ma5": 2268.5, "ma20": 2210.3, "ma60": 2150.8, "close": 2268.55},
    "沪深300": {"rsi14": 56.7, "ma5": 3980.2, "ma20": 3930.5, "ma60": 3880.1, "close": 3980.20},
    "科创50": {"rsi14": 64.5, "ma5": 985.3, "ma20": 950.2, "ma60": 910.6, "close": 985.30},
}


def build_raw_data(market: str = "全部") -> Dict[str, Any]:
    """返回与 RawData 字段对齐的演示数据。"""
    indices = []
    if market in ("A股", "全部"):
        for x in DEMO_INDICES["A股"]:
            d = dict(x); d["market"] = "A股"; indices.append(d)
    if market in ("港股", "全部"):
        for x in DEMO_INDICES["港股"]:
            d = dict(x); d["market"] = "港股"; indices.append(d)
    return {
        "indices": indices,
        "breadth": dict(DEMO_BREADTH),
        "sectors": [dict(s) for s in DEMO_SECTORS],
        "movers": {k: [dict(x) for x in v] for k, v in DEMO_MOVERS.items()},
        "fund_flow": dict(DEMO_FUND_FLOW),
        "dragon": [dict(d) for d in DEMO_DRAGON],
        "news": [dict(n) for n in DEMO_NEWS],
        "tech": dict(DEMO_TECH),
        "source_meta": "demo",
        "degrade_trace": [],
        "missing_items": [],
    }


# ===========================================================================
# 三、数据模型（统一输入输出契约）
# ===========================================================================
@dataclass
class SkillInput:
    trade_date: str = ""
    market: str = "全部"                 # A股 | 港股 | 全部
    days: int = 1
    top_n: int = 10
    include_news: bool = True
    news_file: str = ""                  # 可选：由 WebSearch 整理的新闻 JSON（[{title,source,time,rumor}]）
    output_format: str = "both"          # json | markdown | both


@dataclass
class IndexRow:
    market: str
    name: str
    close: float
    pct: float
    amount_yi: float = 0.0


@dataclass
class SectorRow:
    name: str
    pct1d: float
    amount_yi: float
    net_yi: float


@dataclass
class MoverRow:
    code: str
    name: str
    pct: float
    turnover: float


@dataclass
class NewsItem:
    title: str
    source: str
    time: str
    rumor: bool = False


@dataclass
class SkillOutput:
    skill: str
    version: str
    run_at: str
    trade_date: str
    market: str
    data_source: str
    degraded: bool
    degrade_trace: List[str] = field(default_factory=list)
    indices: List[IndexRow] = field(default_factory=list)
    breadth: Dict[str, Any] = field(default_factory=dict)
    sectors: List[SectorRow] = field(default_factory=list)
    movers: Dict[str, List[MoverRow]] = field(default_factory=dict)
    fund_flow: Dict[str, Any] = field(default_factory=dict)
    dragon: List[Dict[str, Any]] = field(default_factory=list)
    news: List[NewsItem] = field(default_factory=list)
    tech: Dict[str, Any] = field(default_factory=dict)
    market_brief: str = ""
    missing_items: List[str] = field(default_factory=list)
    disclaimer: str = ""
    error_code: Optional[str] = None
    error_msg: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===========================================================================
# 四、可降级多源数据网关（开源：Tushare > Akshare > 网页兜底）
# ===========================================================================
def _f(x) -> float:
    try:
        v = float(x)
        return v if v == v else 0.0  # NaN -> 0
    except Exception:
        return 0.0


def _calc_tech(closes: List[float]) -> Dict[str, Any]:
    """由收盘序列计算 RSI(14) / MA5 / MA20 / MA60（需 >=15 根）。"""
    def rsi(vals, n=14):
        gains = [max(0, vals[i] - vals[i-1]) for i in range(1, len(vals))]
        losses = [max(0, vals[i-1] - vals[i]) for i in range(1, len(vals))]
        if len(gains) < n:
            return None
        ag = sum(gains[-n:]) / n
        al = sum(losses[-n:]) / n
        if al == 0:
            return 100.0
        rs = ag / al
        return round(100 - 100 / (1 + rs), 2)
    return {"rsi14": rsi(closes) or 50.0,
            "ma5": round(sum(closes[-5:]) / 5, 2),
            "ma20": round(sum(closes[-20:]) / 20, 2),
            "ma60": round(sum(closes[-60:]) / 60, 2) if len(closes) >= 60 else None,
            "close": closes[-1]}


def _tech_signal(t: Dict[str, Any]) -> str:
    """由单个指数的技术指标给出一句中文研判。"""
    if not t or t.get("close") is None:
        return ""
    close = t["close"]; ma5 = t.get("ma5"); ma20 = t.get("ma20"); ma60 = t.get("ma60")
    rsi_v = t.get("rsi14")
    parts = []
    seq = [x for x in (ma5, ma20, ma60) if x is not None]
    if len(seq) >= 2 and ma20 is not None:
        parts.append("站上MA20、中期偏强" if close > ma20 else "跌破MA20、中期偏弱")
        if len(seq) == 3:
            if seq[0] > seq[1] > seq[2]:
                parts.append("均线多头排列")
            elif seq[0] < seq[1] < seq[2]:
                parts.append("均线空头排列")
    if rsi_v is not None:
        if rsi_v >= DEFAULT_THRESHOLDS.rsi_overbought:
            parts.append("RSI超买")
        elif rsi_v <= DEFAULT_THRESHOLDS.rsi_oversold:
            parts.append("RSI超卖")
        else:
            parts.append("RSI中性")
    return "；".join(parts)


def _ymd(s: str) -> str:
    """统一日期为 YYYYMMDD（龙虎榜等接口需要，无连字符）。"""
    if not s:
        return ""
    return s.replace("-", "").replace("/", "")


def _robust_call(fn, desc: str = "", tries: int = 3, sleep: float = 1.0):
    """带重试的网络调用（部分源偶发抖动）。"""
    last = None
    for i in range(tries):
        try:
            df = fn()
            if df is not None and (not hasattr(df, "__len__") or len(df) > 0):
                return df
        except Exception as e:
            last = e
        if i < tries - 1:
            time.sleep(sleep)
    raise RuntimeError(f"{desc or getattr(fn, '__name__', '?')} 失败（{last}）")


def _latest_trade_date() -> str:
    """推断最近交易日（优先用上证指数最后一根 K 线，回退到上一个工作日）。"""
    try:
        import akshare as ak  # type: ignore
        h = ak.index_zh_a_hist(symbol="000001", period="daily",
                               start_date="20260101", end_date="20261231")
        if h is not None and len(h):
            d = str(h.iloc[-1]["日期"])
            if "-" in d:
                return d[:10]
            return datetime.datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        pass
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d.isoformat()


class GatewayError(Exception):
    def __init__(self, code: str, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class DataSource:
    name = "base"

    def get_indices(self, market): raise NotImplementedError
    def get_breadth(self, trade_date): raise NotImplementedError
    def get_sectors(self, trade_date): raise NotImplementedError
    def get_movers(self, trade_date): raise NotImplementedError
    def get_fund_flow(self, trade_date): raise NotImplementedError
    def get_dragon(self, trade_date): raise NotImplementedError
    def get_news(self, trade_date): raise NotImplementedError
    def get_tech(self, trade_date): raise NotImplementedError


class DemoSource(DataSource):
    name = "demo"

    def __init__(self, market="全部"):
        self.market = market

    def get_indices(self, market): return build_raw_data(self.market)["indices"]
    def get_breadth(self, trade_date): return build_raw_data(self.market)["breadth"]
    def get_sectors(self, trade_date): return build_raw_data(self.market)["sectors"]
    def get_movers(self, trade_date): return build_raw_data(self.market)["movers"]
    def get_fund_flow(self, trade_date): return build_raw_data(self.market)["fund_flow"]
    def get_dragon(self, trade_date): return build_raw_data(self.market)["dragon"]
    def get_news(self, trade_date): return build_raw_data(self.market)["news"]
    def get_tech(self, trade_date): return build_raw_data(self.market)["tech"]


class TushareSource(DataSource):
    """tushare 适配器（优先源，需配置 TUSHARE_TOKEN）。

    免费 / 基础权限可覆盖：
      - 指数日线 ``pro.index_daily``（A 股）、``pro.index_global``（港股）
      - 龙虎榜 ``pro.top_list``
      - 沪深港通 ``pro.moneyflow_hsgt``、大盘资金流 ``pro.moneyflow``（逐只聚合主力净流入）
      - 技术面：上证指数 ``pro.index_daily`` 历史计算 RSI / MA
    免费版不覆盖（由网关降级到 Akshare）：
      - 涨跌统计（无免费接口）、个股异动（无免费全市场快照）、
      - 板块成交额 / 主力净流入（申万日线 ``sw_daily`` 不含这些字段）
    注：tushare 收盘后数据常延迟，本适配器对交易日做回溯，取最近有数据的交易日。
    """
    name = "tushare"

    def __init__(self):
        try:
            import tushare as ts  # type: ignore
        except Exception as e:
            raise RuntimeError(f"tushare 未安装: {e}")
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("未配置 TUSHARE_TOKEN")
        ts.set_token(token)
        self.pro = ts.pro_api(token)
        self.A_IDX = {"上证指数": "000001.SH", "深证成指": "399001.SZ",
                      "创业板指": "399006.SZ", "沪深300": "000300.SH",
                      "上证50": "000016.SH", "科创50": "000688.SH"}
        self.HK_IDX = {"恒生指数": "HSI", "恒生科技": "HSTECH"}
        # 申万一级行业（2021 版）ts_code 白名单：sw_daily 默认返回全层级（含 composites 与二/三级），
        # 此处仅保留 31 个一级行业，保证板块点评口径清晰。
        self.SW_L1_CODES = {
            "801010.SI", "801030.SI", "801040.SI", "801050.SI", "801080.SI", "801110.SI",
            "801120.SI", "801130.SI", "801140.SI", "801150.SI", "801160.SI", "801170.SI",
            "801180.SI", "801200.SI", "801210.SI", "801230.SI", "801710.SI", "801720.SI",
            "801730.SI", "801740.SI", "801750.SI", "801760.SI", "801770.SI", "801780.SI",
            "801790.SI", "801880.SI", "801890.SI", "801950.SI", "801960.SI", "801970.SI",
            "801980.SI",
        }
        self._td_cache: Optional[str] = None
        self._td_checked: bool = False

    def _resolve_td(self, trade_date: str):
        """确认 tushare 在指定日（今天或给定交易日）是否有数据；无数据返回 None（触发降级）。

        不回溯：避免跨交易日错位（如今天收盘后 tushare 尚未入库，若回退到上一交易日
        会导致报告标题日期与数据日期不一致）。缺失时由网关降级到 Akshare（取当日实时）。
        """
        if self._td_checked:
            return self._td_cache
        if trade_date and trade_date not in ("latest",):
            base = _ymd(trade_date)
        else:
            base = datetime.date.today().strftime("%Y%m%d")
        try:
            df = self.pro.index_daily(ts_code="000001.SH", trade_date=base)
            if df is not None and len(df):
                self._td_cache, self._td_checked = base, True
                return base
        except Exception:
            pass
        self._td_cache, self._td_checked = None, True
        return None

    def get_indices(self, market, trade_date: str = "latest"):
        td = self._resolve_td(trade_date)
        if td is None:
            raise RuntimeError("tushare 当日数据尚未入库（收盘后延迟），降级 Akshare")
        out: List[Dict[str, Any]] = []
        if market in ("A股", "全部"):
            for name, code in self.A_IDX.items():
                try:
                    df = self.pro.index_daily(ts_code=code, trade_date=td)
                    if df is None or not len(df):
                        continue
                    r = df.iloc[0]
                    amt = r.get("amount")
                    out.append({"market": "A股", "name": name,
                                "close": _f(r["close"]), "pct": _f(r["pct_chg"]),
                                "amount_yi": _f(amt) / 1e5 if amt is not None else 0.0})
                except Exception:
                    continue
        if market in ("港股", "全部"):
            for name, code in self.HK_IDX.items():
                try:
                    df = self.pro.index_global(ts_code=code, trade_date=td)
                    if df is None or not len(df):
                        continue
                    r = df.iloc[0]
                    out.append({"market": "港股", "name": name,
                                "close": _f(r["close"]), "pct": _f(r["pct_chg"]),
                                "amount_yi": 0.0})
                except Exception:
                    continue
        if not out:
            raise RuntimeError("tushare 指数不可得")
        return out

    def get_breadth(self, trade_date):
        # 免费版无涨跌统计接口，降级到 Akshare
        raise RuntimeError("tushare 免费版无涨跌统计接口，降级 Akshare")

    def get_sectors(self, trade_date):
        td = self._resolve_td(trade_date)
        if td is None:
            raise RuntimeError("tushare 当日数据尚未入库（收盘后延迟），降级 Akshare")
        # 申万一级行业日线（sw_daily）：含涨跌幅与成交额（amount，千元→亿），但不含主力净流入
        df = self.pro.sw_daily(trade_date=td)
        if df is None or not len(df):
            raise RuntimeError("tushare 申万行业不可得")
        out = []
        for _, r in df.iterrows():
            if str(r.get("ts_code", "")) not in self.SW_L1_CODES:
                continue  # 仅保留申万一级行业，过滤 composites 与二/三级
            amt = r.get("amount")
            amount_yi = round(float(amt) / 1e5, 2) if amt is not None else None  # 千元→亿
            out.append({"name": str(r.get("name", "")), "pct1d": _f(r.get("pct_change")),
                        "amount_yi": amount_yi, "net_yi": None})  # sw_daily 无主力净流入字段
        if not out:
            raise RuntimeError("tushare 申万行业空")
        return out

    def get_movers(self, trade_date):
        # 免费版无全市场快照，降级到 Akshare
        raise RuntimeError("tushare 免费版无全市场快照，降级 Akshare")

    def get_fund_flow(self, trade_date):
        td = self._resolve_td(trade_date)
        if td is None:
            raise RuntimeError("tushare 当日数据尚未入库（收盘后延迟），降级 Akshare")
        ff = {"market_main_net_yi": None, "north_south": None,
              "industry_top_in": [], "industry_top_out": []}
        try:
            # 个股主力净流入（net_mf_amount，单位：千元）→ 亿元
            df = self.pro.moneyflow(trade_date=td)
            if df is not None and len(df) and "net_mf_amount" in df.columns:
                ff["market_main_net_yi"] = float(df["net_mf_amount"].fillna(0).sum()) / 1e5
        except Exception:
            pass
        try:
            # 沪深港通（north_money / south_money，单位：万元）→ 亿元
            df = self.pro.moneyflow_hsgt(trade_date=td)
            if df is not None and len(df):
                r = df.iloc[0]
                ff["north_south"] = {"north_net_yi": _f(r.get("north_money")) / 1e4,
                                    "south_net_yi": _f(r.get("south_money")) / 1e4}
        except Exception:
            pass
        if ff["market_main_net_yi"] is None and ff["north_south"] is None:
            raise RuntimeError("tushare 资金流不可得")
        return ff

    def get_dragon(self, trade_date):
        td = self._resolve_td(trade_date)
        if td is None:
            raise RuntimeError("tushare 当日数据尚未入库（收盘后延迟），降级 Akshare")
        df = self.pro.top_list(trade_date=td)
        if df is None or not len(df):
            raise RuntimeError("tushare 龙虎榜不可得")
        out = []
        for _, r in df.iterrows():
            code = str(r.get("ts_code", ""))[:6]
            net = _f(r.get("net_amount")) / 1e8 if r.get("net_amount") is not None else 0.0
            reason = str(r.get("reason") or "—")
            out.append({"code": code, "name": str(r.get("name", "")),
                        "net_yi": net, "reason": reason})
        return out

    def get_news(self, trade_date):
        return []  # tushare 不提供新闻

    def get_tech(self, trade_date):
        td = self._resolve_td(trade_date)
        if td is None:
            raise RuntimeError("tushare 当日数据尚未入库（收盘后延迟），降级 Akshare")
        start = (datetime.date.today() - datetime.timedelta(days=180)).strftime("%Y%m%d")
        result: Dict[str, Any] = {}
        # A 股主要指数
        for name, code in self.A_IDX.items():
            try:
                df = self.pro.index_daily(ts_code=code, start_date=start, end_date=td)
                if df is None or len(df) < 15:
                    continue
                df = df.sort_values("trade_date")  # tushare 默认降序，须转升序
                closes = [float(x) for x in df["close"].tolist()]
                result[name] = _calc_tech(closes)
            except Exception:
                continue
        # 港股指数（index_global）
        for name, code in self.HK_IDX.items():
            try:
                df = self.pro.index_global(ts_code=code, start_date=start, end_date=td)
                if df is None or len(df) < 15:
                    continue
                df = df.sort_values("trade_date")
                closes = [float(x) for x in df["close"].tolist()]
                result[name] = _calc_tech(closes)
            except Exception:
                continue
        if not result:
            raise RuntimeError("tushare 技术面日线不足")
        return result


class AkshareSource(DataSource):
    """akshare 适配器（开源主源）。

    覆盖：指数（sina/em）、涨跌统计（全市场快照聚合）、板块（同花顺行业汇总）、
    个股异动（全市场快照排序）、资金流（市场 + 行业）、龙虎榜（em/sina）、
    技术面（指数日线计算 RSI/MA）。新闻无可靠市场级源，如实降级。
    注：部分 EastMoney 接口在受限网络会被拦截，已在调用内做 em→sina 回退。
    """
    name = "akshare"

    def __init__(self):
        try:
            import akshare as ak  # type: ignore
        except Exception as e:
            raise RuntimeError(f"akshare 未安装: {e}")
        self.ak = ak

    def get_indices(self, market, trade_date: str = "latest"):
        out: List[Dict[str, Any]] = []
        seen = set()
        # A 股指数：sina 现货（最稳）
        try:
            df = _robust_call(self.ak.stock_zh_index_spot_sina, desc="sina 指数")
            names = A_INDEX_NAMES if market in ("A股", "全部") else []
            for _, r in df.iterrows():
                if r["名称"] in names and (("A股", r["名称"]) not in seen):
                    seen.add(("A股", r["名称"]))
                    out.append({"market": "A股", "name": r["名称"],
                                "close": _f(r["最新价"]), "pct": _f(r["涨跌幅"]),
                                "amount_yi": _f(r.get("成交额", 0)) / 1e8 if "成交额" in r else 0.0})
        except Exception:
            pass
        # 港股指数：em（受限网络可能失败，降级到 web 源）
        if market in ("港股", "全部"):
            try:
                df = _robust_call(self.ak.stock_hk_index_spot_em, desc="em 港股指数")
                for _, r in df.iterrows():
                    if r["名称"] in HK_INDEX_NAMES and (("港股", r["名称"]) not in seen):
                        seen.add(("港股", r["名称"]))
                        out.append({"market": "港股", "name": r["名称"],
                                    "close": _f(r["最新价"]), "pct": _f(r["涨跌幅"]),
                                    "amount_yi": 0.0})
            except Exception:
                pass
        if not out:
            raise RuntimeError("akshare 指数源返回空")
        return out

    def get_breadth(self, trade_date):
        if trade_date and trade_date not in ("latest",) and trade_date != datetime.date.today().isoformat():
            raise RuntimeError("涨跌统计需当日全市场快照，历史交易日不支持，标待补充")
        # 全市场快照聚合涨跌家数（sina 现货，含涨跌幅；em 偶发抖动作回退）
        df = None
        for fn in (self.ak.stock_zh_a_spot, self.ak.stock_zh_a_spot_em):
            try:
                df = _robust_call(fn, desc="akshare 全市场快照", tries=2, sleep=0.5)
                if df is not None and len(df):
                    break
            except Exception:
                df = None
        if df is None or not len(df):
            raise RuntimeError("akshare 全市场快照不可得")
        pct = df["涨跌幅"] if "涨跌幅" in df else df.get("pct_change")
        up = int((pct > 0).sum()); down = int((pct < 0).sum()); flat = int((pct == 0).sum())
        # 涨停/跌停（A股 ±10% / 创业板±20% 近似按 ±9.5% 计）
        limit_up = int((pct >= 9.5).sum()); limit_down = int((pct <= -9.5).sum())
        return {"up": up, "down": down, "flat": flat, "limit_up": limit_up,
                "limit_down": limit_down, "total": int(len(df))}

    def get_sectors(self, trade_date):
        if trade_date and trade_date not in ("latest",) and trade_date != datetime.date.today().isoformat():
            raise RuntimeError("板块汇总需当日快照，历史交易日不支持，标待补充")
        # 同花顺行业板块汇总（约 90 个，沙箱可用）
        df = _robust_call(self.ak.stock_board_industry_summary_ths, desc="同花顺行业汇总")
        out = []
        for _, r in df.iterrows():
            out.append({"name": r["板块"], "pct1d": _f(r["涨跌幅"]),
                        "amount_yi": _f(r["总成交额"]), "net_yi": _f(r["净流入"])})
        if not out:
            raise RuntimeError("同花顺行业汇总返回空")
        return out

    def get_movers(self, trade_date):
        if trade_date and trade_date not in ("latest",) and trade_date != datetime.date.today().isoformat():
            raise RuntimeError("个股异动需当日全市场快照，历史交易日不支持，标待补充")
        # 涨跌幅来自 sina 全市场快照（最稳）；换手率优先 em（含换手率列），缺失则标缺
        df = None
        for fn in (self.ak.stock_zh_a_spot, self.ak.stock_zh_a_spot_em):
            try:
                df = _robust_call(fn, desc="akshare 全市场快照", tries=2, sleep=0.5)
                if df is not None and len(df):
                    break
            except Exception:
                df = None
        if df is None or not len(df):
            raise RuntimeError("akshare 全市场快照不可得")
        pct = df["涨跌幅"] if "涨跌幅" in df else df.get("pct_change")
        has_turn = "换手率" in df
        turn = df["换手率"] if has_turn else None
        rows = []
        for _, r in df.iterrows():
            code = str(r.get("代码", r.get("code", "")))
            code = code[2:] if code[:2] in ("sh", "sz", "bj") else code  # 去交易所前缀
            rows.append({"code": code, "name": r.get("名称", r.get("name", "")),
                         "pct": _f(pct.iloc[_] if hasattr(pct, "iloc") else pct[_]),
                         "turnover": _f(turn.iloc[_] if (turn is not None and hasattr(turn, "iloc")) else 0.0)})
        up = sorted(rows, key=lambda x: -x["pct"])[:DEFAULT_THRESHOLDS.top_n]
        down = sorted(rows, key=lambda x: x["pct"])[:DEFAULT_THRESHOLDS.top_n]
        turn_sorted = sorted(rows, key=lambda x: -x["turnover"])[:DEFAULT_THRESHOLDS.top_n] if has_turn else []
        return {"up": up, "down": down, "turnover": turn_sorted}

    def get_fund_flow(self, trade_date):
        ff = {"market_main_net_yi": None, "north_south": None,
              "industry_top_in": [], "industry_top_out": []}
        # 市场资金流
        try:
            if not trade_date or trade_date in ("latest",):
                end = datetime.date.today()
            else:
                end = datetime.date.fromisoformat(trade_date)
            start = (end - datetime.timedelta(days=5)).isoformat()
            df = _robust_call(lambda: self.ak.stock_market_fund_flow(
                start_date=start.replace("-", ""), end_date=end.strftime("%Y%m%d")),
                desc="akshare 市场资金流", tries=2)
            if df is not None and len(df):
                ff["market_main_net_yi"] = _f(df.iloc[-1].get("主力净流入-净额", 0)) / 1e8
        except Exception:
            pass
        # 沪深港通（北向 / 南向净买额，单位：亿元）
        try:
            hsgt = _robust_call(self.ak.stock_hsgt_fund_flow_summary_em,
                                desc="akshare 沪深港通", tries=2)
            if hsgt is not None and len(hsgt):
                north = _f(hsgt.loc[hsgt["资金方向"] == "北向", "成交净买额"].sum())
                south = _f(hsgt.loc[hsgt["资金方向"] == "南向", "成交净买额"].sum())
                ff["north_south"] = {"north_net_yi": north, "south_net_yi": south}
        except Exception:
            pass
        # 行业资金流（来自同花顺行业汇总）
        try:
            df = _robust_call(self.ak.stock_board_industry_summary_ths, desc="同花顺行业汇总")
            s = sorted([(r["板块"], _f(r["净流入"])) for _, r in df.iterrows()],
                       key=lambda x: -x[1])
            ff["industry_top_in"] = s[:DEFAULT_THRESHOLDS.top_n]
            ff["industry_top_out"] = s[-DEFAULT_THRESHOLDS.top_n:][::-1]
        except Exception:
            pass
        if ff["market_main_net_yi"] is None and not ff["industry_top_in"] and ff["north_south"] is None:
            raise RuntimeError("akshare 资金流不可得")
        return ff

    def get_dragon(self, trade_date):
        td = _ymd(trade_date)
        df = None
        # em：按日期区间取（净买额/上榜原因齐全）；sina 作回退（无净买额，上榜原因在「指标」列）
        for fn in (lambda: self.ak.stock_lhb_detail_em(start_date=td, end_date=td),
                   lambda: self.ak.stock_lhb_detail_daily_sina(date=td)):
            try:
                df = _robust_call(fn, desc="akshare 龙虎榜", tries=2, sleep=0.5)
                if df is not None and len(df):
                    break
            except Exception:
                df = None
        if df is None or not len(df):
            raise RuntimeError("akshare 龙虎榜不可得")
        out = []
        for _, r in df.iterrows():
            if "龙虎榜净买额" in df.columns:
                net = _f(r.get("龙虎榜净买额")) / 1e8  # 元 -> 亿
                reason = str(r.get("上榜原因", ""))
            else:
                net = 0.0
                reason = str(r.get("指标", r.get("上榜原因", "")))
            out.append({"code": str(r.get("代码", r.get("股票代码", ""))),
                        "name": r.get("名称", r.get("股票名称", "")),
                        "net_yi": net, "reason": reason})
        return out

    def get_news(self, trade_date):
        # akshare 无可靠市场级新闻源；建议经 WebSearch 补充。如实降级。
        raise RuntimeError("akshare 无市场级新闻源（公开资讯缺口，建议经 WebSearch 检索）")

    def get_tech(self, trade_date):
        # A 股主要指数（同花顺/新浪日线），港股在 akshare 无干净日线接口，由 tushare 兜底
        AK_IDX = {"上证指数": "sh000001", "深证成指": "sz399001",
                  "创业板指": "sz399006", "沪深300": "sh000300", "上证50": "sh000016",
                  "科创50": "sh000688"}
        result: Dict[str, Any] = {}
        for name, sym in AK_IDX.items():
            closes: List[float] = []
            for fn in (lambda s=sym: self.ak.stock_zh_index_daily(symbol=s),
                       lambda s=sym: self.ak.index_zh_a_hist(
                           symbol=s[2:], period="daily",
                           start_date=(datetime.date.today() - datetime.timedelta(days=120)).strftime("%Y%m%d"),
                           end_date=datetime.date.today().strftime("%Y%m%d"))):
                try:
                    df = _robust_call(fn, desc=f"akshare {name} 日线", tries=2, sleep=0.5)
                    if df is not None and len(df):
                        closes = df["close"].astype(float).tolist() if "close" in df else \
                                 [float(x) for x in df.get("收盘", [])]
                        if len(closes) >= 15:
                            break
                except Exception:
                    pass
            if len(closes) >= 15:
                result[name] = _calc_tech(closes)
        if not result:
            raise RuntimeError("akshare 技术面日线不足")
        return result


class WebSource(DataSource):
    """网页兜底源（腾讯财经 qt.gtimg.cn / 东方财富 Push API）。

    仅覆盖指数等实时行情字段，作为 Akshare 不可用时的最后兜底；
    板块 / 个股 / 资金流 / 龙虎榜 / 新闻无网页兜底，将如实标注缺失。
    """
    name = "web"

    def get_indices(self, market, trade_date: str = "latest"):
        import requests  # type: ignore
        out: List[Dict[str, Any]] = []
        names = (A_INDEX_NAMES if market in ("A股", "全部") else []) + \
                (HK_INDEX_NAMES if market in ("港股", "全部") else [])
        for n in names:
            secid = EASTMONEY_INDEX_SECID.get(n)
            if not secid:
                continue
            try:
                url = (f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}"
                       f"&fields=f43,f57,f58,f170")
                r = requests.get(url, timeout=8)
                d = r.json().get("data") or {}
                if d.get("f43") is None:
                    continue
                pct = _f(d.get("f170"))
                close = _f(d.get("f43"))
                out.append({"market": "港股" if n in HK_INDEX_NAMES else "A股",
                            "name": n, "close": close, "pct": pct, "amount_yi": 0.0})
            except Exception:
                continue
        if not out:
            raise RuntimeError("网页兜底指数源不可得")
        return out

    def get_breadth(self, trade_date): raise NotImplementedError("网页兜底无涨跌统计")
    def get_sectors(self, trade_date): raise NotImplementedError("网页兜底无板块数据")
    def get_movers(self, trade_date): raise NotImplementedError("网页兜底无个股异动")
    def get_fund_flow(self, trade_date): raise NotImplementedError("网页兜底无资金流")
    def get_dragon(self, trade_date): raise NotImplementedError("网页兜底无龙虎榜")
    def get_news(self, trade_date): raise NotImplementedError("网页兜底无新闻")
    def get_tech(self, trade_date): raise NotImplementedError("网页兜底无技术面")


def _build_source(name: str, market: str = "全部"):
    try:
        if name == "tushare":
            return TushareSource()
        if name == "akshare":
            return AkshareSource()
        if name == "web":
            return WebSource()
        if name == "demo":
            return DemoSource(market=market)
    except Exception:
        return None
    return None


CORE_CATEGORIES = ["indices", "breadth", "sectors", "movers", "fund_flow"]


def fetch(inp: SkillInput, demo: bool = False) -> Dict[str, Any]:
    sources_order = ["demo"] if demo else list(GATEWAY_PRIORITY)
    instances = {s: _build_source(s, market=inp.market) for s in sources_order}

    out: Dict[str, Any] = {
        "indices": [], "breadth": {}, "sectors": [], "movers": {},
        "fund_flow": {}, "dragon": [], "news": [], "tech": {},
        "source_meta": "", "degrade_trace": [], "missing_items": [],
    }
    degrade_trace: List[str] = []
    missing_items: List[str] = []
    trade_date = inp.trade_date or "latest"

    # 核心行情类（决定能否出报告）
    for cat in CORE_CATEGORIES:
        if cat == "indices":
            # 指数按市场分段取优：A股/港股各自挑首个可用的源（tushare 缺港股时由 akshare 补齐）
            collected, used_sources = _try_indices(
                instances, sources_order, inp.market, trade_date, degrade_trace)
            if collected:
                out["indices"] = collected
                if not out["source_meta"]:
                    out["source_meta"] = used_sources[0]
            else:
                missing_items.append(cat)
            continue
        if cat == "sectors":
            # 板块优先 akshare（同花顺行业，含成交额/主力净流入/家数）；tushare 申万一级行业
            # 仅含涨跌幅、无金额字段，作为 akshare 不可用时的兜底。避免 L1 抢走板块后
            # 成交额/主力净流入两列全部沦为「—」。
            sectors_order = ["akshare"] + [s for s in sources_order if s != "akshare"]
            used = _try_category(instances, sectors_order, "sectors", trade_date, inp, out, degrade_trace)
            if used == "akshare":
                degrade_trace.append("sectors: 优先 akshare（同花顺行业，含成交额/主力净流入），tushare 申万行业仅作兜底")
            if used is None:
                missing_items.append("sectors")
            continue
        if cat == "fund_flow":
            # 资金流跨源合并：主力净流入与沪深港通各自取首个能提供的源
            merged = _try_fund_flow(instances, sources_order, trade_date, degrade_trace)
            if merged is not None:
                out["fund_flow"] = merged
            else:
                missing_items.append(cat)
            continue
        used = _try_category(instances, sources_order, cat, trade_date, inp, out, degrade_trace)
        if used is None:
            missing_items.append(cat)

    # 非核心类（缺失仅标注，不阻断报告）
    for cat in ("dragon", "news", "tech"):
        used = _try_category(instances, sources_order, cat, trade_date, inp, out, degrade_trace)
        if used is None:
            missing_items.append(cat)

    if not out["indices"] or not out["sectors"]:
        raise GatewayError("MKT_REVIEW_001", ERROR_CODES["MKT_REVIEW_001"])

    out["source_meta"] = (out.get("source_meta") or "unknown")
    out["degrade_trace"] = degrade_trace
    out["missing_items"] = missing_items
    return out


def _try_indices(instances, sources_order, market, trade_date, degrade_trace):
    """指数按市场分段取优：A股 / 港股各自挑首个能提供的源。

    解决 tushare 免费版缺港股（index_global 空）时，--market 全部 仍能由 akshare 补港股，
    避免「标全部却只有 A 股」的失真；同时 degrade_trace 如实记录各分段降级。

    历史交易日护栏：akshare / web 为实时源（只给今天），若指定历史交易日，不允许其实时
    数据回填，避免「报告标 1023、港股却是今天」的日期错位；此时仅尊重 trade_date 的
    tushare 有效，缺失则如实标注。
    """
    is_latest = (not trade_date) or trade_date in ("latest",) or \
               trade_date == datetime.date.today().isoformat()
    segments = (["A股"] if market in ("A股", "全部") else []) + \
               (["港股"] if market in ("港股", "全部") else [])
    collected: List[Dict[str, Any]] = []
    used_sources: List[str] = []
    for seg in segments:
        got = False
        for s in sources_order:
            inst = instances.get(s)
            if inst is None:
                degrade_trace.append(f"indices({seg}): {s} 不可用（未装/无token/异常），跳过")
                continue
            if (not is_latest) and s in ("akshare", "web"):
                degrade_trace.append(f"indices({seg}): {s} 为实时源，历史日不回填，跳过")
                continue
            try:
                val = inst.get_indices(seg, trade_date)
                seg_rows = [r for r in val if r.get("market") == seg]
                if seg_rows:
                    collected.extend(seg_rows)
                    used_sources.append(s)
                    got = True
                    break
            except Exception as e:
                degrade_trace.append(f"indices({seg}): {s} 异常（{e}），尝试下一级")
        if not got:
            degrade_trace.append(f"indices({seg}): 全部源降级失败，缺失")
    return collected, used_sources


def _try_fund_flow(instances, sources_order, trade_date, degrade_trace):
    """资金流跨源合并：主力净流入 / 沪深港通 / 行业榜各自取首个能提供的源。

    解决 tushare 免费版缺沪深港通（moneyflow_hsgt 空）时，仍可由 akshare 补齐北向/南向净买额。

    历史交易日护栏：akshare / web 的沪深港通 / 行业 / 主力净流入均为实时口径，指定历史交易日时
    不允许回填，避免日期错位；此时仅尊重 trade_date 的 tushare 有效。
    """
    is_latest = (not trade_date) or trade_date in ("latest",) or \
               trade_date == datetime.date.today().isoformat()
    merged = {"market_main_net_yi": None, "north_south": None,
              "industry_top_in": [], "industry_top_out": []}
    any_data = False
    for s in sources_order:
        inst = instances.get(s)
        if inst is None:
            degrade_trace.append(f"fund_flow: {s} 不可用，跳过")
            continue
        if (not is_latest) and s in ("akshare", "web"):
            degrade_trace.append(f"fund_flow: {s} 为实时源，历史日不回填，跳过")
            continue
        try:
            val = inst.get_fund_flow(trade_date)
            if val.get("market_main_net_yi") is not None and merged["market_main_net_yi"] is None:
                merged["market_main_net_yi"] = val["market_main_net_yi"]; any_data = True
            if val.get("north_south") is not None and merged["north_south"] is None:
                merged["north_south"] = val["north_south"]; any_data = True
            if val.get("industry_top_in") and not merged["industry_top_in"]:
                merged["industry_top_in"] = val["industry_top_in"]; any_data = True
            if val.get("industry_top_out") and not merged["industry_top_out"]:
                merged["industry_top_out"] = val["industry_top_out"]; any_data = True
        except Exception as e:
            degrade_trace.append(f"fund_flow: {s} 异常（{e}），尝试下一级")
    if not any_data:
        degrade_trace.append("fund_flow: 全部源不可得")
        return None
    return merged


def _try_category(instances, sources_order, cat, trade_date, inp, out, degrade_trace):
    for s in sources_order:
        inst = instances.get(s)
        if inst is None:
            degrade_trace.append(f"{cat}: {s} 不可用（未装/无token/异常），跳过")
            continue
        try:
            if cat == "indices":
                val = inst.get_indices(inp.market, trade_date)
            elif cat == "breadth":
                val = inst.get_breadth(trade_date)
            elif cat == "sectors":
                val = inst.get_sectors(trade_date)
            elif cat == "movers":
                val = inst.get_movers(trade_date)
            elif cat == "fund_flow":
                val = inst.get_fund_flow(trade_date)
            elif cat == "dragon":
                val = inst.get_dragon(trade_date)
            elif cat == "news":
                val = inst.get_news(trade_date)
            else:
                val = inst.get_tech(trade_date)
            if val is None or (isinstance(val, (list, dict)) and len(val) == 0 and cat not in ("breadth", "news", "tech")):
                degrade_trace.append(f"{cat}: {s} 返回空，尝试下一级")
                continue
            out[cat] = val
            if cat in ("indices", "sectors", "breadth", "movers", "fund_flow") and not out["source_meta"]:
                out["source_meta"] = s
            return s
        except Exception as e:
            degrade_trace.append(f"{cat}: {s} 异常（{e}），尝试下一级")
            continue
    return None


# ===========================================================================
# 五、语义标准化 / 工具
# ===========================================================================
def align_trade_date(s: str) -> str:
    if s:
        return s
    return TRADE_DATE


def validate_schema(d: Dict[str, Any]) -> List[str]:
    required = ["skill", "trade_date", "data_source", "indices", "sectors"]
    return [k for k in required if k not in d]


# ===========================================================================
# 六、报告生成（Markdown / HTML）
# ===========================================================================
SIGNAL_ICONS = {
    "强势延续": "🔥",
    "资金异动": "💰",
    "持续失血": "🩸",
    "走弱预警": "⚠️",
    "极端波动": "⚡",
}
DIRECTION_ICONS = {"up": "↑ 看多", "down": "↓ 看空", "neutral": "→ 中性"}
STRENGTH_ICONS = {"strong": "🔴 强", "medium": "🟠 中", "weak": "⚪ 弱"}

SIGNAL_LEGEND = (
    "> **图标说明**　🔥强势延续｜💰资金异动｜🩸持续失血｜⚠️走弱预警｜⚡极端波动　"
    "·　方向 **↑看多 ↓看空 →中性**"
)


def _pct(p):
    try:
        return float(p)
    except Exception:
        return 0.0


def _arrow(p):
    return "▲" if _pct(p) >= 0 else "▼"


def to_markdown(out: SkillOutput) -> str:
    L: List[str] = []
    src = out.data_source or "unknown"
    L.append(f"# 股市每日收评（{out.trade_date} · {out.market}）")
    L.append("")
    L.append(f"> 数据来源：{src} | 生成时间：{out.run_at}")
    if out.degraded:
        L.append("")
        L.append("> ⚠️ 本次发生数据源降级，结论仅供参考：" +
                 ("；".join(out.degrade_trace) or "见下方数据说明"))
    L.append("")

    # 一、盘面综述
    L.append("## 一、盘面综述")
    L.append(out.market_brief or "—")
    L.append("")

    # 二、大盘指数
    L.append("## 二、大盘指数")
    L.append("| 市场 | 指数 | 收盘 | 涨跌幅 | 成交额(亿) |")
    L.append("| --- | --- | --- | --- | --- |")
    for x in out.indices:
        L.append(f"| {x.market} | {x.name} | {x.close:,.2f} | {x.pct:+.2f}% | {x.amount_yi:,.1f} |")
    L.append("")

    # 三、涨跌统计
    if out.breadth:
        b = out.breadth
        L.append("## 三、涨跌统计（A股）")
        L.append(f"- 上涨 **{b.get('up', 0)}** 家 ｜ 下跌 **{b.get('down', 0)}** 家 ｜ 平盘 {b.get('flat', 0)} 家 ｜ 合计 {b.get('total', 0)} 家")
        L.append(f"- 涨停 **{b.get('limit_up', 0)}** 家 ｜ 跌停 **{b.get('limit_down', 0)}** 家")
        L.append("")

    # 四、板块表现
    if out.sectors:
        top_n = out._top_n
        ups = sorted(out.sectors, key=lambda r: -r.pct1d)[:top_n]
        downs = sorted(out.sectors, key=lambda r: r.pct1d)[:top_n]
        L.append(f"## 四、板块表现（Top {top_n}）")
        L.append("**领涨板块**")
        L.append("| 板块 | 涨跌幅 | 成交额(亿) | 主力净流入(亿) |")
        L.append("| --- | --- | --- | --- |")
        for r in ups:
            amt = f"{r.amount_yi:,.1f}" if r.amount_yi is not None else "—"
            net = f"{r.net_yi:+.1f}" if r.net_yi is not None else "—"
            L.append(f"| {r.name} | {r.pct1d:+.2f}% | {amt} | {net} |")
        L.append("")
        L.append("**领跌板块**")
        L.append("| 板块 | 涨跌幅 | 成交额(亿) | 主力净流入(亿) |")
        L.append("| --- | --- | --- | --- |")
        for r in downs:
            amt = f"{r.amount_yi:,.1f}" if r.amount_yi is not None else "—"
            net = f"{r.net_yi:+.1f}" if r.net_yi is not None else "—"
            L.append(f"| {r.name} | {r.pct1d:+.2f}% | {amt} | {net} |")
        L.append("")

    # 五、个股异动
    if out.movers:
        m = out.movers
        L.append("## 五、个股异动")
        L.append("**涨幅榜**")
        L.append("| 代码 | 名称 | 涨跌幅 | 换手率% |")
        L.append("| --- | --- | --- | --- |")
        for x in m.get("up", [])[:out._top_n]:
            L.append(f"| {x.code} | {x.name} | {x.pct:+.2f}% | {x.turnover:.2f} |")
        L.append("")
        L.append("**跌幅榜**")
        L.append("| 代码 | 名称 | 涨跌幅 | 换手率% |")
        L.append("| --- | --- | --- | --- |")
        for x in m.get("down", [])[:out._top_n]:
            L.append(f"| {x.code} | {x.name} | {x.pct:+.2f}% | {x.turnover:.2f} |")
        L.append("")
        L.append("**换手率榜**")
        if m.get("turnover"):
            L.append("| 代码 | 名称 | 涨跌幅 | 换手率% |")
            L.append("| --- | --- | --- | --- |")
            for x in m.get("turnover", [])[:out._top_n]:
                L.append(f"| {x.code} | {x.name} | {x.pct:+.2f}% | {x.turnover:.2f} |")
        else:
            L.append("- 数据待补充（当前数据源未提供换手率）")
        L.append("")

    # 六、资金流向
    if out.fund_flow:
        ff = out.fund_flow
        L.append("## 六、资金流向")
        if ff.get("market_main_net_yi") is not None:
            L.append(f"- 全市场主力净流入：**{ff['market_main_net_yi']:+.1f} 亿元**")
        else:
            L.append("- 全市场主力净流入：数据待补充（市场资金流接口暂不可得）")
        if ff.get("north_south") is not None:
            ns = ff["north_south"]
            L.append(f"- 沪深港通：北向 {ns.get('north_net_yi', 0):+.1f} 亿 ／ 南向 {ns.get('south_net_yi', 0):+.1f} 亿")
        else:
            L.append("- 沪深港通：数据待补充（开源覆盖较弱）")
        if ff.get("industry_top_in"):
            L.append("- 行业主力净流入居前：" + "、".join(f"{n}({v:+.1f}亿)" for n, v in ff["industry_top_in"]))
        if ff.get("industry_top_out"):
            L.append("- 行业主力净流出居前：" + "、".join(f"{n}({v:+.1f}亿)" for n, v in ff["industry_top_out"]))
        L.append("")

    # 七、龙虎榜
    if out.dragon:
        L.append("## 七、龙虎榜")
        L.append("| 代码 | 名称 | 净买额(亿) | 上榜原因 |")
        L.append("| --- | --- | --- | --- |")
        for d in out.dragon[:out._top_n]:
            L.append(f"| {d.get('code','')} | {d.get('name','')} | {_pct(d.get('net_yi')):+.1f} | {d.get('reason','')} |")
        L.append("")
    else:
        L.append("## 七、龙虎榜")
        L.append("- 数据待补充（开源龙虎榜源不可用）")
        L.append("")

    # 八、重要资讯
    if out.news:
        L.append("## 八、重要资讯")
        for n in out.news:
            tag = "【传闻】" if n.rumor else ""
            L.append(f"- {tag}{n.title}（来源：{n.source}，{n.time}）")
        L.append("")
    else:
        L.append("## 八、重要资讯")
        L.append("- 数据待补充（离线源无市场级新闻；可由 agent 经 WebSearch 检索后通过 --news-file 注入，详见 SKILL.md）")
        L.append("")

    # 九、技术面（各主要指数）
    L.append("## 九、技术面（各主要指数）")
    if out.tech:
        for name, t in out.tech.items():
            close = t.get("close")
            rsi_v = t.get("rsi14")
            rsi_tag = ""
            if rsi_v is not None:
                rsi_tag = "（超买）" if rsi_v >= DEFAULT_THRESHOLDS.rsi_overbought else \
                          ("（超卖）" if rsi_v <= DEFAULT_THRESHOLDS.rsi_oversold else "")
            sig = _tech_signal(t)
            L.append(f"**{name}**（收盘 {close}）")
            L.append(f"- RSI(14)：**{rsi_v}**{rsi_tag}")
            L.append(f"- 均线：MA5 {t.get('ma5')} ／ MA20 {t.get('ma20')} ／ MA60 {t.get('ma60')}")
            if sig:
                L.append(f"- 研判：{sig}")
            L.append("")
    else:
        L.append("- 数据待补充（指数日线源暂不可得，可重试）")
    L.append("")

    # 十、数据说明与免责
    L.append("## 十、数据说明与免责")
    if out.missing_items:
        L.append(f"- 缺失数据项（如实标注）：{', '.join(out.missing_items)}")
    if out.degrade_trace:
        for t in out.degrade_trace:
            L.append(f"- 降级：{t}")
    if not out.missing_items and not out.degrade_trace:
        L.append("- 数据完整，未触发降级。")
    L.append("")
    L.append(f"> {out.disclaimer}")
    return "\n".join(L)


HTML_STYLE = """
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:960px;margin:0 auto;padding:20px;color:#1f2937;line-height:1.8;}
  h1{border-bottom:2px solid #2563eb;padding-bottom:8px;}
  h2{margin-top:2rem;color:#1e40af;}
  table{border-collapse:collapse;width:100%;margin:1rem 0;}
  th,td{border:1px solid #d1d5db;padding:8px 12px;text-align:left;}
  th{background:#f3f4f6;}
  blockquote{border-left:3px solid #2563eb;margin:.5rem 0;padding:.5rem 1rem;background:#f8fafc;color:#475569;}
  .disclaimer{margin-top:2rem;padding:1rem;background:#f9fafb;border:1px solid #e5e7eb;color:#6b7280;font-size:.85em;}
  .warn{background:#fef3c7;border-left:3px solid #f59e0b;padding:.6rem 1rem;margin:1rem 0;}
</style>
"""


def _md_to_html_simple(md: str, title: str) -> str:
    lines = md.split("\n")
    out: List[str] = [f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
                      f"<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
                      f"<title>{title}</title>{HTML_STYLE}</head><body>"]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            out.append(f"<h1>{ln[2:]}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{ln[3:]}</h2>")
        elif ln.startswith("> "):
            cls = "warn" if "⚠️" in ln else ""
            out.append(f"<blockquote class='{cls}'>{ln[2:]}</blockquote>")
        elif ln.startswith("| "):
            tbl = [ln]
            j = i + 1
            while j < len(lines) and lines[j].startswith("| "):
                tbl.append(lines[j]); j += 1
            rows = [r.strip().strip("|").split("|") for r in tbl if not set(r.strip()) <= set("|- ")]
            if rows:
                out.append("<table>")
                out.append("<tr>" + "".join(f"<th>{c.strip()}</th>" for c in rows[0]) + "</tr>")
                for r in rows[1:]:
                    out.append("<tr>" + "".join(f"<td>{c.strip()}</td>" for c in r) + "</tr>")
                out.append("</table>")
            i = j - 1
        elif ln.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{lines[i][2:]}</li>"); i += 1
            out.append("</ul>")
            continue
        elif ln.strip() == "":
            pass
        else:
            out.append(f"<p>{ln}</p>")
        i += 1
    out.append("</body></html>")
    return "\n".join(out)


def to_html(out: SkillOutput) -> str:
    return _md_to_html_simple(to_markdown(out), f"股市每日收评（{out.trade_date}）")


# ===========================================================================
# 七、主流程（SOP 编排）
# ===========================================================================
def run_skill(inp: SkillInput, demo: bool = False) -> SkillOutput:
    if not inp.trade_date and not demo:
        inp.trade_date = _latest_trade_date()
    trade_date = align_trade_date(inp.trade_date)
    top_n = max(1, int(inp.top_n))
    run_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    try:
        raw = fetch(inp, demo=demo)
    except GatewayError as ge:
        return SkillOutput(
            skill=SKILL_NAME, version=SKILL_VERSION, run_at=run_at, trade_date=trade_date,
            market=inp.market, data_source="none", degraded=True,
            error_code=ge.code,
            error_msg=f"{ge.msg}（{ERROR_CODES.get(ge.code, '')}）",
            disclaimer=DISCLAIMER,
        )

    source_meta = raw.get("source_meta") or "unknown"
    degrade_trace = list(raw.get("degrade_trace", []))
    missing_items = list(raw.get("missing_items", []))

    # 公开资讯：本 skill 离线源（akshare/tushare/web）均无可靠市场级新闻接口，缺口由
    # agent 经 WebSearch 检索后整理成 news_file（JSON）注入补齐，避免「数据待补充」。
    if inp.news_file and os.path.exists(inp.news_file):
        try:
            with open(inp.news_file, "r", encoding="utf-8") as fh:
                ext_news = json.load(fh)
            if isinstance(ext_news, list) and ext_news:
                # 外部注入优先；源自带（通常为空）置后去重
                seen = set()
                merged = []
                for n in ext_news + (raw.get("news", []) or []):
                    t = str(n.get("title", "")).strip()
                    if not t or t in seen:
                        continue
                    seen.add(t)
                    merged.append(n)
                raw["news"] = merged
                if "news" in missing_items:
                    missing_items.remove("news")
                degrade_trace.append(f"资讯采集：WebSearch 注入 {len(ext_news)} 条（替代缺失的市场级新闻源）")
        except Exception as e:
            degrade_trace.append(f"资讯采集：news_file 解析失败（{e}），维持待补充")

    if "news" in missing_items:
        degrade_trace.append(f"资讯采集：MKT_REVIEW_002 {ERROR_CODES['MKT_REVIEW_002']}")

    indices = [IndexRow(**x) for x in raw.get("indices", [])]
    sectors = [SectorRow(**x) for x in raw.get("sectors", [])]
    movers_raw = raw.get("movers", {})
    movers = {k: [MoverRow(**x) for x in v] for k, v in movers_raw.items()} if movers_raw else {}
    dragon = _merge_dragon(raw.get("dragon", []))
    news_raw = raw.get("news", []) if inp.include_news else []
    news = [NewsItem(**{k: n.get(k, False) if k == "rumor" else n.get(k, "")
                        for k in ("title", "source", "time", "rumor")}) for n in news_raw]
    tech = raw.get("tech", {})

    # 盘面综述（自动生成，基于数据）
    a_indices = [x for x in indices if x.market == "A股"]
    idx_brief = "、".join(f"{x.name}{x.pct:+.2f}%" for x in a_indices[:3]) if a_indices else "A股指数数据缺失"
    up_cnt = sum(1 for s in sectors if s.pct1d > 0)
    if raw.get("breadth"):
        b = raw["breadth"]
        breadth_brief = f"涨跌比 {b.get('up',0)}:{b.get('down',0)}，涨停 {b.get('limit_up',0)} 家"
    else:
        breadth_brief = f"约 {up_cnt}/{len(sectors)} 个板块上涨"
    top_sector = max(sectors, key=lambda s: s.pct1d).name if sectors else "—"
    bottom_sector = min(sectors, key=lambda s: s.pct1d).name if sectors else "—"
    market_brief = (f"今日 {idx_brief}；{breadth_brief}。"
                    f"板块方面 {top_sector} 领涨、{bottom_sector} 领跌。"
                    + ("盘面情绪偏积极。" if up_cnt > len(sectors) / 2 else "盘面情绪偏弱。"))

    # 仅当核心行情类（指数/涨跌/板块/个股/资金流）发生真实降级（尝试下一级）或缺失，
    # 或主源回退到 web 兜底时，才标记 partial；源未配置（如未装/无 token 的跳过）不计。
    _core_degrade = [t for t in degrade_trace
                     if any(f"{c}:" in t for c in CORE_CATEGORIES)
                     and ("尝试下一级" in t or "降级失败" in t)]
    degraded = (source_meta == "web") or bool(_core_degrade) or \
               bool([m for m in missing_items if m in CORE_CATEGORIES])
    out = SkillOutput(
        skill=SKILL_NAME, version=SKILL_VERSION, run_at=run_at, trade_date=trade_date,
        market=inp.market, data_source=source_meta, degraded=degraded,
        degrade_trace=degrade_trace, indices=indices, breadth=raw.get("breadth", {}),
        sectors=sectors, movers=movers, fund_flow=raw.get("fund_flow", {}),
        dragon=dragon, news=news, tech=tech, market_brief=market_brief,
        missing_items=missing_items, disclaimer=DISCLAIMER,
    )
    out._top_n = top_n  # 非契约字段，供报告使用

    schema_missing = validate_schema(out.to_dict())
    if schema_missing:
        out.error_code = "SCHEMA_INVALID"
        out.error_msg = "输出缺失字段: " + ",".join(schema_missing)

    _register_call(out)
    return out


def _register_call(out: SkillOutput) -> None:
    print(f"[register] skill={out.skill} trade_date={out.trade_date} market={out.market} "
          f"source={out.data_source} degraded={out.degraded} "
          f"indices={len(out.indices)} sectors={len(out.sectors)}", file=sys.stderr)


def _merge_dragon(rows: List[Dict[str, Any]], max_reasons: int = 2) -> List[Dict[str, Any]]:
    """龙虎榜按股票合并：同一股票因多上榜原因出现多行时合并为一行。

    - 净买额按股票求和（top_list 每条上榜记录独立计净买，合计为该股当日龙虎榜净买额）
    - 上榜原因去重后最多保留 max_reasons 个，用「、」连接
    - 合并后按净买额降序，便于展示头部个股
    """
    if not rows:
        return []
    grouped: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for r in rows:
        key = str(r.get("code") or r.get("name") or "—")
        if key not in grouped:
            grouped[key] = {"code": r.get("code", ""), "name": r.get("name", ""),
                            "net_yi": 0.0, "_reasons": []}
            order.append(key)
        g = grouped[key]
        g["net_yi"] += float(r.get("net_yi") or 0.0)
        reason = str(r.get("reason") or "").strip()
        if reason and reason != "—" and reason not in g["_reasons"]:
            g["_reasons"].append(reason)
    merged = []
    for key in order:
        g = grouped[key]
        reasons = g["_reasons"][:max_reasons] or ["—"]
        merged.append({"code": g["code"], "name": g["name"],
                       "net_yi": g["net_yi"], "reason": "、".join(reasons)})
    merged.sort(key=lambda x: x["net_yi"], reverse=True)
    return merged


# ===========================================================================
# 八、JSON payload
# ===========================================================================
def to_payload(out: SkillOutput) -> Dict[str, Any]:
    top_n = getattr(out, "_top_n", 10)
    return {
        "trade_date": out.trade_date,
        "market": out.market,
        "summary": out.market_brief,
        "indices": [{"market": x.market, "name": x.name, "close": x.close, "pct": x.pct}
                    for x in out.indices],
        "breadth": out.breadth,
        "sectors": [
            {"name": r.name, "pct1d": r.pct1d, "amount_yi": r.amount_yi, "net_yi": r.net_yi}
            for r in sorted(out.sectors, key=lambda r: -r.pct1d)[:top_n]],
        "movers": {
            "up": [{"code": x.code, "name": x.name, "pct": x.pct, "turnover": x.turnover}
                   for x in out.movers.get("up", [])[:top_n]],
            "down": [{"code": x.code, "name": x.name, "pct": x.pct, "turnover": x.turnover}
                     for x in out.movers.get("down", [])[:top_n]]},
        "fund_flow": out.fund_flow,
        "dragon": out.dragon,
        "news": [{"title": n.title, "source": n.source, "time": n.time, "rumor": n.rumor}
                 for n in out.news],
        "tech": out.tech,
        "meta": {
            "data_source": out.data_source,
            "degraded": "demo" if out.data_source == "demo" else ("partial" if out.degraded else "none"),
            "degrade_trace": out.degrade_trace,
        },
    }


def render(out: SkillOutput, fmt: str = "both") -> str:
    md = to_markdown(out)
    if fmt == "markdown":
        return md
    if fmt == "json":
        return json.dumps(to_payload(out), ensure_ascii=False, indent=2)
    return ("<!-- JSON -->\n" + json.dumps(to_payload(out), ensure_ascii=False, indent=2)
            + "\n\n<!-- MARKDOWN -->\n" + md)


# ===========================================================================
# 九、CLI
# ===========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="股市每日收评 market_daily_review Skill · 可运行脚本（开源版）")
    parser.add_argument("--trade-date", default="", help="YYYY-MM-DD，空=最近交易日")
    parser.add_argument("--market", default="全部", choices=["A股", "港股", "全部"])
    parser.add_argument("--top-n", type=int, default=10, help="板块 / 个股榜单各取前 N")
    parser.add_argument("--no-news", action="store_true", help="关闭公开资讯采集")
    parser.add_argument("--news-file", default="", help="可选：WebSearch 整理的新闻 JSON（注入公开资讯，替代待补充）")
    parser.add_argument("--output-format", default="both", choices=["json", "markdown", "both"])
    parser.add_argument("--out", default="", help="落盘目录，如 files/report")
    parser.add_argument("--demo", action="store_true",
                        help="使用内置演示数据，无需 token / 外部库即可运行")
    args = parser.parse_args()

    inp = SkillInput(
        trade_date=args.trade_date, market=args.market, top_n=args.top_n,
        include_news=not args.no_news, news_file=args.news_file, output_format=args.output_format,
    )

    out = run_skill(inp, demo=args.demo)

    if out.error_code == "MKT_REVIEW_001":
        print(json.dumps(out.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(2)

    text = render(out, args.output_format)
    print(text)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        if args.output_format in ("markdown", "both"):
            with open(os.path.join(args.out, f"{out.trade_date}_股市每日收评.md"), "w", encoding="utf-8") as f:
                f.write(to_markdown(out))
        if args.output_format in ("html", "both"):
            with open(os.path.join(args.out, f"{out.trade_date}_股市每日收评.html"), "w", encoding="utf-8") as f:
                f.write(to_html(out))
        print(f"[ok] 已落盘 {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
