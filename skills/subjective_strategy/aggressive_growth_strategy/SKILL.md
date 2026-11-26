---
name: aggressive-growth-strategy
description: |
  【激进成长策略技能】基于 Tushare 数据的 A 股小盘成长股评估框架：中证2000每日轮动选股、
  八步深度分析（赛道/市值/成长/位置/指数路径/排除/建仓/卖出）、技术面/资金面/舆情校验、
  综合评级（A+~D），高评级（B+及以上）入高评级跟踪池。
  适用于寻找利润层级式增长、具 10 倍市值空间潜力的科技/消费小盘股评估。
  触发词：激进成长策略、成长股分析、中证2000轮动、小盘成长股评估、十倍股挖掘。
version: 1.0.0
author: Warwick
source: 激进成长策略框架（Warwick）
license: MIT
metadata:
  hermes:
    tags: [激进成长, 成长股, 中证2000, 轮动选股, 小盘, a股, 八步分析]
    related_skills: [racing-quant-pick, stock-5d-deep-analysis, sentiment-risk-warning]
---

# 激进成长策略 (Aggressive Growth Strategy)

## 运行环境依赖（重要）

本技能为「提示词驱动型」分析框架，仓库内不自带运行环境与外部脚本，实际执行需依赖以下外部条件，请按需自备：

- **数据源（Tushare）**：支持二选一 —— ① `Tushare MCP`（`mcp_tushareMcp_*` 系列工具）；② 本地 `tushare` Python 包直连（token 取自运行环境 `~/.hermes/config.yaml` 的 `tushareMcp` 段）。MCP 批量返回截断（约 2000 条成分股 ~22 万字符）时，按 `references/tushare-mcp-truncation-workaround.md` 改用本地直连绕过。
- **舆情检索**：最新动态检索依赖 `cn-web-search` 技能的东财搜索 API 配方（`references/eastmoney-search-api.md`）。
- **入池副作用（可选）**：综合评级 B+及以上时，技能会执行 `python3 ~/.hermes/aggressive-growth-tracker/update_tracker.py add ...` 写入高评级跟踪池。该脚本与 `~/.hermes/` 目录**不在本仓库内**，需运行环境自备；若仅做分析、不维护跟踪池，可跳过该步骤，仅产出分析报告。
- **报告输出**：提供 Feishu Markdown 模板（`templates/csi2000-report-template.md`），可适配为其他发布渠道。
- **调度（可选）**：可作为每日 cron 任务（来源 `csi2000_rotation`）触发；轮换状态文件 `~/.hermes/cron/csi2000_rotation.json` 由运行环境维护，不存在时从 -1 开始。

## 触发条件
- 每日中证2000成分股深度分析 cron（来源：csi2000_rotation）
- 用户要求用激进成长框架评估某A股（寻找利润层级式增长、有10倍市值空间潜力的科技/消费小盘）

## 核心逻辑
好赛道（科技/消费）× 利润层级式增长 × 左侧低位买入 × 倒金字塔卖出。评级 B+ 及以上标的入高评级跟踪池。

## 方法论内核（道·法·术·器，必读）

本技能的操作流程（八步分析 / 轮动 / 入池）之上是完整的「周期性成长」投研体系，源自 20 年 A 股一线实战派方法论。以下为执行时贯穿全程的底层逻辑；完整四层体系（含全部表格、公式、案例）见 **`references/methodology.md`**。

- **道（心法）**：农耕周期四季（春耕→夏耘→秋收→冬歇，冬歇保本即胜利，绝不冬天下场搏 10%）；取舍定理（4000 点以上进入博弈区）；能力圈排除铁律（看不懂 / 退市风险 / 造假史 / 利润破不了 1-2 亿 / 商誉跨界 / 蹭热点，六不碰）；交易三戒（戒贪婪·戒逆势·戒浮躁）。
- **法（方法论）**：三层穿透（宏观定大势→产业前瞻→个股定收益）；**好产业公式 = 单价高 × 使用周期短**（AI 服务器 ≈ 天下最好产业）；四大核心原则（独立思考·知行合一·稳健第一·差异化）；10 年周期律与阶梯式慢牛（当前 3600-4200 区间，4200 短期难破）。
- **术（选股交易）**：**选股七标准**（赛道 70% 科技消费 / 市值 50 亿以下 / 较高 ROE / 利润层级式增长 / 左侧布局 / 指数升维路径 2000→1000→300→50 / 无造假退市商誉）；**市值概率思维**（25000 亿 3 年翻倍概率≈0，30 亿若 5 年利润超 25 亿有 50 倍空间）；**小偷式建仓**（单日买入 ≤ 日成交量 10%）；**倒金字塔卖出**（越涨卖得越多）；翻倍后先卖一半分红。
- **器（流程工具）**：投研六步标准化流程；年度复盘制度（全年涨/跌前 100 名检讨）；**风控三体系**（事前准入 / 事中每日核对 / 事后止损，系统性风险「看位置」应对）；对手盘心理模型（割肉派≈底部、套牢派锁仓、补仓派深渊）。

