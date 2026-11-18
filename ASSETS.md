# invest-skill 资产清单（Skill Catalog）

> 本文件维护 `invest-skill` 项目中**所有 Skill 资产**的目录列表与功能简介。
> 每段资产包含：目录路径、分类、作者、版本、形态、功能简介、数据来源、状态。
> 形态说明：`script_based`=提示词+可运行脚本；`llm_prompt`=纯提示词；`base_skill`=已包装为 BaseSkill 类。
> 状态说明：`已入库`=已纳入且有实质内容；`骨架占位`=仅有占位骨架，待填充业务实现。

## 一、已入库资产（含实质内容）

### 1. 政策解读 · policy_interpret
- **目录**：`skills/macro_event/policy_interpret/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：周周
- **版本**：1.1.0
- **形态**：llm_prompt（SKILL.md + references/）
- **功能**：解读政策文件、分析对行业/市场的影响，输出政策原文及结构化分析（背景、核心内容、影响范围、受益行业等），所有内容可溯源（来源 URL + 发布机构 + 文号）。
- **数据来源**：公开政府网站与权威媒体（WebSearch / WebFetch），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 2. 舆情风险预警 · sentiment_risk_warning
- **目录**：`skills/macro_event/sentiment_risk_warning/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：姜青、Warwick
- **版本**：1.1.0（资产包版本；SKILL.md frontmatter 内为 1.0.0）
- **形态**：script_based（SKILL.md + scripts/ + references/）
- **功能**：用「市场/个股舆情 + 量价相对特征」训练随机森林，预测 A 股下一交易日波动率风险并分级（高/中/低 + 0-100 综合风险分）。双模式——大盘（上证/深成/创业板三指数，沙箱可跑）与个股（需本机访问东方财富，含股吧情感）。强制相对值/比率/分位数，规避绝对量级漂移。
- **数据来源**：直连 Tushare / 东方财富 / 通达信（tdx），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 3. A股底部信号监控 · a_share_bottom_monitor
- **目录**：`skills/macro_event/a_share_bottom_monitor/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：Warwick
- **版本**：1.4.1（signal_map.json 统计口径为 v1.1；v1.2 决策层扩展、v1.3 输出呈现优化、v1.4 模式C 适用范围修正、v1.4.1 证伪落点表增列与输出防回流，均非统计重跑）
- **形态**：script_based（SKILL.md + scripts/ + references/ + data/ + stats/）
- **功能**：对主要指数（上证/深证成指/创业板指/中证2000）进行抄底位置监控——基于2014-2026十二年全量回测的已验证信号地图，判断各指数当前是否满足抄底条件、满足到几档；支持每隔约180天自动重跑全部七类统计、比对结论变化、修订信号地图并记录更新历史；并以「状态 + 路径 + 执行」三层补充路径风险（MAE 分位 / Wilson 区间 / 失败案例 / 双基准超额）、买点执行、8 问决策检查表与唯一动作结论。含数据完整性检查（含 path_map 校验）、变更分级协议（微调/修订/重大）、append-only 决策日志与历史台账。v1.2 不改动既有胜率、有效/无效判定与 signal_map 结论；v1.3 将监控报告与决策检查表成品化（结论前置、元信息表格化、变量名/参数名/调试行零裸露、免责与名词说明收敛文末），呈现文案统一由 `decision-rules.md` 的 `MACHINE_CONFIG.presentation` 定义，判定与数值零改动；v1.4 修正模式C 适用范围——仅对当前已触发有效组合信号的指数运行 8 问与四选一动作，未触发的「观察／不具备」类指数改输出「本轮不适用／不参与、不加仓」简报，不再对无仓位账户输出减仓指令，也不写入决策日志；已触发指数输出逐字节不变；v1.4.1 在第七节「证伪条件与当前落点」表格增列历史浮亏中位数与历史最深浮亏（口径与模式C 风险预算一致，可直接用于 R ÷ |最深浮亏| 计算仓位上限），并把「禁止只报胜率」等内部纪律短语纳入 `check_integrity.py` 第 7 项自动拦截，防止约束文案回流到成品输出。
- **数据来源**：直连 Tushare Pro（daily / index_dailybasic，走环境变量 `TUSHARE_TOKEN`），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 3.5 底部政策信号助手 · policy_bottom_monitor
- **目录**：`skills/macro_event/policy_bottom_monitor/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：Warwick
- **版本**：1.0.0
- **形态**：script_based（SKILL.md + scripts/ + references/ + stats/）
- **功能**：底部政策信号助手——基于 2008-2026 年 A 股历轮托底政策回测的验证框架，对"当前（或当日新出台）政策"进行托底强度分级判断（S/A/B/C/D 双轴分类：工具强度轴 × 位置适配度轴），与量价抄底信号（`a_share_bottom_monitor`）叠加输出综合抄底判断；并内置"自更新"机制（每半年或重大政策事件后，重跑回测、比对结论变化、修订政策地图并记录更新历史）。核心原则：政策效果看"真金白银"而非"态度"、组合拳 > 单发、结论须附样本量（26 条政策/17 组合，小样本）。
- **数据来源**：复用同目录族 `a_share_bottom_monitor/data/*.csv` 本地 K 线（上证/深成/创业板/中证2000，cron 每日增量更新）；2008–2013 早期数据缺口可选由环境变量 `POLICY_EARLY_DATA_DIR` 指定目录补充（未配置则跳过并在结论中标注样本区间），**不内置任何环境特定路径**；**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 4. 宏观经济分析 · macro_analysis
- **目录**：`skills/macro_event/macro_analysis/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：姜青
- **版本**：1.0.0
- **形态**：script_based（SKILL.md + scripts/ + assets/）
- **功能**：基于经济增长/流动性/通胀/外部/就业五维度框架，将宏观变量映射到 A 股行业景气与风格轮动，结合实时宏观数据产出《宏观—权益投资分析报告》——含一句话结论、宏观景气定位、五维度证据、行业超低配表。对应架构中"选股/盘前/策略"场景调用的 `macro_analysis` 槽位（已替换原占位骨架，场景 workflow 无需改动）。
- **数据来源**：实时 MCP 源（mx-ds-mcp 东方财富妙想 / tdx-connector 通达信）优先，离线脚本 `scripts/macro_snapshot.py`（基于 akshare）兜底；**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 5. 股票市场热点解读 · market_hotspot
- **目录**：`skills/macro_event/market_hotspot/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：周周
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/output-template.md）
- **功能**：七大模块覆盖市场热点全链条——热点识别与聚合、深度解读分析、产业链映射、资金面追踪、情绪面分析、操作建议生成、风险预警。基于 AkShare 板块/资金/涨跌停接口 + 公开网站检索（WebSearch/WebFetch），输出可溯源、带时间戳的双格式（Markdown/HTML）热点解读报告。对应架构中"盘前/盘中"场景调用的 `market_hotspot` 槽位（已替换原占位骨架，场景 workflow 无需改动）。
- **数据来源**：AkShare 开源库直连 + 公开网站检索（WebSearch/WebFetch），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 6. 行业速报 · industry_brief
- **目录**：`skills/macro_event/industry_brief/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：Warwick
- **版本**：1.0.0（manifest/SKILL.md 内为 1.0.0；README.md 内为 1.0.2）
- **形态**：script_based（SKILL.md + scripts/industry_flash.py + references/ + requirements.txt + README.md）
- **功能**：以申万一级行业为口径，每日生成行业速报——行业强弱排名、资金流向、事件速递，以及一套可解释信号规则（R01-R06，每条必带证据链）。取数走内部三级可降级网关（Tushare > Akshare > 腾讯财经），全源失败明确报错、禁止伪造；支持 `--demo` 演示模式零依赖开箱即跑。对应架构中"选股/尾盘"场景调用的 `industry_brief` 槽位（已替换原占位骨架，场景 workflow 无需改动）。
- **数据来源**：直连 Tushare / Akshare / 腾讯财经（经 scripts/industry_flash.py 内部三级可降级网关），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 7. 股票五维深度分析 · stock_5d_deep_analysis
- **目录**：`skills/subject_analysis/stock_5d_deep_analysis/`
- **分类**：subject_analysis（标的分析类）
- **作者**：Warwick
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/）
- **功能**：对单只 A 股标的执行「五维度个股深度分析」（核心交易数据 / 走势 / 资金 / 基本面 / 综合评价），输出结构化深度报告；可选叠加同业/行业对标（相对估值/动量/基本面/资金）。基于统一的五维分析框架，面向**单标的深度诊断**场景。
- **数据来源**：直连 Tushare / Akshare / 东方财富·腾讯兜底（可降级），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 8. 赛马量化策略选股 · racing_quant_pick
- **目录**：`skills/quant_strategy/racing_quant_pick/`
- **分类**：quant_strategy（量化策略类）
- **作者**：Warwick
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/ + scripts/）
- **功能**：从远程量化策略库（MySQL，连接参数可配置）智能匹配最符合用户需求的量化策略，获取其最新一期持仓个股，转化为可溯源的「选股池 + 策略画像」；支持明确需求 / 指定策略 / 仅查策略 / 互动偏好匹配四种入口，并可衔接 `stock_5d_deep_analysis` 对持仓个股做五维深度分析。框架改编自 racing-quant-ai。
- **数据来源**：直连远程 MySQL 策略库（策略信号源，**可配置 endpoint**，见 references/strategy-schema.md），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 9. 激进成长策略 · aggressive_growth_strategy
- **目录**：`skills/subjective_strategy/aggressive_growth_strategy/`
- **分类**：subjective_strategy（主观策略类）
- **作者**：Warwick
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/ + templates/）
- **功能**：基于 Tushare 数据的 A 股小盘成长股评估框架。以中证2000每日轮动选股为入口，对单股执行八步深度分析（赛道/市值/成长/位置/指数路径/排除/建仓/卖出），叠加技术面（布林/MACD/KDJ/RSI）、资金面（主力净流入）、舆情校验，给出 A+~D 综合评级；评级 B+及以上执行「高评级入池」（依赖运行环境自备的 `~/.hermes/aggressive-growth-tracker/update_tracker.py`，为可选副作用步骤）。适用于寻找利润层级式增长、具 10 倍市值空间潜力的科技/消费小盘股。
- **数据来源**：直连 Tushare（MCP 或本地 `tushare` 包），舆情检索依赖 `cn-web-search` 技能的东财搜索配方，**不经 ctx.gateway**。运行强依赖 `~/.hermes/` 配置与 cron/tracker 环境，详见 SKILL.md「运行环境依赖」段。
- **状态**：已入库（未适配为 BaseSkill）

### 10. 主题产业链深度分析 · concept_chain_analysis
- **目录**：`skills/macro_event/concept_chain_analysis/`
- **分类**：macro_event（宏观 & 事件类）
- **作者**：Warwick
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/）
- **功能**：以产业逻辑驱动，对主题/产业链进行上游/中游/下游 × 核心/弹性/补涨的纵深拆解，构建分层作战图并批量采集行情与资金流，综合研判受益确定性与风险；可选叠加持仓交叉分析，将产业链标的与本项目的量化策略持仓（racing_quant_pick）交叉验证。与同目录 market_hotspot（热点驱动、成分股罗列级）形成视角与深度互补。框架改编自 racing-quant-ai。
- **数据来源**：直连 AkShare + WebSearch/WebFetch（公开可得数据源），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 11. 股票对比分析 · stock_comparative_analysis
- **目录**：`skills/subject_analysis/stock_comparative_analysis/`
- **分类**：subject_analysis（标的分析类）
- **作者**：周周
- **版本**：1.1.0
- **形态**：llm_prompt（SKILL.md + references/ + scripts/）
- **功能**：对 2-5 只股票（含 A 股及 A+H 混合）生成专业证券分析师级别的深度对比报告，覆盖公司简介、基本面、技术面、资金面、消息面五大章节，输出 Markdown 源文件 + HTML 渲染报告（可选 PDF）。内置报告期统一、港股币种处理、成立日期交叉验证等数据质量控制规范，所有数据可溯源、带日期标注。框架源自 ClawHub stock-comparative-analysis。
- **数据来源**：直连 AkShare 开源库 + WebSearch/WebFetch（公开网站/交易所/财经媒体），**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 12. 隔夜外围市场复盘 · overnight_review
- **目录**：`skills/market_review/overnight_review/`
- **分类**：market_review（行情复盘类）
- **作者**：周周、姜青、Warwick
- **版本**：1.4.3
- **形态**：llm_prompt（SKILL.md + references/ + scripts/ + reference/）
- **功能**：生成面向 A 股盘前/盘中/盘后复核的隔夜外围市场复盘——以 Bloomberg「今日五件事」为决策层（事实→含义(本报告观点)→A股传导→验证/失效四句式），先证据后结论：全球行情速览 → 今日五件事 → 图表支撑 → 主线与分歧 → 常驻决策时间线（未来24h关键节点+可折叠一周预览+高敏感事件卡+情景切换矩阵，全部标记推演）。覆盖全球市场行情、风格与宽度、隔夜驱动、跨资产验证、A股主线映射、机构分歧与重点公司验证；输出 Markdown + 自包含 HTML 双格式（图表内嵌 data URI），全部带连续数字角标溯源。
- **数据来源**：经三个已连接 MCP（东方财富妙想 mx-ds-mcp / 腾讯自选股 westock-mcp / 通达信 tdx-connector）取数，Web 搜索仅作主通道不足时回退；**不经 ctx.gateway**
- **状态**：已入库（未适配为 BaseSkill）

### 13. 价值投资分析 · value_investing
- **目录**：`skills/subject_analysis/value_investing/`
- **分类**：subject_analysis（标的分析类）
- **作者**：姜青、Warwick
- **版本**：1.0.0
- **形态**：llm_prompt（SKILL.md + references/ + assets/ + scripts/）
- **功能**：自上而下的基本面价值投资分析框架。严格五步：宏观四方向 → 行业三模型（周期/波特五力/生命周期）→ 公司质量 SWOT → 按公司类型选估值指标与模型 → 综合结论与强制风险提示。核心信条「好公司 ≠ 好股票、价值 ≠ 价格」；Step 0 取数与口径校验执行数据源声明/四级降级/交叉验证/防幻觉护栏，禁止凭记忆填数（缺失保留 N/A）；多股对比可选调用 `scripts/value_scorecard.py` 做四层加权打分（缺失项按权重分摊、估值数据不足时禁止出总分与价格结论）。只给分析框架与参考结论，不荐股、不给目标价。参考样例：中际旭创（300308.SZ）完整分析报告。
- **数据来源**：直连使用者配置的工具（tdx-connector / mx-ds-mcp / Tushare / 公开网页等），数据源以 `references/data-sources.md` 的 level/requires/coverage 声明为准，**不经 ctx.gateway**；凭据零硬编码，由使用者自助配置。
- **状态**：已入库（未适配为 BaseSkill）

## 二、全部 Skill 目录一览

| Skill ID | 名称 | 分类 | 作者 | 版本 | 形态 | 状态 | 目录 |
|---|---|---|---|---|---|---|---|
| policy_interpret | 政策解读 | macro_event | 周周 | 1.1.0 | llm_prompt | 已入库 | `skills/macro_event/policy_interpret/` |
| sentiment_risk_warning | 舆情风险预警 | macro_event | 姜青、Warwick | 1.1.0 | script_based | 已入库 | `skills/macro_event/sentiment_risk_warning/` |
| a_share_bottom_monitor | A股底部信号监控 | macro_event | Warwick | 1.2.0 | script_based | 已入库 | `skills/macro_event/a_share_bottom_monitor/` |
| policy_bottom_monitor | 底部政策信号助手 | macro_event | Warwick | 1.0.0 | script_based | 已入库 | `skills/macro_event/policy_bottom_monitor/` |
| macro_analysis | 宏观经济分析 | macro_event | 姜青 | 1.0.0 | script_based | 已入库 | `skills/macro_event/macro_analysis/` |
| market_hotspot | 股票市场热点解读 | macro_event | 周周 | 1.0.0 | llm_prompt | 已入库 | `skills/macro_event/market_hotspot/` |
| industry_brief | 行业速报 | macro_event | Warwick | 1.0.0 | script_based | 已入库 | `skills/macro_event/industry_brief/` |
| stock_5d_deep_analysis | 股票五维深度分析 | subject_analysis | Warwick | 1.0.0 | llm_prompt | 已入库 | `skills/subject_analysis/stock_5d_deep_analysis/` |
| stock_comparative_analysis | 股票对比分析 | subject_analysis | 周周 | 1.1.0 | llm_prompt | 已入库 | `skills/subject_analysis/stock_comparative_analysis/` |
| racing_quant_pick | 赛马量化策略选股 | quant_strategy | Warwick | 1.0.0 | llm_prompt | 已入库 | `skills/quant_strategy/racing_quant_pick/` |
| aggressive_growth_strategy | 激进成长策略 | subjective_strategy | Warwick | 1.0.0 | llm_prompt | 已入库 | `skills/subjective_strategy/aggressive_growth_strategy/` |
| value_investing | 价值投资分析 | subject_analysis | 姜青、Warwick | 1.0.0 | llm_prompt | 已入库 | `skills/subject_analysis/value_investing/` |
| concept_chain_analysis | 主题产业链深度分析 | macro_event | Warwick | 1.0.0 | llm_prompt | 已入库 | `skills/macro_event/concept_chain_analysis/` |
| fund_analysis | 基金分析报告 | subject_analysis | — | — | 骨架占位 | 占位 | `skills/subject_analysis/fund_analysis/` |
| fund_compare | 基金对比分析 | subject_analysis | — | — | 骨架占位 | 占位 | `skills/subject_analysis/fund_compare/` |
| fund_manager_profile | 基金经理画像 | subject_analysis | — | — | 骨架占位 | 占位 | `skills/subject_analysis/fund_manager_profile/` |
| fund_manager_consistency | 基金经理观点&持仓一致性分析 | subject_analysis | — | — | 骨架占位 | 占位 | `skills/subject_analysis/fund_manager_consistency/` |
| market_daily_review | 股市每日收评 | market_review | Warwick | 1.1.4 | script_based | 已入库 | `skills/market_review/market_daily_review/` |
| overnight_review | 隔夜外围市场复盘 | market_review | 周周、姜青、Warwick | 1.4.3 | llm_prompt | 已入库 | `skills/market_review/overnight_review/` |

## 三、骨架占位 Skill 功能简介（待填充）

**宏观 & 事件类（macro_event）**
（已全部入库，无占位）

**标的分析类（subject_analysis）**
- 基金分析报告：单只基金的投资风格、持仓与绩效分析。
- 基金对比分析：多只基金横向对比（收益/回撤/风格）。
- 基金经理画像：基金经理履历、风格与历史业绩画像。
- 基金经理观点&持仓一致性分析：经理公开观点与实际持仓的一致性核验。

**行情复盘类（market_review）**
（两类均已入库，无占位）

## 四、维护说明

- 新增 Skill 资产：放入对应分类目录（`skills/<category>/<skill_id>/`），补充 `SKILL.md`/`scripts`/`references` 与 `manifest.yaml`，并在本文件登记。
- 作者署名：以 `manifest.yaml` 中 `author` 字段为准。
- 适配要求：纳入编排引擎（被场景 workflow / 外部调用方 `capabilities` 调用）前，需包装为 `BaseSkill` 并统一经 `ctx.gateway` 取数；当前已入库的十五 Skill（8 个 macro_event + 3 个 subject_analysis + 1 个 quant_strategy + 1 个 subjective_strategy + 2 个 market_review）仍为 `script_based` / `llm_prompt` 形态，取数不经网关，属已知缺口（详见 `skills/base/GATEWAY_REFERENCE.md`）。
- 统计：已入库 15 个，骨架占位 4 个，共 19 个 Skill。
