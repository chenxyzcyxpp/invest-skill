# 贡献指南

欢迎为 invest-skill 贡献！本项目最有价值的贡献形式是**新增一个金融 Skill**，
其次是数据源适配、场景编排方案、文档与样例补充。

- 提交前请先开 **Issue** 描述设计，便于评审与避免重复。
- 所有内容须遵守本文的[内容纪律](#内容纪律必读)；PR 请照[检查清单](#pr-检查清单)自查。
- 参与本项目即表示你同意贡献内容按 [Apache-2.0](LICENSE) 授权，且你有权提交该内容。

---

## 快速选择贡献方向

| 你想做的事 | 从哪开始 |
|---|---|
| 新增一个 Skill | [下方「新增 Skill」](#新增一个-skill) |
| 认领占位骨架 | [「Good first issue」](#good-first-issue认领占位骨架) |
| 让某个 Skill 走统一网关 | 先读 [`skills/base/GATEWAY_REFERENCE.md`](skills/base/GATEWAY_REFERENCE.md)，再开 Issue 讨论 |
| 新增业务场景 | 在 `apps/scenarios/` 下加 `workflow.yaml`，见 [`apps/README.md`](apps/README.md) |
| 修文档 / 补样例 / 翻译 | 直接 PR 即可 |

---

## 新增一个 Skill

### 1) 生成骨架

```bash
python skills/scripts/scaffold_skill.py
```

或手动在对应分类目录下创建 `skills/<category>/<skill_id>/`。
分类目前为：`macro_event` / `subject_analysis` / `market_review` /
`quant_strategy` / `subjective_strategy`。若现有分类都不合适，开 Issue 讨论新增分类。

### 2) 目录规范

```
skills/<category>/<skill_id>/
├── SKILL.md            # 必需：方法论/提示词主文件，含 frontmatter
├── manifest.yaml       # 必需：skill_id/name/category/author/version/runtime/calls_gateway + 输入输出契约
├── skill.py            # 必需：BaseSkill 子类（可为占位骨架，须可导入）
├── __init__.py         # 必需
├── references/         # 参考文档：数据源、模板、样例输出、验证规则
├── scripts/            # 可运行脚本（如有）
└── README.md           # 可选但推荐
```

### 3) 关键字段说明

`manifest.yaml` 中：

- `author`：**据实署名**，多位作者用 `、` 分隔；需要匿名可用昵称。
- `version`：与 `SKILL.md` frontmatter 保持一致。
- `runtime`：`llm_prompt`（纯提示词）/ `script_based`（提示词+可运行脚本）/ `base_skill`（已包装为 BaseSkill）。
- `calls_gateway`：**据实填写**。当前所有 Skill 均直连各自数据源，填 `false`；
  只有真正经 `ctx.gateway` 取数时才填 `true`。这一项不许为了"看起来合规"而虚报。
- `input` / `output`：标准输入输出契约，供调度引擎校验与透传。

`SKILL.md` 末尾必须包含统一的**免责声明与风险提示**（见下节模板）。

### 4) 登记

新增后需同步更新：

1. `ASSETS.md` —— 增加资产详情段、目录一览表行，并更新底部统计数字；
2. `skills/<category>/README.md` —— 表格补一行；
3. `skills/scripts/scaffold_skill.py` —— `SKILLS` 注册表补一项；
4. `README.md` —— 若属新增分类或重要能力，更新速览表与能力总览图；
5. `CHANGELOG.md` —— 记一笔。

---

## 内容纪律（必读）

本项目是投研工具库，**不提供投资建议**。所有贡献必须遵守：

1. **不编造**：取数失败、字段缺失、源无数据，一律如实标注 `数据缺失 / N/A / 源不可用`，
   严禁由模型生成数字、结论或引用。
2. **可溯源**：输出字段标注数据来源与获取时间，读者能区分「实测数据」与「模型推断」。
3. **事实与结论分离**：推断须显式标注「本报告观点」「推演」，不得当既成事实陈述。
4. **明确报错**：全源失败返回 error，不静默回退到过期缓存或占位值。
5. **不提供买卖/仓位/止损建议**；重点个股统一称「重点公司验证」。
6. **凭据零硬编码**：任何数据库/API 地址、账号、密码必须由使用者通过环境变量或
   配置注入，代码与文档中不得出现真实凭据或可连接的默认值。
7. **数据合规**：不得内置、分发第三方行情数据；示例使用脱敏/历史样例数据，
   并注明来源与使用条款由接入方自行负责。

### 免责声明模板（放入每个 `SKILL.md` 末尾）

```markdown
## 免责声明与风险提示

本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
```

---

## Good first issue：认领占位骨架

以下 4 个目录目前只有骨架（`__init__.py` / `manifest.yaml` / `skill.py`），
**非常适合作为第一个 PR**：

| 目录 | 待实现内容 |
|---|---|
| `skills/subject_analysis/fund_analysis/` | 单只基金的投资风格、持仓与绩效分析 |
| `skills/subject_analysis/fund_compare/` | 多只基金横向对比（收益/回撤/风格） |
| `skills/subject_analysis/fund_manager_profile/` | 基金经理履历、风格与历史业绩画像 |
| `skills/subject_analysis/fund_manager_consistency/` | 经理公开观点与实际持仓的一致性核验 |

认领方式：在对应 Issue 下留言，然后按上文「新增一个 Skill」流程填充，
并把 `ASSETS.md` 中该行状态从「骨架占位」改为「已入库」。

---

## PR 检查清单

- [ ] `python -m py_compile` 通过（所有新增/修改的 `.py`）
- [ ] `manifest.yaml` 可被 `yaml.safe_load` 解析，字段齐全、`calls_gateway` 据实
- [ ] `skill.py` 可导入，类名与 `__init__.py` 一致
- [ ] `SKILL.md` 含统一免责声明；无真实凭据、无内部环境绝对路径
- [ ] 样例数据已脱敏，不含实时或未授权数据
- [ ] 已同步更新 `ASSETS.md`、分类 `README.md`、脚手架注册表、`CHANGELOG.md`
- [ ] 未提交 `__pycache__/`、`.pyc`、`.env`、本地数据交付物（已在 `.gitignore`）

---

## 本地自检

```bash
# 编译所有 Python
python -m compileall -q skills apps

# 校验所有 manifest
python -c "
import yaml, glob
for f in glob.glob('skills/**/manifest.yaml', recursive=True):
    yaml.safe_load(open(f, encoding='utf-8'))
print('all manifests OK')
"

# 验证编排链路
python -m apps.entry.cli --list
```
