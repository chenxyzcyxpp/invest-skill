# -*- coding: utf-8 -*-
"""A股底部信号监控 Skill —— 宏观 & 事件类

真实实现见 SKILL.md（提示词）+ scripts/（可运行 Python），本文件为占位骨架。

数据来源：直连 Tushare Pro（daily / index_dailybasic，走环境变量 TUSHARE_TOKEN），
不经 ctx.gateway。调用方若要执行监控，应由 LLM 读取 SKILL.md 并按其流程
驱动 scripts/ 中的 fetch_data.py / check_integrity.py / monitor.py / recompute_stats.py。

作者：Warwick
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class AShareBottomMonitorSkill(BaseSkill):
    skill_id = "a_share_bottom_monitor"
    skill_name = "A股底部信号监控"
    category = "macro_event"
    # 真实逻辑在 SKILL.md + scripts/，需 LLM + Tushare 数据源支撑，尚未包装为 BaseSkill
    description = "对主要指数进行抄底位置监控，并支持半年度重跑自更新（基于2014-2026十二年回测信号地图）"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill 后，此处包装 scripts/ 执行并收敛为带 sources 列表的 SkillResult。
        # 取数直连 Tushare（非 ctx.gateway），故 data_source 标 None 并据实说明。
        return SkillResult(
            skill_id=self.skill_id,
            success=False,
            data={},
            data_source=None,
            error="未适配为 BaseSkill：请按 SKILL.md 由 LLM 驱动 scripts/ 执行（直连 Tushare，不经 ctx.gateway）",
            meta={"runtime": "script_based", "calls_gateway": False, "author": "Warwick"},
        )
