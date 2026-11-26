# 盘前 / 午盘 / 盘后 综合分析功能 · 设计方案（v2 采纳 SOP · 已实施）

> 状态：**已实施**（v1.0.0，作者 Warwick）。本文记录设计决策与 SOP 采纳判断；实现见 `SKILL.md` / `recipes/` / `examples/`。
> 目标：把现有 15 个 Skill 按「盘前 / 午盘 / 盘后」编排成综合分析，产出
> **可追溯的 Markdown 报告 + 可分享的 PNG 卡片**，且能随每次 Skill 更新低成本迭代。
>
> **v2 变更**：采纳《因维思投研作业流程 SOP》的真实作业流程——盘前 6 步、盘后 7 步、
> 时点纪律、失败隔离实战；确认时段时刻、旧场景取代、署名 Warwick、样例用真实历史数据。

---

## 一、为什么要这样做（设计前提）

| 现状 | 结论 |
|---|---|
| `apps/scenarios/{pre_market,intraday,closing}/workflow.yaml` 只是 Skill ID 列表；子 Skill 全是占位骨架（`run()` 返回空），跑不出真报告 | 不能只靠现有 workflow 引擎，需要「声明式配方 + LLM 执行提示词」 |
| 15 个分析能力在各自 `SKILL.md`（提示词）+ `scripts/`（脚本）里，由 Agent/人驱动，不经 `ctx.gateway` | 综合分析的「执行」本质是 **Agent 按时段配方逐个读 SKILL.md 执行 + 脚本辅助** |
| `presentation/` 已有 15 卡型映射、定时触发表、`data_as_of` 时效协议、渲染器 | 现成的「呈现出口」，直接复用，不重复造轮子 |
| **SOP 已用 15 项能力真实跑通盘前 6 步、盘后 7 步**，且有失败隔离与时点纪律的实战记录 | 配方不是凭空设计，直接对齐已验证的作业流程，可信度高 |

**核心结论**：功能形态 = **声明式「时段编排配方」**。每次 Skill 更新只改配方（数据），不改代码。

---

## 二、SOP 采纳判断（哪些采纳、哪些调整）

### 2.1 盘前（SOP 6 步 → 全部采纳）

SOP 盘前 08:30–09:25，六步：隔夜外围复盘 → 政策消息梳理 → 波动风险预警 → 主线热点预判 → 策略持仓核对 → 决策检查表。

| SOP 环节 | Skill | 采纳 | 卡型（presentation） | 说明 |
|---|---|---|---|---|
| ① 隔夜外围复盘 | `overnight_review` | ✅ | `overnight` | 核心，required |
| ② 政策消息梳理 | `policy_interpret` | ✅ | `policy` | 可选 |
| ③ 波动风险预警 | `sentiment_risk_warning` | ✅ | `sentiment` | 核心，required；**必须用盘前口径输入**（见 2.4） |
| ④ 主线热点预判 | `market_hotspot` / `industry_brief` | ✅ | `hotspot` / `industry` | 采纳 SOP 的"或"为两步并列，默认 `hotspot` |
| ⑤ 策略持仓核对 | `racing_quant_pick` | ✅ | `quantpick` | 可选，凭据缺失时如实标缺口（SOP 实战） |
| ⑥ 决策检查表 | `a_share_bottom_monitor`（模式C） | ✅ | `bottom_signal` | 核心，required；沿用模式C 适用范围守卫 |

**产出汇总**（沿用 SOP）：大势判断 · 主线方向 · 风险等级 · 策略持仓 · 决策检查结论。

### 2.2 盘后（SOP 7 步 → 全部采纳）

SOP 盘后 15:10–20:00，七步：收盘复盘 → 行业强弱 → 主线归因 → 舆情风险 → 底部信号 → 策略持仓 → 重点公司验证。

| SOP 环节 | Skill | 采纳 | 卡型 | 说明 |
|---|---|---|---|---|
| ① 收盘复盘 | `market_daily_review` | ✅ | `daily` | 核心，required |
| ② 行业强弱速报 | `industry_brief` | ✅ | `industry` | 核心，required |
| ③ 主线归因 | `market_hotspot` | ✅ | `hotspot` | 可选；限流时降级交叉验证（SOP 实战） |
| ④ 舆情风险评分 | `sentiment_risk_warning` | ✅ | `sentiment` | 可选；小样本必警（SOP 实战） |
| ⑤ 底部信号监控 | `a_share_bottom_monitor` | ✅ | `bottom_signal` | 核心，required |
| ⑥ 策略持仓更新 | `racing_quant_pick` | ✅ | `quantpick` | 可选，凭据缺失如实标注 |
| ⑦ 重点公司验证 | `stock_comparative_analysis` | ✅ | `stockcmp` | 可选，**依赖 ⑥ 有持仓池**，无输入则不产出（SOP 实战） |

**产出汇总**（沿用 SOP）：收评 + 行业速报 + 热点归因 + 风险评分 + 信号 + 标的池 + 重点验证。

### 2.3 午盘（SOP 未覆盖 → 保留为「建议性组合」，标注未经 SOP 验证）

