# -*- coding: utf-8 -*-
"""隔夜外围市场复盘 Skill —— 行情复盘类（market_review，提示词驱动型占位骨架）。

注意：本 Skill 的真实执行规格在 SKILL.md（提示词）中定义，是一套「提示词驱动型」
实现：生成面向 A 股盘前/盘中/盘后复核的隔夜外围市场复盘。取数经三个已连接 MCP
（东方财富妙想 / 腾讯自选股 / 通达信），不经由本项目可降级数据网关 ctx.gateway
（calls_gateway=false）。

本文件是供 invest-skill 框架「注册 / 加载」用的占位骨架：
- 在框架内运行时，继承真实的 `skills.base.skill_base.BaseSkill`；
- 在「独立打包」场景下（未安装 `skills.base`）会自动降级为最小占位基类，保证
  import overnight_review.skill 不报错，且类结构与框架保持一致。

当前 run() 为占位实现，待把 SKILL.md 适配进 BaseSkill 运行时（需 LLM + 已连接 MCP）后填充。
"""

from __future__ import annotations

try:
    # 框架内运行：使用项目真实基类
    from skills.base.skill_base import BaseSkill, SkillContext, SkillResult
except Exception:  # 独立打包场景：未安装 skills.base 时降级为最小占位
    from dataclasses import dataclass
    from typing import Any, Dict, Optional

    class SkillResult:
        """最小占位结果类，对齐框架 SkillResult 的关键字段。"""
        def __init__(self, skill_id: str, success: bool = True,
                     data: Optional[Dict[str, Any]] = None,
                     data_source: Optional[str] = None,
                     error: Optional[str] = None):
            self.skill_id = skill_id
            self.success = success
            self.data = data or {}
            self.data_source = data_source
            self.error = error

    class SkillContext:
        """最小占位上下文类，对齐框架 SkillContext 的关键字段。"""
        def __init__(self, gateway: Any = None, params: Optional[Dict[str, Any]] = None):
            self.gateway = gateway
            self.params = params or {}

    class BaseSkill:
        """独立场景下的占位基类，仅用于保证 import 不报错与结构兼容。"""
        skill_id: str = ""
        skill_name: str = ""
        category: str = ""
        description: str = ""

        def run(self, ctx: Any, **kwargs: Any) -> Any:
            raise NotImplementedError(
                "在 invest-skill 框架内运行时由真实 BaseSkill 提供 run()；"
                "独立运行请遵循 SKILL.md 提示词。"
            )


class OvernightReviewSkill(BaseSkill):
    skill_id = "overnight_review"
    skill_name = "隔夜外围市场复盘"
    category = "market_review"
    description = "生成面向A股盘前/盘中/盘后复核的隔夜外围市场复盘（全球行情/今日五件事/主线分歧/决策时间线）"

    def run(self, ctx: SkillContext, **kwargs: Any) -> SkillResult:
        # TODO: 适配 SKILL.md 提示词执行逻辑（提示词驱动，取数经已连接 MCP，
        # 不经 ctx.gateway）。辅助脚本 scripts/render_self_contained_html.py、
        # scripts/normalize_traceability.py 用于 HTML 自包含化与溯源编号规范化。
        data: Dict[str, Any] = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None)
            if ctx is not None else None,
        )
