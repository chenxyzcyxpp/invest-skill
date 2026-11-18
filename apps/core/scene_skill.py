# -*- coding: utf-8 -*-
"""把应用层场景包装成「组合型 Skill」。

一个场景 = 对多个原子 Skill 的编排。通过继承 BaseSkill，场景对外暴露
与组件层 Skill **完全一致**的 run(ctx) -> SkillResult 契约，从而可被
hermes / openclaw 等外部调用方「像调用一个 skill 一样」直接调用——
调用方无需感知它内部编排了哪些子 Skill、走了哪个数据源。
"""
from pathlib import Path
from typing import Any, Dict, Optional

from skills.base.skill_base import BaseSkill, SkillContext, SkillResult

from .orchestrator import Orchestrator
from .workflow import Workflow, load_workflow


class SceneSkill(BaseSkill):
    """场景级 Skill：run() 内部用编排引擎执行自己的 workflow.yaml。"""

    category = "scenario"

    def __init__(self, scene_id: str, workflow: Workflow):
        self.skill_id = scene_id
        self.skill_name = workflow.name
        self.description = workflow.description
        self._workflow = workflow

    def run(self, ctx: SkillContext, **kwargs) -> SkillResult:
        sub: Dict[str, SkillResult] = Orchestrator().execute(self._workflow, ctx.gateway)
        data: Dict[str, Any] = {sid: r.data for sid, r in sub.items()}
        sources = sorted({r.data_source for r in sub.values() if r.data_source})
        ok = all(r.success for r in sub.values())
        err = "; ".join(f"{sid}:{r.error}" for sid, r in sub.items() if not r.success) or None
        return SkillResult(
            skill_id=self.skill_id,
            success=ok,
            data={"scene": self.skill_name, "skills": data},
            data_source=",".join(sources) if sources else None,
            error=err,
            meta={"node_count": len(sub)},
        )

    @classmethod
    def from_dir(cls, scene_dir) -> "SceneSkill":
        wf = load_workflow(str(Path(scene_dir) / "workflow.yaml"))
        return cls(Path(scene_dir).name, wf)
