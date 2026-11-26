# 标的分析类

> 组件层 · 标的分析类

本目录下的 Skill 遵循 `skills/base/skill_base.py` 定义的统一契约，
统一通过 `ctx.gateway`（可降级数据网关）取数，不直接接触底层数据源，
可被上层任意业务场景（选股/诊股/盘前/盘中/尾盘/策略）编排调用。

## 包含的 Skill

| Skill ID | 名称 | 说明 |
|----------|------|------|
| `stock_5d_deep_analysis` | 股票五维深度分析 | 单只股票五维深度分析，可选叠加同业/行业对标 |
| `stock_comparative_analysis` | 股票对比分析 | 多标的（2-5 只，含 A 股及 A+H 混合）五维深度对比分析 |
| `value_investing` | 价值投资分析 | 自上而下的基本面价值投资框架：五步分析（宏观/行业/SWOT/估值/结论）、Step 0 取数校验、可选四层打分卡；好公司≠好股票、价值≠价格 |
| `fund_analysis` | 基金分析报告 | 单只基金全面分析报告 |
| `fund_compare` | 基金对比分析 | 多只基金横向对比分析 |
| `fund_manager_profile` | 基金经理画像 | 刻画基金经理风格与业绩画像 |
| `fund_manager_consistency` | 基金经理观点&持仓一致性分析 | 分析基金经理观点与持仓的一致性 |