SOP 只有盘前、盘后两段，**没有午盘流程**。为满足「盘前/午盘/盘后」三时段需求，午盘按以下原则设计并明确标注：

| 环节 | Skill | 卡型 | 说明 |
|---|---|---|---|
| 上午热点速览 | `market_hotspot` | `hotspot` | 可选 |
| 行业强弱 | `industry_brief` | `industry` | 可选 |
| 波动风险预警 | `sentiment_risk_warning` | `sentiment` | 可选；午盘口径输入 |

> ⚠️ 午盘这一段是**基于现有 Skill 的建议性组合，未经 SOP 实战验证**。审阅时可决定：保留（标"实验性"）/ 砍掉（只做盘前盘后）/ 后续补 SOP 再定。

### 2.4 SOP 的两条关键实战纪律（必须写进执行层）

1. **时点纪律**：SOP 盘前回溯证明——同一天盘前舆情指数 -0.808（看空）、收盘后 +0.664（看多），差异源于输入口径。盘前流程必须严格锁定 09:25 前可得信息（K线截到前一交易日、新闻剔除当日收评），**否则结论失真**。这与 presentation 的 `data_as_of` 协议同源，配方里用 `as_of_policy: pre_open` 显式声明。
2. **失败隔离**：SOP 盘后实战中，策略库凭据缺失→脚本按红线报错退出、不编造；重点公司因无输入→不产出。配方用 `required` + `depends_on` 表达这种依赖，Agent 遇缺失如实标注、不让单点失败拖垮整场。

---

## 三、整体结构（三层）

```
apps/scenarios/session_analysis/            ← 新场景（取代旧三空壳场景；纳入 capabilities，25 → 26）
├── SKILL.md                                ← ② 聚合提示词：指导 Agent 按时段配方执行
├── manifest.yaml                           ← 场景级契约（scene_id=session_analysis / 作者 Warwick / 版本）
├── README.md                               ← 入口说明
├── recipes/                                ← ① 声明式时段配方（可迭代核心，纯数据）
│   ├── session_map.yaml                    ←    时段 → Skill / 卡型 / 时效 / 顺序 / 依赖
│   └── report_template.md                  ←    MD 综合报告骨架（盘前/午盘/盘后三段）
└── examples/                               ← 样例产出（真实历史数据，见第七节）
    └── closing_20261113.md / .png   ← 已生成：真实历史数据盘后样例（MD + PNG + cards.json）
```

- **① 配置层**：`recipes/session_map.yaml` 是可迭代核心——「哪些 Skill、何时跑、出什么卡」全在这里。
- **② 执行层**：`SKILL.md` 给 Agent 的聚合提示词，读配方 → 逐个执行上游 Skill → 收集结构化结果。
- **③ 呈现层**：复用 `presentation/` 的卡型映射与渲染器，聚合结果组装成 NoviceCard JSON → MD + PNG。

---

## 四、① 时段配方（session_map.yaml 设计）

声明式数据，字段示意（非最终实现；盘前/盘后按 SOP，午盘标实验性）：

```yaml
version: 1
author: Warwick
sessions:
  pre_market:                              # 盘前 08:30–09:25
    window: "08:30–09:25"
    as_of_policy: pre_open                 # 时点纪律：锁定 09:25 前信息（SOP 关键）
    steps:
      - {skill_id: overnight_review,        card_type: overnight,     order: 1, required: true}
      - {skill_id: policy_interpret,        card_type: policy,        order: 2, required: false}
      - {skill_id: sentiment_risk_warning,  card_type: sentiment,     order: 3, required: true,
         as_of_policy: pre_open}            # 盘前口径输入，防时点失真
      - {skill_id: market_hotspot,          card_type: hotspot,       order: 4, required: false}
      - {skill_id: racing_quant_pick,       card_type: quantpick,     order: 5, required: false}
      - {skill_id: a_share_bottom_monitor,  card_type: bottom_signal, order: 6, required: true,
         mode: C}                           # 模式C，适用范围守卫
    report_sections: [大势判断, 主线方向, 风险等级, 策略持仓, 决策检查结论]

  midday:                                  # 午盘（实验性，SOP 未覆盖）
    window: "11:30–13:00"
    experimental: true
    as_of_policy: intraday
    steps:
      - {skill_id: market_hotspot,          card_type: hotspot,   order: 1, required: false}
      - {skill_id: industry_brief,          card_type: industry,  order: 2, required: false}
      - {skill_id: sentiment_risk_warning,  card_type: sentiment, order: 3, required: false}
    report_sections: [上午热点, 行业强弱, 风险提示, 下午关注]

  closing:                                 # 盘后 15:10–20:00（SOP 7 步）
    window: "15:10–20:00"
    as_of_policy: close
    steps:
      - {skill_id: market_daily_review,     card_type: daily,      order: 1, required: true}
      - {skill_id: industry_brief,          card_type: industry,   order: 2, required: true}
      - {skill_id: market_hotspot,          card_type: hotspot,    order: 3, required: false}
      - {skill_id: sentiment_risk_warning,  card_type: sentiment,  order: 4, required: false,
         small_sample_warn: true}
      - {skill_id: a_share_bottom_monitor,  card_type: bottom_signal, order: 5, required: true}
      - {skill_id: racing_quant_pick,       card_type: quantpick,  order: 6, required: false}
      - {skill_id: stock_comparative_analysis, card_type: stockcmp, order: 7, required: false,
         depends_on: racing_quant_pick}     # 无持仓池输入则不产出（SOP 实战）
    report_sections: [今日复盘, 行业速报, 热点归因, 风险评分, 底部信号, 策略动态, 重点验证]
```

