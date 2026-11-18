# -*- coding: utf-8 -*-
"""赛马量化策略选股 Skill —— 量化策略类（quant_strategy）

真实业务逻辑在 SKILL.md（提示词规格）+ references/（策略库 schema 与输出模板）中，
由 LLM 读取提示词后经 MySQL 策略库 / WebSearch 等工具取数执行。
本文件仅占位，待适配为 BaseSkill + LLM 运行时后可被场景 workflow / 外部能力目录调用。
"""
from __future__ import annotations

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult


class RacingQuantPickSkill(BaseSkill):
    skill_id = "racing_quant_pick"
    skill_name = "赛马量化策略选股"
    category = "quant_strategy"
    description = "从远程量化策略库智能匹配策略、获取持仓，输出选股池与策略画像"
    author = "Warwick"
    version = "1.0.0"

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        # TODO: 适配为 BaseSkill + LLM 运行时：
        #   加载 SKILL.md 提示词，注入 MySQL 策略库查询工具（可配置 endpoint）与
        #   个股分析工具，将生成结果收敛为带 data_source / sources 列表的 SkillResult。
        # 注意：当前真实取数依赖工具直连远程 MySQL 策略库（策略信号源），
        #       不经 ctx.gateway（见 manifest.yaml calls_gateway=false）。
        data = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None),
        )
