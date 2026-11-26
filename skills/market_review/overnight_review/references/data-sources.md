# 数据接口与时间规则（个人通用版）

> 本文件定义隔夜外围市场复盘所需的数据来源与查询规则。本技能**不依赖任何单一商业金融数据库**，数据层由以下**三个已连接 MCP** 共同承担：
> - **东方财富妙想 MCP**（`mx-ds-mcp`）：覆盖全球宏观、港美股、行业产业链、商品、新闻、研报、公告。
> - **腾讯自选股 MCP**（`westock-mcp`）：覆盖 A 股盘中验证（市场总览、板块、个股行情、资金流、筹码、技术、新闻/公告/研报）。
> - **通达信 MCP**（`tdx-connector`）：覆盖 A 股/港股/期货行情、K 线、技术指标、F10 深度资料、板块行业、研报一致预期。

## 推荐查询矩阵

| 需求 | 主工具 | 补充工具 | 查询要点 |
|---|---|---|---|
| 全球主要指数、风格与宽度 | `mx_index_block_finance_data` | `mx_us_finance_data`、`mx_hk_finance_data`、`mx_comprehensive_finance_data` | 指数/板块 + 交易日/区间 + 涨跌幅/收盘 |
| 美股指数/个股/估值/财务 | `mx_us_finance_data` | — | 标的 + 字段 + 目标交易日/区间（覆盖行情、估值、盈利预测、IPO/回购/分红） |
| 港股指数/个股 | `mx_hk_finance_data` | `westock_mcp.data_sector`（港美行业） | 标的 + 字段 + 目标交易日 |
| 日韩欧及新兴市场股票/德股/台股 | `mx_comprehensive_finance_data` | `tdx_connector.tdx_lookup_stock` → `tdx_kline` | 日股/韩股/台股/德股/其他跨市场品种 |
| 全球及中国宏观时序（GDP/CPI/PMI/利率/社融等） | `mx_macro_data` | — | 指标 + 经济体/行业 + 区间 + 频率（全球及中国宏观指标、区域经济） |
| 大宗商品（油/金/铜/铝等）量价 | `mx_macro_data` | `mx_comprehensive_finance_data`（期货）、`tdx_connector.tdx_futures_quotes` | 品种 + 区间 + 同比/环比 |
| 隔夜财经事件 / 新闻 / 央行 / 政策 | `mx_finance_search_news` | `westock_mcp.data_news` | 市场/主体 + 绝对日期区间 + 事件类型 |
| 券商研报、评级观点、目标价 | `mx_finance_search_news` | `westock_mcp.data_news`(type=1 研报)、`tdx_connector.tdx_api_data`（研报一致预期 yzyq） | 机构/行业 + 日期区间 + 共识/分歧 |
| 公司正式披露 / 公告（含港美股） | `mx_finance_search_notice` | `westock_mcp.data_news`(type=0 公告) | 主体 + 公告类型 + 日期区间 |
| A 股板块/行业映射、成分、估值 | `mx_index_block_finance_data` | `westock_mcp.data_sector`、`tdx_connector.tdx_api_data`（板块行业） | 规范标的 + 业务/行情/估值/财务字段 |
| A 股盘中验证：指数/板块/个股/资金/筹码/技术 | `westock_mcp.data_market_overview` / `data_index` / `data_sector` / `data_quote` / `data_fund_flow` / `data_chip` / `data_technical` | `tdx_connector.tdx_quotes` / `tdx_kline` / `tdx_api_data` | 交易日期 + 代码；筹码/技术按 data_chip/data_technical 口径 |
| 个股技术形态与 F10 深度资料 | `tdx_connector.tdx_api_data` | `westock_mcp.data_technical` | 代码（纯数字）+ entry/fixedTag |

## 关键事件时间与预期查询

高敏感事件（非农、CPI、PCE、央行会议、GDP、PMI 等）必须同时查询并交叉核验：

1. **正式日程/发布机构**：确认事件名称、当地日期、当地时间和时区；
2. **宏观结构化数据**：获取前值、市场预期、修正值及指标定义；
3. **公开资讯**：补充市场当前定价、敏感资产和事件前后背景；
4. **北京时间**：依据事件发生地时区及夏令时状态换算，**不使用固定模板时间**。

推荐查询应同时包含：`事件标准名 + 发布机构 + 当地日期 + 当地发布时间及时区/夏令时 + 前值 + 市场预期 + 修正值`。

事件卡只有在发布时间与前值/预期可核验时才标“已确认”；时间无法确认时写“具体时间待确认”，不得按历史惯例推断或编造。