**字段说明**：
- `order`：执行与呈现顺序；`required`：核心卡缺失则整场降级为「数据未就绪」，可选卡缺失标「—」继续；
- `as_of_policy`：时点纪律（`pre_open`/`intraday`/`close`），决定取数截止口径；
- `depends_on`：前置依赖（如重点公司验证依赖策略持仓池），前置缺失则跳过并如实标注；
- `card_type`：直接引用 presentation 的 15 卡型，不重复定义话术与视觉。

---

## 五、② 聚合提示词（SKILL.md 设计）

给 Agent 的执行纪律（要点，非全文）：

1. **读配方**：根据当前时段加载 `session_map.yaml` 对应 steps。
2. **时点守卫**：按 `as_of_policy` 锁定取数口径（盘前严格 09:25 前信息），防 SOP 揭示的时点失真。
3. **逐个执行**：按 `order` 读每个上游 Skill 的 `SKILL.md`，按其流程执行，收集结构化结果。
4. **依赖与失败隔离**：`depends_on` 前置缺失则跳过；单 Skill 失败如实记录到「数据缺口」，不拖垮整场、不编造（SOP 实战纪律）。
5. **时效判定**：每个结果做 `data_as_of` 判定，过期按 `required` 处理（降级说明 / 标「—」）。
6. **组装双产出**：
   - **MD 报告**：按 `report_sections` 填结构化内容，每段带来源与数据截至标注，末尾「数据缺口」+ 统一免责；
   - **PNG 卡片**：各步结果组装成 NoviceCard JSON，调用 `presentation/scripts/render_cards.py --png` 出组合长图。
7. **合规红线**：沿用 presentation 的 8 条（数字零加工、事实观点分离、缺失如实、不给买卖指令、小样本必警、免责固定）。

---

## 六、③ 产出形态（MD + PNG）

**MD 报告**（可追溯）：按时段分节，每节含结论 + 来源 + `data_as_of`，末尾「数据缺口」与统一免责；盘前附「预判 vs 实际收盘」对照位（SOP 亮点）。

**PNG 卡片**（可分享）：该时段各步卡按顺序拼成竖版长图（820px 宽），复用 presentation 渲染器，视觉与单卡一致。

---

## 七、可迭代性（最关键的设计）

| Skill 变化 | 需要做什么 |
|---|---|
| 某 Skill 升级（如底部信号 v1.4.1） | **什么都不改**——配方引用 `skill_id`，Agent 自动读该 Skill 最新 `SKILL.md` |
| 新增一个 Skill | 在 `session_map.yaml` 对应时段加一行 step + `card_type`；新卡型则在 presentation 补映射 |
| 调整时段组合 / 时效 / 依赖 | 只改配方对应字段 |
| 报告模板变化 | 只改 `report_template.md` |

**保证**：配方是纯数据（YAML），不写分析逻辑、不硬编码数值/日期；Skill 版本与形态从各自 `manifest.yaml` 动态读取。「随 Skill 更新自动迭代」是设计自带的。

---

## 八、落地决策（已确认）

| 项 | 结论 |
|---|---|
| 时段触发时刻 | 盘前 08:30–09:25、午盘 11:30–13:00、盘后 15:10–20:00（SOP 口径） |
| Skill 组合 | 盘前 6 步 / 盘后 7 步全采纳 SOP；午盘保留为实验性建议组合 |
| 旧三空壳场景 | **直接取代**（删除 pre_market/intraday/closing） |
| 署名 | Warwick |
| 样例数据 | 真实历史数据 |

---

## 九、实施前待确认项（已全部确认）

1. **午盘去留**：SOP 无午盘流程。是保留为实验性、还是砍掉只做盘前盘后？
2. **样例素材缺口**：SOP 提到的 `files/report/2026-11-25_*` 真实报告产物**不在本工作区**（属另一执行环境）。工作区现有真实样例为几份 11-13 的历史 markdown（底部信号日报、决策检查表、中际旭创价值投资分析等）。样例产出该如何取材？
   - A. 用工作区现有历史样例拼一个演示时段（数据截至日不一致，需如实标注）；
   - B. 请你把 SOP 里的 `files/report/2026-11-25_*` 报告包上传，用完整真实数据做样例；
   - C. 先做配方与提示词，样例产出留空占位，等有数据再补。
3. **旧场景处置**：确认直接删除三个空壳目录（不再保留兼容别名）——实施时会从能力目录移除旧 ID，请确认外部无依赖。

---

> 本文件为设计记录 v2。第九节三项已确认：午盘保留为实验性；样例由本库直接生成（真实历史数据，2026-11-13 盘后）；旧三场景直接删除取代。实现已完成并登记。
