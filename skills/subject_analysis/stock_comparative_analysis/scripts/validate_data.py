#!/usr/bin/env python3
"""
股票对比报告数据验证器

在生成报告前检查数据完整性，确保：
- 所有必需的数据字段已获取
- 数据日期有效且一致
- 标记缺失数据并提示
- 生成数据质量报告

使用：
    python validate_data.py <stock_codes.json>
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


# 必需的数据字段定义（数据维度 -> 必需字段）
REQUIRED_FIELDS = {
    "公司简介": [
        "股票简称", "股票代码", "主营业务", "公司简介",
        "证监会行业", "申万行业", "概念板块", "成立日期", "上市日期"
    ],
    "财务报表": [
        "营业收入", "营收增长", "净利润", "毛利率",
        "营业利润率", "净利率", "报告期"
    ],
    "财务分析": [
        "净资产收益率", "总资产收益率", "流动比率", "速动比率", "资产负债率",
        "营收三年复合增长", "净利润三年复合增长"
    ],
    "估值分析": [
        "总市值", "市盈率TTM", "市净率", "PEG", "股息率",
        "交易日期"
    ],
    "区间行情": [
        "开始日期", "结束日期", "开始价格", "结束价格", "最高价",
        "最低价", "涨跌幅", "换手率", "成交量"
    ],
    "技术指标": [
        "RSI", "MACD", "KDJ", "BOLL", "交易日期"
    ],
    "资金流向": [
        "主力净流入", "超大单净流入", "大单净流入",
        "中单净流入", "小单净流入", "交易日期"
    ],
    "融资融券": [
        "融资余额", "融券余额", "融资净买入",
        "融券净卖出", "交易日期"
    ],
    "研究报告": [
        "机构名称", "评级类型", "摘要", "发布日期"
    ],
    "公司公告": [
        "标题", "类别", "发布日期"
    ],
    "股票舆情": [
        "标题", "内容摘要", "发布时间"
    ]
}

# 数据有效性检查配置（按数据维度设置最大有效期，单位：天）
DATA_VALIDITY = {
    "财务报表": 90,   # 财务数据最大有效期（天）
    "财务分析": 90,
    "区间行情": 1,    # 行情数据最大有效期（天）
    "技术指标": 1,
    "资金流向": 1,
    "融资融券": 1,
    "研究报告": 30,   # 资讯类数据最大有效期（天）
    "公司公告": 30,
    "股票舆情": 30,
}


class DataValidator:
    """数据验证器"""
    
    def __init__(self, stock_codes: List[str]):
        self.stock_codes = stock_codes
        self.data_store: Dict[str, Dict[str, Any]] = {}
        self.validation_results: Dict[str, Any] = {
            "stocks": {},
            "overall_quality": "unknown",
            "missing_data": [],
            "warnings": [],
            "data_dates": {}
        }
    
    def add_data(self, api_name: str, stock_code: str, data: Any):
        """添加数据到存储"""
        if stock_code not in self.data_store:
            self.data_store[stock_code] = {}
        self.data_store[stock_code][api_name] = data
    
    def check_required_fields(self, api_name: str, stock_code: str, data: Any) -> List[str]:
        """检查必需字段是否存在"""
        if api_name not in REQUIRED_FIELDS:
            return []
        
        missing = []
        required = REQUIRED_FIELDS[api_name]
        
        if isinstance(data, dict):
            for field in required:
                if field not in data or data[field] is None:
                    missing.append(field)
        elif isinstance(data, list) and len(data) > 0:
            # 对于列表数据，检查第一个元素
            first_item = data[0] if data else {}
            for field in required:
                if field not in first_item or first_item[field] is None:
                    missing.append(field)
        
        return missing
    
    def check_data_freshness(self, api_name: str, stock_code: str, data: Any) -> Optional[str]:
        """检查数据新鲜度"""
        # 尝试从数据中提取日期字段
        date_fields = ["交易日期", "报告期", "发布日期", "发布时间", "结束日期"]
        data_date = None
        
        if isinstance(data, dict):
            for field in date_fields:
                if field in data and data[field]:
                    data_date = data[field]
                    break
        elif isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            for field in date_fields:
                if field in first_item and first_item[field]:
                    data_date = first_item[field]
                    break
        
        if not data_date:
            return None
        
        # 解析日期
        try:
            if isinstance(data_date, str):
                # 尝试多种日期格式
                for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        data_date = datetime.strptime(data_date[:10], "%Y-%m-%d")
                        break
                    except ValueError:
                        continue
            elif isinstance(data_date, (int, float)):
                data_date = datetime.fromtimestamp(data_date / 1000)
        except Exception:
            return None
        
        # 计算数据年龄
        today = datetime.now()
        age_days = (today - data_date).days
        
        # 根据数据维度判断是否过期
        max_age = DATA_VALIDITY.get(api_name, 30)
        
        if age_days > max_age:
            return f"数据已过时 {age_days} 天（最大允许 {max_age} 天）"
        
        return None
    
    def validate_stock(self, stock_code: str) -> Dict[str, Any]:
        """验证单只股票的数据"""
        result = {
            "stock_code": stock_code,
            "data_completeness": 0,
            "total_checks": 0,
            "passed_checks": 0,
            "missing_fields": {},
            "warnings": [],
            "data_dates": {}
        }
        
        if stock_code not in self.data_store:
            result["warnings"].append("无任何数据")
            return result
        
        stock_data = self.data_store[stock_code]
        
        for api_name, data in stock_data.items():
            result["total_checks"] += 1
            
            # 检查必需字段
            missing = self.check_required_fields(api_name, stock_code, data)
            if missing:
                result["missing_fields"][api_name] = missing
                result["warnings"].append(f"{api_name}: 缺少字段 {', '.join(missing)}")
            else:
                result["passed_checks"] += 1
            
            # 检查数据新鲜度
            freshness_warning = self.check_data_freshness(api_name, stock_code, data)
            if freshness_warning:
                result["warnings"].append(f"{api_name}: {freshness_warning}")
            
            # 记录数据日期
            if isinstance(data, (dict, list)) and data:
                date_fields = ["交易日期", "报告期", "发布日期", "结束日期"]
                for field in date_fields:
                    if isinstance(data, dict) and field in data:
                        result["data_dates"][api_name] = data[field]
                        break
                    elif isinstance(data, list) and len(data) > 0 and field in data[0]:
                        result["data_dates"][api_name] = data[0][field]
                        break
        
        # 计算数据完整度
        if result["total_checks"] > 0:
            result["data_completeness"] = round(
                result["passed_checks"] / result["total_checks"] * 100, 1
            )
        
        return result
    
    def validate_all(self) -> Dict[str, Any]:
        """验证所有股票数据"""
        for stock_code in self.stock_codes:
            self.validation_results["stocks"][stock_code] = self.validate_stock(stock_code)
        
        # 计算整体数据质量
        completeness_scores = [
            s["data_completeness"] 
            for s in self.validation_results["stocks"].values()
        ]
        
        if not completeness_scores:
            self.validation_results["overall_quality"] = "no_data"
        else:
            avg_completeness = sum(completeness_scores) / len(completeness_scores)
            
            if avg_completeness >= 90:
                self.validation_results["overall_quality"] = "excellent"
            elif avg_completeness >= 70:
                self.validation_results["overall_quality"] = "good"
            elif avg_completeness >= 50:
                self.validation_results["overall_quality"] = "fair"
            else:
                self.validation_results["overall_quality"] = "poor"
        
        # 汇总缺失数据
        for stock_code, stock_result in self.validation_results["stocks"].items():
            for api_name, fields in stock_result["missing_fields"].items():
                for field in fields:
                    self.validation_results["missing_data"].append({
                        "stock": stock_code,
                        "api": api_name,
                        "field": field
                    })
            
            self.validation_results["warnings"].extend([
                f"[{stock_code}] {w}" for w in stock_result["warnings"]
            ])
        
        return self.validation_results
    
    def get_report(self) -> str:
        """生成验证报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("股票对比报告数据验证报告")
        lines.append("=" * 60)
        lines.append(f"验证时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"分析标的：{', '.join(self.stock_codes)}")
        lines.append("")
        
        # 整体质量
        quality_map = {
            "excellent": "优秀 ✅",
            "good": "良好 ✓",
            "fair": "一般 ⚠️",
            "poor": "较差 ❌",
            "no_data": "无数据 ❌"
        }
        lines.append(f"整体数据质量：{quality_map.get(self.validation_results['overall_quality'], '未知')}")
        lines.append("")
        
        # 各股票数据完整度
        lines.append("各股票数据完整度:")
        for stock_code, result in self.validation_results["stocks"].items():
            status = "✅" if result["data_completeness"] >= 80 else "⚠️" if result["data_completeness"] >= 50 else "❌"
            lines.append(f"  {stock_code}: {result['data_completeness']}% {status}")
        lines.append("")
        
        # 数据日期
        lines.append("数据截止日期:")
        for stock_code, result in self.validation_results["stocks"].items():
            if result["data_dates"]:
                latest_date = max(result["data_dates"].values())
                lines.append(f"  {stock_code}: {latest_date}")
        lines.append("")
        
        # 警告信息
        if self.validation_results["warnings"]:
            lines.append("警告信息:")
            for warning in self.validation_results["warnings"][:10]:  # 最多显示 10 条
                lines.append(f"  ⚠️ {warning}")
            if len(self.validation_results["warnings"]) > 10:
                lines.append(f"  ... 还有 {len(self.validation_results['warnings']) - 10} 条警告")
        lines.append("")
        
        # 缺失数据
        if self.validation_results["missing_data"]:
            lines.append("缺失数据字段:")
            for item in self.validation_results["missing_data"][:10]:  # 最多显示 10 条
                lines.append(f"  ❌ {item['stock']}.{item['api']}.{item['field']}")
            if len(self.validation_results["missing_data"]) > 10:
                lines.append(f"  ... 还有 {len(self.validation_results['missing_data']) - 10} 个缺失字段")
        lines.append("")
        
        # 建议
        lines.append("建议:")
        if self.validation_results["overall_quality"] in ["excellent", "good"]:
            lines.append("  ✅ 数据质量良好，可以生成报告")
        elif self.validation_results["overall_quality"] == "fair":
            lines.append("  ⚠️ 数据基本完整，但部分字段缺失，报告中需标注数据暂缺")
        else:
            lines.append("  ❌ 数据质量较差，建议检查数据源可用性或稍后重试")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法：python validate_data.py <stock_codes.json>")
        print("\n示例:")
        print('  echo \'["600519", "000858"]\' > stocks.json')
        print("  python validate_data.py stocks.json")
        sys.exit(1)
    
    stocks_file = Path(sys.argv[1])
    
    if not stocks_file.exists():
        print(f"[ERROR] 文件不存在：{stocks_file}")
        sys.exit(1)
    
    # 读取股票代码
    stock_codes = json.loads(stocks_file.read_text(encoding='utf-8'))
    
    if not isinstance(stock_codes, list) or len(stock_codes) == 0:
        print("[ERROR] 股票代码列表为空或格式错误")
        sys.exit(1)
    
    print(f"[INFO] 验证 {len(stock_codes)} 只股票的数据完整性...")
    
    # 创建验证器
    validator = DataValidator(stock_codes)
    
    # 注意：实际使用时需要通过公开数据源（AkShare / WebSearch / WebFetch）获取数据
    # 这里仅演示验证器用法
    # validator.add_data("公司简介", "600519", {...})
    # validator.add_data("财务报表", "600519", {...})
    # ...
    
    # 运行验证
    results = validator.validate_all()
    
    # 输出报告
    report = validator.get_report()
    print(report)
    
    # 保存验证结果
    output_file = stocks_file.parent / "data_validation_result.json"
    output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n[INFO] 验证结果已保存：{output_file}")
    
    # 根据数据质量返回退出码
    if results["overall_quality"] in ["excellent", "good"]:
        sys.exit(0)
    elif results["overall_quality"] == "fair":
        sys.exit(1)  # 警告
    else:
        sys.exit(2)  # 错误


if __name__ == "__main__":
    main()
