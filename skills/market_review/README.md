# 行情复盘类

> 组件层 · 行情复盘类

本目录下的 Skill 遵循 `skills/base/skill_base.py` 定义的统一契约，可被上层任意业务场景（选股/诊股/盘前/盘中/尾盘/策略）编排调用。

> 注意：已入库的 `market_daily_review`（股市每日收评）为 `script_based` 形态，其取数直连开源数据源（Tushare > Akshare > 腾讯财经/东方财富，四级可降级，见其 `references/data-sources.md`），**不经**体系 `ctx.gateway`（`calls_gateway: false`，语义为"不经网关"，非"不取数"），与 `industry_brief` 同款结构。已入库的 `overnight_review`（隔夜外围市场复盘）为 `llm_prompt` 形态，取数经三个已连接 MCP（mx-ds-mcp / westock-mcp / tdx-connector），同样**不经** `ctx.gateway`。

## 包含的 Skill

| Skill ID | 名称 | 状态 | 说明 |
|----------|------|------|------|
| `market_daily_review` | 股市每日收评 | 已入库（script_based） | 基于开源数据源，自动生成 A 股/港股每个交易日的收盘点评报告 |
| `overnight_review` | 隔夜外围市场复盘 | 已入库（llm_prompt） | 生成面向A股盘前/盘中/盘后复核的隔夜外围市场复盘（今日五件事决策层+常驻决策时间线） |
