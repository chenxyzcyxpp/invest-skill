#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-skill 组件层脚手架。

用法：
    python skills/scripts/scaffold_skill.py

一次性生成「通用 Skill 组件层（架构第二层）」的标准骨架：
  - skills/base/        统一契约（Skill 基类、标准输入输出、上下文）
  - skills/<category>/  三大类目录 + README
  - skills/<category>/<skill_id>/  每个 Skill 的 manifest.yaml + skill.py + __init__.py

设计原则（与架构一致）：
  * 每个 Skill 输入输出契约标准化，可跨场景复用；
  * 所有 Skill 统一通过 ctx.gateway（可降级数据网关）取数，不直接接触底层数据源；
  * 返回结果携带 data_source 标记，体现实际数据来源。
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent  # .../skills

# ---------------------------------------------------------------------------
# Skill 定义：category -> (skill_id, skill_name, description)
# ---------------------------------------------------------------------------
SKILLS = {
    "macro_event": {
        "display": "宏观 & 事件类",
        "desc": "政策、舆情、宏观、热点、行业等宏观与事件维度的通用 Skill。",
        "items": [
            ("policy_interpret", "政策解读", "对宏观政策进行解读与影响分析"),
            ("sentiment_risk_warning", "舆情风险预警", "监测舆情异动并输出风险预警信号"),
            ("macro_analysis", "宏观经济分析", "分析宏观经济指标与周期位置"),
            ("market_hotspot", "股票市场热点解读", "解读市场热点板块与题材轮动"),
            ("industry_brief", "行业速报", "生成行业动态与事件速报"),
            ("concept_chain_analysis", "主题产业链深度分析", "主题/产业链上下游纵深拆解，可选持仓交叉"),
            ("a_share_bottom_monitor", "A股底部信号监控", "指数抄底位置监控，半年度重跑自更新"),
            ("policy_bottom_monitor", "底部政策信号助手", "政策托底强度双轴分级，与量价信号叠加"),
        ],
    },
    "subject_analysis": {
        "display": "标的分析类",
        "desc": "股票、基金、基金经理等标的维度的对比与画像 Skill。",
        "items": [
            ("stock_5d_deep_analysis", "股票五维深度分析", "单只股票五维深度分析，可选叠加同业/行业对标"),
            ("stock_comparative_analysis", "股票对比分析", "对 2-5 只股票（含 A 股及 A+H 混合）生成五维深度对比分析报告"),
            ("value_investing", "价值投资分析", "自上而下的基本面价值投资框架：五步分析、Step 0 取数校验、可选四层打分卡"),
            ("fund_analysis", "基金分析报告", "单只基金全面分析报告"),
            ("fund_compare", "基金对比分析", "多只基金横向对比分析"),
            ("fund_manager_profile", "基金经理画像", "刻画基金经理风格与业绩画像"),
            ("fund_manager_consistency", "基金经理观点&持仓一致性分析", "分析基金经理观点与持仓的一致性"),
        ],
    },
    "market_review": {
        "display": "行情复盘类",
        "desc": "每日收盘与隔夜外围等行情复盘 Skill。",
        "items": [
            ("market_daily_review", "股市每日收评", "基于开源数据源，自动生成 A 股/港股每个交易日的收盘点评报告"),
            ("overnight_review", "隔夜外围市场复盘", "生成面向A股盘前/盘中/盘后的隔夜外围市场复盘（今日五件事+决策时间线）"),
        ],
    },
    "quant_strategy": {
        "display": "量化策略类",
        "desc": "量化策略信号相关 Skill：策略匹配、持仓获取、选股池生成。",
        "items": [
            ("racing_quant_pick", "赛马量化策略选股", "从远程量化策略库匹配策略、获取持仓，输出选股池"),
        ],
    },
    "subjective_strategy": {
        "display": "主观策略类",
        "desc": "主观/基本面分析驱动的 Skill：LLM 八步分析、人工研判逻辑做个股/策略评估。",
        "items": [
            ("aggressive_growth_strategy", "激进成长策略", "基于 Tushare 的 A 股小盘成长股评估：中证2000轮动、八步分析、综合评级"),
        ],
    },
}


