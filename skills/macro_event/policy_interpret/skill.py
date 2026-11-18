# -*- coding: utf-8 -*-
"""政策解读 Skill —— 宏观 & 事件类（占位骨架）。

注意：本 Skill 的真实执行规格定义在同目录的 SKILL.md（提示词驱动的 LLM 技能，
依赖 WebSearch/WebFetch 抓取公开政府网站）。当前 run() 为占位实现，
待把 SKILL.md 适配进 BaseSkill 运行时（需 LLM + WebSearch 工具支撑）后填充。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class PolicyInterpretSkill(BaseSkill):
    skill_id = "policy_interpret"
    skill_name = "政策解读"
    category = "macro_event"
    description = "对宏观政策进行解读与影响分析"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配 SKILL.md 的提示词逻辑（需 LLM + WebSearch/WebFetch 运行时）。
        # 取数走公开政府网站，不经 ctx.gateway（本 Skill 不属于金融行情/财务数据源）。
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
