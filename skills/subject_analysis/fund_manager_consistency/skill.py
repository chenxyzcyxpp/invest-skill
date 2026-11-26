# -*- coding: utf-8 -*-
"""基金经理观点&持仓一致性分析 Skill —— 标的分析类"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class FundManagerConsistencySkill(BaseSkill):
    skill_id = "fund_manager_consistency"
    skill_name = "基金经理观点&持仓一致性分析"
    category = "subject_analysis"
    description = "分析基金经理观点与持仓的一致性"

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
