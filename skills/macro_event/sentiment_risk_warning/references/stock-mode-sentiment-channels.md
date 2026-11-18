# 个股模式舆情通道（2026-10-15 新闻通道落地后）

## 结论（现状）
个股模式（stock_risk_scorer）舆情为**双文本通道**：股吧（guba.eastmoney.com）+
个股新闻（东财 search-api）。两通道各自按日聚合情感后逐日加权合成（默认 0.5/0.5），
报告分通道展示样本数并列出「近期新闻标题」。

历史：2026-10-13 前个股模式只有股吧通道，新闻仅大盘模式使用；用户问
「为什么个股分析案例没有舆情新闻」暴露缺口 → 2026-10-15 补上新闻通道
（本次会话完成）。**此后用户再问「个股报告没有舆情新闻」，先查通道抓取状态，
不要再答「设计上就没有」——那是旧口径。**

## 数据源与代码位置
- `data.py fetch_news(code)`：东财 `search-api-web.eastmoney.com/search/jsonp`（cb() 解包）；
  keyword 优先股票名称（`_stock_name()` 走 push2 f58），失败退回代码；
  返回 `date/title/content`（去 `<em>` 高亮）；pageSize=30 单页；失败返回 `[]` 不抛错
  （上层降级为仅股吧并标注）。
- `data.py fetch_kline()`：东财 push2his 优先 → 失败自动回退 Tushare
  （`daily` + `daily_basic` 换手率，amount 千元→元 ×1000，token 取自
  `~/.hermes/config.yaml`）；两个源都失败才抛错。
- `sentiment.py merge_opinion_channels()`：多通道逐日加权合成（weights 默认 0.5/0.5）。
- `cli.py`：`--no-news` 关闭新闻通道；meta 带 `channels_meta` / `news_titles`。
- `report.py`：控制台/HTML/JSON 三处展示通道明细 + 新闻标题。

## 康龙化成 300759 案例对比

### 改前（2026-10-13，`/tmp/kanglong/risk_report_300759.json`）
- 股吧仅 2 条、scored_terms=0、opinion=0.0；报告 100 分高风险
  **完全由量价特征**（pct_chg importance 0.358 主导）推出，不是舆情利空。

### 改后（2026-10-15，`/tmp/kanglong_v2/risk_report_300759.json`）
- 股吧 2 条 + **新闻 30 条**（询价转让 38.89 元/13 家机构接盘、摩根大通 H 股好仓
  14.11% 等）；报告列出 6 条近期新闻标题；pred_vol 3.86%、grade 中、score 78。
- 新闻 30 条仅 7 个情感词命中、9 个稀疏日 → 当日 opinion 仍偏中性（+0.000）。

## 解读要点
- 双通道时看 `channels_meta`：哪个通道抓取失败/稀疏，舆情指数就是另一通道或量价主导。
- 新闻命中词少（如康龙 7/30）常见——东财新闻标题多为中性公告（询价转让、评级），
  情感词典对公告类文本不敏感，属预期，不代表新闻通道坏了。
- opinion 命中率 <50% 仍不入训练矩阵、仅当期信号 → 特征重要性里 opinion_index 可为 0。

## 文档/代码漂移核对点（2026-10-15 更新）
- **已落地**：股吧 + 新闻双通道、`--no-news`、K线 Tushare 回退。
- **未落地**：proxy 通道（银河融资融券/龙虎榜/股东户数 margin_net_buy）与
  `--sentiment auto|guba|proxy|none` 参数——SKILL.md §1.2 有宣称但代码无实现。
  任何依赖 proxy 的宣称，先核对 cli.py/data.py 是否已落地。

## 排查顺序（用户问「为什么没舆情」时）
1. 打开报告看「舆情通道」行：股吧 N 条 + 新闻 M 条。
2. N 很小（<5）→ 东财股吧抓取受限/解析失败（查 `fetch_guba`）；M=0 → 新闻通道失败
   （查 `fetch_news` / search-api 网络）或用了 `--no-news`。
3. opinion_index=0 + note 命中率<50% → 舆情不入训练矩阵，结论由量价主导，
   勿误读为舆情利空；对外汇报明确「本轮结论由量价主导」。
4. 需要更全舆情 → 自备语料 `--posts`，或扩展新闻页数/关键词。
