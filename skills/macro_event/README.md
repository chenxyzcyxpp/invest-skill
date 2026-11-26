# 宏观 & 事件类

> 组件层 · 宏观 & 事件类

本目录下的 Skill 遵循 `skills/base/skill_base.py` 定义的统一契约，
统一通过 `ctx.gateway`（可降级数据网关）取数，不直接接触底层数据源，
可被上层任意业务场景（选股/诊股/盘前/盘中/尾盘/策略）编排调用。

## 包含的 Skill

| Skill ID | 名称 | 说明 |
|----------|------|------|
| `policy_interpret` | 政策解读 | 对宏观政策进行解读与影响分析 |
| `sentiment_risk_warning` | 舆情风险预警 | 监测舆情异动并输出风险预警信号 |
| `macro_analysis` | 宏观经济分析 | 分析宏观经济指标与周期位置 |
| `market_hotspot` | 股票市场热点解读 | 解读市场热点板块与题材轮动 |
| `industry_brief` | 行业速报 | 生成行业动态与事件速报 |
| `concept_chain_analysis` | 主题产业链深度分析 | 产业链纵深拆解（上/中/下游 × 核心/弹性/补涨），可选持仓交叉 |
| `a_share_bottom_monitor` | A股底部信号监控 | 指数抄底位置监控（2014-2026 十二年回测信号地图）+ 半年度自更新 |
| `policy_bottom_monitor` | 底部政策信号助手 | 政策托底强度双轴分级（S/A/B/C/D），与量价信号叠加输出综合抄底判断 |
