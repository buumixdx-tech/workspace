import pandas as pd
import json
import os

excel_path = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis\result_p5_20260309085921.xlsx"
p5_dir = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis\p5"
output_html = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis\stock_hotspots_report.html"

# Read excel
try:
    df = pd.read_excel(excel_path)
    df = df.fillna("")
except Exception as e:
    print(f"读取Excel失败: {e}")
    exit(1)

columns = df.columns.tolist()

stock_data = []
for index, row in df.iterrows():
    # Find code
    code_col = [c for c in columns if "代码" in str(c)]
    if code_col:
        code = str(row.get(code_col[0], ""))
    else:
        code = str(row.iloc[0])

    md_filename = code.replace(".", "") + ".md"
    md_path = os.path.join(p5_dir, md_filename)
    
    md_content = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()
    else:
        md_content = f"未找到对应研究报告: {md_filename}"
        
    row_dict = {col: str(row.get(col, "")) for col in columns}
    row_dict["_markdown_content"] = md_content
    
    stock_data.append(row_dict)

html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>股票热点分析整合报告</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            display: flex;
            height: 100vh;
            overflow: hidden;
            background-color: #f5f7fa;
        }}
        .left-pane {{
            width: 50%;
            height: 100%;
            border-right: 2px solid #ccc;
            overflow-y: auto;
            background-color: #ffffff;
        }}
        .right-pane {{
            width: 50%;
            height: 100%;
            overflow-y: auto;
            padding: 20px;
            box-sizing: border-box;
            background-color: #ffffff;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 8px 12px;
            border-bottom: 1px solid #ddd;
            text-align: left;
            font-size: 14px;
        }}
        th {{
            background-color: #f0f2f5;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        tr:hover {{
            background-color: #f1f8ff;
            cursor: pointer;
        }}
        .selected-row {{
            background-color: #d1e8ff !important;
        }}
        .markdown-body {{
            font-size: 15px;
            line-height: 1.6;
            color: #333;
        }}
        .markdown-body h1, .markdown-body h2, .markdown-body h3 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
            margin-top: 1.5em;
        }}
        img {{
            max-width: 100%;
        }}
        .placeholder {{
            color: #999;
            text-align: center;
            margin-top: 50px;
        }}
    </style>
</head>
<body>

<div class="left-pane">
    <table id="stockTable">
        <thead>
            <tr>
                {table_headers}
            </tr>
        </thead>
        <tbody id="stockTbody">
            <!-- 动态填充 -->
        </tbody>
    </table>
</div>

<div class="right-pane">
    <div id="mdContainer" class="markdown-body">
        <div class="placeholder">请在左侧点击股票查看对应的研究报告</div>
    </div>
</div>

<script>
    const columns = {columns_json};
    const stockData = {stock_data_json};

    const tbody = document.getElementById('stockTbody');
    const mdContainer = document.getElementById('mdContainer');
    
    // 初始化列表
    stockData.forEach((stock, index) => {{
        const tr = document.createElement('tr');
        tr.id = 'row-' + index;
        
        columns.forEach(col => {{
            const td = document.createElement('td');
            td.textContent = stock[col];
            tr.appendChild(td);
        }});
        
        tr.addEventListener('click', () => {{
            // 移除其他行的选中状态
            document.querySelectorAll('#stockTbody tr').forEach(r => r.classList.remove('selected-row'));
            tr.classList.add('selected-row');
            
            // 渲染markdown
            mdContainer.innerHTML = marked.parse(stock._markdown_content);
        }});
        
        tbody.appendChild(tr);
    }});
</script>
</body>
</html>
"""

header_html = "".join([f"<th>{col}</th>" for col in columns])

final_html = html_template.format(
    table_headers=header_html,
    columns_json=json.dumps(columns, ensure_ascii=False),
    stock_data_json=json.dumps(stock_data, ensure_ascii=False)
)

with open(output_html, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"HTML报告已生成: {output_html}")
