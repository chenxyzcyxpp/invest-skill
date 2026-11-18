---
name: policy-interpretation
description: |
  当用户需要解读政策文件、分析政策对行业/市场的影响、查询特定领域政策动态时触发。基于公开可得数据源（中国政府网、国家法律法规数据库、各部委及地方政府官网、权威媒体），输出政策原文及结构化分析。
version: 1.1.0
---

# 政策解读与分析

从公开可得数据源获取政策文件，输出原文及结构化分析（背景、核心内容、影响范围、受益行业等）。所有内容可溯源，带原始发布时间戳与来源 URL。

**详细政策范围定义与数据源清单**见 `references/TOOL_GUIDE.md`。

## 核心工作流程

工具调用能并发时尽量并发以提速。

### 1. 解析意图

从用户提问提取：

- **关键词**：行业或政策主题（AI、半导体、新能源、货币政策等）
- **日期范围**：自然语言换算（近一周=7天，近一月=30天，近一年=365天），未指定默认近一月，格式 YYYY-MM-DD
- **政策类型**（可选）：宏观/行业/区域/财政/货币/环保/产业
- **地域范围**（可选）：全国性/省级/市级

### 2. 检索政策（公开数据源）

使用 `WebSearch` + `WebFetch` 从公开政府网站与权威媒体检索政策文件，详见 `references/TOOL_GUIDE.md`。

- **检索**：用 `WebSearch`，关键词建议含政策特征词（政策、通知、意见、方案、规划、办法、规定、决定、条例、公报），并尽量通过 `allowed_domains` 限定到 `gov.cn` 或具体部委站点；抓取原文用 `WebFetch`。
- **溯源**：每条政策记录其来源 URL、发布机构、发布时间、文号（如有）。

若结果为空，提示用户放宽日期或调整关键词后终止。

### 3. 合并筛选

- 仅保留有明确发布机构、文号、政策名称的内容
- 按 policyID 合并分析维度，按 publishDate 降序
- 政策内容保持原文，不改写不摘要
- 标注受益行业、受影响企业

### 3.5 生成文件

根据合并筛选后的结构化数据，**同时生成两份文件**：

1. **Markdown 文件**：按 §4.1 格式写入 `files/report/{主题}_政策解读_{YYYYMMDD}.md`
2. **HTML 文件**：按 §5 模板写入 `files/report/{主题}_政策解读_{YYYYMMDD}.html`，溯源角标实现双向跳转

向用户回复时提供两个文件的 file link。

### 4. 输出格式（强制双格式）

**默认必须同时输出 Markdown（.md）和 HTML（.html）两种格式文件。** 不得仅输出其中一种。文件保存至 `files/report/` 目录。

#### 4.1 Markdown 格式

Markdown 文件作为可编辑、可版本管理的原始文档。结构如下：

```markdown
# 政策解读报告：{主题}

> **数据范围**：{beginDate} 至 {endDate}
> **生成时间**：{timestamp}

---

## 一、政策概览

| # | 政策名称 | 发布机构 | 发布时间 | 政策类型 |
|---|---------|---------|---------|---------|
| 1 | ... | ... | ... | ... |

## 二、政策详情

### 2.1 {政策标题}

- **发布机构**：...
- **发布时间**：...
- **文号**：...（如有）
- **来源**：...（URL）

#### 政策背景
> 原文内容 [¹]

#### 核心内容
> 原文内容 [²]

#### 影响范围
> 原文内容

#### 受益行业
> 原文内容

...（检索到的所有分析维度均保留）

## 三、受益行业汇总

| 行业 | 关联政策 |
|------|---------|
| ... | ... |

## 四、数据来源

[1] 来源描述...
[2] 来源描述...
```

#### 4.2 HTML 格式（带可跳转溯源角标）

HTML 文件为最终交付阅读格式。**必须实现以下功能**：

1. **溯源角标跳转**：文中每个数据/观点引用处标注上标角标（如 `[¹]`），点击后跳转到页面底部「数据来源」列表对应条目
2. **来源列表回跳**：每条来源末尾附带返回箭头 `↩`，点击后回跳到文中第一个引用该来源的位置
3. **角标编号与来源列表序号一一对应**

详细 HTML 模板与技术要求见 **§5 HTML 格式规范**。

#### 4.3 数据结构

内部使用的 JSON 结构（不直接输出给用户，仅用于构建 MD/HTML）：

```json
[
  {
    "policyID": "政策ID",
    "title": "政策标题",
    "publishDate": "YYYY-MM-DD HH:mm:ss",
    "issuingOrg": "发布机构",
    "policyType": "政策类型",
    "region": "地域范围",
    "sourceURL": "来源 URL",
    "docNumber": "文号（如有）",
    "analysisResults": [
      { "dimension": "分析维度", "content": "原文内容" }
    ],
    "benefitIndustries": ["受益行业"],
    "affectedCompanies": ["受影响企业"]
  }
]
```

分析维度包括但不限于：政策背景、核心内容、影响范围、实施时间、受益行业、风险提示、政策解读、实施效果。检索到的所有维度均保留。

完整输出示例见 `references/EXAMPLE_OUTPUT.md`。

### 5. HTML 格式规范

#### 5.1 溯源跳转机制

**前端（引用处 → 来源列表）**：

```html
文中引用处：
<sup id="ref-1"><a href="#src-1">[1]</a></sup>

多条引用同一来源时，使用相同编号：
第一条出现 → <sup id="ref-1a"><a href="#src-1">[1]</a></sup>
第二条出现 → <sup id="ref-1b"><a href="#src-1">[1]</a></sup>
```

