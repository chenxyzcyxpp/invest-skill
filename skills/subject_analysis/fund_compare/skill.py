# -*- coding: utf-8 -*-
"""基金对比分析 Skill —— 标的分析类"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class FundCompareSkill(BaseSkill):
    skill_id = "fund_compare"
    skill_name = "基金对比分析"
    category = "subject_analysis"
    description = "多只基金横向对比分析"

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
