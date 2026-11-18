---
name: industry-brief
description: |
  行业速报：以申万一级行业为口径，输出行业强弱排名、资金流向、事件速递与可解释信号
  （R01-R06），生成每日行业速报。所有结论带证据链、可降级、不伪造数据。
  触发词：行业速报、行业强弱、行业资金、板块速报、行业事件、今日行业、行业涨跌。
version: 1.0.0
author: Warwick
license: MIT
metadata:
  hermes:
    tags: [行业速报, 申万一级, 行业强弱, 资金流向, 行业事件, a股, industry-brief]
    related_skills: [policy-interpretation, sentiment-risk-warning, market-hotspot]
---

# 行业速报（申万一级 · 强弱 / 资金 / 事件 / 信号）

## Overview

本 skill 以**申万一级行业**为统一口径，每日生成一份行业速报：行业强弱排名、资金流向、
事件速递，以及一套**可解释的信号规则（R01-R06）**，每条信号必带证据链。取数走内部三级
可降级网关（Tushare > Akshare > 腾讯财经），全源失败返回明确错误、禁止伪造。

**核心原则**：结论必须可解释、可溯源；信号带证据；数据缺失则降级标注，绝不以估算值冒充。

## 触发条件

- 用户要求「行业速报」「行业强弱」「行业资金流向」「板块速报」「今日行业表现」
- 需要在行业层面给出当日强弱榜、资金异动、事件驱动机会
- 需要结合行业涨跌 / 主力资金 / 行业新闻做一线研判

**Don't use for：**

- 单只个股深度分析 → `stock_5d_deep_analysis`
- 宏观政策原文解读 → `policy_interpret`
- 全市场舆情风险预警 → `sentiment_risk_warning`
- 市场热点题材轮动解读 → `market_hotspot`

---

## 一、框架原理

### 1.1 口径与覆盖

- 行业口径：**申万一级行业（31 个）**，行业代码 `SW801XXX`（见 `scripts/industry_flash.py` 内 `SW_INDUSTRIES` 静态映射）。
- 每个行业产出自变量：当日涨跌幅（pct1d）、近 5 日涨跌幅（pct5d）、换手率（turnover）、主力资金净流入（moneyflow）。
- 行业新闻 / 事件：从公开财经源检索近 N 日行业相关新闻，作为 R05 事件驱动信号输入。

### 1.2 信号规则（R01-R06，阈值可配置）

所有信号必带 `evidence`（命中字段 + 数值 + 来源），禁止裸结论。

| 规则 | 名称 | 触发条件（示例阈值，集中配置可运营调参） | 方向 |
|------|------|----------------------------------------|------|
| R01 | 强势延续 | 近 5 日涨幅居前（pct5d ≥ +3%）且当日继续上涨（pct1d > 0） | 看多 |
| R02 | 资金异动 | 当日主力净流入 / 成交额 ≥ +1.5% 且居全行业前 1/3 | 看多 |
| R03 | 持续失血 | 近 5 日累计下跌（pct5d ≤ -3%）且资金净流出 | 看空 |
| R04 | 走弱预警 | 当日跌幅居前（pct1d ≤ -2%）且位于近 20 日低位分位 | 看空 |
| R05 | 事件驱动 | 近 N 日检索到行业重大事件（政策 / 并购 / 业绩 / 黑天鹅） | 中性→关注 |
| R06 | 估值触底 | 行业 PB/PE 处近 5 年 ≤ 10% 分位（可选，依赖估值源） | 中长期看多 |

> 阈值集中在 `scripts/industry_flash.py` 的 `CONFIG` 中，运营可在不改动逻辑的前提下调参。

### 1.3 可降级数据网关

三级降级（详见 `references/data-sources.md`）：

1. **Tushare**：行业指数行情 `index_daily`（申万行业，`sw_industry` 指数或成分股聚合）、行业资金 `moneyflow_ind`（如有权限）。
2. **Akshare**：行业板块行情 `ak.stock_board_industry_name_em`（东方财富行业板块，含涨跌幅 / 换手 / 资金）。
3. **腾讯财经网页源**：行业板块页面 HTML 兜底解析。
4. **演示数据兜底**：无 token / 源不可达时，`scripts/industry_flash.py --demo` 用内置演示数据跑通全流程，**仅用于管线验证**，报告须标注 `degraded`。

