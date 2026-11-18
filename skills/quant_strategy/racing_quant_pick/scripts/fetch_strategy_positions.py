#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马量化策略选股 · 策略库持仓拉取参考脚本（可配置 endpoint）

用法：
  python fetch_strategy_positions.py --list-recommended
  python fetch_strategy_positions.py --match "动量" --top 20
  python fetch_strategy_positions.py --strategy-id stXXXX --top 20

连接参数**必须由使用者自行配置**，通过环境变量
RACING_DB_HOST / RACING_DB_PORT / RACING_DB_USER / RACING_DB_PASSWORD / RACING_DB_NAME
注入，或用 --db-host/--db-port/--db-user/--db-pass/--db-name 覆盖。
本仓库**不内置任何数据库地址、账号或密码**；缺省必填参数时明确报错退出，绝不回退到
任何隐含默认值。请连接自有或已获授权的策略库。

依赖：pymysql（pip install pymysql）。缺失时给出明确提示而非静默失败。
"""
from __future__ import annotations

import argparse
import json
import os
import sys


REQUIRED_ENV = {
    "host": ("db_host", "RACING_DB_HOST"),
    "user": ("db_user", "RACING_DB_USER"),
    "password": ("db_pass", "RACING_DB_PASSWORD"),
    "database": ("db_name", "RACING_DB_NAME"),
}


def get_db_config(args) -> dict:
    """组装连接配置：仅取显式入参 / 环境变量，缺失即报错，不设任何隐含默认值。"""
    cfg = {}
    missing = []
    for key, (arg_name, env_name) in REQUIRED_ENV.items():
        value = getattr(args, arg_name) or os.getenv(env_name)
        if not value:
            missing.append(env_name)
        cfg[key] = value
    if missing:
        sys.stderr.write(
            "[ERROR] 缺少数据库连接配置：" + ", ".join(missing) + "\n"
            "请通过环境变量或 --db-host/--db-user/--db-pass/--db-name 提供。\n"
            "本仓库不内置任何数据库地址、账号或密码，请连接自有或已获授权的策略库。\n"
        )
        sys.exit(2)
    cfg["port"] = int(args.db_port or os.getenv("RACING_DB_PORT", "3306"))
    return cfg


def connect(cfg: dict):
    try:
        import pymysql
    except ImportError:
        sys.stderr.write("[ERROR] 缺少依赖 pymysql，请先执行: pip install pymysql\n")
        sys.exit(2)
    return pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], database=cfg["database"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def list_recommended(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT strategy_id, strategy_name, strategy_name_cn, strategy_cat, "
            "strategy_summ FROM strategy_information WHERE if_recommended = 1"
        )
        return cur.fetchall()


def match_strategies(conn, kw: str, limit: int):
    with conn.cursor() as cur:
        like = f"%{kw}%"
        cur.execute(
            "SELECT strategy_id, strategy_name, strategy_name_cn, strategy_cat, "
            "strategy_summ, strategy_table FROM strategy_information "
            "WHERE strategy_desc LIKE %s OR strategy_cat LIKE %s "
            "ORDER BY if_recommended DESC LIMIT %s",
            (like, like, limit),
        )
        return cur.fetchall()


def get_positions(conn, strategy_id: str, top: int):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT strategy_table FROM strategy_information WHERE strategy_id = %s",
            (strategy_id,),
        )
        row = cur.fetchone()
        if not row or not row.get("strategy_table"):
            sys.stderr.write(f"[ERROR] 未找到策略 {strategy_id} 的持仓表\n")
            sys.exit(1)
        table = row["strategy_table"]
        cur.execute(
            f"SELECT trade_date, trading_info, update_time FROM `{table}` "
            "WHERE strategy_id = %s ORDER BY trade_date DESC LIMIT 1",
            (strategy_id,),
        )
        pos = cur.fetchone()
    if not pos:
        return None
    trading_info = json.loads(pos["trading_info"]) if pos.get("trading_info") else {}
    items = sorted(trading_info.items(), key=lambda kv: float(kv[1] or 0), reverse=True)[:top]
    return {"trade_date": pos.get("trade_date"), "positions": items}


def main():
    p = argparse.ArgumentParser(description="赛马量化策略选股 · 策略库持仓拉取")
    p.add_argument("--list-recommended", action="store_true", help="列出所有推荐策略")
    p.add_argument("--match", type=str, default=None, help="关键词匹配策略(strategy_desc)")
    p.add_argument("--strategy-id", type=str, default=None, help="指定策略 ID/名称")
    p.add_argument("--top", type=int, default=20, help="持仓/匹配条数上限")
    p.add_argument("--db-host", type=str, default=None)
    p.add_argument("--db-port", type=str, default=None)
    p.add_argument("--db-user", type=str, default=None)
    p.add_argument("--db-pass", type=str, default=None)
    p.add_argument("--db-name", type=str, default=None)
    args = p.parse_args()

    cfg = get_db_config(args)
    conn = connect(cfg)
    try:
        if args.list_recommended:
            print(json.dumps(list_recommended(conn), ensure_ascii=False, indent=2))
        elif args.match:
            print(json.dumps(match_strategies(conn, args.match, args.top), ensure_ascii=False, indent=2))
        elif args.strategy_id:
            pos = get_positions(conn, args.strategy_id, args.top)
            print(json.dumps(pos, ensure_ascii=False, indent=2) if pos else "[WARN] 无持仓数据")
        else:
            sys.stderr.write("[ERROR] 请至少指定 --list-recommended / --match / --strategy-id 之一\n")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
