# 主观策略类

> 组件层 · 主观策略类

本目录承载**主观 / 基本面分析驱动**的 Skill：以 LLM 八步分析框架、人工研判逻辑
对个股 / 策略做深度评估，区别于量化策略类（quant_strategy）的「信号 / 模型驱动」。

> 架构说明：本层 Skill 取数直连外部数据源（Tushare 等），**不经 ctx.gateway**
> （见各 Skill 的 `calls_gateway=false`）。这是与组件层契约「统一走网关」的已知缺口，
> 待后续统一改造。

## 包含的 Skill

| Skill ID | 名称 | 说明 |
|----------|------|------|
| `aggressive_growth_strategy` | 激进成长策略 | 基于 Tushare 的 A 股小盘成长股评估框架：中证2000轮动、八步分析、综合评级、高评级入池 |
