---
name: racing-quant-pick
description: |
  【赛马量化策略选股技能】从远程量化策略数据库（MySQL）智能匹配最符合用户需求的量化策略，
  获取策略对应的最新持仓个股，转化为可溯源的「选股池 + 策略画像」，并可衔接个股深度分析。
  支持「明确需求」「指定策略 ID/名称」「仅查策略」「互动偏好匹配」四种入口。
  触发词：量化选股、策略选股、数据库选股、racing quant、赛马量化、量化分析、AI选股。
version: 1.0.0
author: Warwick
source: 策略选股模块改编自 racing-quant-ai（chenxyzcyxpp / Warwick）
license: MIT
metadata:
  hermes:
    tags: [量化选股, 策略选股, 数据库选股, 赛马量化, 持仓获取, a股, racing-quant-pick]
    related_skills: [stock-5d-deep-analysis, macro-analysis, industry-brief]
---

# 赛马量化策略选股（量化策略库 → 选股池）

## 一、技能定位

本技能是 invest-skill 组件层的**量化策略信号**能力：把「远程量化策略库」中的策略，
按用户需求智能匹配，并拉取其**最新一期持仓个股**，输出结构化的选股池与策略画像。
它是「信号 → 资产」的匹配入口，可与 `stock_5d_deep_analysis`（五维深度分析）衔接，
对选出的持仓个股进一步诊断。

> 注意：本技能产出的是**策略信号层的标的池**（策略怎么选的），不是行情分析。
> 个股的质量判断应交给 `stock_5d_deep_analysis` 等标的分析 Skill。

## 二、策略库数据模型（详见 references/strategy-schema.md）

策略库为远程 MySQL，含两张核心表：

| 表 | 作用 | 关键字段 |
|----|------|----------|
| `strategy_information`（主策略表） | 策略元信息与对应持仓表名 | `strategy_id`、`strategy_name`、`strategy_name_cn`、`strategy_cat`、`strategy_desc`、`strategy_summ`、`how_to_trade`、`if_recommended`、`strategy_table` |
| `{strategy_table}`（持仓表，每张策略一张） | 该策略历史与最新持仓 | `trade_date`、`strategy_id`、`trading_info`(JSON: {代码: 权重})、`update_time` |

匹配逻辑：先在主表用关键词/分类/偏好检索策略 → 取到 `strategy_table` → 查持仓表取**最新一期** `trade_date` 的 `trading_info` → 得到「代码: 权重」字典。

## 三、核心工作流

**入口 A｜用户有明确需求 / 指定策略**
1. 连接策略库（见第四节可配置 endpoint）。
2. 明确指定 `strategy_id/名称` → 直接定位；否则用需求关键词在 `strategy_desc` 语义匹配 1–3 个策略。
3. 取匹配策略的最新持仓（默认前 10–20 只，取 `trading_info` 解析为 代码/名称/权重）。
4. 对持仓个股可选衔接 `stock_5d_deep_analysis` 做深度分析（默认前 5 只，由 `top_n` 控制）。
5. 按 `references/output-template.md` 输出完整报告。

**入口 B｜用户只想浏览策略**
1. 按关键词/分类筛选策略，仅输出策略列表（名称/中文名/简介/分类/是否推荐）。
2. 用户选定后，再执行入口 A 的 3–5 步（不自动默认选中任何策略）。

**入口 C｜偏好不明确（互动匹配，优先）**
1. 主动提问：投资周期（短/中/长）、风险承受（保守/稳健/激进）、风格（价值成长/红利低波/动量趋势/事件驱动）、行业偏好、特殊需求。
2. 将偏好转为关键词，在 `strategy_desc` 语义匹配 3–5 个策略，**请用户确认**后再拉持仓。

> 兜底规则：若关键词/偏好/分类匹配出 ≥2 条策略，仅展示【策略名称 + 中文简介】列表，等用户手动选定，不自动默认。

## 四、策略库连接配置（⚠️ 红线）

- 连接参数 **必须由使用者自行配置**，通过环境变量或 `db_config` 传入，
  **禁止硬编码 IP/账号/密码**；本技能与参考脚本**不内置任何默认数据源**。
- 必填项：`RACING_DB_HOST` / `RACING_DB_USER` / `RACING_DB_PASSWORD` / `RACING_DB_NAME`
  （端口可选，缺省 3306）；缺失时明确报错退出，不回退到任何隐含默认值。
- 请连接**自有或已获授权**的策略库；任何外部策略库都视为「外部策略信号源」，
  可用性、合规性与数据授权由接入方自行负责。
- 该连接是**策略信号源**，与行情数据源（Tushare/Akshare/东财）分层，不计入行情网关降级链。
- 连接失败 → 如实返回错误，不得编造持仓或返回占位值。
- 配置说明见 `references/strategy-schema.md` 与 `scripts/fetch_strategy_positions.py`。

## 五、与个股分析衔接（可选）

当需要对选出的持仓个股做质量判断时，调用 `stock_5d_deep_analysis`（五维深度分析）：
对前 `top_n` 只个股逐一输出五维报告，再汇总到综合总结。本技能**不替代**个股分析，
仅负责「选」与「策略画像」。

## 六、输出格式（详见 references/output-template.md）

报告须包含：
- 策略信息（名称/ID/中文名/分类/简介/描述/调仓规则/是否推荐）
- 持仓列表（股票代码 / 名称 / 占比权重）
- 个股分析（可选，前 `top_n` 只按五维框架）
- 综合总结（策略优势、风险提示、投资建议）
- 信息来源注释（公开研报、微信公众号深度报告标题）
- 免责声明（本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。）

## 七、工具调用规范

- 取策略持仓：通过可配置 MySQL 连接（脚本 `scripts/fetch_strategy_positions.py` 或 MySQL MCP）。
- 个股公开信息：`WebSearch` / `wechat-article-search`（机构研报、公众号深度报告）。
- 个股深度分析：调用 `stock_5d_deep_analysis` 或对应工具。
- 严禁编造持仓、策略描述、研报标题；无法获取的数据如实标 N/A。

## 八、红线与陷阱

1. 不自动默认选中任一策略（≥2 个匹配时须用户确认）。
2. 不编造数据；连接/查询失败如实报错。
3. 公开策略库为第三方外部源，可用性不保证，须可配置替换。
4. 本技能只做「选股池 + 策略画像」，不替代行情/个股分析，不涉交易执行（无下单逻辑）。
