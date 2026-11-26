# -*- coding: utf-8 -*-
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
    print(f"\u25b6 运行场景：{wf.name}（{len(wf.steps)} 个 Skill 节点）")
    print(f"  说明：{wf.description}")
    results = Orchestrator().execute(wf, gateway)
    for sid, res in results.items():
        mark = "\u2705" if res.success else "\u274c"
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