> 八步深度分析中的每个步骤都对应上述内核，下方表格第 3 列标注其方法论依据；评估时须同时校验「选股与风控铁律」。

## 执行流程（工作流二：八步深度分析）

### 0. 交易日检查
`mcp_tushareMcp_trade_cal`（exchange=SSE, cal_date=今日YYYYMMDD）。is_open != "1" → 回复"今日非交易日，跳过分析"并结束，不做其他操作。

### 1. 获取中证2000成分股
`mcp_tushareMcp_index_weight`：index_code=932000.CSI, start/end=上月首末日。
⚠️ **约2000条返回会截断（~22万字符）**，改用本地 tushare 直连，代码见 references/tushare-mcp-truncation-workaround.md。

### 2. 轮换选股
- 读 `~/.hermes/cron/csi2000_rotation.json` 的 last_index（文件不存在或为空则从 -1 开始）
- new_index = (last_index+1) % len(成分列表)；按列表顺序取第 new_index 只
- 记录 con_code(ts_code) 和 weight；用 write_file 写回 {"last_index", "last_stock", "last_date", "stock_name"}

### 3. 基础信息
`mcp_tushareMcp_stock_basic`（ts_code）→ 名称/行业/市场/上市日期。

### 4. 八步深度分析
| 步骤 | 数据源 | 要点 | 方法论依据 |
|---|---|---|---|
| Step1 赛道 | stock_basic.industry | 科技或消费=好产业标准 | 法·好产业公式（单价高×周期短）；术·选股七标准①赛道 |
| Step2 市值 | daily_basic | circ_mv/total_mv，判断10倍空间概率 | 术·市值概率思维（50亿以下10倍概率高，25000亿≈0） |
| Step3 成长 | fina_indicator | ROE/净利同比/营收同比，检验利润层级式增长 | 术·选股七标准③④（较高ROE/层级式增长） |
| Step4 位置 | daily 近250日K线 | 当前价格分位<50%=左侧机会 | 术·选股七标准⑤左侧布局；道·农耕周期（春耕位） |
| Step5 指数路径 | index_weight 逐指数查 | 是否被纳入更大指数（参数注意见Pitfalls） | 术·选股七标准⑥升维路径 2000→1000→300→50 |
| Step6 排除 | stock_st + 价格/PE | ST、股价<2元、PE<0 排除 | 道·能力圈排除铁律（退市/造假/长不大） |
| Step7 建仓 | daily 近20日均量 | 单日最大买入量=日均量×10%，分3-4批 | 术·小偷式建仓（≤日成交量10%，底部吸筹） |
| Step8 卖出 | 无 | 倒金字塔：涨20%卖5%→40%卖10%→60%卖15%→80%卖20%→100%卖50% | 术·倒金字塔卖出（越涨卖越多，不追最高点） |

### 5. 技术面信号
`mcp_tushareMcp_stk_factor`：布林（价<中轨偏弱/触下轨超卖）、MACD（金叉多/死叉空）、KDJ（K<20超卖/>80超买）、RSI（6日<30超卖/>70超买）。
综合：4指标中≥3偏多=买入信号，≥3偏空=卖出信号，否则观望/持有（注意MACD柱收窄、KDJ低位金叉等企稳迹象要文字点出）。

### 6. 资金动向
`mcp_tushareMcp_moneyflow` 近5日，判断主力（大单+特大单）连续净流入/流出。

### 7. 最新动态
用东财搜索API（execute_code + urllib.request，配方见 cn-web-search 技能 references/eastmoney-search-api.md）：
- **个股：裸股票名 + sort=default**（加"最新消息/研报"后缀会被全站热点污染）
- 行业宽泛搜索易污染，改用具体公司/事件关键词 + sort=time
- 任务要求三连搜："[名称] 最新消息" / "[名称] 研报" / "[行业] 趋势 2026"

### 8. 报告
Feishu Markdown 模板见 templates/csi2000-report-template.md。含基础信息表、八步分析、技术面、资金动向、最新动态、综合评级、数据来源、免责声明。

### 9. 高评级入池（重要）
评级 **B+及以上** → 必须执行入池（漏入池视为重大事故）：
```bash
python3 ~/.hermes/aggressive-growth-tracker/update_tracker.py add {ts_code} {股票名称} {评级} csi2000_rotation --logic "{核心逻辑一句话}" --date {今日YYYY-MM-DD}
```
已在池中会提示"已在跟踪池中(active)"并自动更新，无需额外处理。入池后报告末尾加：
`📌 已加入高评级跟踪池（来源：中证2000轮动，评级：{评级}）`

## 评级标准
A+=极强关注 / A=强烈关注 / A-=重点关注 / B+=值得关注偏强 / B=值得关注 / B-=一般偏弱 / C=一般 / D=回避。B+及以上入池；低于B+跳过入池步骤。

