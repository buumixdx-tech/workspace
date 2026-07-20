#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成股票热点分析查询HTML页面
- 模糊搜索概念板块
- 分级选择热点
- 显示股票详细信息（含MD文档）
"""

import os
import json
import glob
import re
from datetime import datetime
from pathlib import Path


def read_all_md_files(p5_dir: str) -> dict:
    """读取所有MD文件"""
    md_contents = {}
    md_files = glob.glob(os.path.join(p5_dir, "*.md"))
    
    for md_file in md_files:
        filename = os.path.basename(md_file)
        # 转换为JSON中使用的股票代码格式: SH603709 -> SH.603709
        code = filename.replace('.md', '')
        if code.startswith('SH') or code.startswith('SZ'):
            # 格式: SH600000 -> SH.600000
            code = code[:2] + '.' + code[2:]
        
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                md_contents[code] = f.read()
        except Exception as e:
            print(f"读取失败 {md_file}: {e}")
    
    return md_contents


def build_hotspot_tree():
    """从hotspots2.txt构建热点树"""
    hotspots_file = r"d:\WorkSpace\Trading\Akshare\docs\hotspots2.txt"
    
    if not os.path.exists(hotspots_file):
        return {}
    
    with open(hotspots_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = {}
    current_level1 = None
    current_level2 = None
    
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 判断层级
        if re.match(r'^[\d]+\.[\d]+\.[\d]+\.', line):
            # 三级: 1.1.1
            level3 = re.sub(r'^[\d]+\.[\d]+\.[\d]+\s+', '', line)
            if current_level1 and current_level2:
                if 'level3' not in tree[current_level1][current_level2]:
                    tree[current_level1][current_level2]['level3'] = []
                tree[current_level1][current_level2]['level3'].append(level3)
        
        elif re.match(r'^[\d]+\.[\d]+\.', line):
            # 二级: 1.1
            level2 = re.sub(r'^[\d]+\.[\d]+\s+', '', line)
            current_level2 = level2
            if current_level1 and current_level2:
                if current_level2 not in tree[current_level1]:
                    tree[current_level1][current_level2] = {'level3': []}
        
        elif re.match(r'^[\d]+\.', line):
            # 一级: 1
            level1 = re.sub(r'^[\d]+\.\s+', '', line)
            current_level1 = level1
            current_level2 = None
            if level1 not in tree:
                tree[level1] = {}
    
    return tree


def generate_html(json_path: str, p5_dir: str, output_path: str):
    """生成HTML文件"""
    
    # 读取JSON数据
    print(f"读取JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 读取MD文件
    print(f"读取MD文件: {p5_dir}")
    md_contents = read_all_md_files(p5_dir)
    print(f"读取了 {len(md_contents)} 个MD文件")
    
    # 构建热点树
    print("构建热点树...")
    hotspot_tree = build_hotspot_tree()
    
    # 转换为JavaScript数据
    json_data_js = json.dumps(data, ensure_ascii=False)
    md_contents_js = json.dumps(md_contents, ensure_ascii=False)
    hotspot_tree_js = json.dumps(hotspot_tree, ensure_ascii=False)
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票热点分析查询系统</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f7fa;
            min-height: 100vh;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            font-size: 24px;
            font-weight: 600;
        }}
        
        .header .subtitle {{
            opacity: 0.9;
            font-size: 14px;
            margin-top: 5px;
        }}
        
        .container {{
            display: flex;
            min-height: calc(100vh - 80px);
        }}
        
        .sidebar {{
            width: 400px;
            background: white;
            border-right: 1px solid #e8e8e8;
            padding: 20px;
            overflow-y: auto;
        }}
        
        .main {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }}
        
        .search-section {{
            margin-bottom: 20px;
        }}
        
        .search-section h3 {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        
        .search-input {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.2s;
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .search-results {{
            margin-top: 8px;
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 6px;
            display: none;
            background: white;
        }}
        
        .search-results.active {{
            display: block;
        }}
        
        .search-result-item {{
            padding: 8px 12px;
            cursor: pointer;
            border-bottom: 1px solid #f0f0f0;
            font-size: 13px;
        }}
        
        .search-result-item:hover {{
            background: #f5f7fa;
        }}
        
        .search-result-item:last-child {{
            border-bottom: none;
        }}
        
        .hotspot-selector {{
            margin-bottom: 20px;
        }}
        
        .hotspot-level {{
            margin-bottom: 10px;
        }}
        
        .hotspot-level label {{
            display: block;
            font-size: 12px;
            color: #888;
            margin-bottom: 5px;
        }}
        
        .hotspot-level select {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            background: white;
        }}
        
        .selected-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 15px;
        }}
        
        .tag {{
            display: inline-flex;
            align-items: center;
            padding: 5px 10px;
            background: #667eea;
            color: white;
            border-radius: 15px;
            font-size: 12px;
        }}
        
        .tag .remove {{
            margin-left: 5px;
            cursor: pointer;
            opacity: 0.8;
        }}
        
        .tag .remove:hover {{
            opacity: 1;
        }}
        
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
            width: 100%;
        }}
        
        .btn-primary:hover {{
            background: #5568d3;
        }}
        
        .btn-secondary {{
            background: #f0f0f0;
            color: #666;
            margin-top: 10px;
            width: 100%;
        }}
        
        .results-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .results-count {{
            color: #666;
            font-size: 14px;
        }}
        
        .stock-list {{
            display: grid;
            gap: 15px;
        }}
        
        .stock-card {{
           