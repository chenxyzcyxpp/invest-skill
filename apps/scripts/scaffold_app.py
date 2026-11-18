#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""invest-skill 应用层脚手架。

用法：
    python apps/scripts/scaffold_app.py

生成「应用层（架构第一层）」的标准骨架：
  - apps/core/        编排引擎：Skill 自动发现、Workflow 定义、串行/并行执行
  - apps/scenarios/   六大业务场景，每个场景一份 workflow.yaml（仅编排，不含逻辑）
  - apps/entry/       交互入口示例（python -m apps.entry.cli --scene <id>）

设计原则（与架构一致）：
  * 应用层只做 Skill 工作流编排，不含业务逻辑；
  * 业务场景 = 对组件层 Skill 的组合，新增场景优先复用已有 Skill；
  * Skill 统一经下层「可降级数据网关」取数，应用层无感数据源。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # .../apps

# ---------------------------------------------------------------------------
# 六大业务场景：scene_id -> (名称, 说明, [(skill_id, parallel_group, params)])
# 编排节点引用的 skill_id 必须存在于 skills/ 组件层。
# parallel_group 相同则并行，不同则按组号串行。
# ---------------------------------------------------------------------------
SCENARIOS = {
    "stock_pick": {
        "name": "选股场景",
        "desc": "条件选股、标的初筛、因子初筛、候选池生成",
        "steps": [
            ("macro_analysis", 0, {}),
            ("industry_brief", 0, {}),
        ],
    },
    "stock_diagnose": {
        "name": "诊股场景",
        "desc": "个股深度诊断、基本面体检、估值测算、企业风险画像",
        "steps": [
            ("sentiment_risk_warning", 0, {}),
            ("stock_5d_deep_analysis", 0, {}),
            ("stock_comparative_analysis", 0, {}),
        ],
    },
    "pre_market": {
        "name": "盘前场景",
        "desc": "隔夜外盘复盘、财经早报、政策速览、当日机会预判",
        "steps": [
            ("policy_interpret", 0, {}),
            ("macro_analysis", 0, {}),
            ("market_hotspot", 0, {}),
        ],
    },
    "intraday": {
        "name": "盘中场景",
        "desc": "异动监控、行情解读、资金流向、实时事件推送",
        "steps": [
            ("sentiment_risk_warning", 0, {}),
            ("market_hotspot", 0, {}),
        ],
    },
    "closing": {
        "name": "尾盘场景",
        "desc": "收盘复盘、市场强弱统计、尾盘机会扫描",
        "steps": [
            ("market_daily_review", 0, {}),
            ("industry_brief", 0, {}),
        ],
    },
    "strategy": {
        "name": "策略场景",
        "desc": "策略回测、拥挤度/羊群风险检测、策略赛马打分、策略归因",
        "steps": [
            ("macro_analysis", 0, {}),
            ("sentiment_risk_warning", 0, {}),
        ],
    },
}

# ---------------------------------------------------------------------------
# 核心文件内容
# ---------------------------------------------------------------------------
CORE_INIT = '''# -*- coding: utf-8 -*-
"""apps/core 编排引擎。"""
'''

REGISTRY_PY = '''# -*- coding: utf-8 -*-
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
'''

WORKFLOW_PY = '''# -*- coding: utf-8 -*-
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
'''

ORCHESTRATOR_PY = '''# -*- coding: utf-8 -*-
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
'''

ENTRY_INIT = '''# -*- coding: utf-8 -*-
"""apps/entry 交互入口。"""
'''

CLI_PY = '''# -*- coding: utf-8 -*-
"""应用层交互入口示例。

用法：
    python -m apps.entry.cli --scene stock_pick
    python -m apps.entry.cli --scene pre_market
    python -m apps.entry.cli --list
"""
import argparse
from pathlib import Path

from ..core.orchestrator import Orchestrator
from ..core.workflow import load_workflow

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def list_scenes():
    return sorted(p.name for p in SCENARIO_DIR.iterdir() if (p / "workflow.yaml").exists())


def run_scene(scene_id, gateway=None):
    wf_path = SCENARIO_DIR / scene_id / "workflow.yaml"
    if not wf_path.exists():
        raise SystemExit(f"未找到场景 {scene_id} 的 workflow.yaml")
    wf = load_workflow(wf_path)
    print(f"\\u25b6 运行场景：{wf.name}（{len(wf.steps)} 个 Skill 节点）")
    print(f"  说明：{wf.description}")
    results = Orchestrator().execute(wf, gateway)
    for sid, res in results.items():
        mark = "\\u2705" if res.success else "\\u274c"
        print(f"  {mark} {sid}  source={res.data_source}  data={res.data}")
    return results


def main():
    parser = argparse.ArgumentParser(description="invest-skill 应用层入口")
    parser.add_argument("--list", action="store_true", help="列出所有业务场景")
    parser.add_argument("--scene", choices=list_scenes(), help="业务场景 ID")
    args = parser.parse_args()
    if args.list:
        print("可用业务场景：")
        for s in list_scenes():
            print(f"  - {s}")
        return
    if not args.scene:
        parser.error("请通过 --scene 指定场景，或 --list 查看全部")
    run_scene(args.scene)


if __name__ == "__main__":
    main()
'''