**行业新闻源缺口（重要）**：三源体系对「行业级新闻 / 事件」覆盖很弱。当前 R05 事件驱动
建议复用 `sentiment_risk_warning` 的事件流，或评估接入第四资讯源（见 `references/data-sources.md` 第六节）。

---

## 二、Agent 执行流程

依赖 `scripts/industry_flash.py`（单文件，含三级降级网关 + 演示兜底 + 信号 + 报告 + CLI）。

**演示模式（沙箱可直接跑，无需 token）：**

```bash
python3 <skill>/scripts/industry_flash.py --demo --output-format markdown
python3 <skill>/scripts/industry_flash.py --demo --output-format json
```

**真实模式（需本机可访问 Tushare / Akshare / 腾讯；未接入时如实报错，不伪造）：**

```bash
# 指定交易日，输出 Markdown + 落盘 files/report/
python3 <skill>/scripts/industry_flash.py --trade-date 2026-10-16 --output-format markdown --out files/report

# 只看资金视角、Top3
python3 <skill>/scripts/industry_flash.py --trade-date 2026-10-16 --focus fund --top-n 3
```

- `--demo`：使用内置演示数据，输出完整六段式速报；报告 `meta.degraded = demo`。
- 真实模式三源全部失败：脚本抛 `IND_FLASH_001` 并退出，**不输出伪造数据**（Agent 须如实告知用户）。
- 部分源降级：报告 `meta.degraded = partial`，`meta.degrade_trace` 记录各源成败。

---

## 三、输出格式

### 3.1 六段式速报（Markdown 主干）

```markdown
# 行业速报（{trade_date}）

> 数据范围：申万一级 31 行业 | 生成时间：{timestamp} | 数据状态：{degraded}

## 一、一句话概览
{全市场行业涨跌分布 + 最强/最弱行业 + 主线判断}

## 二、行业强弱榜（Top {top_n}）
| 排名 | 行业 | 当日% | 近5日% | 换手% |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |

## 三、资金流向（Top {top_n}）
| 行业 | 主力净流入(亿) | 净流入/成交额% |
|---|---|---|
| ... | ... | ... |

## 四、事件速递
- 【{行业}】{事件标题}（来源：{source}，时间：{time}）

## 五、信号解读（R01-R06）

> **图标说明**　🔥强势延续｜💰资金异动｜🩸持续失血｜⚠️走弱预警｜📰事件驱动｜⚡极端波动　·　方向 ↑看多 ↓看空 →中性　·　强度 🔴强 🟠中 ⚪弱

| 类型 | 行业 | 方向 | 强度 | 关键证据 |
|---|---|---|---|---|
| 🔥 **R01 强势延续** | {行业} | ↑ 看多 | 🔴 强 | 涨幅榜第N；5日累计涨幅 +X% |
| 🩸 **R03 持续失血** | {行业} | ↓ 看空 | 🔴 强 | 净流出累计 X 亿元（阈值 Y） |

## 六、数据说明与免责
- 数据来源：{data_source}；降级标记：{degraded}；降级轨迹：{degrade_trace}
- 免责声明：{标准文案}
```

### 3.2 结构化 `data`（脚本同时输出 JSON，供上游编排消费）

```json
{
  "trade_date": "2026-10-16",
  "summary": "全市场 N 涨 M 跌，电子/半导体领涨，地产链持续失血",
  "strength_rank": [ {"industry":"电子","pct1d":2.31,"pct5d":5.12,"turnover":3.4}, ... ],
  "fund_flow":     [ {"industry":"电子","net_inflow":42.6,"inflow_ratio":2.1}, ... ],
  "events":       [ {"industry":"半导体","title":"...","source":"...","time":"..."} ],
  "signals":      [ {"rule":"R01","industry":"电子","direction":"bullish","evidence":{...}} ],
  "meta": {
    "data_source": "tushare>akshare",
    "degraded": "partial|demo|none",
    "degrade_trace": {"tushare":"ok","akshare":"fail:...","tencent":"skip"}
  }
}
```

完整字段与示例见 `references/EXAMPLE_OUTPUT.md`。

---

## 四、能力边界（必须告知用户）

