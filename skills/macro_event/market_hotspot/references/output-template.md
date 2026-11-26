# 股票市场热点解读报告 - 输出模板

## Markdown 格式模板

```markdown
# 股票市场热点解读报告
**生成时间：** {YYYY-MM-DD HH:mm}
**分析周期：** {用户指定的时间范围}
**输出格式：** Markdown

## 📊 核心摘要
{100-200 字核心观点，带溯源角标 [1][2]}

## 🔥 热点识别
{热点列表及分类，每个热点带溯源角标 [3][4]}

### 政策热点
- {热点 1} [3]
- {热点 2} [4]

### 行业热点
- {热点 3} [5]
- {热点 4} [6]

### 概念热点
- {热点 5} [7]
- {热点 6} [8]

## 📖 深度解读
{成因分析、影响评估、持续性判断，带溯源角标 [9][10]}

### 热点成因
{分析内容} [9]

### 影响评估
{分析内容} [10]

### 持续性判断
{分析内容}

## 🔗 产业链映射
{上下游关联、标的筛选，带溯源角标 [11][12]}

### 上游
- {标的 1}
- {标的 2}

### 中游
- {标的 3}
- {标的 4}

### 下游
- {标的 5}
- {标的 6}

### 龙头标的
| 标的 | 市值 | PE | 逻辑 |
|------|------|-----|------|
| {股票 1} | {值} | {值} | {逻辑} [11] |
| {股票 2} | {值} | {值} | {逻辑} [12] |

## 💰 资金面分析
{主力/北向/南向资金流向，带溯源角标 [13][14]}

### 主力资金
{分析内容} [13]

### 北向资金
{分析内容} [14]

### 龙虎榜解读
{分析内容}

## 📈 情绪面分析
{涨停数、连板高度、情绪周期，带溯源角标 [15]}

### 涨停统计
- 涨停家数：{值} [15]
- 连板高度：{值}
- 炸板率：{值}

### 情绪周期判断
{分析内容}

## 💡 操作建议
{短线/中线/长线策略}

### 短线策略
{建议内容}

### 中线策略
{建议内容}

### 长线策略
{建议内容}

## ⚠️ 风险预警
{风险提示}

- {风险 1}
- {风险 2}
- {风险 3}

## 📋 数据来源
[1] AkShare (stock_board_industry_name_em) - {更新时间} - 行业板块行情
[2] AkShare (stock_board_concept_name_em) - {更新时间} - 概念板块行情
[3] 巨潮资讯网 / 交易所官网 - {更新时间} - 公司公告
[4] 政府网站 (gov.cn) - {更新时间} - 政策文件
...

---
**免责声明：** 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
```

