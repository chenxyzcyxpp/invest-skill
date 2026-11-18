#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Authors: Warwick
"""
industry_flash.py — 行业速报 · 可运行主脚本（script_based 形态）
=============================================================
以申万一级行业为口径，输出行业强弱排名、资金流向、事件速递与可解释信号（R01-R06），
生成每日行业速报（Markdown / HTML / JSON）。

用法：
  # 演示模式（沙箱可直接跑，无需 token / 外部库）
  python3 industry_flash.py --demo --output-format markdown
  python3 industry_flash.py --demo --output-format json

  # 真实模式（需本机可访问 Tushare / Akshare / 腾讯；未接入时如实报错，不伪造）
  python3 industry_flash.py --trade-date 2026-10-16 --output-format markdown --out files/report
  python3 industry_flash.py --trade-date 2026-10-16 --focus fund --top-n 3

  # 仅落盘 files/report/{trade_date}_行业速报.md / .html
  python3 industry_flash.py --demo --out files/report

数据源（三级可降级，详见 references/data-sources.md）：
  Tushare（优先）> Akshare（次级）> 腾讯财经网页源（兜底）> 演示数据（--demo）
  行情三源全部失败 → 抛 IND_FLASH_001 退出，不输出伪造速报。
  行业新闻源在三源体系中覆盖弱，R05 事件驱动建议复用 sentiment_risk_warning 事件流
  或经 WebSearch 检索（见 references/data-sources.md 第二节）。

约束（与框架铁律一致）：
  * 禁止编造数据：任何数值必须来自脚本计算；数据源失败报错退出。
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
SKILL_NAME = "industry_brief"
SKILL_VERSION = "1.0.0"

# 网关数据源优先级（全局约定的降级顺序）
GATEWAY_PRIORITY: List[str] = ["tushare", "akshare", "tencent_web"]

ERROR_CODES = {
    "IND_FLASH_001": "行情三类数据源全部失败",
    "IND_FLASH_002": "事件源全部失败但行情可用",
    "IND_FLASH_003": "申万分类映射不可用且无静态表",
}

DISCLAIMER = (
    "本服务内容来源于公开及第三方数据源，仅自动化加工展示，"
    "不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，"
    "内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。"
    "市场有风险，投资需谨慎。"
)

# 申万一级行业（31 个）静态映射表 —— 真实应来自底层语义标准化节点统一维护。
# 此处自包含一份，保证兜底口径可用。
SW_INDUSTRIES: Dict[str, str] = {
    "农林牧渔": "SW801010", "基础化工": "SW801030", "钢铁": "SW801040", "有色金属": "SW801050",
    "电子": "SW801080", "家用电器": "SW801110", "食品饮料": "SW801120", "纺织服饰": "SW801130",
    "轻工制造": "SW801140", "医药生物": "SW801150", "公用事业": "SW801160", "交通运输": "SW801170",
    "房地产": "SW801180", "商贸零售": "SW801200", "社会服务": "SW801210", "综合": "SW801230",
    "建筑材料": "SW801710", "建筑装饰": "SW801720", "电力设备": "SW801730", "国防军工": "SW801740",
    "计算机": "SW801750", "传媒": "SW801760", "通信": "SW801770", "银行": "SW801780",
    "非银金融": "SW801790", "汽车": "SW801880", "机械设备": "SW801890", "煤炭": "SW801950",
    "石油石化": "SW801960", "环保": "SW801970", "美容护理": "SW801980",
}


@dataclass
class SignalThresholds:
    """初版信号规则阈值（R01-R06），集中配置可运营调参。"""
    rank_top_n: int = 5                 # 强弱榜默认前 N
    momentum_5d_strong: float = 3.0     # R01: 5日累计涨幅 > 该值 => 强势延续
    net_inflow_abs: float = 20.0        # R02: 单日净流入(亿) > 该值 => 资金异动
    net_outflow_3d: float = 30.0        # R03: 净流出累计(亿) > 该值 => 持续失血
    event_move_abs: float = 1.5         # R05: 命中事件且行业涨跌幅(绝对值) > 该值 => 事件驱动异动
    extreme_move_abs: float = 4.0       # R06: 单日涨跌幅(绝对值) > 该值 => 极端波动
    leading_stocks: int = 3             # 领涨/领跌个股展示数量


DEFAULT_THRESHOLDS = SignalThresholds()


# ===========================================================================
# 二、演示数据（无需任何 token / 外部库即可跑通完整 SOP）
# ===========================================================================
TRADE_DATE = "2026-10-16"

# 行业日线行情（pct1d / pct5d / turnover 为成交额亿元）
DAILY: Dict[str, Dict[str, float]] = {
    "SW801080": {"name": "电子", "pct1d": 2.35, "pct5d": 5.12, "turnover": 1283.4},
    "SW801750": {"name": "计算机", "pct1d": 1.98, "pct5d": 4.20, "turnover": 980.1},
    "SW801770": {"name": "通信", "pct1d": 1.45, "pct5d": 2.10, "turnover": 410.3},
    "SW801730": {"name": "电力设备", "pct1d": 0.85, "pct5d": -1.20, "turnover": 760.0},
    "SW801780": {"name": "银行", "pct1d": 0.30, "pct5d": 0.50, "turnover": 300.1},
    "SW801790": {"name": "非银金融", "pct1d": 0.12, "pct5d": -0.80, "turnover": 420.0},
    "SW801150": {"name": "医药生物", "pct1d": -0.75, "pct5d": -2.80, "turnover": 610.5},
    "SW801120": {"name": "食品饮料", "pct1d": -1.10, "pct5d": -3.50, "turnover": 540.2},
    "SW801050": {"name": "有色金属", "pct1d": -1.55, "pct5d": -2.30, "turnover": 520.0},
    "SW801880": {"name": "汽车", "pct1d": -2.10, "pct5d": -4.10, "turnover": 690.0},
}

# 行业资金流（当日主力净流入，亿元）
MONEYFLOW: Dict[str, float] = {
    "SW801080": 45.2, "SW801750": 38.5, "SW801770": 12.0, "SW801730": -22.3,
    "SW801780": 5.0, "SW801790": -3.2, "SW801150": -9.4, "SW801120": -18.6,
    "SW801050": -11.5, "SW801880": -34.0,
}

INDEX = {"close": 3265.4, "pct": 0.62, "name": "上证指数"}

# 行业事件（fact_flag: fact 事实 / rumor 传闻）
EVENTS: List[Dict[str, str]] = [
    {"industry_id": "SW801080", "industry_name": "电子", "event_type": "policy",
     "summary": "半导体国产化替代政策再加码，设备招标提速", "source": "akshare:stock_news_em",
     "publish_time": "2026-10-16 14:20", "fact_flag": "fact"},
    {"industry_id": "SW801080", "industry_name": "电子", "event_type": "earnings",
     "summary": "某晶圆龙头三季报超预期，毛利率环比改善", "source": "akshare:stock_news_em",
     "publish_time": "2026-10-16 11:05", "fact_flag": "fact"},
    {"industry_id": "SW801750", "industry_name": "计算机", "event_type": "supply_demand",
     "summary": "国产算力需求旺盛，服务器订单能见度延长", "source": "akshare:stock_news_em",
     "publish_time": "2026-10-16 10:30", "fact_flag": "fact"},
    {"industry_id": "SW801730", "industry_name": "电力设备", "event_type": "overseas",
     "summary": "网传海外光伏组件关税上调，尚未官方确认", "source": "tencent_news",
     "publish_time": "2026-10-16 13:50", "fact_flag": "rumor"},
    {"industry_id": "SW801120", "industry_name": "食品饮料", "event_type": "rumor",
     "summary": "渠道传某白酒批价松动，等待公司回应", "source": "tencent_news",
     "publish_time": "2026-10-16 15:02", "fact_flag": "rumor"},
]

LEADING_STOCKS: Dict[str, List[Dict[str, str]]] = {
    "SW801080": [{"code": "688981", "name": "中芯国际", "pct1d": 8.1},
                 {"code": "002371", "name": "北方华创", "pct1d": 6.7},
                 {"code": "603501", "name": "韦尔股份", "pct1d": 5.9}],
    "SW801750": [{"code": "688256", "name": "寒武纪", "pct1d": 7.2},
                 {"code": "300308", "name": "中际旭创", "pct1d": 5.4}],
    "SW801880": [{"code": "601127", "name": "赛力斯", "pct1d": -6.3},
                 {"code": "002594", "name": "比亚迪", "pct1d": -4.1}],
    "SW801120": [{"code": "600519", "name": "贵州茅台", "pct1d": -2.0}],
    "SW801730": [{"code": "300750", "name": "宁德时代", "pct1d": -1.8}],
}


def build_raw_data() -> Dict[str, Any]:
    """返回与 RawData 字段对齐的演示数据。"""
    industry_list = [{"id": k, "name": v["name"]} for k, v in DAILY.items()]
    daily = {k: {"name": v["name"], "pct1d": v["pct1d"], "pct5d": v["pct5d"], "turnover": v["turnover"]}
             for k, v in DAILY.items()}
    return {
        "industry_list": industry_list,
        "daily": daily,
        "moneyflow": dict(MONEYFLOW),
        "index": dict(INDEX),
        "events": [dict(e) for e in EVENTS],
        "leading_stocks": LEADING_STOCKS,
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
    industry_level: str = "sw_l1"
    top_n: int = 5
    include_events: bool = True
    focus: str = "all"                 # all | strength | fund | event
    output_format: str = "both"        # json | markdown | both


@dataclass
class IndustryRow:
    rank: int
    industry_id: str
    industry_name: str
    pct_change_1d: float
    pct_change_5d: float
    turnover_yi: float
    net_flow_yi: float
    aggregate_method: str = "official"
    pct5d_missing: bool = False      # 5日动量历史拉取失败（如实标注，不伪造为 0）
    leading_stocks: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class IndustryEvent:
    industry_id: str
    industry_name: str
    event_type: str
    summary: str
    source: str
    publish_time: str
    fact_flag: str = "fact"


@dataclass
class Signal:
    industry_id: str
    industry_name: str
    signal: str
    direction: str                    # up | down | neutral
    strength: str                     # strong | medium | weak
    evidence: List[str] = field(default_factory=list)
    rule_id: str = ""


@dataclass
class SkillOutput:
    skill: str
    version: str
    run_at: str
    trade_date: str
    industry_level: str
    data_source: str
    degraded: bool
    degrade_trace: List[str] = field(default_factory=list)
    market_brief: str = ""
    industry_ranking: List[IndustryRow] = field(default_factory=list)
    industry_events: List[IndustryEvent] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    missing_items: List[str] = field(default_factory=list)
    disclaimer: str = ""
    error_code: Optional[str] = None
    error_msg: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ===========================================================================
# 四、可降级多源数据网关
# ===========================================================================
# ---------------------------------------------------------------------------
# 通用：安全浮点 / 带重试的网络调用 / 最近交易日推断
# ---------------------------------------------------------------------------
def _f(x) -> float:
    try:
        v = float(x)
        return v if v == v else 0.0  # NaN -> 0
    except Exception:
        return 0.0


def _robust_call(fn, desc: str = "", tries: int = 4, sleep: float = 1.0):
    """带重试的 akshare 网络调用（部分源偶发 'No tables found' 抖动）。"""
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
    """推断最近交易日（同花顺板块指数最后一根 K 线日期，回退到上一个工作日）。"""
    try:
        import akshare as ak  # type: ignore
        h = ak.stock_board_industry_index_ths(symbol="半导体",
                                             start_date="20261001", end_date="20261231")
        if h is not None and len(h):
            return str(h.iloc[-1]["日期"])
    except Exception:
        pass
    d = datetime.date.today()
    while d.weekday() >= 5:  # 跳过周末
        d -= datetime.timedelta(days=1)
    return d.isoformat()


class GatewayError(Exception):
    def __init__(self, code: str, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(f"[{code}] {msg}")


class DataSource:
    name = "base"

    def get_industry_list(self, level): raise NotImplementedError
    def get_daily(self, trade_date, level): raise NotImplementedError
    def get_moneyflow(self, trade_date): raise NotImplementedError
    def get_index(self, trade_date): raise NotImplementedError
    def get_events(self, trade_date): raise NotImplementedError


class DemoSource(DataSource):
    name = "demo"

    def get_industry_list(self, level): return build_raw_data()["industry_list"]
    def get_daily(self, trade_date, level): return build_raw_data()["daily"]
    def get_moneyflow(self, trade_date): return build_raw_data()["moneyflow"]
    def get_index(self, trade_date): return build_raw_data()["index"]
    def get_events(self, trade_date): return build_raw_data()["events"]


class TushareSource(DataSource):
    """tushare 适配器（优先源）。需配置 TUSHARE_TOKEN 才能工作。"""
    name = "tushare"

    def __init__(self):
        try:
            import tushare as ts  # type: ignore
        except Exception as e:
            raise RuntimeError(f"tushare 未安装: {e}")
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("未配置 TUSHARE_TOKEN")
        self.pro = ts.pro_api(token)

    def get_industry_list(self, level):
        # 接入示例：self.pro.index_classify(level='L1', src='SW')
        raise NotImplementedError("tushare 行业分类接口待接入")
    def get_daily(self, trade_date, level):
        raise NotImplementedError("tushare 申万行业日线待接入")  # sw_daily
    def get_moneyflow(self, trade_date):
        raise NotImplementedError("tushare 行业资金流待接入")      # 积分依赖
    def get_index(self, trade_date):
        raise NotImplementedError("tushare 指数日线待接入")
    def get_events(self, trade_date):
        return []  # tushare 不提供新闻，事件将降级到 akshare/tencent


class AkshareSource(DataSource):
    """akshare 适配器（次级源）。

    本沙箱/云环境 EastMoney 接口被 403 拦截，实际落地为「同花顺行业板块」口径：
      - 行情/换手/领涨股：stock_board_industry_summary_ths（约 90 个行业板块）
      - 5 日动量：stock_board_industry_index_ths（板块指数日线，按窗口拉取）
      - 资金流（主力净流入）：同上汇总表的「净流入」列（单位：亿元）
      - 指数：stock_zh_index_spot_sina（上证指数）
    口径说明：同花顺行业板块（约 90 个）≠ 申万一级 31；金额单位亿元、涨跌幅为%。
    行业新闻在同花顺/akshare 体系中无可靠分类源，get_events 如实抛错 -> IND_FLASH_002 降级。
    """
    name = "akshare"

    def __init__(self):
        try:
            import akshare as ak  # type: ignore
        except Exception as e:
            raise RuntimeError(f"akshare 未安装: {e}")
        self.ak = ak
        self._summary = None

    def _get_summary(self):
        if self._summary is None:
            self._summary = _robust_call(self.ak.stock_board_industry_summary_ths,
                                        desc="同花顺行业汇总")
        return self._summary

    def get_industry_list(self, level):
        df = self._get_summary()
        return [{"id": n, "name": n} for n in df["板块"].tolist()]

    def get_daily(self, trade_date, level):
        df = self._get_summary()
        boards = df["板块"].tolist()
        if not trade_date or trade_date in ("latest",):
            end_dt = datetime.date.today()
        else:
            end_dt = datetime.date.fromisoformat(trade_date)
        # 同花顺接口要求 YYYYMMDD（无横线），否则返回空/异常
        end = end_dt.strftime("%Y%m%d")
        start = (end_dt - datetime.timedelta(days=20)).strftime("%Y%m%d")
        pct5d: Dict[str, Optional[float]] = {}
        for n in boards:
            try:
                h = _robust_call(
                    lambda: self.ak.stock_board_industry_index_ths(
                        symbol=n, start_date=start, end_date=end),
                    desc=f"同花顺行业指数({n})", tries=3, sleep=0.3)
                if h is not None and len(h) >= 6:
                    c0 = _f(h.iloc[-6]["收盘价"]); c1 = _f(h.iloc[-1]["收盘价"])
                    if c0:
                        pct5d[n] = round((c1 / c0 - 1) * 100, 2)
                    else:
                        pct5d[n] = None  # 价格异常，标记缺失
                else:
                    pct5d[n] = None  # 历史不足 6 根，标记缺失
            except Exception:
                pct5d[n] = None  # 单板块历史缺失不致命，但如实标记（不伪造为 0）
        out: Dict[str, Any] = {}
        for _, r in df.iterrows():
            n = r["板块"]
            out[n] = {
                "name": n,
                "pct1d": _f(r["涨跌幅"]),
                "pct5d": pct5d.get(n, None),
                "turnover": _f(r["总成交额"]),  # 亿元
            }
        return out

    def get_moneyflow(self, trade_date):
        df = self._get_summary()
        return {r["板块"]: _f(r["净流入"]) for _, r in df.iterrows()}  # 亿元

    def get_index(self, trade_date):
        idx = _robust_call(self.ak.stock_zh_index_spot_sina, desc="新浪指数")
        row = idx[idx["名称"] == "上证指数"]
        if len(row):
            r = row.iloc[0]
            return {"name": "上证指数", "pct": _f(r["涨跌幅"]), "close": _f(r["最新价"])}
        raise RuntimeError("新浪指数未返回上证指数")

    def get_events(self, trade_date):
        # 行业新闻无可靠分类源（见 references/data-sources.md 第二节），如实降级。
        raise RuntimeError("akshare 无分类行业新闻源（事件流缺口）")


class TencentSource(DataSource):
    """腾讯财经网页源（兜底源）。行业需由成分股聚合，新闻稳定性低。"""
    name = "tencent_web"

    def get_industry_list(self, level):
        return [{"id": v, "name": k} for k, v in SW_INDUSTRIES.items()]
    def get_daily(self, trade_date, level):
        raise NotImplementedError("腾讯网页源无行业聚合接口，需由成分股聚合计算")
    def get_moneyflow(self, trade_date):
        raise NotImplementedError("腾讯网页源无行业资金流，显式缺失")
    def get_index(self, trade_date):
        raise NotImplementedError("腾讯网页源基础指数待接入")
    def get_events(self, trade_date):
        raise NotImplementedError("腾讯网页源新闻抓取待接入")


def _build_source(name: str):
    try:
        if name == "tushare":
            return TushareSource()
        if name == "akshare":
            return AkshareSource()
        if name == "tencent_web":
            return TencentSource()
        if name == "demo":
            return DemoSource()
    except Exception:
        return None
    return None


CATEGORIES = ["industry_list", "daily", "moneyflow", "index", "events"]


def fetch(inp: SkillInput, demo: bool = False) -> Dict[str, Any]:
    sources_order = ["demo"] if demo else list(GATEWAY_PRIORITY)
    instances = {s: _build_source(s) for s in sources_order}

    out = {
        "industry_list": [], "daily": {}, "moneyflow": {},
        "index": {}, "events": [], "leading_stocks": {},
        "source_meta": "", "degrade_trace": [], "missing_items": [],
    }
    degrade_trace: List[str] = []
    missing_items: List[str] = []
    level = inp.industry_level if inp.industry_level in ("sw_l1", "sw_l2") else "sw_l1"
    trade_date = inp.trade_date or "latest"

    for cat in CATEGORIES:
        used = None
        for s in sources_order:
            inst = instances.get(s)
            if inst is None:
                degrade_trace.append(f"{cat}: {s} 不可用（未装/无token），跳过")
                continue
            try:
                if cat == "industry_list":
                    val = inst.get_industry_list(level)
                elif cat == "daily":
                    val = inst.get_daily(trade_date, level)
                elif cat == "moneyflow":
                    val = inst.get_moneyflow(trade_date)
                elif cat == "index":
                    val = inst.get_index(trade_date)
                else:
                    val = inst.get_events(trade_date)
                if val is None or (isinstance(val, (list, dict)) and len(val) == 0 and cat != "events"):
                    if cat == "events":
                        out[cat] = []
                        used = s
                        break
                    degrade_trace.append(f"{cat}: {s} 返回空，尝试下一级")
                    continue
                out[cat] = val
                used = s
                break
            except Exception:
                degrade_trace.append(f"{cat}: {s} 异常，尝试下一级")
                continue
        if used is None:
            missing_items.append(cat)
        elif cat == "daily":
            out["source_meta"] = used

    if not out["industry_list"] or not out["daily"]:
        raise GatewayError("IND_FLASH_001", ERROR_CODES["IND_FLASH_001"])

    if demo:
        out["leading_stocks"] = build_raw_data()["leading_stocks"]

    out["degrade_trace"] = degrade_trace
    out["missing_items"] = missing_items
    return out


# ===========================================================================
# 五、语义标准化（最小实现）
# ===========================================================================
def align_trade_date(s: str) -> str:
    if s:
        return s
    return TRADE_DATE  # 演示/兜底：最近交易日


def normalize_event(e: Dict[str, Any]) -> Dict[str, Any]:
    iid = e.get("industry_id") or ""
    name = e.get("industry_name") or SW_INDUSTRIES.get(iid, iid)
    return {
        "industry_id": iid,
        "industry_name": name,
        "event_type": e.get("event_type", "other"),
        "summary": e.get("summary", ""),
        "source": e.get("source", ""),
        "publish_time": e.get("publish_time", ""),
        "fact_flag": e.get("fact_flag", "fact"),
    }


def validate_schema(d: Dict[str, Any]) -> List[str]:
    required = ["skill", "trade_date", "data_source", "industry_ranking", "signals"]
    return [k for k in required if k not in d]


# ===========================================================================
# 六、信号规则引擎（R01-R06）
# ===========================================================================
def apply_rules(ranked: List[Dict[str, Any]], events: List[Dict[str, Any]],
                index: Dict[str, Any], th: SignalThresholds) -> List[Signal]:
    signals: List[Signal] = []
    top_n = max(th.rank_top_n, 1)
    ev_by: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        ev_by.setdefault(e.get("industry_id") or e.get("industry_name"), []).append(e)

    for row in ranked:
        name = row["industry_name"]
        iid = row.get("industry_id", name)
        rank = row.get("rank", 999)
        pct1d = float(row.get("pct1d", 0.0))
        pct5d = float(row.get("pct5d") or 0.0)   # 缺失按 0（不误触发 R01）
        net = float(row.get("net_flow_yi", 0.0))

        # R01 强势延续
        if rank <= top_n and pct5d > th.momentum_5d_strong:
            signals.append(Signal(iid, name, "强势延续", "up",
                                  "strong" if pct5d > 5 else "medium",
                                  [f"涨幅榜第{rank}", f"5日累计涨幅 {pct5d:.2f}%"], "R01"))
        # R02 资金异动
        if net > th.net_inflow_abs:
            signals.append(Signal(iid, name, "资金异动", "up",
                                  "strong" if net > 2 * th.net_inflow_abs else "medium",
                                  [f"单日净流入 {net:.1f} 亿元（阈值 {th.net_inflow_abs}）"], "R02"))
        # R03 持续失血
        if net < -th.net_outflow_3d:
            signals.append(Signal(iid, name, "持续失血", "down", "strong",
                                  [f"净流出累计 {abs(net):.1f} 亿元（阈值 {th.net_outflow_3d}）"], "R03"))
        # R04 走弱预警（涨幅榜前列但资金净流出）
        if rank <= top_n and net < 0:
            signals.append(Signal(iid, name, "走弱预警", "neutral", "weak",
                                  [f"涨幅榜第{rank} 但资金净流出 {abs(net):.1f} 亿元"], "R04"))
        # R05 事件驱动异动
        for e in ev_by.get(iid, []) + ev_by.get(name, []):
            if abs(pct1d) >= th.event_move_abs:
                direction = "up" if pct1d > 0 else "down"
                tag = "【传闻】" if e.get("fact_flag") == "rumor" else ""
                signals.append(Signal(iid, name, "事件驱动异动", direction, "medium",
                                      [f"事件[{e.get('event_type')}]{tag}: {e.get('summary')}",
                                       f"当日涨跌幅 {pct1d:.2f}%"], "R05"))
        # R06 极端波动
        if abs(pct1d) > th.extreme_move_abs:
            signals.append(Signal(iid, name, "极端波动", "up" if pct1d > 0 else "down", "strong",
                                  [f"单日涨跌幅 {pct1d:.2f}%（阈值 ±{th.extreme_move_abs}）"], "R06"))

    order = {"R06": 0, "R01": 1, "R02": 2, "R05": 3, "R03": 4, "R04": 5}
    signals.sort(key=lambda s: order.get(s.rule_id, 9))
    return signals


# ===========================================================================
# 七、报告生成（Markdown / HTML）
# ===========================================================================
# 信号图标体系（直观符号）—— 与报告「图标说明」、SKILL.md 保持一致
SIGNAL_ICONS = {
    "强势延续": "🔥",      # 强者恒强
    "资金异动": "💰",      # 主力净流入异动
    "持续失血": "🩸",      # 主力持续净流出
    "走弱预警": "⚠️",      # 涨幅居前但资金背离
    "事件驱动异动": "📰",  # 受事件驱动异动
    "极端波动": "⚡",      # 单日涨跌幅极端
}
DIRECTION_ICONS = {"up": "↑ 看多", "down": "↓ 看空", "neutral": "→ 中性"}
STRENGTH_ICONS = {"strong": "🔴 强", "medium": "🟠 中", "weak": "⚪ 弱"}

SIGNAL_LEGEND = (
    "> **图标说明**　🔥强势延续｜💰资金异动｜🩸持续失血｜⚠️走弱预警｜📰事件驱动｜⚡极端波动　"
    "·　方向 **↑看多 ↓看空 →中性**　·　强度 **🔴强 🟠中 ⚪弱**"
)


def to_markdown(out: SkillOutput, focus: str = "all") -> str:
    L: List[str] = []
    src = out.data_source or "unknown"
    if out.data_source == "tushare":
        scope = "申万一级 31 行业"
    elif out.data_source == "demo":
        scope = "申万一级 31 行业（演示）"
    else:
        scope = "同花顺行业板块（约90个）"
    L.append(f"# 行业速报（{out.trade_date}）")
    L.append("")
    L.append(f"> 数据范围：{scope} | 生成时间：{out.run_at} | 数据状态：{out.data_source}")
    if out.degraded:
        L.append("")
        L.append("> ⚠️ 本次发生数据源降级，结论仅供参考：" +
                 ("；".join(out.degrade_trace) or "见下方数据说明"))
    L.append("")

    # 一、一句话概览
    if focus in ("all", "strength", "fund", "event"):
        L.append("## 一、一句话概览")
        L.append(out.market_brief or "—")
        L.append("")

    # 二、行业强弱榜
    if focus in ("all", "strength"):
        top_n = getattr(out, "_top_n", 5)
        rows = out.industry_ranking
        ups = sorted([r for r in rows if r.pct_change_1d > 0], key=lambda r: -r.pct_change_1d)
        downs = sorted([r for r in rows if r.pct_change_1d < 0], key=lambda r: r.pct_change_1d)
        L.append(f"## 二、行业强弱榜（Top {top_n}）")
        L.append("| 排名 | 行业 | 当日% | 近5日% | 换手% | 净流入(亿) |")
        L.append("| --- | --- | --- | --- | --- | --- |")
        for r in ups[:out._top_n]:
            p5 = "—" if r.pct5d_missing else f"{r.pct_change_5d:+.2f}"
            L.append(f"| {r.rank} | {r.industry_name} | ▲{r.pct_change_1d:+.2f} | "
                     f"{p5} | {r.turnover_yi:.1f} | {r.net_flow_yi:+.1f} |")
        for r in downs[:out._top_n]:
            p5 = "—" if r.pct5d_missing else f"{r.pct_change_5d:+.2f}"
            L.append(f"| {r.rank} | {r.industry_name} | ▼{r.pct_change_1d:+.2f} | "
                     f"{p5} | {r.turnover_yi:.1f} | {r.net_flow_yi:+.1f} |")
        L.append("")

    # 三、资金流向
    if focus in ("all", "fund"):
        top_n = getattr(out, "_top_n", 5)
        net_sorted = sorted(out.industry_ranking, key=lambda r: -r.net_flow_yi)
        top_in = net_sorted[:top_n]
        top_out = net_sorted[-top_n:][::-1]
        L.append(f"## 三、资金流向（Top {out._top_n}）")
        L.append("| 行业 | 主力净流入(亿) | 净流入/成交额% |")
        L.append("| --- | --- | --- |")
        for r in top_in:
            ratio = (r.net_flow_yi / r.turnover_yi * 100) if r.turnover_yi else 0.0
            L.append(f"| {r.industry_name} | {r.net_flow_yi:+.1f} | {ratio:.1f} |")
        if top_out:
            L.append("")
            L.append("净流出居前：" + "、".join(
                f"{r.industry_name}({r.net_flow_yi:+.1f}亿)" for r in top_out))
        L.append("")

    # 四、事件速递
    if focus in ("all", "event"):
        L.append("## 四、事件速递")
        if out.industry_events:
            for e in out.industry_events:
                tag = "【传闻】" if e.fact_flag == "rumor" else ""
                L.append(f"- 【{e.industry_name}】{tag}{e.summary}（来源：{e.source}，{e.publish_time}）")
        else:
            miss = "事件源未覆盖" if "events" in out.missing_items else "无"
            L.append(f"- 本交易日未采集到行业事件（{miss}）")
        L.append("")

    # 五、信号解读
    if focus in ("all", "strength", "fund", "event"):
        L.append("## 五、信号解读（R01-R06）")
        L.append(SIGNAL_LEGEND)
        L.append("")
        if out.signals:
            L.append("| 类型 | 行业 | 方向 | 强度 | 关键证据 |")
            L.append("| --- | --- | --- | --- | --- |")
            for s in out.signals:
                icon = SIGNAL_ICONS.get(s.signal, "•")
                direction = DIRECTION_ICONS.get(s.direction, s.direction)
                strength = STRENGTH_ICONS.get(s.strength, s.strength)
                ev = "；".join(s.evidence) if s.evidence else "—"
                L.append(f"| {icon} **{s.rule_id} {s.signal}** | {s.industry_name} | {direction} | {strength} | {ev} |")
        else:
            L.append("- 当前无命中信号")
        L.append("")

    # 六、数据说明与免责
    L.append("## 六、数据说明与免责")
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
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:900px;margin:0 auto;padding:20px;color:#1f2937;line-height:1.8;}
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
    """极简 Markdown → HTML（仅覆盖本报告用到的 #/##/表格/>/列表）。"""
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