1. 行业口径为申万一级（31 个）；细分到二级/三级需扩展映射。
2. 行业新闻 / 事件源在三源体系中覆盖弱，R05 当前依赖检索或复用舆情事件流，**事件可能不全**。
3. 资金流口径：Tushare 行业资金需权限，Akshare 东方财富板块口径为「板块主力净流入」，与个股加总口径不完全一致。
4. 信号规则为**启发式**，不是买卖建议；R06 估值分位依赖估值源，缺省不输出。
5. 不构成投资建议，仅作行业层面的快速扫描，需结合其他维度交叉验证。

---

## 五、工程约束（开发规范 / Common Pitfalls）

1. **禁止编造数据**：任何涨跌幅 / 资金 / 信号必须来自脚本计算；数据源失败脚本报错退出，Agent 不得用估算值替代，须如实标注「数据获取失败」。
2. **全源失败必报错**：Tushare / Akshare / 腾讯 三源都失败抛 `IND_FLASH_001`，不输出伪造速报。
3. **信号必带证据**：每条 R01-R06 信号必须附 `evidence`（命中字段 + 数值 + 来源），禁止裸结论。
4. **演示数据≠真实行情**：`--demo` 仅验证管线，报告须标注 `degraded=demo`；真实速报必须走真实取数，无源时如实报告。
5. **降级须标注**：部分源失败须标 `degraded=partial` 并附 `degrade_trace`，禁止把「仅演示/部分源」冒充「全量真实」。
6. **行业名称统一**：内部用申万标准名（如「电子」「电力设备」），输出与映射表一致，避免别名漂移。
7. **阈值可运营调参**：R01-R06 阈值集中在 `CONFIG`，改阈值不改逻辑；调整前先复验历史样本。
8. **升级同步调用方**：若本 skill 被 cron / 场景编排挂载，升级 SKILL.md 或脚本后须同步相关 prompt 的口径与输出模板。

---

## 六、Verification Checklist

- [ ] 演示模式：`python3 industry_flash.py --demo --output-format markdown` 输出完整六段式速报
- [ ] 演示模式：`--output-format json` 输出合法 JSON，含 strength_rank / fund_flow / signals / meta
- [ ] 信号证据：每条 R01-R06 命中项在 JSON 中带 `evidence`
- [ ] 降级标注：`--demo` 报告 `meta.degraded = demo`
- [ ] 真实模式无 token：脚本抛 `IND_FLASH_001` 且退出，不生成伪造文件
- [ ] 部分降级：某源失败时在 `degrade_trace` 可见，报告标 `partial`
- [ ] 行业名一致：输出行业名与 `SW_INDUSTRIES` 映射完全一致
- [ ] 数据真实性：所有数值可溯源至脚本输入，无占位伪造

---

## 七、上架信息

- 作者：Warwick
- 分类：金融 / 行业研究
- 标签：行业速报, 申万一级, 行业强弱, 资金流向, 行业事件, A股
- 版本：1.0.0
- 更新日志：
  - v1.0.0 (2026-10-18): 首版。script_based 形态；三级可降级网关（Tushare>Akshare>腾讯）+ 演示兜底；申万一级 31 行业口径；信号规则 R01-R06（带证据链）；六段式速报（MD/JSON 双格式）；SKILL.md + references/data-sources.md + references/EXAMPLE_OUTPUT.md。
  - v1.0.1 (2026-10-18): 信号解读改为带图标的表格（🔥💰🩸⚠️📰⚡ 信号类型 + ↑↓→ 方向 + 🔴🟠⚪ 强度），章节内附「图标说明」；强弱榜当日涨跌幅加 ▲▼ 涨跌箭头。
  - v1.0.2 (2026-10-18): 5 日动量可靠性加固——`stock_board_industry_index_ths` 单板块历史拉取加 3 次重试（消化同花顺偶发 'No tables found' 抖动）；拉取失败不再静默填 0，改标记缺失并在报告/JSON 中如实显示「—」/null，杜绝伪造 0 值误导 R01。

---

## 参考资料

- `references/data-sources.md` — 行业数据源细节（Tushare / Akshare / 腾讯行业板块）、三级降级路径、行业新闻缺口与建议。
- `references/EXAMPLE_OUTPUT.md` — 完整结构化输出示例与字段说明。

## 免责声明与风险提示

本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