## HTML 格式模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票市场热点解读报告</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
            line-height: 1.6;
        }
        h1 { 
            color: #1a1a1a; 
            border-bottom: 3px solid #0066cc; 
            padding-bottom: 10px; 
        }
        h2 { 
            color: #333; 
            border-left: 4px solid #0066cc; 
            padding-left: 12px; 
            margin-top: 30px; 
        }
        h3 {
            color: #555;
            margin-top: 20px;
        }
        .meta { 
            background: #f5f5f5; 
            padding: 15px; 
            border-radius: 8px; 
            margin-bottom: 20px; 
        }
        .citation { 
            font-size: 0.8em; 
            vertical-align: super; 
            color: #0066cc; 
            text-decoration: none; 
        }
        .sources { 
            background: #fafafa; 
            padding: 20px; 
            border-radius: 8px; 
            margin-top: 40px; 
        }
        .source-item { 
            font-size: 0.9em; 
            color: #666; 
            margin: 8px 0; 
        }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin: 15px 0; 
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }
        th { 
            background: #f0f0f0; 
            font-weight: 600; 
        }
        .warning { 
            background: #fff3cd; 
            border-left: 4px solid #ffc107; 
            padding: 15px; 
            margin: 15px 0; 
        }
        .disclaimer { 
            font-size: 0.85em; 
            color: #666; 
            border-top: 2px solid #ddd; 
            padding-top: 15px; 
            margin-top: 40px; 
        }
        .back-to-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #0066cc;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <h1>📊 股票市场热点解读报告</h1>
    <div class="meta">
        <strong>生成时间：</strong>{YYYY-MM-DD HH:mm}<br>
        <strong>分析周期：</strong>{用户指定的时间范围}<br>
        <strong>输出格式：</strong>HTML
    </div>
    
    <h2>📊 核心摘要</h2>
    <p>{内容带溯源角标 <a href="#source1" class="citation">[1]</a>}</p>
    
    <h2>🔥 热点识别</h2>
    <h3>政策热点</h3>
    <ul>
        <li>{热点 1} <a href="#source3" class="citation">[3]</a></li>
        <li>{热点 2} <a href="#source4" class="citation">[4]</a></li>
    </ul>
    
    <h3>行业热点</h3>
    <ul>
        <li>{热点 3} <a href="#source5" class="citation">[5]</a></li>
        <li>{热点 4} <a href="#source6" class="citation">[6]</a></li>
    </ul>
    
    <h2>📖 深度解读</h2>
    <p>{内容带溯源角标}</p>
    
    <h2>🔗 产业链映射</h2>
    <table>
        <thead>
            <tr>
                <th>标的</th>
                <th>市值</th>
                <th>PE</th>
                <th>逻辑</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{股票 1}</td>
                <td>{值}</td>
                <td>{值}</td>
                <td>{逻辑} <a href="#source11" class="citation">[11]</a></td>
            </tr>
        </tbody>
    </table>
    
    <h2>💰 资金面分析</h2>
    <p>{内容带溯源角标}</p>
    
    <h2>📈 情绪面分析</h2>
    <p>{内容带溯源角标}</p>
    
    <h2>💡 操作建议</h2>
    <p>{策略内容}</p>
    
    <h2>⚠️ 风险预警</h2>
    <div class="warning">
        <ul>
            <li>{风险 1}</li>
            <li>{风险 2}</li>
            <li>{风险 3}</li>
        </ul>
    </div>
    
    <h2 id="sources">📋 数据来源</h2>
    <div class="sources">
        <div class="source-item" id="source1">[1] AkShare (stock_board_industry_name_em) - {更新时间} - 行业板块行情</div>
        <div class="source-item" id="source2">[2] AkShare (stock_board_concept_name_em) - {更新时间} - 概念板块行情</div>
        <div class="source-item" id="source3">[3] 巨潮资讯网 / 交易所官网 - {更新时间} - 公司公告</div>
        ...
    </div>
    
    <div class="disclaimer">本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。</div>
    
    <a href="#" class="back-to-top">↑ 返回顶部</a>
</body>
</html>
```

## 溯源角标使用规范

1. **角标位置**：紧跟在数据/结论后面，如 `涨停家数增至 85 家 [15]`
2. **角标格式**：
   - Markdown: `[1]`
   - HTML: `<a href="#source1" class="citation">[1]</a>`
3. **序号规则**：按首次出现顺序编号，全文统一
4. **文末清单**：必须包含序号、数据来源名称、数据更新时间、查询参数
5. **数据验证**：关键数据需多源交叉验证，标注多个角标如 `[1][3]`

## 数据源清单（公开数据源版）

**量化行情类（AkShare 开源库，免费无 API Key）：**

| 序号 | 数据源 | 接口/工具 | 用途 |
|------|--------|-----------|------|
| [1] | AkShare | stock_board_industry_name_em | 行业板块行情排名 |
| [2] | AkShare | stock_board_concept_name_em | 概念板块行情排名 |
| [3] | AkShare | stock_board_concept_cons_em | 概念股成分 |
| [4] | AkShare | stock_board_industry_cons_em | 行业成分股 |
| [5] | AkShare | stock_individual_fund_flow | 个股资金流 |
| [6] | AkShare | stock_sector_fund_flow_rank | 行业/板块资金流 |
| [7] | AkShare | stock_hsgt_hist_em | 沪深股通/北向资金 |
| [8] | AkShare | stock_zt_pool_em | 涨停池/涨跌停统计 |
| [9] | AkShare | stock_lhb_detail_em | 龙虎榜/机构席位 |
| [10] | AkShare | stock_financial_analysis_indicator | 财务指标 |

**公开资讯类（WebSearch + WebFetch）：**

| 序号 | 数据源 | 域名 | 用途 |
|------|--------|------|------|
| [11] | 权威财经媒体（新华社/证券时报/证券日报/上海证券报/财联社） | 各官网 | 财经/市场/个股新闻、舆情 |
| [12] | 中国政府网 / 部委官网 | gov.cn | 政策会议、政策文件 |
| [13] | 国家法律法规数据库 | flk.npc.gov.cn | 法律法规 |
| [14] | 巨潮资讯网 / 上交所 / 深交所 | cninfo.com.cn / sse.com.cn / szse.cn | A 股公司公告 |
| [15] | 东方财富研报中心 / 权威媒体深度报道 | data.eastmoney.com | 券商研报、深度解读 |
