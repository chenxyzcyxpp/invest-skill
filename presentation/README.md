# presentation · 小白卡可视化输出层

> 作者：刘宇恒 · 版本 2.0.0 · 横切输出层（与 `skills/base/` 平行，非 15 个分析 Skill 之一）

## 这是什么

invest-skill 的**可视化输出翻译层**：把上游 15 个分析 Skill 的结构化报告，翻译成普通用户一眼看懂的**小白卡片**（人话话术 + 固定视觉 + 合规红线），最终以 **PNG 图片**形态交付到聊天宿主（WorkBuddy / 企业微信等）。

**定位：翻译层，不是分析层。** 不新增任何分析、不改动上游结论、数字逐字段照抄。

```
上游 Skill 报告（Markdown / JSON）
        │  按 SKILL.md 话术表提取字段
        ▼
NoviceCard JSON（invest-novice-card/1，含 data_as_of）
        │
        ├─ 用法 A：宿主 Agent 纯对话组装（零依赖，LLM 按话术表填卡）
        └─ 用法 B：scripts/render_cards.py 确定性渲染 → HTML → PNG
        ▼
一问一卡一图（一句引导语 + 一张卡）
```

## 目录结构

```
presentation/
├── SKILL.md                       # 输出层总纲：场景触发协议 + 15 技能→14 卡型映射 + 契约 + 话术表 + 红线
├── manifest.yaml                  # 输出层契约（layer: output，不计入 Skill 总数）
├── README.md
├── scripts/
│   ├── render_cards.py            # 确定性渲染器：JSON → 自包含 HTML，带 --check 数字回比
│   └── html2png.py                # HTML → 整页 PNG（两遍无头 Chrome）
└── examples/
    ├── samples.json               # 4 张样例卡（上游真实样例数据，零加工）
    ├── samples.html               # 渲染结果，双击即看
    └── samples.png                # 整页截图，聊天宿主最终交付形态
```

## 快速试用

```bash
# 渲染 HTML
python -X utf8 presentation/scripts/render_cards.py presentation/examples/samples.json -o /tmp/cards.html

# 数字一致性校验（0 missing 才算过）
python -X utf8 presentation/scripts/render_cards.py presentation/examples/samples.json --check /tmp/cards.html

# 直接出 PNG（Linux/root 用 CHROME 指定浏览器）
CHROME=/usr/bin/chromium python -X utf8 presentation/scripts/render_cards.py presentation/examples/samples.json --png /tmp/cards.png
```

## 核心纪律（详见 SKILL.md）

- **数字零加工**：逐字段照抄，禁止重算/单位换算；档位翻人话是标签翻译，数值不动。
- **事实与观点分离**：观点/推演/评级带「（报告观点）/（模型预测）」尾标。
- **一问一卡一图**：进卡交互只回一句引导语 + 一张卡，禁止文字总结绕开合规翻译。
- **数据新鲜度**：`data_as_of` 必填，宁可不卡、不可旧卡。
- **合规**：缺失如实标「—」、不给买卖指令与目标价、小样本必警、免责句固定。

## 与上游的关系

本层**不修改任何上游 Skill**，只消费其报告字段。上游新增 Skill 时，按 SKILL.md 第 3 节补一张卡型映射与话术表即可，无需改动渲染器。
