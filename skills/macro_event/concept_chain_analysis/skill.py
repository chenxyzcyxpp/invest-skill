# -*- coding: utf-8 -*-
"""主题产业链深度分析 Skill —— 宏观 & 事件类（与 market_hotspot 并列互补）

真实业务逻辑在 SKILL.md（提示词规格）+ references/（产业链分层方法论与输出模板）中，
由 LLM 读取提示词后经 AkShare + WebSearch/WebFetch 取数执行，可选衔接 racing_quant_pick
的持仓数据做交叉分析。本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景
workflow / 外部能力目录调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class ConceptChainAnalysisSkill(BaseSkill):
    skill_id = "concept_chain_analysis"
    skill_name = "主题产业链深度分析"
    category = "macro_event"
    description = "以产业逻辑驱动，对主题/产业链上下游纵深拆解并可选叠加持仓交叉分析"
    author = "Warwick"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入 AkShare / WebSearch / WebFetch 工具，
        #   可选通过 ctx.capabilities 调用 racing_quant_pick 获取策略持仓做交叉分析，
        #   将生成结果收敛为带 sources 列表的 SkillResult。
        # 注意：当前真实取数依赖 AkShare 直连 + 公开网站检索（WebSearch/WebFetch），
        #       不经 ctx.gateway（见 manifest.yaml calls_gateway=false）。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
