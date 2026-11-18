# 股市每日收评 使用示例（开源版）

version: "1.0.0"

> 本 Skill 为脚本驱动型（script_based），核心为 `scripts/market_review.py`。以下示例均基于命令行直接调用；
> 在 invest-skill 框架内由 `skill.py` 注册后，由调度引擎按 manifest 透传参数并调用脚本。

## 一、CLI 基础用法

```bash
# 演示模式（无需 token / 外部库，沙箱可直接跑）
python3 scripts/market_review.py --demo --output-format markdown

# 演示模式输出 JSON（供下游消费）
python3 scripts/market_review.py --demo --output-format json

# 真实模式：指定交易日 + 全部市场
python3 scripts/market_review.py --trade-date 2026-10-22 --market 全部 --top-n 10

# 真实模式：仅 A 股，落盘到 files/report
python3 scripts/market_review.py --trade-date 2026-10-22 --market A股 --out files/report

# 关闭公开资讯采集
python3 scripts/market_review.py --demo --no-news
```

## 二、参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--trade-date` | 空（最近交易日） | YYYY-MM-DD |
| `--market` | 全部 | A股 / 港股 / 全部 |
| `--top-n` | 10 | 板块 / 个股榜单条数 |
| `--output-format` | both | markdown / html / json / both |
| `--out` | 空 | 落盘目录，如 files/report |
| `--demo` | 关闭 | 使用内置演示数据 |
| `--no-news` | 关闭 | 关闭公开资讯采集 |

## 三、输出样例（markdown，节选）

```markdown
# 股市每日收评（2026-10-22 · 全部）

> 数据来源：demo | 生成时间：2026-10-22T13:15:20+08:00

## 一、盘面综述
今日 上证指数+0.62%、深证成指+0.85%、创业板指+1.12%；涨跌比 3120:1680，涨停 86 家。板块方面 半导体 领涨、房地产 领跌。盘面情绪偏弱。

## 二、大盘指数
| 市场 | 指数 | 收盘 | 涨跌幅 | 成交额(亿) |
| --- | --- | --- | --- | --- |
| A股 | 上证指数 | 3,325.40 | +0.62% | 4,210.5 |
| 港股 | 恒生指数 | 21,580.30 | -0.35% | 980.0 |

## 十、数据说明与免责
- 缺失数据项（如实标注）：dragon, news
- 数据完整，未触发降级。
> 本服务内容来源于公开及第三方数据源，仅自动化加工展示，不构成投资建议或承诺，不能替代独立判断。受数据源、传输、解析等因素影响，内容可能存在偏差，不保证内容真实准确完整。服务方不对据此决策产生的后果负责。市场有风险，投资需谨慎。
```

## 四、JSON payload 样例（节选）

```json
{
  "trade_date": "2026-10-22",
  "market": "全部",
  "summary": "今日 上证指数+0.62%……盘面情绪偏弱。",
  "indices": [{"market":"A股","name":"上证指数","close":3325.4,"pct":0.62}],
  "breadth": {"up":3120,"down":1680,"flat":210,"limit_up":86,"limit_down":12,"total":5010},
  "sectors": [{"name":"半导体","pct1d":3.85,"amount_yi":1283.4,"net_yi":45.2}],
  "movers": {"up":[{"code":"688981","name":"中芯国际","pct":12.3,"turnover":8.5}]},
  "meta": {"data_source":"demo","degraded":"demo","degrade_trace":[]}
}
```

## 五、降级行为示例

- **无 TUSHARE_TOKEN + akshare 可用**：自动 L1→L2，报告 `data_source=akshare`。
- **akshare 全接口不可达**：L1→L2 失败，L3 网页兜底仅补齐指数；板块 / 个股等标注「数据待补充」，`degraded=true`。
- **指数 / 板块四类源全失败**：脚本抛 `MKT_REVIEW_001` 并以退出码 2 退出，**不输出伪造报告**。
- **龙虎榜 / 资讯缺口**：报告第十节标注 `dragon, news` 为缺失项，不编造具体数值。

## 六、最佳实践

1. 生产环境优先配置 `TUSHARE_TOKEN` 以获得最完整覆盖；未配置时自动降级到 Akshare。
2. 受限网络环境关注 EastMoney 接口拦截，脚本已内置 sina / 网页兜底。
3. 市场级新闻建议结合 WebSearch 补充，脚本仅负责结构化维度，不编造资讯。
4. 每次运行检查 `degrade_trace`，对标注「数据待补充」的维度谨慎引用。

## 七、常见问题（FAQ）

- **Q：为什么 reports 用的是 `files/report/` 而不是 `reports/`？**
  A：开源版统一使用 `files/report/` 作为工作空间产物目录，与 invest-skill 体系产物约定一致。
- **Q：港股指数取不到？**
  A：港股指数依赖 `stock_hk_index_spot_em`（EastMoney），受限网络失败时会由 L3 网页兜底补齐；若仍失败则在第十节标注缺失。
- **Q：能否只输出 JSON？**
  A：可以，`--output-format json` 输出扁平结构化结果，供下游编排消费。
