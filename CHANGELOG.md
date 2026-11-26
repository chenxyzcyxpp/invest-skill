# Changelog

本项目所有 notable 变更记录在此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- `apps/scenarios/session_analysis`（盘前/午盘/盘后综合分析）：新增应用层场景（作者 Warwick），以声明式时段配方 `recipes/session_map.yaml` 编排现有 Skill，产出可追溯 MD 报告 + 可分享 PNG 卡片。盘前 6 步、盘后 7 步采纳投研作业流程 SOP 实战，午盘 3 步为实验性建议组合；含时点纪律、失败隔离、依赖跳过三条 SOP 实战纪律；随每次 Skill 更新自动迭代。**直接取代**旧三空壳场景 `pre_market`/`intraday`/`closing`（场景数 6→4、能力总数 25→23）；附真实历史数据样例 MD + PNG（`--check` 0 missing）。
- `presentation/`（小白卡可视化输出层）：新增横切输出层（layer: output，不计入 15 个 Skill），把 15 个分析 Skill 的报告翻译成小白卡片 PNG。含 `SKILL.md` v2.0.0（场景触发协议 + 一问一卡一图 + data_as_of 新鲜度 + 15 卡型映射 + 8 条红线）、`scripts/render_cards.py`（确定性渲染 + `--check` 数字回比）、`scripts/html2png.py`（整页 PNG）、4 张真实数据样例卡；署名刘宇恒。入库时补价值投资卡型（第 15 卡型）、把原宿主概念改成本库口径，并修复 `html2png.py` 缺 `import sys` 与 Chrome root 环境缺 `--no-sandbox` 两处缺陷。
- `value_investing`（价值投资分析）：新增标的分析类 Skill，自上而下基本面五步框架 + Step 0 取数校验 + 可选四层打分卡，作者姜青、Warwick；附中际旭创（300308.SZ）完整样例报告。已登记 `ASSETS.md`、标的分析类 README、脚手架注册表与速览表（已入库 14 → 15）。
- `SYNC.md`：Gitee 主仓库与 GitHub 公开镜像的双平台版本对应关系、同步 SOP 与安全红线；
  `README.md`「版本」一节挂上入口。

---

## [0.1.0] - 2026-11-07 — 首个开源版本

开源就绪整改：**定位诚实化、可跑通、可合规使用、可参与贡献**。

### Security
- 移除 `racing_quant_pick` 中硬编码的数据库地址/账号/密码：连接参数改为**必须由使用者
  通过环境变量或 CLI 注入，缺失即明确报错**，仓库不再内置任何默认数据源；
  同步清理 `SKILL.md`、`manifest.yaml`、`strategy-schema.md` 中的明文凭据与示例库名。

### Added
- `LICENSE`（Apache License 2.0 全文）与 `NOTICE`（版权与第三方说明）。
- `CONTRIBUTING.md`：新增 Skill 完整流程、内容纪律、凭据零硬编码要求、
  免责声明模板、PR 检查清单，以及 4 个基金分析占位的 **good first issue** 认领入口。
- `README.md` 重写：一句话定位、状态徽章、顶层免责声明、14 个 Skill 速览表、
  **真实可跑的 Quickstart**、能力总览图与真实报告截图、防幻觉护栏、Roadmap。
- `docs/images/`：能力总览图 + 隔夜外围市场复盘真实报告截图。
- `CHANGELOG.md` 本文件。

### Changed
- **项目定位纠偏**：从"已实现的多源可降级数据网关架构"改为
  "**14 个开箱即用的金融投研 Skill 资产库**"；明确标注数据网关目前**仅为设计规范
  （未实现）**、14/14 个 Skill 均为直连取数（`calls_gateway: false`），
  知识图谱/运营后台/对话入口为规划中。不再做未落地的架构承诺。
- Quickstart 改为 Gitee 仓库地址与真实 CLI（`python -m apps.entry.cli --list` /
  `--scene`），并如实说明当前场景编排返回空骨架结果、不产出完整报告。
- 文档数字对账：`GATEWAY_REFERENCE.md` 8→14 个 Skill、
  `apps/README.md` 19→24 个能力、`skills/README.md` 四大类→五大类及取数表述。
- 清理临时环境痕迹：早期回测数据不再硬编码环境特定绝对路径，改为可选环境变量
  `POLICY_EARLY_DATA_DIR`（未配置则跳过并标注样本区间）。

---

## [0.0.1] - 2026-10 ~ 2026-11 — 内部建设期

按提交历史摘录的主要里程碑（未发版）：

- **初始化**：项目 README 与架构草案、应用层与组件层骨架、打通 Skill 编排链路。
- **Skill 陆续入库**（按时间）：政策解读、舆情风险预警、A股底部信号监控、
  宏观经济分析、股票市场热点解读、行业速报、股票五维深度分析、主题产业链深度分析、
  赛马量化策略选股、股市每日收评、股票对比分析、激进成长策略、
  底部政策信号助手、隔夜外围市场复盘 —— 共 **14 个**。
- **规范建设**：新增数据网关参考规范（四级降级链 + 防幻觉护栏）；
  统一所有 Skill 产出内容的标准免责声明；作者署名匿名化（周琳燕 → 周周）。
- **结构调整**：新建 `subjective_strategy` 分类并将激进成长策略移入；
  补齐激进成长策略「道·法·术·器」方法论；多次 `.gitignore` 与资产清单维护。
- **资产清单**：`ASSETS.md` 持续维护，最终统计为 已入库 14 / 骨架占位 4 / 共 18。
