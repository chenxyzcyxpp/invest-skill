# -*- coding: utf-8 -*-
"""行业速报 Skill —— 宏观 & 事件类（脚本驱动型占位骨架）。

注意：本 Skill 的真实执行规格在 SKILL.md（提示词）+ scripts/industry_flash.py（可运行 Python）
中定义，是一套「脚本驱动型」实现：以申万一级行业为口径，输出行业强弱排名、资金流向、
事件速递与可解释信号（R01-R06），生成每日行业速报。其取数直连 Tushare / Akshare / 腾讯财经
（三级可降级，经 scripts/industry_flash.py 内部网关，不经由本项目可降级数据网关 ctx.gateway）。

本文件是供 invest-skill 框架「注册 / 加载」用的占位骨架：
- 在框架内运行时，继承真实的 `skills.base.skill_base.BaseSkill`；
- 在「独立打包」场景下（未安装 `skills.base`，例如直接解压本压缩包查看），会自动降级为
  最小占位基类，保证 `import industry_brief.skill` 不报错，且类结构与框架保持一致。

当前 run() 为占位实现，待把 SKILL.md + scripts 适配进 BaseSkill 运行时（需 LLM + 本地数据源）后填充。
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
                "独立运行请使用 scripts/industry_flash.py。"
            )


class IndustryBriefSkill(BaseSkill):
    skill_id = "industry_brief"
    skill_name = "行业速报"
    category = "macro_event"
    description = "以申万一级行业为口径，输出行业强弱排名、资金流向、事件速递与可解释信号"

    def run(self, ctx: SkillContext, **kwargs: Any) -> SkillResult:
        # TODO: 适配 SKILL.md + scripts/industry_flash.py 的执行逻辑（脚本驱动，直连
        # tushare/akshare/腾讯，不经 ctx.gateway）。
        # 真实取数在 scripts/industry_flash.py 内完成（三级可降级网关 + 演示数据兜底），
        # 数据源为 Tushare / Akshare / 腾讯财经，属本项目可降级数据网关覆盖范围外，需单独适配。
        data: Dict[str, Any] = {}
        return SkillResult(
            skill_id=self.skill_id,
            success=True,
            data=data,
            data_source=getattr(ctx.gateway, "last_data_source", None)
            if ctx is not None else None,
        )
