# -*- coding: utf-8 -*-
"""激进成长策略 Skill —— 主观策略类（subjective_strategy）

真实业务逻辑在 SKILL.md（提示词规格）+ references/（Tushare MCP 截断绕过配方）
+ templates/（Feishu 报告模板）中，由 LLM 读取提示词后经 Tushare（MCP 或本地直连）
取数执行。本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景 workflow 调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class AggressiveGrowthStrategySkill(BaseSkill):
    skill_id = "aggressive_growth_strategy"
    skill_name = "激进成长策略"
    category = "subjective_strategy"
    description = "A 股小盘成长股评估框架：中证2000轮动选股、八步深度分析、综合评级"
    author = "Warwick"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入 Tushare（MCP 或本地直连）与
        #   cn-web-search 东财搜索工具，将生成结果收敛为带 data_source 的 SkillResult。
        # 注意：当前真实取数依赖 Tushare（行情/基本面数据源），
        #       不经 ctx.gateway（见 manifest.yaml calls_gateway=false）。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
