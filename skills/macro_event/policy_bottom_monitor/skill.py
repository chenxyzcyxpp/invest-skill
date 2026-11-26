# -*- coding: utf-8 -*-
"""底部政策信号助手 Skill —— 宏观 & 事件类

真实实现见 SKILL.md（提示词）+ scripts/（可运行 Python），本文件为占位骨架。

数据来源：复用同目录族 a_share_bottom_monitor 的本地 K 线
（../a_share_bottom_monitor/data/*.csv，cron 每日增量更新），不经 ctx.gateway。
调用方若要执行判断，应由 LLM 读取 SKILL.md 并按其流程驱动
scripts/ 中的 policy_check.py / recompute_policy_stats.py。

作者：Warwick
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class PolicyBottomMonitorSkill(BaseSkill):
    skill_id = "policy_bottom_monitor"
    skill_name = "底部政策信号助手"
    category = "macro_event"
    # 真实逻辑在 SKILL.md + scripts/，需 LLM 驱动，尚未包装为 BaseSkill
    description = "对政策进行托底强度双轴分级（S/A/B/C/D），与量价抄底信号叠加输出综合抄底判断"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill 后，此处包装 scripts/ 执行并收敛为带 sources 列表的 SkillResult。
        # 取数复用本地 K 线（非 ctx.gateway），故 data_source 标 None 并据实说明。
        return SkillResult(
            skill_id=self.skill_id,
            success=False,
            data={},
            data_source=None,
            error="未适配为 BaseSkill：请按 SKILL.md 由 LLM 驱动 scripts/ 执行（复用 a_share_bottom_monitor 本地 K 线，不经 ctx.gateway）",
            meta={"runtime": "script_based", "calls_gateway": False, "author": "Warwick"},
        )
