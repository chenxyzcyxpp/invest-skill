# -*- coding: utf-8 -*-
"""股票市场热点解读 Skill —— 宏观 & 事件类

真实业务逻辑在 SKILL.md（提示词规格）+ references/output-template.md（输出模板）中，
由 LLM 读取提示词后经 AkShare + WebSearch/WebFetch 取数执行。
本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景 workflow / 外部能力目录调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class MarketHotspotSkill(BaseSkill):
    skill_id = "market_hotspot"
    skill_name = "股票市场热点解读"
    category = "macro_event"
    description = "识别并解读当日/阶段板块、题材热点与资金主线"
    author = "周周"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入 AkShare / WebSearch / WebFetch 工具，
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
