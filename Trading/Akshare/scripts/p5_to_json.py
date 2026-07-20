#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 result_p5_*.xlsx 转换为结构化 JSON 文件
- 读取热点分析Excel数据
- 从ClickHouse查询概念板块信息
- 输出包含hooked_hotspots、potential_hotspots、concept_boards的JSON
"""

import pandas as pd
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from market.ck_client import ClickHouseClient


def convert_stock_code_to_ck_format(code: str) -> str:
    """将 SH.603709 转换为 sh.603709 格式"""
    if not code or pd.isna(code):
        return ""
    code = str(code).strip().upper()
    if code.startswith("SH."):
        return "sh." + code[3:]
    elif code.startswith("SZ."):
        return "sz." + code[3:]
    return code.lower()


def parse_hotspots(hotspot_str: str) -> list:
    """解析热点字符串为结构化列表"""
    if not hotspot_str or pd.isna(hotspot_str):
        return []
    
    hotspots = []
    items = str(hotspot_str).split(",")
    
    for item in items:
        item = item.strip()
        if not item:
            continue
        
        # 解析层级: "AI应用-AI应用场景-AI电商" 或 "AI应用-潜在可能的应用关联"
        parts = item.split("-")
        
        hotspot = {}
        if len(parts) >= 1 and parts[0]:
            hotspot["level1"] = parts[0].strip()
        if len(parts) >= 2 and parts[1]:
            hotspot["level2"] = parts[1].strip()
        if len(parts) >= 3 and parts[2]:
            hotspot["level3"] = parts[2].strip()
        
        if hotspot:
            hotspots.append(hotspot)
    
    return hotspots


def fetch_concept_boards_from_ck(ck_client: ClickHouseClient, stock_codes: list) -> dict:
    """从ClickHouse查询概念板块信息"""
    if not stock_codes:
        return {}
    
    # 转换股票代码格式
    ck_codes = [convert_stock_code_to_ck_format(code) for code in stock_codes if code]
    
    # 查询概念成分股表
    query = f"""
    SELECT concept_name, stock_code 
    FROM stock_data.finance_concept_components 
    WHERE stock_code IN ({','.join([f"'{code}'" for code in ck_codes])})
    """
    
    try:
        df = ck_client.query_df(query)
        if df is None or df.empty:
            return {}
        
        # 构建股票->概念板块映射
        stock_concepts = {}
        for _, row in df.iterrows():
            stock_code = row['stock_code'].lower() if row['stock_code'] else ""
            concept_name = row['concept_name']
            
            if stock_code not in stock_concepts:
                stock_concepts[stock_code] = []
            stock_concepts[stock_code].append({"concept_name": concept_name})
        
        return stock_concepts
    except Exception as e:
        print(f"查询ClickHouse失败: {e}")
        return {}


def build_hotspots_index(stocks: list) -> tuple:
    """构建热点索引"""
    hooked_index = {}
    potential_index = {}
    
    for stock in stocks:
        code = stock.get("code", "")
        
        # 挂钩热点索引
        for hotspot in stock.get("hooked_hotspots", []):
            level1 = hotspot.get("level1", "")
            if level1:
                if level1 not in hooked_index:
                    hooked_index[level1] = {"count": 0, "stocks": []}
                hooked_index[level1]["count"] += 1
                hooked_index[level1]["stocks"].append(code)
        
        # 潜在热点索引
        for hotspot in stock.get("potential_hotspots", []):
            level1 = hotspot.get("level1", "")
            if level1:
                if level1 not in potential_index:
                    potential_index[level1] = {"count": 0, "stocks": []}
                potential_index[level1]["count"] += 1
                potential_index[level1]["stocks"].append(code)
    
    return hooked_index, potential_index


def build_concept_board_index(stocks: list) -> dict:
    """构建概念板块索引"""
    concept_index = {}
    
    for stock in stocks:
        code = stock.get("code", "")
        
        for board in stock.get("concept_boards", []):
            concept_name = board.get("concept_name", "")
            if concept_name:
                if concept_name not in concept_index:
                    concept_index[concept_name] = {"count": 0, "stocks": []}
                concept_index[concept_name]["count"] += 1
                concept_index[concept_name]["stocks"].append(code)
    
    return concept_index


def convert_excel_to_json(excel_path: str, output_dir: str):
    """主转换函数"""
    print(f"读取Excel文件: {excel_path}")
    df = pd.read_excel(excel_path)
    
    print(f"共 {len(df)} 条股票记录")
    
    # 获取所有股票代码用于查询概念板块
    stock_codes = df['股票代码'].tolist()
    
    # 连接ClickHouse查询概念板块
    print("连接ClickHouse查询概念板块...")
    ck_client = None
    try:
        ck_client = ClickHouseClient()
        stock_concepts = fetch_concept_boards_from_ck(ck_client, stock_codes)
        print(f"查询到 {len(stock_concepts)} 只股票的概念板块信息")
    except Exception as e:
        print(f"ClickHouse连接失败: {e}")
        stock_concepts = {}
    finally:
        if ck_client:
            ck_client.close()
    
    # 转换股票数据
    stocks = []
    for _, row in df.iterrows():
        code = str(row['股票代码']).strip() if pd.notna(row['股票代码']) else ""
        name = str(row['股票名称']).strip() if pd.notna(row['股票名称']) else ""
        
        # 转换股票代码为ClickHouse格式查询概念板块
        ck_code = convert_stock_code_to_ck_format(code)
        
        stock_item = {
            "code": code,
            "name": name,
            "market_cap_adjusted": float(row['调整后流通市值（亿）']) if pd.notna(row['调整后流通市值（亿）']) else 0.0,
            "business_description": str(row['公司基本业务介绍']).strip() if pd.notna(row['公司基本业务介绍']) else "",
            "hooked_hotspots": parse_hotspots(row.get('挂钩领域', '')),
            "potential_hotspots": parse_hotspots(row.get('潜在关联领域', '')),
            "concept_boards": stock_concepts.get(ck_code, [])
        }
        
        stocks.append(stock_item)
    
    # 构建索引
    print("构建热点索引...")
    hooked_index, potential_index = build_hotspots_index(stocks)
    
    print("构建概念板块索引...")
    concept_board_index = build_concept_board_index(stocks)
    
    # 构建最终JSON
    output_data = {
        "metadata": {
            "source_file": os.path.basename(excel_path),
            "concept_source": "ClickHouse: finance_concept_components",
            "total_stocks": len(stocks),
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        },
        "stocks": stocks,
        "hooked_hotspots_index": hooked_index,
        "potential_hotspots_index": potential_index,
        "concept_board_index": concept_board_index
    }
    
    # 输出文件
    os.makedirs(output_dir, exist_ok=True)
    excel_filename = os.path.basename(excel_path)
    json_filename = excel_filename.replace('.xlsx', '.json')
    output_path = os.path.join(output_dir, json_filename)
    
    print(f"写入JSON文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"转换完成! 共处理 {len(stocks)} 只股票")
    print(f"  - 挂钩热点类别: {len(hooked_index)}")
    print(f"  - 潜在热点类别: {len(potential_index)}")
    print(f"  - 概念板块类别: {len(concept_board_index)}")
    
    return output_path


def find_latest_p5_file(stock_analysis_dir: str) -> str:
    """查找最新的 result_p5_*.xlsx 文件"""
    import glob
    
    pattern = os.path.join(stock_analysis_dir, "result_p5_*.xlsx")
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"未找到 {pattern}")
    
    # 按文件名排序，返回最新的
    latest = sorted(files, reverse=True)[0]
    return latest


def main():
    # 路径配置
    stock_analysis_dir = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis"
    
    # 查找最新的 p5 文件
    excel_path = find_latest_p5_file(stock_analysis_dir)
    
    # 执行转换
    output_path = convert_excel_to_json(excel_path, stock_analysis_dir)
    
    print(f"\n输出文件: {output_path}")


if __name__ == "__main__":
    main()
