# 数据源与实现说明

本文档记录舆情风险预警 skill 的数据接口细节、numpy 回退实现要点与已知限制，
供后续维护与故障排查使用。

## 一、大盘模式数据源

### 1.1 上证 K 线（tdx 连接器）

Agent 侧通过 `tdx_kline(code="000001", setcode="1", period="4", wantNum=1250)` 取数，
落盘 `sh_index_kline.txt`。脚本 `market_risk.py` 的 `load_kline()` 支持：

- CSV 格式：首行表头 `date,open,high,low,close[,volume,amount]`，后续每行一条记录
- JSON 格式：`list[dict]`，字段同上

### 1.2 新闻（wenda_news_query）

`news.json` 支持：
- `list[dict]`，字段 `date/title/content`（或 `datetime/summary`）
- `dict` 包一层 `data` 或 `news` 键

### 1.3 市场快照（snapshot.json）

字段见 SKILL.md 第四节。`amount_yi` 为全市场成交额（亿元），`up_total/down_total`
为涨跌家数（计算广度），`usdcny` 为汇率（计算 usdcny_pct）。

## 二、个股模式数据源（东方财富）

本机网络受限时（实测 push2his curl exit=52 空响应），真实行情不可用；
需在能访问东财的环境运行。以下为脚本实现所用的接口：

| 用途 | 接口 | 说明 |
|---|---|---|
| 日 K 线（前复权） | `push2his.eastmoney.com/api/qt/stock/kline/get` | secid=1.沪/0.深，fields2=f51..f61（date/open/close/high/low/vol/amount/振幅/pct/涨跌额/换手） |
| 日 K 线（回退） | Tushare `daily` + `daily_basic` | 东财 push2his 不可达时自动回退（本机实测可用）；daily.amount 千元→元 ×1000；换手率取自 daily_basic.turnover_rate；token 从 ~/.hermes/config.yaml 提取 |
| 股吧帖子 | `guba.eastmoney.com/list,<code>_<page>.html` | HTML 正则解析标题（class=article-title / a[title]） |
| 个股新闻 | `search-api-web.eastmoney.com/search/jsonp` | keyword=股票名称（push2 f58，失败退回代码）；cb() 解包；返回 date/title/content（去 <em> 高亮）；pageSize=30 单页 |
| 行业板块涨跌幅 | `push2.eastmoney.com/api/qt/stock/get` | f127=行业名 f128=行业代码 → 板块指数 secid=`90.BKxxxx` 取 f170 |

### 2.1 失败降级

- K 线：东财 push2his 失败 → Tushare 回退（不中断）；两者都失败抛错不伪造
- 行业板块接口失败：`ind_pct` 使用个股 20 日均涨幅代理，报告标注「行业板块接口不可用…代理」
- 股吧解析不到帖子：明确报错，不伪造（但新闻通道仍可独立工作）
- 新闻通道失败 / `--no-news`：仅用股吧，报告标注「新闻通道不可用/已关闭」
- 自备语料：`--posts guba.csv`（列 `date,text` 或 `date,title`），覆盖网络不可达场景

## 三、numpy 回退随机森林实现要点

`scripts/rf_model.py` 在无 sklearn 时自动回退：

- **bootstrap**：每棵树有放回采样 n 个样本
- **节点分裂**：随机抽取 `max_features=sqrt(p)` 个特征，搜索方差下降最大的阈值
- **递归终止**：深度 ≥ max_depth(10)、样本 < min_samples_split(3)、子节点 < min_samples_leaf(2)、父节点方差≈0
- **特征重要性**：累计每次分裂的方差下降（×该节点样本数），按特征归一化——近似 sklearn 方差重要性口径
- **性能**：单树约 0.1s（1200×7），103 棵约 11s；前向验证采用「85% 训练 / 后 15% 预测」单次训练，避免逐日滚动重训（60 次重训会超过 10 分钟）

## 四、舆情指数实现

- 情感词典：金融领域正/负词 + 否定词（翻转极性）+ 程度副词（放大系数）
- 分词：优先 jieba，缺失用词典正向最大匹配
- 大盘：TF-IDF × 情感词极性，tanh 压缩到 (-1,1)
- 个股：按日聚合，稀疏日（<3 帖）退化为情感求和，否则 TF-IDF 加权 + tanh
- 历史舆情通常不可得：无历史序列时 `opinion_index` 列置 0（不参与训练），当期舆情作为报告中的校验信号单独输出

## 五、风险分级与综合分映射

- 分级：波动率 >4% 高 / 2~4% 中 / <2% 低
- 综合分（0-100 封顶，分段线性）：
  - 0% → 0 分
  - 2% → 50 分
  - 4% → 80 分
  - 6%+ → 100 分

## 六、真实数据采集（大盘模式三指数实战已验证，2026-10-09）

