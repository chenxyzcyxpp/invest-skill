# 行业速报 Skill（industry_brief）

> 以申万一级行业为口径，输出**行业强弱排名、资金流向、事件速递与可解释信号（R01-R06）**，
> 自动生成每日「行业速报」（Markdown / HTML / JSON 三格式）。

- **Skill 类别**：宏观 & 事件类（macro_event）
- **形态**：`script_based`（SKILL.md 提示词 + `scripts/` 下可运行 Python）
- **负责人**：Warwick ｜ **版本**：1.0.2
- **取数方式**：直连 Tushare / Akshare / 腾讯财经（三级可降级网关，**不经**项目 `ctx.gateway`）
- **核心约束**：禁止编造数据；数据源全失败即报错退出（不输出伪造速报）；信号必带证据链

---

## 一、目录结构

```
industry_brief/
├── __init__.py              # 包标识
├── manifest.yaml            # Skill 契约（id/输入输出/错误码/网关优先级），供调度引擎校验
├── skill.py                 # 框架注册占位骨架（自动兼容独立打包 / 框架内运行）
├── SKILL.md                 # 核心规格：触发条件、七步工作流、R01-R06 规则、报告格式、边界
├── requirements.txt         # 运行依赖（--demo 零依赖；真实模式需 akshare）
├── references/
│   ├── data-sources.md      # 行业数据源与三级降级、行业新闻缺口与反哺建议
│   └── EXAMPLE_OUTPUT.md    # 结构化 JSON 示例与字段说明
└── scripts/
    └── industry_flash.py    # 可运行主脚本（自包含，可脱离 skills 包独立运行）
```

> 说明：`manifest.yaml` 与 `skill.py` 用于接入 invest-skill 框架；真正可独立执行的逻辑在
> `SKILL.md` + `scripts/industry_flash.py`。

---

## 二、快速开始（独立运行）

本压缩包**完全独立**，无需克隆 invest-skill 仓库即可运行。`scripts/industry_flash.py`
是单文件、自包含脚本（仅依赖标准库 + 可选 `akshare`）。

### 1. 演示模式（零依赖，开箱即跑）

```bash
cd industry_brief/scripts
python3 industry_flash.py --demo --output-format markdown   # 终端输出 Markdown
python3 industry_flash.py --demo --output-format json        # 终端输出 JSON
python3 industry_flash.py --demo --out files/report          # 落盘 .md + .html
```

演示模式使用内置演示数据校验整套管线（报告标注 `degraded=demo`），**不需要 token、不需要网络**。

### 2. 真实模式（直连市场数据）

```bash
# 自动定位最近交易日，生成 Markdown + HTML 到 files/report/
python3 industry_flash.py --output-format both --out files/report

# 指定交易日 / 聚焦资金 / 限制条数
python3 industry_flash.py --trade-date 2026-10-16 --focus fund --top-n 3
```

真实模式会自动尝试三级数据源（Tushare > Akshare > 腾讯财经），全部失败则抛出
`IND_FLASH_001` 并退出，**绝不输出伪造速报**。

---

## 三、命令行参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--demo` | 否 | 演示模式，用内置数据跑通管线 |
| `--trade-date YYYY-MM-DD` | 最近交易日 | 速报基准日；`latest` 自动推断 |
| `--focus` | `all` | `strength`/`fund`/`event`/`all` 关注重点 |
| `--top-n` | `5` | 强弱榜 / 资金榜展示条数 |
| `--output-format` | `markdown` | `markdown`/`json`/`html`/`both` |
| `--out DIR` | 无 | 落盘目录（生成 `{trade_date}_行业速报.md/.html`） |

---

## 四、信号规则速览（R01-R06）

所有信号均带 `evidence` 证据链与 `direction`/`strength`，报告内以图标呈现：

| 编号 | 名称 | 触发条件（默认阈值） | 图标 |
|---|---|---|---|
| R01 | 强势延续 | 近5日涨幅 ≥ 3% 且当日继续上涨 | 🔥 |
| R02 | 资金异动 | 主力净流入 ≥ 10 亿 或 净流出 ≥ 10 亿 | 💰 |
| R03 | 持续失血 | 近3日累计净流出 > 30 亿 | 🩸 |
| R04 | 走弱预警 | 当日上涨但资金净流出（背离） | ⚠️ |
| R05 | 事件驱动 | 命中行业事件且涨跌幅(绝对值) > 1.5% | 📰 |
| R06 | 极端波动 | 单日涨跌幅(绝对值) > 4% | ⚡ |

方向 ↑看多 / ↓看空 / →中性；强度 🔴强 / 🟠中 / ⚪弱。完整规则与可配置阈值见 `SKILL.md`。

---

## 五、数据源与降级

三级可降级网关，**逐级降级、全源失败报错**：

1. **Tushare**（优先）：申万行业指数、资金流；需 `TUSHARE_TOKEN`。
2. **Akshare**（次级）：行业板块行情 / 资金流 / 5日动量 / 指数（本环境经同花顺、新浪口径）。
3. **腾讯财经网页源**（兜底）：网页抓取行业行情。
4. **演示数据**（仅 `--demo`）：内置样本，仅验管线。

> 行业新闻源在三源体系中覆盖较弱，R05 事件驱动建议复用 `sentiment_risk_warning` 事件流
> 或经 WebSearch 检索（详见 `references/data-sources.md`）。

---

## 六、依赖

```bash
pip install -r requirements.txt
```

- `--demo` 模式：**零第三方依赖**，标准库即可。
- 真实模式：需 `akshare>=1.11.0`（自动带入 pandas / numpy）。

---

## 七、如何接入 invest-skill 框架

本 Skill 已对齐 `policy_interpret` / `sentiment_risk_warning` 的扩展结构与格式。接入方式：

1. 将整个 `industry_brief/` 目录放到 `skills/macro_event/` 下（与参考 skill 同级）；
2. 框架 `registry.py` 会自动扫描 `skills/macro_event/industry_brief/skill.py` 中的
   `BaseSkill` 子类并以 `skill_id` 注册；
3. `manifest.yaml` 不参与加载，供调度引擎 / 运营后台校验契约；
4. 真实执行由 `SKILL.md` 提示词驱动 LLM + `scripts/industry_flash.py` 落库取数完成；
5. `skill.py` 的 `run()` 当前为占位骨架，待适配为 BaseSkill 运行时后填充真实逻辑。

---

## 八、免责声明与风险提示

本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