**后端（来源列表 → 文内回跳）**：

```html
<li id="src-1">
  {来源描述}
  <a href="#ref-1a" class="backlink" title="返回文中">↩</a>
</li>
```

**CSS 样式要求**：

```css
sup a {
  text-decoration: none;
  color: #2563eb;
  font-weight: 600;
  font-size: 0.8em;
  padding: 0 2px;
}
sup a:hover {
  text-decoration: underline;
  color: #1d4ed8;
}
.sources {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 2px solid #e5e7eb;
}
.sources ol {
  padding-left: 1.5rem;
}
.sources li {
  margin-bottom: 0.5rem;
  line-height: 1.6;
  scroll-margin-top: 20px;
}
.backlink {
  text-decoration: none;
  margin-left: 0.5rem;
  color: #6b7280;
  font-size: 0.85em;
}
.backlink:hover {
  color: #2563eb;
}
```

#### 5.2 HTML 页面结构模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>政策解读报告：{主题}</title>
  <style>
    /* 基础样式 */
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #1f2937; line-height: 1.8; }
    h1 { border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
    h2 { margin-top: 2rem; color: #1e40af; }
    h3 { color: #374151; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }
    th { background: #f3f4f6; }
    blockquote { border-left: 3px solid #2563eb; margin: 0.5rem 0; padding: 0.5rem 1rem; background: #f8fafc; }
    .meta { color: #6b7280; font-size: 0.9em; margin-bottom: 2rem; }
    .risk { background: #fef3c7; border-left: 3px solid #f59e0b; padding: 1rem; margin: 1rem 0; }
    /* 溯源样式 */
    sup a { text-decoration: none; color: #2563eb; font-weight: 600; font-size: 0.8em; padding: 0 2px; }
    sup a:hover { text-decoration: underline; color: #1d4ed8; }
    .sources { margin-top: 2rem; padding-top: 1rem; border-top: 2px solid #e5e7eb; }
    .sources ol { padding-left: 1.5rem; }
    .sources li { margin-bottom: 0.5rem; line-height: 1.6; scroll-margin-top: 20px; }
    .backlink { text-decoration: none; margin-left: 0.5rem; color: #6b7280; font-size: 0.85em; }
    .backlink:hover { color: #2563eb; }
    .disclaimer { margin-top: 2rem; padding: 1rem; background: #f9fafb; border: 1px solid #e5e7eb; color: #6b7280; font-size: 0.85em; }
  </style>
</head>
<body>
  <h1>政策解读报告：{主题}</h1>
  <div class="meta">
    <p>数据范围：{beginDate} 至 {endDate} | 生成时间：{timestamp}</p>
  </div>

  <!-- 政策概览表格 -->
  <h2>一、政策概览</h2>
  <table>...</table>

  <!-- 逐条政策详情，每条中引用标注角标 -->
  <h2>二、政策详情</h2>
  <h3>{政策标题}</h3>
  <p><strong>发布机构：</strong>... <sup id="ref-1a"><a href="#src-1">[1]</a></sup></p>
  ...

  <!-- 受益行业汇总 -->
  <h2>三、受益行业汇总</h2>
  ...

  <!-- 数据来源列表（可跳转回文中） -->
  <div class="sources">
    <h2>四、数据来源</h2>
    <ol>
      <li id="src-1">来源描述 <a href="#ref-1a" class="backlink" title="返回文中">↩</a></li>
      <li id="src-2">来源描述 <a href="#ref-2" class="backlink" title="返回文中">↩</a></li>
    </ol>
  </div>

  <!-- 免责声明 -->
  <div class="disclaimer">本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。</div>
</body>
</html>
```

#### 5.3 生成规则

1. **编号唯一性**：每个独立数据来源分配唯一序号，与来源列表一一对应
2. **首次引用定位**：文中同一来源如被多次引用，第一次出现的 `id` 记为 `ref-N-a`，第二次为 `ref-N-b`；来源列表的 `↩` 链接固定回跳到 `ref-N-a`（即该来源在文中首次出现的位置）
3. **仅引用事实数据处标注角标**：政策原文、核心内容等检索返回的分析维度内容需要标注来源；分析者自身的归纳性判断（如受益行业、影响范围综述）不需要标注
4. **文件保存路径**：Markdown 文件 → `files/report/{主题}_政策解读_{YYYYMMDD}.md`；HTML 文件 → `files/report/{主题}_政策解读_{YYYYMMDD}.html`

## Gotchas

- **强制双格式输出**：每次必须同时生成 .md 和 .html 两个文件，缺一不可；HTML 中必须实现溯源角标双向跳转
- **严格排除非政策数据**：CPI/PPI/GDP 等统计数据、券商研报、股票行情、大宗商品价格均不属于本技能范围。详细排除清单见 `references/TOOL_GUIDE.md`
- **政策内容必须原文输出**：不得改写、摘要或重新表述
- **优先官方来源**：优先使用 gov.cn、部委官网、国家法律法规数据库等一手来源；权威媒体（新华社、人民日报等）用于政策解读与官方讲话；避免引用转载类商业网站
- **受益行业识别可能有遗漏**：基于政策内容分析，非穷举
- **非政策类查询请转交其他技能**：宏观数据用 finance-data，研报用 industry-research-summary

## 注意事项

- 政策解读仅供参考，不构成投资建议
- 数据覆盖范围依赖公开政府网站与权威媒体的可访问性
- 查询结果为空时，建议用户放宽时间范围或使用更通用的关键词