def to_html(out: SkillOutput, focus: str = "all") -> str:
    md = to_markdown(out, focus=focus)
    return _md_to_html_simple(md, f"行业速报（{out.trade_date}）")


# ===========================================================================
# 八、主流程（七步 SOP 编排）
# ===========================================================================
def run_skill(inp: SkillInput, demo: bool = False) -> SkillOutput:
    if not inp.trade_date and not demo:
        inp.trade_date = _latest_trade_date()
    trade_date = align_trade_date(inp.trade_date)
    level = inp.industry_level if inp.industry_level in ("sw_l1", "sw_l2") else "sw_l1"
    top_n = max(1, int(inp.top_n))
    run_at = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

    try:
        raw = fetch(inp, demo=demo)
    except GatewayError as ge:
        return SkillOutput(
            skill=SKILL_NAME, version=SKILL_VERSION, run_at=run_at, trade_date=trade_date,
            industry_level=level, data_source="none", degraded=True, market_brief="",
            error_code=ge.code,
            error_msg=f"{ge.msg}（{ERROR_CODES.get(ge.code, '')}）",
            disclaimer=DISCLAIMER,
        )

    source_meta = raw.get("source_meta") or "unknown"
    degrade_trace = list(raw.get("degrade_trace", []))
    missing_items = list(raw.get("missing_items", []))
    if "events" in missing_items:
        degrade_trace.append(f"事件采集：IND_FLASH_002 {ERROR_CODES['IND_FLASH_002']}")

    daily = raw.get("daily", {})
    moneyflow = raw.get("moneyflow", {})
    rows_raw = []
    for iid, d in daily.items():
        name = d.get("name") or iid
        p5 = d.get("pct5d", None)
        rows_raw.append({
            "industry_id": iid, "industry_name": name,
            "pct1d": float(d.get("pct1d", 0.0)),
            "pct5d": (float(p5) if p5 is not None else None),
            "pct5d_missing": (p5 is None),
            "turnover": float(d.get("turnover", 0.0)),
            "net_flow_yi": float(moneyflow.get(iid, 0.0)),
            "aggregate_method": "official",
        })
    rows_raw.sort(key=lambda r: -r["pct1d"])
    for i, r in enumerate(rows_raw, start=1):
        r["rank"] = i

    ls_map = raw.get("leading_stocks", {})
    ranking: List[IndustryRow] = []
    for r in rows_raw:
        leading = [{"code": s["code"], "name": s["name"], "pct1d": float(s["pct1d"])}
                   for s in ls_map.get(r["industry_id"], [])[:DEFAULT_THRESHOLDS.leading_stocks]]
        ranking.append(IndustryRow(
            rank=r["rank"], industry_id=r["industry_id"], industry_name=r["industry_name"],
            pct_change_1d=r["pct1d"], pct_change_5d=(r["pct5d"] or 0.0),
            turnover_yi=r["turnover"], net_flow_yi=r["net_flow_yi"],
            aggregate_method=r["aggregate_method"], pct5d_missing=r["pct5d_missing"],
            leading_stocks=leading,
        ))

    events_raw = raw.get("events", []) if inp.include_events else []
    events_norm = [normalize_event(e) for e in events_raw]
    industry_events = [IndustryEvent(**{k: e.get(k) for k in
                     ("industry_id", "industry_name", "event_type", "summary",
                      "source", "publish_time", "fact_flag")}) for e in events_norm]

    sigs = apply_rules(rows_raw, events_norm, raw.get("index", {}), DEFAULT_THRESHOLDS)

    idx = raw.get("index", {})
    up_cnt = sum(1 for r in rows_raw if r["pct1d"] > 0)
    total = len(rows_raw)
    idx_name = idx.get("name", "大盘")
    idx_pct = idx.get("pct", 0.0)
    market_brief = (f"{idx_name}收{idx_pct:+.2f}%，{total} 个行业中 {up_cnt} 个上涨"
                   + ("；行业事件正常采集" if events_norm else "；本日无行业事件覆盖"))

    degraded = bool([m for m in missing_items if m != "events"])  # 仅事件缺口不触发顶部降级横幅
    out = SkillOutput(
        skill=SKILL_NAME, version=SKILL_VERSION, run_at=run_at, trade_date=trade_date,
        industry_level=level, data_source=source_meta, degraded=degraded,
        degrade_trace=degrade_trace, market_brief=market_brief, industry_ranking=ranking,
        industry_events=industry_events, signals=sigs, missing_items=missing_items,
        disclaimer=DISCLAIMER,
    )
    out._top_n = top_n  # 供报告使用（非契约字段）
    out._focus = inp.focus

    schema_missing = validate_schema(out.to_dict())
    if schema_missing:
        out.error_code = "SCHEMA_INVALID"
        out.error_msg = "输出缺失字段: " + ",".join(schema_missing)

    _register_call(out)
    return out