## 铁律
1. 🔒 财务数据必须来自API调用结果，严禁凭记忆引用；无法验证标注"⚠️财务数据未验证"
2. 数据获取失败如实标注"数据获取失败"，不得编造任何具体数值
3. 使用今日实际日期，不用示例日期
4. 北交所（.BJ）股票同样正常分析
5. 入池来源固定填 `csi2000_rotation`

## Pitfalls
- **MCP截断**：index_weight 2000只返回~22万字符被截断 → 本地 tushare 直连绕过（token 位置与代码见 references/tushare-mcp-truncation-workaround.md）
- **index_weight 不支持 ts_code 参数**（50101 参数校验失败）→ 逐 index_code 查询后过滤 con_code
- **terminal 中 curl | python3 管道会被沙箱安全扫描拦截** → 新闻/API搜索用 execute_code 内 urllib.request
- 成分股列表顺序 = 权重降序（与MCP返回一致），轮换序号必须按此顺序
- fina_indicator 的 gross_margin 字段实为毛利金额（元），netprofit_margin 才是净利率（%）
- **技能名连字符 vs 下划线**：cron 任务引用 `aggressive_growth_strategy`（下划线）加载会失败——技能实际文件名是 `aggressive-growth-strategy`（连字符）。加载失败不必反复重试，直接按本文档流程执行即可（2026-10-23 实测）
- **home 目录是 /home/ubuntu 而非 /root**：write_file 写 `~/.hermes/cron/csi2000_rotation.json` 时若 shell 展开成 /root 会 Permission denied，务必用 `$HOME`（/home/ubuntu）展开
- **python3 -c 内联脚本含双引号会报 SyntaxError**（shell 吃掉引号导致 `index_code=932000.CSI` 变非法字面量）→ 先 write_file 写 .py 脚本文件再执行，不要用内联 -c
- **research_report 接口无访问权限**（40203）→ 券商研报信息改用东财搜索API按关键词检索（如"[名称] 研报"），如实标注研报未获取，勿依赖该接口
- **moneyflow 金额字段单位已是万元**：buy_lg/sell_lg/buy_elg/sell_elg/net_mf_amount 均以万元为单位，主力净额=(buy_lg+buy_elg-sell_lg-sell_elg)直接相加，**勿再除10000**（2026-10-30 悦达投资实测：脚本多除10000导致主力净额失真为0.03万级，报告需手工重算）
- **csi2000_rotation.json 并发写入警告**：write_file 写轮换文件时可能提示 "modified by sibling subagent"——并发 cron job 可能触碰该文件；先用 cat/read 读最新内容再写，内容通常一致无需特殊处理，但不要盲写覆盖

## 选股与风控铁律（评估时必须逐项校验）

**选股七标准（全部满足才进入高评级候选）：**
1. 赛道：科技或消费（70% 集中度），对照海外市值变迁
2. 市值：50 亿以下为佳（10 倍股概率远高于千亿以上）
3. 财务：较高 ROE（成长质量验证）
4. 成长性：利润能层级式增长（1亿→2亿→5亿→25亿，市值同步 10x-50x）
5. 位置：左侧布局（市场共识形成前进入）
6. 指数路径：处于升维路径（从未进指数 → 2000 → 1000 → 300 → 50，被动资金持续涌入）
7. 排除项：无造假 / 退市 / 商誉风险

**能力圈排除铁律（六不碰）：** 看不懂的、有退市风险（2元以下虹吸）、有造假史、利润破不了 1-2 亿的「长不大」、跨界并购堆商誉、每个热点都蹭的。→ **宁可错过，绝不踩雷。**

**卖出与分红：** 倒金字塔卖出（越涨挂单越大），不追求卖在碎骨成交的最高点；翻倍后先卖一半分红，回笼客户本金降低波动心理影响。换仓看市值空间（上了 5000 亿后重算涨 2-3 倍概率）。

**系统性风险「看位置」应对：** 低位（如外部冲击事件）不砍反加；高位（当前 3600-4200）出现系统性问题则减仓；依据 = 泡沫大小 + 获利盘大小 + 国家意志方向。

## 注意事项
1. 本体系适用于 A 股，偏小盘成长风格，不适用于大盘价值或纯短线
2. 「好产业」标准是动态的，AI 服务器之后可能出现新品类
3. 冬天判断需综合多维度信号，不可单一指标定论
4. 倒金字塔卖出需较大资金量，小资金可简化执行
5. 10 年周期律是经验总结非铁律，需结合当下实际判断
6. 所有概率判断都基于信息不完整的估计，需持续修正

## 支持文件
- references/methodology.md — **方法论内核全本**（道·法·术·器四层体系：农耕周期、好产业公式、选股七标准、倒金字塔、风控三体系、对手盘模型、执行指南、注意事项）
- references/tushare-mcp-truncation-workaround.md — token 位置、完整成分股获取、指数成员查询、250日分位/均量计算代码
- templates/csi2000-report-template.md — Feishu 报告模板
