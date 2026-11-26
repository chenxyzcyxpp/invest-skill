# 开源数据源库函数映射表（API Reference）

> 本文件将每日收评各数据维度映射到**开源 Python 库（akshare / tushare）与公开网页接口**的可调用函数。
> 所有接口均来自公开开源数据源，**不含任何商业数据供应商专有工具**。工具名称必须准确，不可捏造。

## 维度 → 开源接口映射表

| 数据维度 | 优先级 L1 (Tushare) | 优先级 L2 (Akshare) | 优先级 L3 (网页兜底) | 市场 |
|----------|---------------------|----------------------|----------------------|------|
| 大盘指数（A股） | `pro.index_daily(ts_code, trade_date)` | `stock_zh_index_spot_sina()` | 东方财富 `push2` (secid) | A股 |
| 大盘指数（港股） | — | `stock_hk_index_spot_em()` | 东方财富 `push2` (HSI/HSTECH) | 港股 |
| 涨跌统计 | 本地聚合 `pro.daily` | `stock_zh_a_spot_em()` / `stock_zh_a_spot()` 聚合 | — | A股 |
| 板块表现 | `pro.sw_daily` / `index_member` | `stock_board_industry_summary_ths()` | — | A股 |
| 个股异动 | `pro.daily` 排序 | `stock_zh_a_spot_em()` / `stock_zh_a_spot()` 排序 | — | A股 |
| 资金流向（市场） | `pro.moneyflow` | `stock_market_fund_flow()` | — | A股 |
| 资金流向（行业） | — | `stock_board_industry_summary_ths()` 净流入列 | — | A股 |
| 龙虎榜 | `pro.top_list` | `stock_lhb_detail_em()` / `stock_lhb_detail_daily_sina()` | — | A股 |
| 技术面（RSI/MA） | `pro.index_daily` | `index_zh_a_hist(symbol="000001")` + 本地计算 | — | A股 |
| 重要资讯 | — | 无稳定市场级源（建议 WebSearch） | — | 全部 |

## 数据时效性

| 数据类型 | 更新频率 | 延迟 | 溯源要求 |
|----------|----------|------|----------|
| 指数行情 | 实时 | <1 分钟 | 标注 data_source |
| 涨跌统计 | 实时 | <1 分钟 | 标注 data_source |
| 板块表现 | 实时 | <5 分钟 | 标注 data_source |
| 个股异动 | 实时 | <1 分钟 | 标注 data_source |
| 资金流向 | 实时 | <5 分钟 | 标注 data_source |
| 龙虎榜 | 盘后 | 收盘后 30 分钟 | 标注 data_source |
| 技术面 | 实时计算 | <1 分钟 | 标注 data_source |

## 数据获取注意事项

### 指数（A 股）
- `stock_zh_index_spot_sina()` 返回列含 `名称 / 最新价 / 涨跌幅 / 成交额`，按名称筛选 `上证指数 / 深证成指 / 创业板指 / 沪深300 / 科创50 / 上证50`。

### 涨跌统计
- 全市场快照（em/sina）聚合涨跌幅：`>0` 上涨、`<0` 下跌、`==0` 平盘；`>=9.5` 近似涨停、`<=-9.5` 近似跌停。
- 快照不可得时标注缺失，不编造。

### 板块表现
- `stock_board_industry_summary_ths()` 返回约 90 个同花顺行业板块，含 `板块 / 涨跌幅 / 总成交额 / 净流入 / 领涨股`；金额单位亿元、涨跌幅为 %。

### 龙虎榜
- `stock_lhb_detail_em(date=...)` 受限网络可能失败，回退 `stock_lhb_detail_daily_sina(date=...)`。
- 盘后约 30 分钟才更新。

### 技术面（RSI / MA）
- 用 `index_zh_a_hist(symbol="000001", period="daily")` 取上证日线收盘价，本地计算：
  - `RSI(14)`：14 日平均涨幅 / 平均跌幅推导
  - `MA5 / MA20 / MA60`：对应周期收盘均价

### 超时处理策略
| 类型 | 建议超时 | 降级策略 |
|------|----------|----------|
| 行情类（指数 / 快照） | 15 秒 | 重试 1 次，仍失败标注"数据待补充" / 降级下一级 |
| 龙虎榜类 | 20 秒 | 回退 sina |
| 新闻类 | 20 秒 | 标注"数据待补充"，建议 WebSearch |
| 资金流类 | 15 秒 | 盘后可能延迟，标注"盘后更新" |
