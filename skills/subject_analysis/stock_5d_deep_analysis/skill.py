# -*- coding: utf-8 -*-
"""股票五维深度分析 Skill —— 标的分析类（subject_analysis）

真实业务逻辑在 SKILL.md（提示词规格）+ references/（五维度框架与输出模板）中，
由 LLM 读取提示词后经 Tushare / akshare / WebSearch 等工具取数执行。
本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景 workflow / 外部能力目录调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class Stock5dDeepAnalysisSkill(BaseSkill):
    skill_id = "stock_5d_deep_analysis"
    skill_name = "股票五维深度分析"
    category = "subject_analysis"
    description = "对单只 A 股标的执行五维度深度分析，可选叠加同业/行业对标"
    author = "Warwick"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入 Tushare / akshare / WebSearch 工具，
        #   将生成结果收敛为带 data_source / sources 列表的 SkillResult。
        # 注意：当前真实取数依赖工具直连（Tushare > akshare > 东方财富/腾讯兜底），
        #       不经 ctx.gateway（见 manifest.yaml calls_gateway=false）。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