# ---------------------------------------------------------------------------
# 模板
# ---------------------------------------------------------------------------
BASE_SKILL_PY = '''# -*- coding: utf-8 -*-
"""通用 Skill 组件层 —— 统一契约定义。

所有组件层 Skill 必须继承 BaseSkill，遵循统一输入输出契约：
  * 输入：由调度引擎注入的 SkillContext（含数据网关与参数）
  * 输出：统一的 SkillResult（含 data_source 来源标记）
  * 取数：统一通过 ctx.gateway 调用下层「可降级数据网关」，禁止直连数据源
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SkillContext:
    """调度引擎注入的运行时上下文。"""

    gateway: Any = None                       # 可降级数据网关（架构第三层），由引擎注入
    params: Dict[str, Any] = field(default_factory=dict)  # 调用参数透传


@dataclass
class SkillResult:
    """所有 Skill 的统一输出契约。"""

    skill_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    data_source: Optional[str] = None         # 实际数据源标记（来自网关，如 tushare/akshare/tencent）
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """组件层 Skill 基类。子类只需实现 run()。"""

    # 元数据（建议子类覆盖）
    skill_id: str = ""
    skill_name: str = ""
    category: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict) if False else {}
    output_schema: Dict[str, Any] = {}

    @abstractmethod
    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        """执行业务逻辑。统一通过 ctx.gateway 取数，不直接接触数据源。"""
        raise NotImplementedError
'''

SKILL_PY_TPL = '''# -*- coding: utf-8 -*-
"""{{skill_name}} Skill —— {{category_display}}"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class {{Class}}Skill(BaseSkill):
    skill_id = "{{skill_id}}"
    skill_name = "{{skill_name}}"
    category = "{{category}}"
    description = "{{description}}"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 实现业务逻辑。
        # 取数统一走下层网关，例如：
        #     df = ctx.gateway.query("stock_daily", ts_code=..., ...)
        #     source = ctx.gateway.last_data_source   # 取实际来源标记
        # 不要在此直连 Tushare / Akshare / 网页源。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
'''

INIT_PY_TPL = '''# -*- coding: utf-8 -*-
from .skill import {{Class}}Skill

__all__ = ["{{Class}}Skill"]
'''

MANIFEST_TPL = '''skill_id: {{skill_id}}
skill_name: {{skill_name}}
category: {{category}}
description: "{{description}}"
calls_gateway: true          # 统一经可降级数据网关取数
# 标准输入契约（由调度引擎按此校验/透传）
input:
  - name: query
    type: string
    required: true
    description: "调用参数，具体字段随 Skill 业务而定"
# 标准输出契约
output:
  - name: data
    type: object
    description: "Skill 返回的核心结果"
  - name: data_source
    type: string
    description: "实际数据源标记（tushare/akshare/tencent）"
'''

CATEGORY_README_TPL = '''# {{category_display}}

> 组件层 · {{category_display}}

本目录下的 Skill 遵循 `skills/base/skill_base.py` 定义的统一契约，
统一通过 `ctx.gateway`（可降级数据网关）取数，不直接接触底层数据源，
可被上层任意业务场景（选股/诊股/盘前/盘中/尾盘/策略）编排调用。

## 包含的 Skill

| Skill ID | 名称 | 说明 |
|----------|------|------|
{{rows}}
'''

