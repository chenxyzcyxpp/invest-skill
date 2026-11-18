# -*- coding: utf-8 -*-
"""通用 Skill 组件层 —— 统一契约定义。

所有组件层 Skill 必须继承 BaseSkill，遵循统一输入输出契约：
  * 输入：由调度引擎注入的 SkillContext（含数据网关与参数）
  * 输出：统一的 SkillResult（含 data_source 来源标记）
  * 取数：统一通过 ctx.gateway 调用下层「可降级数据网关」，禁止直连数据源
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SkillContext:
    """调度引擎注入的运行时上下文。"""

    gateway: Any = None                       # 可降级数据网关（架构第三层），由引擎注入
    params: Dict[str, Any] = field(default_factory=dict)  # 调用参数透传


@dataclass
class SkillResult:
    """所有 Skill 的统一输出契约。"""

    skill_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    data_source: Optional[str] = None         # 实际数据源标记（来自网关，如 tushare/akshare/tencent）
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """组件层 Skill 基类。子类只需实现 run()。"""

    # 元数据（建议子类覆盖）
    skill_id: str = ""
    skill_name: str = ""
    category: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict) if False else {}
    output_schema: Dict[str, Any] = {}

    @abstractmethod
    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        """执行业务逻辑。统一通过 ctx.gateway 取数，不直接接触数据源。"""
        raise NotImplementedError