def _register_call(out: SkillOutput) -> None:
    print(f"[register] skill={out.skill} trade_date={out.trade_date} "
          f"source={out.data_source} degraded={out.degraded} "
          f"ranking={len(out.industry_ranking)} signals={len(out.signals)}", file=sys.stderr)


# ===========================================================================
# 九、JSON payload（对齐 references/EXAMPLE_OUTPUT.md 扁平结构）
# ===========================================================================
def to_payload(out: SkillOutput) -> Dict[str, Any]:
    top_n = getattr(out, "_top_n", 5)
    strength = sorted(out.industry_ranking, key=lambda r: -r.pct_change_1d)[:top_n]
    fund = sorted([r for r in out.industry_ranking if r.net_flow_yi > 0],
                  key=lambda r: -r.net_flow_yi)[:top_n]
    return {
        "trade_date": out.trade_date,
        "summary": out.market_brief,
        "strength_rank": [
            {"industry": r.industry_name, "pct1d": round(r.pct_change_1d, 2),
             "pct5d": (None if r.pct5d_missing else round(r.pct_change_5d, 2)),
             "turnover": round(r.turnover_yi, 1)}
            for r in strength],
        "fund_flow": [
            {"industry": r.industry_name, "net_inflow": round(r.net_flow_yi, 1),
             "inflow_ratio": round(r.net_flow_yi / r.turnover_yi * 100, 1) if r.turnover_yi else 0.0}
            for r in fund],
        "events": [
            {"industry": e.industry_name, "title": e.summary, "source": e.source, "time": e.publish_time}
            for e in out.industry_events],
        "signals": [
            {"rule": s.rule_id, "name": s.signal, "industry": s.industry_name,
             "direction": s.direction, "evidence": s.evidence}
            for s in out.signals],
        "meta": {
            "data_source": out.data_source,
            "degraded": "demo" if out.data_source == "demo" else ("partial" if out.degraded else "none"),
            "degrade_trace": out.degrade_trace,
        },
    }


