# -*- coding: utf-8 -*-
"""宏观经济分析 Skill —— 宏观 & 事件类

真实实现见 SKILL.md（提示词）+ scripts/macro_snapshot.py（akshare 离线兜底），
本文件为占位骨架。

数据来源：实时 MCP 源（mx-ds-mcp 东方财富妙想 / tdx-connector 通达信）优先，
离线脚本（akshare）兜底；均不经 ctx.gateway。调用方若要执行，应由 LLM 读取
SKILL.md 并按其流程驱动脚本/外部 MCP 源。

作者：姜青
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class MacroAnalysisSkill(BaseSkill):
    skill_id = "macro_analysis"
    skill_name = "宏观经济分析"
    category = "macro_event"
    # 真实逻辑在 SKILL.md + scripts/，需 LLM + 外部数据源支撑，尚未包装为 BaseSkill
    description = "基于五维度宏观框架映射到 A 股行业与风格配置，产出宏观—权益投资分析报告"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill 后，此处包装 SKILL.md + scripts/ 执行并收敛为带 sources 列表的 SkillResult。
        # 取数走 MCP 实时源 / akshare，非 ctx.gateway，故 data_source 标 None 并据实说明。
        return SkillResult(
            skill_id=self.skill_id,
            success=False,
            data={},
            data_source=None,
            error="未适配为 BaseSkill：请按 SKILL.md 由 LLM 驱动 MCP 实时源 / scripts/macro_snapshot.py 执行（不经 ctx.gateway）",
            meta={"runtime": "script_based", "calls_gateway": False, "author": "姜青"},
        )
