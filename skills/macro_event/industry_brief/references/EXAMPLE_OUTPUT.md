# 输出示例

本文档给出行业速报的结构化 `data`（JSON）完整示例与字段说明，以及 Markdown 六段式主干示例。

## 一、结构化输出示例（data）

```json
{
  "trade_date": "2026-10-16",
  "summary": "全市场 18 涨 13 跌，电子、半导体领涨，地产链持续失血；资金向硬科技聚集，R05 半导体事件驱动升温。",
  "strength_rank": [
    {"industry": "电子",     "pct1d": 2.31, "pct5d": 5.12, "turnover": 3.4},
    {"industry": "电力设备", "pct1d": 1.86, "pct5d": 3.94, "turnover": 2.8},
    {"industry": "医药生物", "pct1d": 1.12, "pct5d": 2.10, "turnover": 1.9}
  ],
  "fund_flow": [
    {"industry": "电子",     "net_inflow": 42.6, "inflow_ratio": 2.1},
    {"industry": "电力设备", "net_inflow": 28.3, "inflow_ratio": 1.6},
    {"industry": "食品饮料", "net_inflow": 15.1, "inflow_ratio": 1.0}
  ],
  "events": [
    {"industry": "半导体", "title": "某存储龙头上调四季度指引，行业景气度超预期", "source": "财联社", "time": "2026-10-15 20:30"},
    {"industry": "房地产", "title": "多地优化限购政策，地产链情绪修复", "source": "新华网", "time": "2026-10-16 09:15"}
  ],
  "signals": [
    {"rule": "R01", "name": "强势延续", "industry": "电子", "direction": "bullish",
     "evidence": {"pct5d": 5.12, "pct1d": 2.31, "threshold_pct5d": 3.0}},
    {"rule": "R02", "name": "资金异动", "industry": "电子", "direction": "bullish",
     "evidence": {"net_inflow": 42.6, "inflow_ratio": 2.1, "rank": 1}},
    {"rule": "R03", "name": "持续失血", "industry": "房地产", "direction": "bearish",
     "evidence": {"pct5d": -4.20, "net_inflow": -12.4}},
    {"rule": "R05", "name": "事件驱动", "industry": "半导体", "direction": "watch",
     "evidence": {"event": "某存储龙头上调指引", "source": "财联社"}}
  ],
  "meta": {
    "data_source": "tushare>akshare",
    "degraded": "partial",
    "degrade_trace": {"tushare": "ok", "akshare": "fail: timeout", "tencent": "skip: used akshare", "news": "ok: sentiment_stream"}
  }
}
```

## 二、字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | string | 速报基准交易日，YYYY-MM-DD |
| summary | string | 一句话概览：涨跌分布 + 主线判断 |
| strength_rank[] | array | 行业强弱榜（按 pct1d 降序取 Top N） |
| strength_rank[].industry | string | 申万一级行业名 |
| strength_rank[].pct1d | number | 当日涨跌幅 % |
| strength_rank[].pct5d | number | 近 5 日涨跌幅 % |
| strength_rank[].turnover | number | 换手率 % |
| fund_flow[] | array | 资金流向榜（按净流入降序取 Top N） |
| fund_flow[].net_inflow | number | 主力净流入（亿元，板块口径） |
| fund_flow[].inflow_ratio | number | 净流入 / 成交额 % |
| events[] | array | 事件速递（R05 输入） |
| events[].industry / title / source / time | string | 行业 / 标题 / 来源 / 时间 |
| signals[] | array | 命中信号 R01-R06 |
| signals[].rule | string | 规则编号 R01-R06 |
| signals[].direction | string | bullish / bearish / watch |
| signals[].evidence | object | 命中证据：字段 + 数值 + 阈值 |
| meta.data_source | string | 实际数据来源链（如 `tushare>akshare`） |
| meta.degraded | string | `none` / `partial` / `demo` |
| meta.degrade_trace | object | 各源成败明细 |

## 三、Markdown 六段式主干示例

```markdown
# 行业速报（2026-10-16）

> 数据范围：申万一级 31 行业 | 生成时间：2026-10-16 16:30 | 数据状态：partial

## 一、一句话概览
全市场 18 涨 13 跌，电子、半导体领涨，地产链持续失血；资金向硬科技聚集。

## 二、行业强弱榜（Top 3）
| 排名 | 行业 | 当日% | 近5日% | 换手% |
|---|---|---|---|---|
| 1 | 电子 | +2.31 | +5.12 | 3.4 |
| 2 | 电力设备 | +1.86 | +3.94 | 2.8 |
| 3 | 医药生物 | +1.12 | +2.10 | 1.9 |

## 三、资金流向（Top 3）
| 行业 | 主力净流入(亿) | 净流入/成交额% |
|---|---|---|
| 电子 | 42.6 | 2.1 |
| 电力设备 | 28.3 | 1.6 |
| 食品饮料 | 15.1 | 1.0 |

## 四、事件速递
- 【半导体】某存储龙头上调四季度指引，行业景气度超预期（来源：财联社，2026-10-15 20:30）

## 五、信号解读（R01-R06）
- **R01 强势延续** · 电子：pct5d +5.12%、pct1d +2.31% → 强势延续 [证据]
- **R03 持续失血** · 房地产：pct5d -4.20%、资金净流出 → 走弱 [证据]

## 六、数据说明与免责
- 数据来源：tushare>akshare；降级标记：partial；轨迹：tushare ok / akshare timeout / tencent skip
- 免责声明：本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
```
