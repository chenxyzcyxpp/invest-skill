# -*- coding: utf-8 -*-
"""Skill 注册中心：自动发现 skills/ 组件层下所有 Skill。

应用层编排引擎据此把 workflow.yaml 中的 skill_id 解析为可执行的 Skill 实例。
"""
import importlib
from pathlib import Path

from skills.base.skill_base import BaseSkill

_CACHE: dict = {}


def _discover() -> None:
    skills_pkg = importlib.import_module("skills")
    root = Path(skills_pkg.__file__).parent
    for cat in root.iterdir():
        if not cat.is_dir() or cat.name in ("base", "scripts", "__pycache__"):
            continue
        for sk in cat.iterdir():
            if not sk.is_dir() or sk.name.startswith("_"):
                continue
            try:
                mod = importlib.import_module(f"skills.{cat.name}.{sk.name}.skill")
            except Exception:
                continue
            for v in vars(mod).values():
                if isinstance(v, type) and issubclass(v, BaseSkill) and v is not BaseSkill:
                    inst = v()
                    _CACHE[inst.skill_id] = inst


def get_skill(skill_id: str):
    if not _CACHE:
        _discover()
    return _CACHE.get(skill_id)


def all_skills() -> dict:
    if not _CACHE:
        _discover()
    return dict(_CACHE)