TOP_README = '''# apps/ 应用层（业务场景 · 编排层）

> invest-skill 架构 **第一层**：应用层（面向用户，六大投资场景，编排层）。

本层**仅做 Skill 工作流编排，不含业务逻辑**，是用户直接交互的入口。
每个业务场景 = 对 `skills/` 组件层 Skill 的组合（声明式 `workflow.yaml`），
新增场景优先复用已有 Skill，而非从零写逻辑。

## 目录结构

```
apps/
├── core/                 # 编排引擎（不含业务）
│   ├── registry.py       # Skill 自动发现 / 注册中心
│   ├── workflow.py       # Workflow / Step 定义 + YAML 加载
│   └── orchestrator.py   # 串行/并行执行引擎
├── scenarios/            # 六大业务场景，每个一份 workflow.yaml
│   ├── stock_pick/       # 选股场景
│   ├── stock_diagnose/   # 诊股场景
│   ├── pre_market/       # 盘前场景
│   ├── intraday/         # 盘中场景
│   ├── closing/          # 尾盘场景
│   └── strategy/         # 策略场景
├── entry/                # 交互入口
│   └── cli.py            # python -m apps.entry.cli --scene <id>
└── scripts/
    └── scaffold_app.py   # 脚手架：生成/扩展应用层骨架
```

## 六大业务场景 → 组件层 Skill 映射

| 场景 | 编排的 Skill（skill_id） |
|------|--------------------------|
| 选股 stock_pick | macro_analysis, industry_brief |
| 诊股 stock_diagnose | sentiment_risk_warning, stock_5d_deep_analysis |
| 盘前 pre_market | policy_interpret, macro_analysis, market_hotspot |
| 盘中 intraday | sentiment_risk_warning, market_hotspot |
| 尾盘 closing | market_daily_review, industry_brief |
| 策略 strategy | macro_analysis, sentiment_risk_warning |

> 映射严格对应架构文档的「场景-Skill-网关」示例；Skill 节点全部经
> 下层「可降级数据网关」取数，应用层对数据源无感。

## 运行一个场景

```bash
# 查看全部场景
python -m apps.entry.cli --list

# 运行选股场景（当前 Skill 为骨架，返回空结果，仅验证编排链路）
python -m apps.entry.cli --scene stock_pick
```

## workflow.yaml 编排格式

```yaml
name: 选股场景
scene_id: stock_pick
description: 条件选股、标的初筛、因子初筛、候选池生成
steps:
  - skill_id: macro_analysis      # 引用 skills/ 组件层 skill_id
    parallel_group: 0             # 同组并行，不同组按组号串行
    params: {}                    # 透传给 Skill.run(**params)
  - skill_id: industry_brief
    parallel_group: 0
    params: {}
    parallel_group: 1
    params: {}
```

## 新增一个业务场景

1. 在 `scenarios/` 下新建目录，编写 `workflow.yaml`（仅组合已有 Skill）；
2. 运行脚手架可一键生成骨架：
   ```bash
   python apps/scripts/scaffold_app.py
   ```
3. 无需改动任何 Skill 或数据网关代码 —— 这正是分层架构带来的扩展性。
'''

APPS_INIT = '''# -*- coding: utf-8 -*-
"""apps/ 应用层（架构第一层，业务场景编排层）。"""
'''

SCENARIO_INIT = '''# 应用层业务场景目录（仅承载 workflow.yaml 编排定义）。
'''

WORKFLOW_YAML_TPL = '''name: {{name}}
scene_id: {{scene_id}}
description: "{{desc}}"
# 编排：仅组合组件层 Skill，不含业务逻辑；同 parallel_group 并行，不同组串行。
steps:
{{steps}}
'''

STEP_TPL = """  - skill_id: {skill_id}
    parallel_group: {parallel_group}
    params: {{}}
"""


def render(tpl: str, **kw) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def main() -> None:
    os.makedirs(ROOT, exist_ok=True)

    (ROOT / "README.md").write_text(TOP_README, encoding="utf-8")
    (ROOT / "__init__.py").write_text(APPS_INIT, encoding="utf-8")

    # core
    core = ROOT / "core"
    core.mkdir(exist_ok=True)
    (core / "__init__.py").write_text(CORE_INIT, encoding="utf-8")
    (core / "registry.py").write_text(REGISTRY_PY, encoding="utf-8")
    (core / "workflow.py").write_text(WORKFLOW_PY, encoding="utf-8")
    (core / "orchestrator.py").write_text(ORCHESTRATOR_PY, encoding="utf-8")

    # entry
    entry = ROOT / "entry"
    entry.mkdir(parents=True, exist_ok=True)
    (entry / "__init__.py").write_text(ENTRY_INIT, encoding="utf-8")
    (entry / "cli.py").write_text(CLI_PY, encoding="utf-8")

    # scenarios
    scen = ROOT / "scenarios"
    scen.mkdir(parents=True, exist_ok=True)
    (scen / "__init__.py").write_text(SCENARIO_INIT, encoding="utf-8")

    for scene_id, info in SCENARIOS.items():
        d = scen / scene_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text("", encoding="utf-8")
        steps = "".join(
            STEP_TPL.format(skill_id=sid, parallel_group=pg) for sid, pg, _ in info["steps"]
        )
        (d / "workflow.yaml").write_text(
            render(WORKFLOW_YAML_TPL, name=info["name"], scene_id=scene_id,
                   desc=info["desc"], steps=steps),
            encoding="utf-8",
        )

    print(f"✅ 应用层骨架生成完成：{len(SCENARIOS)} 个业务场景，"
          f"编排引擎位于 apps/core/")


if __name__ == "__main__":
    main()
