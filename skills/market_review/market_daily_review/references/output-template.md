# 股市每日收评报告 - HTML 输出模板

本模板提供完整的 HTML 报告结构，包含响应式设计、数据来源区与免责声明。
实际生成由 `scripts/market_review.py` 的 `to_markdown` / `to_html` 负责，以下为样式与结构参考。

## 结构（十段式）

1. 盘面综述
2. 大盘指数（表：市场 / 指数 / 收盘 / 涨跌幅 / 成交额）
3. 涨跌统计（上涨 / 下跌 / 平盘 / 涨停 / 跌停）
4. 板块表现（领涨 / 领跌，含涨跌幅 / 成交额 / 主力净流入）
5. 个股异动（涨幅 / 跌幅 / 换手率榜）
6. 资金流向（全市场主力净流入 / 行业净流入居前 / 净流出居前）
7. 龙虎榜（代码 / 名称 / 净买额 / 上榜原因）
8. 重要资讯（标题 / 来源 / 时间；传闻标注）
9. 技术面（RSI / MA 均线）
10. 数据说明与免责（缺失项 / 降级 trace / 免责声明）

## 样式（参考）

```css
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:960px;margin:0 auto;padding:20px;color:#1f2937;line-height:1.8;}
h1{border-bottom:2px solid #2563eb;padding-bottom:8px;}
h2{margin-top:2rem;color:#1e40af;}
table{border-collapse:collapse;width:100%;margin:1rem 0;}
th,td{border:1px solid #d1d5db;padding:8px 12px;text-align:left;}
th{background:#f3f4f6;}
blockquote{border-left:3px solid #2563eb;margin:.5rem 0;padding:.5rem 1rem;background:#f8fafc;color:#475569;}
.disclaimer{margin-top:2rem;padding:1rem;background:#f9fafb;border:1px solid #e5e7eb;color:#6b7280;font-size:.85em;}
.warn{background:#fef3c7;border-left:3px solid #f59e0b;padding:.6rem 1rem;margin:1rem 0;}
```

## 数据来源区（必须包含）

> 数据来源：{data_source} | 生成时间：{run_at}
> 若存在降级：⚠️ 本次发生数据源降级，结论仅供参考：{degrade_trace}

## 免责声明与风险提示

本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
