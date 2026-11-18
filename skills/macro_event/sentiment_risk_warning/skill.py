# -*- coding: utf-8 -*-
"""舆情风险预警 Skill —— 宏观 & 事件类（占位骨架）。

注意：本 Skill 的真实执行规格在 SKILL.md（提示词）+ scripts/（可运行 Python）中定义，
是一套「脚本驱动型」实现：用「市场/个股舆情 + 量价相对特征」训练随机森林预测 A 股
下一交易日波动率风险并分级。其取数直连 Tushare / 东方财富 / 通达信（tdx），
不经由本项目可降级数据网关（ctx.gateway）。当前 run() 为占位实现，
待把 SKILL.md + scripts 适配进 BaseSkill 运行时（需 LLM + 本地数据源）后填充。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class SentimentRiskWarningSkill(BaseSkill):
    skill_id = "sentiment_risk_warning"
    skill_name = "舆情风险预警"
    category = "macro_event"
    description = "监测舆情异动并输出风险预警信号"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配 SKILL.md + scripts/ 的执行逻辑（脚本驱动，直连 tushare/东财，不经 ctx.gateway）。
        # 真实取数在 scripts/market_collect.py、scripts/market_risk.py、scripts/stock_risk_scorer/cli.py 中完成，
        # 数据源为 Tushare / 东方财富 / 通达信，属本项目可降级数据网关覆盖范围外，需单独适配。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