大盘真实数据采集链路已跑通（见 `scripts/market_collect.py`），一次命令落盘
**三指数** `kline_<code>.json / snapshot_<code>.json` + 共用 `news.json`
（上证另存 `sh_index_kline.json / snapshot.json` 兼容旧名），后接
`market_risk.py --compare <dir>` 出三指数对比预警，或 `--kline/--snapshot/--code/--name`
逐指数出单只详细报告。关键接口口径（实测确认，注意与直觉/旧笔记的差异）：

| 数据 | 来源 | 单位与口径（实测） |
|---|---|---|
| 上证/深成/创业板 60 月 K 线 | Tushare `index_daily` 000001.SH / 399001.SZ / 399006.SZ | 2021-09 起约 1491 行（按日历日×1.8 换算，含非交易日过滤后约 1250 交易日）；amount 千元 |
| 沪深300/科创50 涨跌幅 | Tushare `index_daily` 399300.SZ / 000688.SH | pct_chg 直接使用 |
| 全市场成交额 | Tushare `daily_info` | **amount 单位已是亿元**；取 ts_code ∈ {SH_MARKET, SZ_MARKET} 相加（沪 8120+深 8716=16836 亿） |
| 涨跌家数分布 | 东财 `push2ex.getTopicZDFenBu` | **本机 curl 可用**（与 push2his 不通相反）；fenbu 每项单键 {涨跌幅档:家数} |
| 主力资金净流入 | Tushare `moneyflow_mkt_dc` | **net_amount 单位元**，÷1e8 得亿元（实测 -4.80e10 元 = -480.4 亿） |
| 新闻 | 东财 `search-api-web.eastmoney.com/search/jsonp` | **Tushare `pro.news` 无权限**；jsonp 用正则 `cb\((.*)\)` 解包，keyword="A股 大盘" |
| 汇率 USDCNY | Tushare `fx_daily` | **无权限** → 兜底 7.15 中性值（变化率≈0，对模型影响可忽略） |

Tushare token：本地 `tushare` 库（v1.4.29 已装）可直接用，token 从
`~/.hermes/config.yaml` 的 `tushareMcp.url` 中 `token=` 参数提取；
用本地库而非 MCP 调大接口可避免 MCP 返回被截断（322KB 级响应会截断）。

**注意（2026-10-09 实测）**：`get_tushare_token()` 打印「未从 config.yaml 提取到
Tushare token，接口将失败」时**不代表真的失败**——tushare 库会沿用先前会话
`ts.set_token()` 持久化的 token，`index_daily` 等调用照常成功（本机实测三指数各
拉到 1491 行）。判断标准是数据是否落盘，不是告警行；若 K 线行数为 0 再排查 token。

### 三指数对比实战解读要点（2026-10-09 案例）

- 2026-10-08 大跌日采集：上证 -0.79%、深成 -2.07%、创业板 -3.15%；
  舆情（全市场新闻 20 条）指数 +0.369 偏多，涨跌家数 925/4338 广度极弱。
- 对比输出：上证 2.16%/中/52，深成 3.44%/中/72，创业板 4.73%/高/87，
  风险梯度与当日跌幅结构一致（创业板跌最重 → 预测风险最高），
  且三指数分差 ≥20 触发「结构行情概率大」提示。
- **名义风险等级与综合风险分矛盾时（如贴近 2% 阈值），按"偏防守"解读**——
  指数看综合分+舆情方向，勿只看绝对波动率。

## 七、已知限制

1. 本机（hermes 环境）无法访问东财 push2his（curl exit=52），个股真实行情需外部环境；
   **但东财 push2ex（涨跌分布/涨停池）可用**，大盘模式涨跌家数靠它补齐
2. 训练期无历史舆情 → opinion 不作为训练特征，仅当期校验（SKILL.md 已声明）
3. VIF 过滤会剔除常数/完全共线特征（如演示数据中全 0 的 usdcny_pct），属预期行为
4. 演示数据仅用于管线验证与离线自测，不构成真实预警
5. Tushare `pro.news` / `fx_daily` 无权限，新闻走东财搜索、汇率用中性兜底
5. **演示数据种子必须确定性派生，禁止用 `hash(code)`**：Python 3 字符串 hash 每次进程随机化（PYTHONHASHSEED），导致同参数重复运行结果不一致、自测无法复现。正确做法：`int(re.sub(r"\D","",code)) % 2**31` 由代码数字派生种子（cli.py `_demo_kline` 已采用，market_risk.py 用固定 seed=2026）
6. **风险分必须封顶 0-100**：映射函数曾出现 117/100（分段线性未 clamp），已在 `risk_score`/`_risk_score` 加 `min(max(s,0),100)`。修改分级阈值时留意封顶
7. **numpy 回退 RF 的 OOS 评估勿逐日滚动重训**：60 次重训 × 103 棵树 ≈ 11 分钟，直接超时；改为「前 85% 训练一次、预测后 15% 每一天」的固定模型前向验证，严格无泄露且仅 2 次训练（~20 秒）