TOP_README = '''# skills/ 通用 Skill 组件层

> invest-skill 架构 **第二层**：通用 Skill 组件层（原子可复用能力）。

本层承载可被应用层（选股/诊股/盘前/盘中/尾盘/策略六大场景）通用调用的
**原子化 Skill**。每个 Skill 输入输出契约标准化、可跨场景复用，且**不直接调用**
任何原始数据源，统一通过下层「可降级数据网关」取数。

## 目录结构

```
skills/
├── base/                # 统一契约：Skill 基类、标准输入输出、上下文
│   └── skill_base.py
├── macro_event/         # 宏观 & 事件类
├── subject_analysis/    # 标的分析类
├── market_review/       # 行情复盘类
├── quant_strategy/      # 量化策略类
├── subjective_strategy/ # 主观策略类
└── scripts/
    └── scaffold_skill.py  # 脚手架：生成/扩展 Skill 骨架
```

## 四大类 Skill

| 类别 | 目录 | 包含 |
|------|------|------|
| 宏观 & 事件类 | `macro_event/` | 政策解读、舆情风险预警、宏观经济分析、股票市场热点解读、行业速报、主题产业链深度分析 |
| 标的分析类 | `subject_analysis/` | 股票五维深度分析、基金分析、基金对比、基金经理画像、基金经理一致性分析 |
| 行情复盘类 | `market_review/` | 股市每日收评、隔夜外围市场复盘 |
| 量化策略类 | `quant_strategy/` | 赛马量化策略选股 |
| 主观策略类 | `subjective_strategy/` | 激进成长策略 |

## 统一契约（重要）

所有 Skill 继承 `skills/base/skill_base.py` 的 `BaseSkill`：

- **输入**：`SkillContext`（由调度引擎注入，含 `gateway` 与 `params`）
- **输出**：`SkillResult`（统一结构，携带 `data_source` 来源标记）
- **取数**：仅通过 `ctx.gateway` 调用下层网关，禁止直连数据源

```python
from skills.base.skill_base import BaseSkill, SkillContext, SkillResult

class MySkill(BaseSkill):
    skill_id = "my_skill"
    skill_name = "示例 Skill"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        df = ctx.gateway.query(...)          # 统一走网关
        return SkillResult(skill_id=self.skill_id, success=True,
                           data={}, data_source=ctx.gateway.last_data_source)
```

## 新增一个 Skill

1. 运行脚手架（按提示选择类别并填写信息），或手动在对应类别目录下：
   ```bash
   python skills/scripts/scaffold_skill.py
   ```
2. 在 `<category>/<skill_id>/skill.py` 的 `run()` 中填充业务逻辑，统一经 `ctx.gateway` 取数。
3. 在 `<category>/<skill_id>/manifest.yaml` 中维护输入输出契约。
4. 在 `<category>/README.md` 的表格中补充一行。
'''

BASE_INIT = '''# -*- coding: utf-8 -*-
from .skill_base import BaseSkill, SkillContext, SkillResult

__all__ = ["BaseSkill", "SkillContext", "SkillResult"]
'''


def render(tpl: str, **kw) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def class_name(skill_id: str) -> str:
    parts = skill_id.split("_")
    return "".join(p.capitalize() for p in parts)


def main() -> None:
    os.makedirs(ROOT, exist_ok=True)

    # 顶层 README
    (ROOT / "README.md").write_text(TOP_README, encoding="utf-8")

    # base 契约
    base_dir = ROOT / "base"
    base_dir.mkdir(exist_ok=True)
    (base_dir / "skill_base.py").write_text(BASE_SKILL_PY, encoding="utf-8")
    (base_dir / "__init__.py").write_text(BASE_INIT, encoding="utf-8")

    total = 0
    for category, info in SKILLS.items():
        cat_dir = ROOT / category
        cat_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        for skill_id, skill_name, description in info["items"]:
            skill_dir = cat_dir / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)

            cls = class_name(skill_id)
            (skill_dir / "__init__.py").write_text(
                render(INIT_PY_TPL, Class=cls), encoding="utf-8")
            (skill_dir / "skill.py").write_text(
                render(SKILL_PY_TPL, skill_id=skill_id, skill_name=skill_name,
                       description=description, category=category,
                       category_display=info["display"], Class=cls),
                encoding="utf-8")
            (skill_dir / "manifest.yaml").write_text(
                render(MANIFEST_TPL, skill_id=skill_id, skill_name=skill_name,
                       description=description, category=category),
                encoding="utf-8")
            rows.append(f"| `{skill_id}` | {skill_name} | {description} |")
            total += 1

        (cat_dir / "__init__.py").write_text("", encoding="utf-8")
        (cat_dir / "README.md").write_text(
            render(CATEGORY_README_TPL, category_display=info["display"],
                   rows="\n".join(rows)),
            encoding="utf-8")

    # scripts 占位（本脚本自身已存在）
    print(f"✅ 组件层骨架生成完成：{total} 个 Skill，分布于 "
          f"{len(SKILLS)} 个类别目录。")


if __name__ == "__main__":
    main()
