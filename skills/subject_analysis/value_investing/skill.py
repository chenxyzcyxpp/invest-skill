# -*- coding: utf-8 -*-
"""价值投资分析 Skill —— 标的分析类（subject_analysis）

真实业务逻辑在 SKILL.md（提示词规格）+ references/（方法论、数据源、样例报告）中，
由 LLM 读取提示词后经使用者配置的工具（MCP / Tushare / 公开网页）取数执行。
scripts/value_scorecard.py 提供离线可跑的四层加权打分卡（可选量化层）。
本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景 workflow / 外部能力目录调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class ValueInvestingSkill(BaseSkill):
    skill_id = "value_investing"
    skill_name = "价值投资分析"
    category = "subject_analysis"
    description = "自上而下的基本面价值投资分析框架，好公司≠好股票、价值≠价格，只给分析框架不荐股"
    author = "姜青、Warwick"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入使用者配置的数据源工具，
        #   将五步分析结果与 Step 0 数据表收敛为带 data_source 的 SkillResult。
        # 注意：当前真实取数依赖工具直连，不经 ctx.gateway（见 manifest.yaml calls_gateway=false）。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
