# -*- coding: utf-8 -*-
"""编排引擎：按 workflow 串行/并行执行 Skill 节点。"""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from skills.base.skill_base import SkillContext, SkillResult

from .registry import get_skill


class Orchestrator:
    def execute(self, workflow, gateway=None, max_workers: int = 4) -> Dict[str, SkillResult]:
        results: Dict[str, SkillResult] = {}
        groups = sorted({s.parallel_group for s in workflow.steps})
        for g in groups:
            group_steps = [s for s in workflow.steps if s.parallel_group == g]
            if len(group_steps) == 1:
                results.update(self._run_one(group_steps[0], gateway))
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futs = [ex.submit(self._run_one, s, gateway) for s in group_steps]
                    for fut in futs:
                        results.update(fut.result())
        return results

    @staticmethod
    def _run_one(step, gateway):
        skill = get_skill(step.skill_id)
        if skill is None:
            return {step.skill_id: SkillResult(
                skill_id=step.skill_id, success=False,
                error=f"skill '{step.skill_id}' not found")}
        ctx = SkillContext(gateway=gateway, params=step.params)
        try:
            res = skill.run(ctx, **step.params)
        except Exception as e:  # 单节点失败不影响整体编排
            res = SkillResult(skill_id=step.skill_id, success=False, error=str(e))
        return {step.skill_id: res}