| 需求 | 主工具 | 补充工具 | 输出要求 |
|---|---|---|---|
| 宏观数据发布时间与前值/预期 | `mx_macro_data` | `mx_finance_search_news` | 当地时间、北京时间、前值、预期、修正值 |
| 央行会议/官员讲话 | `mx_finance_search_news` | Web 搜索（仅主通道不足时） | 机构、议程、当地时区、北京时间、确认状态 |
| 公司财报发布时间 | `mx_finance_search_notice` | `mx_finance_search_news` | 盘前/盘后、当地时间、北京时间、报告期 |
| 展会/会议/政策发布 | `mx_finance_search_news` | `mx_finance_search_notice` | 正式日程、影响窗口、是否交易时段 |

## 美股数据接口

### mx_us_finance_data
**用途**：获取美股主要指数、个股的指定日收盘价、涨跌幅及估值等。
**参数**：自然语言问句，例如“苹果和特斯拉近 10 个交易日的涨跌幅、换手率”。
**返回**：覆盖行情、技术指标、估值盈利预测、财务三表、IPO/回购/分红等。
**使用场景**：第二章美股隔夜表现、估值水位点评。

## 港股数据接口

### mx_hk_finance_data
**用途**：获取港股主要指数（恒生指数、恒生科技指数等）与重点个股日行情。
**参数**：自然语言问句，例如“腾讯、阿里、美团最近一个交易日收盘价与涨跌幅”。
**使用场景**：第二章港股隔夜表现。

## 全球宏观与商品接口

### mx_macro_data
**用途**：查询全球及中国宏观经济、行业经济与大宗商品高频/历史指标。
**适用**：GDP、CPI、PPI、M2、社融、利率、进出口、PMI、区域经济，以及能源/金属/化工/农产品/新能源等行业的量价数据。
**使用场景**：第三章日韩及欧洲市场概览、商品（油金铜铝）走势。

### mx_comprehensive_finance_data
**用途**：跨市场综合查询，覆盖日股/韩股/台股/德股、期货、期权、企业发行人等。
**使用场景**：日韩欧股票、商品期货（沪铜/原油/黄金等）。

## 舆情、政策与研报接口

### mx_finance_search_news
**用途**：检索新闻资讯、研究报告、评级观点、目标价、投资逻辑、行业趋势。
**使用场景**：隔夜事件、机构策略、券商观点、赛道研判。

### mx_finance_search_notice
**用途**：检索上市公司/基金/债券/港美股公告与官方披露。
**使用场景**：公司正式披露、重大事项。

### westock_mcp.data_news
**用途**：个股新闻/公告/研报列表（type：0 公告 / 1 研报 / 2 新闻 / 3 全部）。
**使用场景**：A 股个股层面的公告与研报补充。

### tdx_connector.tdx_api_data
**用途**：A 股/港股 F10 深度资料，含研报一致预期（entry `CWServ.tdxf10_gg_ybpj`, fixedTag `yzyq`）、财务、股东、资金、板块行业等 30 个接口。
**使用场景**：重点公司验证、研报一致预期、板块行业映射。

## A 股盘中验证接口（westock + tdx）

- `westock_mcp.data_market_overview`：市场总览（涨跌统计/成交/估值/宽度）。
- `westock_mcp.data_index`：指数行情。
- `westock_mcp.data_sector`：板块数据（申万行业、概念、涨跌排名、资金流入）。
- `westock_mcp.data_quote`：个股行情快照。
- `westock_mcp.data_fund_flow`：个股/板块资金流向。
- `westock_mcp.data_chip`：筹码分布（获利比例、集中度）。
- `westock_mcp.data_technical`：技术指标（KDJ/MACD/RSI/BOLL）。
- `tdx_connector.tdx_quotes` / `tdx_kline`：实时行情与 K 线。
- `tdx_connector.tdx_api_data`：F10 深度资料与板块行业。

## 数据接口与异常处理

- 美股指数不得使用个股接口；港股实体优先使用规范名称或工具返回的规范代码。
- 工具失败先同参数重试一次；空结果只修正一个最关键的参数缺口，再按回退路径处理（主工具 → 同生态补充工具 → Web 搜索）。
- 数据缺失必须说明缺失项及对结论的影响，不得用训练知识补精确事实。
- 商品仅有文本源时，只描述方向、事件和机制，不做精细排名或与结构化行情混算。
- 数据核验、事件时间、映射和去重执行 `data-validation.md`。
- **覆盖能力与缺口说明**：上述三个 MCP 已覆盖原技能所需的全球指数、港美股、全球宏观、商品、新闻、研报、公告、A 股盘中验证等全部维度；唯一弱项是**调研纪要（机构实地调研/交流纪要）**维度覆盖有限，相关结论应标注来源为公开研报或公告，不得声称引用未获取的调研纪要。
