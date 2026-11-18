# 策略库数据模型与查询样本

> 本文件描述量化策略 MySQL 库的核心表结构与查询方式。
> **连接参数必须由使用者自行配置**（环境变量 / `db_config`），本仓库不内置任何 IP、账号或密码。
> 请连接自有或已获授权的策略库。

## 1. 连接参数（全部必填，无默认值）

| 参数 | 说明 | 来源 |
|------|------|------|
| `host` | 数据库地址 | `RACING_DB_HOST` / `--db-host` |
| `port` | 端口 | `RACING_DB_PORT` / `--db-port`（缺省 3306） |
| `user` | 账号 | `RACING_DB_USER` / `--db-user` |
| `password` | 密码 | `RACING_DB_PASSWORD` / `--db-pass` |
| `database` | 库名 | `RACING_DB_NAME` / `--db-name` |

> 除端口外均为**必填**，缺失时 `scripts/fetch_strategy_positions.py` 会明确报错退出，
> 不回退到任何隐含默认值。任何外部策略库视为外部信号源，可用性与合规性由接入方自行负责。

## 2. 主策略表 `strategy_information`

| 字段 | 类型 | 说明 |
|------|------|------|
| `strategy_table` | text | 该策略对应的持仓数据表名称 |
| `strategy_name` | text | 策略英文名称 |
| `strategy_id` | text | 策略 ID（唯一标识） |
| `benchmark` | text | 对标指数 |
| `owner_name` | text | 策略创建人姓名 |
| `owner_id` | text | 创建人 ID |
| `start_date` | datetime | 策略开始回测时间 |
| `online_date` | datetime | 策略上线时间 |
| `strategy_name_cn` | text | 策略中文名称 |
| `strategy_summ` | text | 策略简介 |
| `strategy_desc` | text | 策略详细描述（语义匹配主字段） |
| `strategy_cat` | text | 策略分类（量价/基本面/事件驱动/量化选股等） |
| `how_to_trade` | text | 交易调仓规则 |
| `if_recommended` | bigint | 是否推荐（1=推荐，0=不推荐） |

## 3. 持仓表 `{strategy_table}`

每张策略一张表，表名来自主表的 `strategy_table` 字段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trade_date` | text | 交易日期 |
| `strategy_name` | text | 策略名称 |
| `strategy_id` | text | 策略 ID |
| `trading_info` | text | 持仓信息 JSON，主键为证券代码、值为权重，如 `{'300001.SZ':'0.1'}` |
| `trade_price` | text | 交易价格（open/close） |
| `update_time` | datetime | 更新时间 |

## 4. 查询样本

**列出所有推荐策略**
```sql
SELECT strategy_id, strategy_name, strategy_name_cn, strategy_cat, strategy_summ
FROM strategy_information
WHERE if_recommended = 1;
```

**按关键词/分类匹配策略（语义检索主字段 strategy_desc）**
```sql
SELECT strategy_id, strategy_name, strategy_name_cn, strategy_cat, strategy_summ, strategy_table
FROM strategy_information
WHERE strategy_desc LIKE '%动量%'
   OR strategy_cat LIKE '%量价%'
ORDER BY if_recommended DESC;
```

**取某策略最新一期持仓**
```sql
SELECT trade_date, trading_info, update_time
FROM {strategy_table}
WHERE strategy_id = 'stXXXX'
ORDER BY trade_date DESC
LIMIT 1;
```
> `trading_info` 为 JSON 字符串，解析为 `{代码: 权重}` 字典即得到「代码/权重」选股池。
> 股票名称可通过行情源（Tushare/Akshare）按代码反查。

## 5. 参考脚本

`scripts/fetch_strategy_positions.py` 提供可配置 endpoint 的命令行实现：
- `python scripts/fetch_strategy_positions.py --list-recommended`
- `python scripts/fetch_strategy_positions.py --match "动量" --top 20`
- `python scripts/fetch_strategy_positions.py --strategy-id stXXXX --top 20`
