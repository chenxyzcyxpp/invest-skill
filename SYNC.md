# 双平台同步与版本对应关系

> 本文是 invest-skill 的**发布运维文档**：记录 Gitee（开发主仓库）与 GitHub（公开镜像）
> 的版本对应关系、历史差异的成因，以及可复现的同步操作。
> 目标是任何时候都能回答三个问题：**两边是不是同一份内容？差在哪？怎么对齐？**

## 1. 平台对照

| 项 | Gitee · 主仓库 | GitHub · 公开镜像 |
|---|---|---|
| 仓库地址 | https://gitee.com/warwickInv/invest-skill | https://github.com/chenxyzcyxpp/invest-skill |
| 所属账号 | `warwickInv` | `chenxyzcyxpp` |
| 定位 | 开发主仓库，日常提交 / PR / Tag 都在这里 | 对外展示镜像，只保留当前内容快照 |
| 默认分支 | `main` | `main` |
| 其他分支 | `master`、`feat/a-share-bottom-monitor-v1.1` 等 | 无 |
| Git 历史 | 完整（内部建设期 → 首个开源版本） | **单提交**，不携带历史 |
| Tag | `v0.1.0` | 无 |
| README 指向 | clone 地址与徽章以 Gitee 为准 | 仓库描述 / homepage 回指 Gitee |

> ⚠️ **两个平台的 commit SHA 不会相同**——GitHub 仓库是重新 `git init` 后推送的快照。
> 判断内容是否一致，请比对 **tree SHA**（第 5.3 节），而不是 commit SHA。

## 2. 当前版本对应

| 内容版本 | Gitee `main` | GitHub `main` | 文件数 | 基线 tree SHA | 同步日期 |
|---|---|---|---|---|---|
| `v0.1.0` · 底部信号监控 `1.4.1` | `253624c` | `e84d71d` | 223 | `3581fc24fe4d798625f7e89920d319ad56fc038a` | 2026-11-17 |

- **内容版本**是对应关系的锚点（取自 `CHANGELOG.md` 与各 Skill 的 `manifest.yaml`），
  不随文档自身改动而变。
- 上表的 commit / tree SHA 是**写入本文时那一刻的快照记录**；由于本文自身也是被同步的内容，
  每次修改本文都会让 HEAD 再次前进——这是预期行为，**不必反复追平**，下次内容版本真正变化
  时一并更新即可。任何时候都可用第 5.3 节的命令确认两边内容一致。
- 项目版本号与 Skill 版本号是两套体系：前者是整个仓库的发版号，后者是单个 Skill 的迭代号。

## 3. 为什么 GitHub 只有快照（背景与红线）

2026-11 同步 GitHub 前的安全扫描发现：git 历史中有 **13 / 35 个提交**包含
`racing_quant_pick` 的明文数据库密码（当时写在 `strategy-schema.md` 与
`fetch_strategy_positions.py` 中）。当前 HEAD 已在 `v0.1.0` 整改中清理干净，
但历史提交里的密钥仍可被 `git log -p` 检出。

因此同步策略定为：**GitHub 只推当前快照，不推历史**。做法是从 HEAD 用
`git archive` 导出文件，在新目录重新初始化仓库后做单次提交。这样：

- GitHub 上不存在任何含明文凭据的历史对象；
- 两个平台内容一致，但 commit SHA 不同；
- Gitee 保留完整历史，作为开发与审计主仓库。

> **红线**：以后同步 GitHub 时，不要把 Gitee 作为 remote 直接 push，
> 否则会把含密钥的历史一并推上去。始终走第 5 节的快照流程。

## 4. 同步记录（append-only，新的在上）

| 日期 | 内容版本 | Gitee HEAD | GitHub HEAD | 说明 |
|---|---|---|---|---|
| 2026-11-17 | v0.1.0 / 底部信号 1.4.1 | `253624c` | `e84d71d` | 新增 `SYNC.md` 后重新同步：Gitee 直推、GitHub 重建无历史快照；tree `3581fc24` 两边一致 |
| 2026-11-17 | v0.1.0 / 底部信号 1.4.1 | `4081994` | `f43c374` | 首次同步：新建公开仓库 `chenxyzcyxpp/invest-skill`，推送 222 文件无历史快照 |

## 5. 同步操作 SOP

### 5.1 前置条件

- 本地 `/workspace` 的 `main` 已与 Gitee `origin/main` 一致；
- 一个具备 `contents:write` 的 GitHub token（fine-grained 需勾选 Contents = **Read and write**）。

### 5.2 步骤

```bash
# 1) 先确保 Gitee 主仓库最新
cd /workspace
git push origin main

# 2) 导出无历史快照
SNAP=$(mktemp -d)
git archive HEAD | tar -x -C "$SNAP"
cd "$SNAP"
git init -q -b main
git add -A
git -c user.name="invest-skill" -c user.email="invest-skill@local" \
    commit -q -m "chore: 同步快照 — <填入内容版本>"

# 3) 推送到 GitHub（token 只走环境变量，不落盘、不进 remote URL）
git remote add github https://github.com/chenxyzcyxpp/invest-skill.git
AUTH=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
GIT_TERMINAL_PROMPT=0 git -c "http.extraHeader=Authorization: Basic $AUTH" \
    push -f github main:main
```

> `-f` 是安全的：GitHub 镜像的内容始终以 Gitee HEAD 为准；
> 但推送前仍应先确认没有他人向镜像提交过（见 5.3）。

### 5.3 校验

```bash
# 两边 tree SHA 应相等
git -C /workspace rev-parse HEAD^{tree}   # Gitee 侧（已与远端同步）
git -C "$SNAP" rev-parse HEAD^{tree}      # GitHub 快照侧
```

校验通过后，在第 4 节追加一行同步记录，并更新第 2 节的基线 SHA。

## 6. 已知差异（不是 bug）

| 差异 | 原因 |
|---|---|
| commit SHA 不同 | GitHub 是独立初始化的快照仓库 |
| GitHub 无 Tag / 无历史分支 | 只推 `main` 当前内容 |
| README clone 地址只写 Gitee | 项目既定宣发定位（见 README 徽章） |
| Gitee 有 `master` 旧分支 | 历史遗留，默认分支已切 `main` |

## 7. 维护清单

- [ ] 每次 Gitee 发版或重要更新后，跑一遍第 5 节同步；
- [ ] 同步后在第 4 节追加记录，并更新第 2 节基线 SHA；
- [ ] 不要把含凭据的历史 push 到 GitHub；
- [ ] 用完的 GitHub token 及时 Revoke。
