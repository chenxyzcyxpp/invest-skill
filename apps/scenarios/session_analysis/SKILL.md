---
name: session-analysis
version: 1.0.0
author: Warwick
license: Apache-2.0
category: scenario
description: >
  盘前/午盘/盘后综合分析场景。按声明式时段配方编排现有 Skill，产出
  可追溯的 Markdown 报告 + 可分享的 PNG 卡片。随每次 Skill 更新自动迭代。
metadata:
  schema: session-analysis/1
  layer: orchestration
  recipes: recipes/session_map.yaml
---

# 盘前 / 午盘 / 盘后 综合分析（session_analysis）

> 版本 1.0.0 · 作者 Warwick · 隶属 `apps/scenarios/` 应用层场景。
> **定位：编排层，不是分析层。** 本场景不新增任何分析能力，只做一件事：
> 按 `recipes/session_map.yaml` 的时段配方，逐个调用上游 Skill，把结论汇总成
> 一份 Markdown 报告 + 一组 PNG 卡片。所有数值逐字段照抄上游，不改结论、不重算。

## 0. 何时触发

| 用户说法 | 时段 | 配方键 |
| --- | --- | --- |
| "盘前分析""开盘前瞻""今天怎么看""早报综合" | 盘前 | `pre_market` |
| "午盘速览""上午复盘""下午怎么看" | 午盘（实验性） | `midday` |
| "盘后分析""收盘复盘""今天总结""收盘怎么看" | 盘后 | `closing` |
| 未指明时段 | 按当前北京时间落在 `window` 的时段；跨时段则询问用户 | — |

## 1. 执行协议（严格按顺序）

### 1.1 读配方
读取 `recipes/session_map.yaml`，取目标时段的 `steps`（按 `order` 排序）、
`as_of_policy`、`report_sections`、`policies.<as_of_policy>` 口径。
**不要凭记忆决定跑哪些 Skill——一切以配方为准。**

### 1.2 时点守卫（SOP 关键纪律）
按 `policies.<as_of_policy>` 锁定取数口径：
- `pre_open`：严格只用 09:25 前可得信息——K线截到**前一交易日**、新闻**剔除当日收评与盘后公告**；
- `intraday`：11:30 数据截面；
- `close`：15:10 后收盘口径。
> 违反时点纪律会让结论失真（SOP 实战：同一天盘前舆情指数 -0.808 看空、收盘后 +0.664 看多）。
> 步骤级 `as_of_policy` 覆盖时段级（如盘前的波动风险预警必须用 `pre_open`）。

### 1.3 逐个执行
对每个 step，按 `order`：
1. 读取上游 Skill 的 `SKILL.md`（路径：从 `skills/<category>/<skill_id>/SKILL.md` 定位），
   按其定义的流程执行；有 `scripts/` 的按其 CLI 取数/复算；
2. 若有 `mode`（如底部信号 `mode: C`），按该模式执行并遵守其适用范围守卫；
3. 收集结构化结果 + `data_as_of` + 来源版本，供组装使用。

### 1.4 依赖与失败隔离（SOP 实战纪律）
- `depends_on`：前置 step 无输出 → 跳过本步，记入「数据缺口」，**不编造**（如重点公司验证无持仓池则不产出）；
- 失败/凭据缺失/限流：如实记录，不让单点失败拖垮整场；
- 可选步（`required: false`）缺失 → 该节标「—（数据缺口：原因）」继续；
- 必需步（`required: true`）缺失或 `data_as_of` 过期 → 整场标注「数据未就绪」，其余节照常输出。

### 1.5 时效判定
每个结果核对 `data_as_of`：过期按 1.4 的 required 规则处理。
不同节数据截止日不统一时，**以每节标注为准，不跨节混用**。

### 1.6 组装双产出
**① Markdown 报告**（可追溯）：
- 用 `recipes/report_template.md` 作骨架，按 `report_sections` 逐节填充；
- 每节含：来源 Skill + 版本 + `data_as_of` + 结构化结论 + 关键证据；
- 盘前段保留「预判 vs 实际收盘对照」位（SOP 亮点，盘后回填）；
- 末尾「数据缺口与降级说明」表 + 统一免责（模板已内置，照抄）。

**② PNG 卡片**（可分享）：
- 把各 step 结果按 `order` 组装成 NoviceCard JSON 数组（schema `invest-novice-card/1`，
  字段定义见 `presentation/SKILL.md` 第 1 节），`card_type` 用配方指定值；
- `source.skill` / `data_as_of` 逐卡保留；
- 调用渲染：
  ```bash
  python3.11 -X utf8 presentation/scripts/render_cards.py CARDS.json -o cards.html
  python3.11 -X utf8 presentation/scripts/render_cards.py CARDS.json --check cards.html   # 数字回比，须 0 missing
  python3.11 -X utf8 presentation/scripts/render_cards.py CARDS.json --png cards.png       # 整页长图
  ```
  Linux/root 环境 PNG 导出需 `CHROME=/usr/bin/chromium`（脚本已内置该候选）。

## 2. 合规红线（与 presentation 八条同源，违反即废）

1. **数字零加工**：数值逐字段照抄上游，注明来源与 `data_as_of`，不重算、不臆测；
2. **事实/观点分离**：模型或报告的观点必须标注「（报告观点）」，不得伪装成事实；
3. **缺失如实**：数据缺口、凭据缺失、依赖未满足一律如实标注，不用搜索结果或记忆补数；
4. **不给买卖指令**：只输出状态、风险、条件，不给「买入/卖出/目标价」指令；
5. **小样本必警**：上游统计 n<10 必须附小样本句；
6. **时点不混用**：盘前口径不得混入当日收盘/盘后信息；
7. **免责固定**：报告末尾免责用模板内置版本，不改写、不删减；
8. **成品化交付**：输出是成品报告，不出现内部纪律短语、调试行、`None`/`True/False` 等技术痕迹。

## 3. 迭代指南（随 Skill 更新）

| 变化 | 操作 |
| --- | --- |
| 某 Skill 升级 | 不改任何文件——执行时自动读该 Skill 最新 `SKILL.md` |
| 新增 Skill | 在 `session_map.yaml` 对应时段加一行 step + `card_type`；新卡型先在 `presentation/SKILL.md` 补映射 |
| 调整组合/时效/依赖 | 只改 `session_map.yaml` 对应字段 |
| 报告模板变化 | 只改 `recipes/report_template.md` |

## 4. 资源索引

- `recipes/session_map.yaml`：时段编排配方（可迭代核心）
- `recipes/report_template.md`：MD 报告骨架
- `examples/`：真实历史数据样例（MD + PNG）
- `DESIGN.md`：设计方案与 SOP 采纳判断
- `presentation/`：卡型映射与渲染器（呈现出口，复用）

---

> **历史回测 ≠ 未来收益，不构成投资建议。**
>
> 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
