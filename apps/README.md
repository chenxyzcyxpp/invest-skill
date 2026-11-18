# apps/ 应用层（业务场景 · 编排层）

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
| 诊股 stock_diagnose | sentiment_risk_warning, stock_5d_deep_analysis, stock_comparative_analysis |
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
```

## 新增一个业务场景

1. 在 `scenarios/` 下新建目录，编写 `workflow.yaml`（仅组合已有 Skill）；
2. 运行脚手架可一键生成骨架：
   ```bash
   python apps/scripts/scaffold_app.py
   ```
3. 无需改动任何 Skill 或数据网关代码 —— 这正是分层架构带来的扩展性。

## 场景 = 可被外部「像 Skill 一样」调用的能力

应用层场景本质是「组合型 Skill」。通过 `apps/core/scene_skill.py` 的
`SceneSkill(BaseSkill)`，每个场景对外暴露与组件层原子 Skill **完全一致**
的 `run(ctx) -> SkillResult` 契约，因此可被外部 Agent / 编排引擎等调用方
**无差别地当作一个 skill 调用**——调用方无需知道它内部编排了哪些子 Skill。

`apps/core/capabilities.py` 提供统一能力目录，把原子 Skill 与场景 Skill
抹平差异，合并为一份按 `skill_id` 寻址的扁平清单：

```python
from apps.core.capabilities import get_capability, list_capabilities
from skills.base.skill_base import SkillContext

caps = list_capabilities()              # {id: 原子Skill 或 SceneSkill}
scene = get_capability("stock_pick")    # 场景，与原子 Skill 同一接口
result = scene.run(SkillContext())      # 与调用任何 Skill 完全一致
```

当前 `list_capabilities()` 共暴露 **25 个能力**（15 个已入库原子 Skill + 4 个占位骨架 + 6 个场景）。
外部调用方只需依赖这一层统一接口，不感知应用层/组件层的分界。

> 注意：场景编排链路已可运行（见下方 `--scene`），但多数原子 Skill 尚未适配为
> `BaseSkill`，因此当前执行返回的是**空结果骨架**（`data={}`），用于验证编排而非产出报告。
