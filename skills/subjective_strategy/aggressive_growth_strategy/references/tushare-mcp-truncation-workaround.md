# Tushare MCP 截断绕过与批量查询配方（2026-10-22 实测）

## 背景
`mcp_tushareMcp_index_weight` 返回约2000条成分股时响应达 ~224K 字符被截断，无法取全列表做轮换选股。
本机已装 tushare Python 包（1.4.29），用本地直连替代 MCP 即可拿到完整数据。

## Token 位置
`~/.hermes/config.yaml` 的 tushareMcp 段：
```yaml
tushareMcp:
  url: https://api.tushare.pro/mcp/?token=<TOKEN>
```
定位命令：`grep -ri "tushare" ~/.hermes/config.yaml`

## 完整成分股获取（顺序与MCP一致 = 权重降序）
```python
import tushare as ts
ts.set_token('<TOKEN>')
pro = ts.pro_api()
# ⚠️ 当月快照可能未发布：月末 cron 运行查当月（如20261001-20261031）常返回0行
# （实测2026-10-30查10月=0行，快照为月末发布，最新可用=20260930）
# → 扩窗探测（近3个月）取最新可用快照，勿直接取空 DataFrame（IndexError）
probe = pro.index_weight(index_code='932000.CSI', start_date='20260801', end_date='20261031')
latest = sorted(probe['trade_date'].unique())[-1]   # 保留最新一个快照日
df = probe[probe['trade_date']==latest].reset_index(drop=True)  # 2000行
df.to_csv('/tmp/csi2000_constituents.csv', index=False)
```
⚠️ 轮换选股必须用此顺序（权重降序）取第 new_index 只，与 MCP 返回一致。

## 指数成员查询（Step5 指数路径）
`index_weight` 不支持按 ts_code 反查（报 50101 参数校验失败），逐指数查 index_code 后过滤：
```python
candidates = {
  '000852.SH': '中证1000', '000905.SH': '中证500', '000300.SH': '沪深300',
  '399001.SZ': '深证成指', '399106.SZ': '深证综指',
  '000688.SH': '科创50', '000698.SH': '科创100', '399303.SZ': '国证2000',
}
```
⚠️ 科创板/688开头小盘股重点查 科创50(000688)/科创100(000698)；中证2000池内小盘查 国证2000(399303)、中证1000 判断升维路径。2026-10-23 毕得医药实测：688073.SH 仅在 932000.CSI + 399303.SZ 命中，其余为空——空=未纳入，如实标注"潜在升维未兑现"。
    df = pro.index_weight(index_code=idx, start_date='YYYYMM01', end_date='YYYYMM31')
    df = df[df['trade_date']==sorted(df['trade_date'].unique())[-1]]
    hit = df[df['con_code']==ts_code]
    print(name, '✅在成分' if len(hit) else '❌不在')
# 自身权重：
df2k = pro.index_weight(index_code='932000.CSI', start_date=..., end_date=...)
```

## 250日价格分位 + 20日均量（Step4 / Step7）
```python
df = pro.daily(ts_code=ts_code, start_date='YYYYMMDD', end_date='YYYYMMDD').sort_values('trade_date')
closes, highs, lows = df['close'], df['high'], df['low']
pos = (closes.iloc[-1]-lows.min())/(highs.max()-lows.min())*100  # 区间法分位
below = (closes < closes.iloc[-1]).sum()/len(closes)*100         # 收盘价分位
vol20 = df['vol'].tail(20).mean()*100                            # 股/日（vol单位是手）
max_buy = vol20*0.1                                              # 单日最大买入量(10%)
```

## 其他实测要点
- MCP 单股查询（daily_basic / fina_indicator / stk_factor / moneyflow / stock_basic / stock_st）返回正常无截断
- stock_st 返回空列表 = 非ST
- 数据覆盖：daily 单次可拉近250+日；index_weight 需指定起止日
- **fina_indicator 报告期滞后**：10月末最新仍为20260630(H1)；最新季报（20260930 Q3）数据用东财搜索新闻获取（实测悦达投资10/29三季报新闻含营收/净利/扣非同比），报告标注"媒体披露"而非API验证
