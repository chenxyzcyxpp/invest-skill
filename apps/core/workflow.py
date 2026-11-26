# -*- coding: utf-8 -*-
"""Workflow 定义与加载（编排层的数据契约）。

workflow.yaml 是「拖拽编排」的产物：一份声明式文件，描述本场景由哪些
组件层 Skill 节点组成、并行分组与参数。应用层不含业务逻辑，只负责编排。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml


@dataclass
class Step:
    skill_id: str
    parallel_group: int = 0
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    name: str
    scene_id: str = ""
    description: str = ""
    steps: List[Step] = field(default_factory=list)

    def run(self, gateway=None):
        from .orchestrator import Orchestrator
        return Orchestrator().execute(self, gateway)


def load_workflow(path: str) -> "Workflow":
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    steps = [
        Step(
            skill_id=s["skill_id"],
            parallel_group=int(s.get("parallel_group", 0)),
            params=s.get("params") or {},
        )
        for s in doc.get("steps", [])
    ]
    return Workflow(
        name=doc.get("name", ""),
        scene_id=doc.get("scene_id", ""),
        description=doc.get("description", ""),
        steps=steps,
    )
