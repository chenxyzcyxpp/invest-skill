# skills/ 通用 Skill 组件层

> invest-skill 架构 **第二层**：通用 Skill 组件层（原子可复用能力）。

本层承载可被应用层（选股/诊股/策略/盘前-午盘-盘后综合分析四大场景）调用的
**原子化 Skill**。每个 Skill 有标准的输入输出契约（`BaseSkill` / `SkillContext` /
`SkillResult`），可跨场景复用。

> **现状说明**：目前 15 个已入库 Skill **均直连各自数据源**
> （`calls_gateway: false`），尚未接入统一数据网关。目标架构要求 Skill 统一经
> `ctx.gateway` 取数，这一改造列在项目 `README.md` 的 Roadmap 中；
> 网关设计规范见 [`base/GATEWAY_REFERENCE.md`](base/GATEWAY_REFERENCE.md)。
> 下文「统一契约」描述的是**目标契约**，不是当前所有 Skill 的实现状态。

> **可视化输出层**：仓库顶层的 [`presentation/`](../presentation/) 是横切输出层，
> 把本层 15 个 Skill 的报告翻译成小白卡片 PNG；它不取数、不参与本层的能力发现，
> 也不计入 15 个 Skill 统计。

## 目录结构

```
skills/
├── base/                    # 统一契约：Skill 基类、标准输入输出、上下文
│   ├── skill_base.py
│   └── GATEWAY_REFERENCE.md # 数据网关设计规范（参考文档，非运行时代码）
├── macro_event/             # 宏观 & 事件类（8）
├── subject_analysis/        # 标的分析类（3 已入库 + 4 占位）
├── market_review/           # 行情复盘类（2）
├── quant_strategy/          # 量化策略类（1）
├── subjective_strategy/     # 主观策略类（1）
└── scripts/
    └── scaffold_skill.py    # 脚手架：生成/扩展 Skill 骨架
```

## 五大类 Skill

| 类别 | 目录 | 已入库 | 包含 |
|------|------|--------|------|
| 宏观 & 事件类 | `macro_event/` | 8 | 政策解读、舆情风险预警、A股底部信号监控、底部政策信号助手、宏观经济分析、股票市场热点解读、行业速报、主题产业链深度分析 |
| 标的分析类 | `subject_analysis/` | 3 | 股票五维深度分析、股票对比分析、价值投资分析（另有 4 个基金分析骨架占位，见 `CONTRIBUTING.md`） |
| 行情复盘类 | `market_review/` | 2 | 股市每日收评、隔夜外围市场复盘 |
| 量化策略类 | `quant_strategy/` | 1 | 赛马量化策略选股 |
| 主观策略类 | `subjective_strategy/` | 1 | 激进成长策略 |

完整清单（含作者、版本、形态、数据来源）见根目录 [`ASSETS.md`](../ASSETS.md)。

## 统一契约（目标态）

所有 Skill 继承 `skills/base/skill_base.py` 的 `BaseSkill`：

- **输入**：`SkillContext`（由调度引擎注入，含 `gateway` 与 `params`）
- **输出**：`SkillResult`（统一结构，携带 `data_source` 来源标记）
- **取数**：目标为仅通过 `ctx.gateway` 调用下层网关（当前尚未落地，见上方现状说明）

```python
from skills.base.skill_base import BaseSkill, SkillContext, SkillResult

class MySkill(BaseSkill):
    skill_id = "my_skill"
    skill_name = "示例 Skill"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        df = ctx.gateway.query(...)          # 目标：统一走网关
        return SkillResult(skill_id=self.skill_id, success=True,
                           data={}, data_source=ctx.gateway.last_data_source)
```

## 新增一个 Skill

完整流程、目录规范、内容纪律与 PR 检查清单见根目录
**[`CONTRIBUTING.md`](../CONTRIBUTING.md)**。简要步骤：

1. 运行脚手架（按提示选择类别并填写信息）：
   ```bash
   python skills/scripts/scaffold_skill.py
   ```
2. 填充 `SKILL.md`（方法论/提示词 + 统一免责声明）、`scripts/`、真实样例报告。
3. 在 `manifest.yaml` 中维护输入输出契约，`calls_gateway` **据实填写**。
4. 同步登记：`ASSETS.md`、`<category>/README.md`、`scaffold_skill.py`、`CHANGELOG.md`。
