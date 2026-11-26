# 股市每日收评 Skill（market_daily_review）

> 基于**开源金融数据源**，自动生成 **A 股 / 港股每个交易日的收盘点评报告**：大盘指数、涨跌统计、
> 板块表现、个股异动、资金流向、龙虎榜、重要资讯、技术面、盘面综述，全部市场或单市场，所有数据带
> 溯源标记与降级标记。

- **Skill 类目**：市场复盘类（market_review）
- **形态**：`script_based`（脚本驱动，由 `scripts/market_review.py` 直连开源数据源取数；与 `industry_brief` 同形态）
- **负责人**：Warwick ｜ **版本**：1.1.4（开源首版 v1.0.0 → 真接通 v1.1.x）
- **取数方式**：直连开源数据源（Tushare > Akshare > 腾讯财经/东方财富四级降级），**不经**体系可降级数据网关 `ctx.gateway`
- **数据源合规**：**完全开源**，不依赖任何商业数据供应商；缺失/失败如实标注，严禁编造
- **参与编排**：与 `industry_brief`（行业速报）在「尾盘场景」中互补

---

## 一、目录结构

```
market_daily_review/
├── __init__.py              # 包标识
├── manifest.yaml            # Skill 契约（id/输入输出/错误码/网关语义/四级数据源），供调度引擎校验
├── skill.py                 # 框架注册占位骨架（自动兼容独立打包 / 框架内运行）
├── SKILL.md                 # 核心规格：触发条件、10步SOP、十段式报告、降级链路、边界、Pitfalls
├── scripts/
│   └── market_review.py     # 可运行主脚本（四级降级网关 + 报告生成 + CLI）
├── references/
│   ├── data-sources.md      # 数据采集与可降级方案（四级降级、铁律、可靠性矩阵、日期格式）
│   ├── api-reference.md     # 开源数据源库函数映射表（维度 → 开源库调用）
│   ├── output-template.md   # HTML 报告模板（含样式与数据说明区）
│   └── examples.md          # CLI 用法示例与输出样例
└── README.md                # 本文件
```

> 说明：`manifest.yaml` 与 `skill.py` 用于接入 invest-skill 框架；真正由 LLM / 脚本执行的逻辑在
> `SKILL.md` + `scripts/` + `references/`（本 Skill 为脚本驱动型，核心取数在 `scripts/market_review.py`）。

---

## 二、与体系规范的关系

本 Skill 已对齐 invest-skill 体系的 Skill 规范（`industry_brief` / `policy_interpret` 同款结构与格式）：

| 规范要素 | 本 Skill 处理 |
|---|---|
| 统一契约 `manifest.yaml` | ✅ 已补全（含 `skill_id` / `category` / `author` / `version` / `spec` / `runtime` / `calls_gateway` / `data_sources` / input / output） |
| 框架注册 `skill.py` | ✅ 已补全 `BaseSkill` 占位骨架，独立打包时自动降级为最小基类，import 不报错 |
| 报告/数据可溯源 | ✅ `data_source` 来源标记 + `degrade_trace` 降级标记 + 第十节数据说明 |
| 禁止伪造数据 | ✅ 缺失/延迟数据标注「数据待补充」，核心源全失败抛 `MKT_REVIEW_001` 退出，不编造 |
| 可降级数据采集 | ✅ 四级降级（Tushare > Akshare > 腾讯财经/东方财富 > demo），细则见 `references/data-sources.md` |
| 包结构 | ✅ `skills/<category>/<skill_id>/` 标准布局，与参考 Skill 同级 |

**关键融合点（详见 SKILL.md 第六节）**：本 Skill 经**开源数据源**取数（脚本内部四级降级），而非体系的
Tushare/Akshare/腾讯三级网关，故 `calls_gateway: false`（语义为"不经 `ctx.gateway`"，非"不取数"）。

---

## 三、如何接入 invest-skill 框架

1. 将整个 `market_daily_review/` 目录放到 `skills/<category>/` 下：
   - 推荐 `skills/market_review/market_daily_review/`；
   - 若仓库将收评归入宏观事件类，亦可放 `skills/macro_event/market_daily_review/`（`manifest.yaml` 的 `category` 字段相应调整）。
2. 框架 `registry.py` 自动扫描 `skills/.../market_daily_review/skill.py` 中的 `BaseSkill` 子类并以 `skill_id` 注册。
3. `manifest.yaml` 不参与加载，供调度引擎 / 运营后台校验契约。
4. 真实执行由 `scripts/market_review.py` 完成（脚本驱动，直连开源数据源）；
   `skill.py` 的 `run()` 当前为占位骨架，待适配为 BaseSkill 运行时后填充。

---

## 四、references 索引

- `references/data-sources.md` — 数据采集与可降级方案：四级降级链路、🔴 数据校验铁律、接口可靠性矩阵、日期格式差异、交叉验证、采集状态报告。
- `references/api-reference.md` — 开源数据源库函数映射表（各维度 → 开源库调用）。
- `references/output-template.md` — 完整 HTML 报告模板（含 CSS、十段式结构、数据来源区、免责声明）。
- `references/examples.md` — CLI 用法示例、参数说明、输出样例、降级行为、最佳实践、FAQ。

---

## 五、依赖与运行

- **真实运行需**：`akshare`（开源主源）；可选 `tushare`（优先源，需 `TUSHARE_TOKEN`）；`requests`（网页兜底）。
- **无需第三方 Python 依赖即可验证管线**：`python3 scripts/market_review.py --demo`（`--demo` 模式使用内置样例，零外部依赖）。
- 若需在独立环境校验 `skill.py` 可导入：`python3 -c "import market_daily_review.skill"`（无 `skills.base` 时自动降级，不报错）。

---

## 六、免责声明与风险提示

本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
