# -*- coding: utf-8 -*-
"""统一能力目录：把组件层 Skill 与应用层场景合并为一份「可调用能力清单」。

外部调用方（hermes / openclaw 等）只需：

    from apps.core.capabilities import get_capability, list_capabilities
    cap = get_capability("stock_pick")      # 场景，与原子 Skill 同一接口
    result = cap.run(ctx)                   # 与调用任何 Skill 完全一致

原子 Skill 与场景 Skill 在此被抹平差异：统一以 skill_id 寻址，
统一以 .run(ctx) 调用，统一返回 SkillResult。
"""
import importlib
from pathlib import Path

from .scene_skill import SceneSkill


def _discover_skills() -> dict:
    from .registry import all_skills
    return all_skills()


def _discover_scenes() -> dict:
    apps_pkg = importlib.import_module("apps")
    scen_dir = Path(apps_pkg.__file__).parent / "scenarios"
    out = {}
    for d in scen_dir.iterdir():
        if d.is_dir() and (d / "workflow.yaml").exists():
            out[d.name] = SceneSkill.from_dir(d)
    return out


def list_capabilities() -> dict:
    """返回 {id: skill_like} 合并清单（原子 Skill + 场景 Skill）。"""
    caps: dict = {}
    caps.update(_discover_skills())
    caps.update(_discover_scenes())
    return caps


def get_capability(skill_id: str):
    """按 id 取得一个可被 .run(ctx) 调用的能力（原子或场景）。"""
    return list_capabilities().get(skill_id)


def call(skill_id: str, ctx=None, **params):
    """便捷调用：按 id 取得能力并立即执行。"""
    cap = get_capability(skill_id)
    if cap is None:
        raise KeyError(f"unknown capability: {skill_id}")
    from skills.base.skill_base import SkillContext
    ctx = ctx or SkillContext(params=params)
    return cap.run(ctx, **params)