def render(out: SkillOutput, fmt: str = "both") -> str:
    focus = getattr(out, "_focus", "all")
    md = to_markdown(out, focus=focus)
    if fmt == "markdown":
        return md
    if fmt == "json":
        return json.dumps(to_payload(out), ensure_ascii=False, indent=2)
    return ("<!-- JSON -->\n" + json.dumps(to_payload(out), ensure_ascii=False, indent=2)
            + "\n\n<!-- MARKDOWN -->\n" + md)


# ===========================================================================
# 十、CLI
# ===========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="行业速报 industry_brief Skill · 可运行脚本")
    parser.add_argument("--trade-date", default="", help="YYYY-MM-DD，空=最近交易日")
    parser.add_argument("--industry-level", default="sw_l1", choices=["sw_l1", "sw_l2"])
    parser.add_argument("--top-n", type=int, default=5, help="强弱榜 / 资金榜各取前 N")
    parser.add_argument("--focus", default="all", choices=["all", "strength", "fund", "event"])
    parser.add_argument("--no-events", action="store_true", help="关闭行业事件采集")
    parser.add_argument("--output-format", default="both", choices=["json", "markdown", "both"])
    parser.add_argument("--out", default="", help="落盘目录，如 files/report")
    parser.add_argument("--demo", action="store_true",
                        help="使用内置演示数据，无需 token / 外部库即可运行")
    args = parser.parse_args()

    inp = SkillInput(
        trade_date=args.trade_date, industry_level=args.industry_level, top_n=args.top_n,
        include_events=not args.no_events, focus=args.focus, output_format=args.output_format,
    )

    out = run_skill(inp, demo=args.demo)

    if out.error_code == "IND_FLASH_001":
        print(json.dumps(out.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(2)

    text = render(out, args.output_format)
    print(text)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        if args.output_format in ("markdown", "both"):
            with open(os.path.join(args.out, f"{out.trade_date}_行业速报.md"), "w", encoding="utf-8") as f:
                f.write(to_markdown(out, focus=args.focus))
        if args.output_format in ("html", "both"):
            with open(os.path.join(args.out, f"{out.trade_date}_行业速报.html"), "w", encoding="utf-8") as f:
                f.write(to_html(out, focus=args.focus))
        print(f"[ok] 已落盘 {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
