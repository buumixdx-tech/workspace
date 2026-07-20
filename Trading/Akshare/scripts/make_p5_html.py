import json
import os
import re
from pypinyin import pinyin, Style

# Paths
base_dir = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis"
json_path = os.path.join(base_dir, "result_p5_20260309085921.json")
hotspots_path = r"d:\WorkSpace\Trading\Akshare\docs\hotspots2.txt"
p5_dir = os.path.join(base_dir, "p5")
output_html = os.path.join(base_dir, "stock_dashboard.html")

def normalize_code(code):
    return code.replace(".", "")

def clean_label(label):
    label = re.sub(r'^\d+([\.、]\d+)*[、\.]*', '', label)
    label = label.strip('。，, ')
    return label.strip()

def get_initial(text):
    if not text: return "#"
    first_char = text[0]
    # Check if first char is English
    if 'a' <= first_char.lower() <= 'z':
        return first_char.upper()
    # Otherwise assume Chinese and get pinyin initial
    result = pinyin(first_char, style=Style.FIRST_LETTER)
    if result and result[0] and result[0][0]:
        initial = result[0][0][0].upper()
        if 'A' <= initial <= 'Z':
            return initial
    return "#"

def parse_hotspots(path):
    hierarchy = {}
    last_l1 = None
    last_l2 = None
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            l3_match = re.match(r'^(\d+)\.(\d+)\.(\d+)', line)
            l2_match = re.match(r'^(\d+)\.(\d+)', line)
            l1_match = re.match(r'^(\d+)[、\.]', line)
            
            label = clean_label(line)
            
            if l3_match:
                if last_l1 and last_l2:
                    if label not in hierarchy[last_l1][last_l2]:
                        if "、" in label and last_l1 == "AI应用":
                            for sub in label.split("、"):
                                hierarchy[last_l1][last_l2].append(sub.strip())
                        else:
                            hierarchy[last_l1][last_l2].append(label)
            elif l2_match:
                if last_l1:
                    last_l2 = label
                    if last_l2 not in hierarchy[last_l1]:
                        hierarchy[last_l1][last_l2] = []
            elif l1_match:
                if "（" in label:
                    label = label.split("（")[0].strip()
                last_l1 = label
                last_l2 = None
                if last_l1 not in hierarchy:
                    hierarchy[last_l1] = {}
                    
    return hierarchy

def main():
    if not os.path.exists(json_path):
        print(f"Error: JSON file not found at {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    stocks = data.get("stocks", [])
    
    # Process stocks and attach MD content
    all_concepts_map = {} # { concept_name: initial }
    for stock in stocks:
        normalized_code = normalize_code(stock['code'])
        md_path = os.path.join(p5_dir, f"{normalized_code}.md")
        stock['md_content'] = ""
        if os.path.exists(md_path):
            with open(md_path, 'r', encoding='utf-8') as f:
                stock['md_content'] = f.read()
        
        for cb in stock.get('concept_boards', []):
            name = cb['concept_name']
            if name not in all_concepts_map:
                all_concepts_map[name] = get_initial(name)

    # Group concepts by initial
    grouped_concepts = {}
    for name, initial in all_concepts_map.items():
        if initial not in grouped_concepts:
            grouped_concepts[initial] = []
        grouped_concepts[initial].append(name)

    # Sort groups and items within groups
    sorted_initials = sorted(grouped_concepts.keys())
    final_concepts_list = [] # List of { "letter": "A", "items": [...] }
    for letter in sorted_initials:
        final_concepts_list.append({
            "letter": letter,
            "items": sorted(grouped_concepts[letter])
        })

    # Parse predefined Hotspots Hierarchy
    hotspot_hierarchy = parse_hotspots(hotspots_path)

    # Final data object
    final_data = {
        "stocks": stocks,
        "predefined_hotspots": hotspot_hierarchy,
        "grouped_concepts": final_concepts_list
    }

    # Generate HTML content
    html_template = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投研数据中心 - 概念字母版</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --primary-light: #dbeafe;
            --secondary: #64748b;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --border: #e2e8f0;
            --sidebar-width: 380px;
        }

        * { box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; display: flex; height: 100vh; overflow: hidden; }

        #sidebar { width: var(--sidebar-width); background: var(--card-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; z-index: 50; }
        .sidebar-header { padding: 24px; border-bottom: 1px solid var(--border); text-align: center; }
        .sidebar-header h1 { font-family: 'Outfit', sans-serif; font-size: 1.5rem; margin: 0; background: linear-gradient(to right, #2563eb, #7c3aed); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        
        .sidebar-content { flex: 1; overflow-y: auto; padding: 20px; }
        .filter-group { background: #f1f5f9; padding: 15px; border-radius: 12px; margin-bottom: 20px; }
        .filter-label { font-weight: 600; font-size: 0.8rem; color: var(--secondary); margin-bottom: 10px; display: block; text-transform: uppercase; }
        
        select { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 10px; outline: none; transition: 0.2s; background: white; color: #000; font-weight: 500; }
        select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
        
        optgroup { font-style: normal; font-weight: bold; color: var(--primary); }
        option { color: #000; }

        .stats { font-size: 0.85rem; color: var(--secondary); padding-bottom: 15px; border-bottom: 1px solid var(--border); margin-bottom: 15px; }
        
        #stock-list { display: flex; flex-direction: column; gap: 8px; }
        .stock-card { padding: 12px 16px; border-radius: 10px; cursor: pointer; border: 1px solid var(--border); background: white; transition: 0.2s; }
        .stock-card:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .stock-card.active { background: var(--primary-light); border-color: var(--primary); }
        .stock-card .name { font-weight: 600; }
        .stock-card .meta { font-size: 0.75rem; color: var(--secondary); margin-top: 4px; }

        #content { flex: 1; overflow-y: auto; background: white; }
        .view-wrapper { max-width: 900px; margin: 0 auto; padding: 60px 40px; }
        .placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: var(--secondary); opacity: 0.5; }

        .tag { display: inline-flex; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; margin: 0 6px 6px 0; border: 1px solid transparent; }
        .tag-hooked { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
        .tag-potential { background: #fef9c3; color: #854d0e; border-color: #fef08a; }
        .tag-concept { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }

        .markdown-body { line-height: 1.8; color: #334155; }
        .markdown-body h1 { border-bottom: 1px solid var(--border); padding-bottom: 0.3em; margin-top: 1.5em; }
        .markdown-body h2 { border-bottom: 1px solid #f1f5f9; padding-bottom: 0.3em; margin-top: 1.5em; }
    </style>
</head>
<body>

<div id="sidebar">
    <div class="sidebar-header"><h1>小票筛选</h1></div>
    <div class="sidebar-content">
        <div class="filter-group">
            <span class="filter-label">🔍 概念板块 (A-Z 排序)</span>
            <select id="concept-filter">
                <option value="">-- 请选择板块 --</option>
            </select>
        </div>

        <div class="filter-group">
            <span class="filter-label">🔥 热门板块</span>
            <select id="h-l1"><option value="">全部一级</option></select>
            <select id="h-l2" style="display:none;"><option value="">全部二级</option></select>
            <select id="h-l3" style="display:none;"><option value="">全部三级</option></select>
        </div>

        <div class="stats" id="stats-info">加载中...</div>
        <div id="stock-list"></div>
    </div>
</div>

<div id="content">
    <div id="detail-view" class="placeholder">请选择左侧股票查看深度报告</div>
</div>

<script>
    const data = %DATA_JSON%;
    
    const ui = {
        concept: document.getElementById('concept-filter'),
        l1: document.getElementById('h-l1'),
        l2: document.getElementById('h-l2'),
        l3: document.getElementById('h-l3'),
        list: document.getElementById('stock-list'),
        stats: document.getElementById('stats-info'),
        detail: document.getElementById('detail-view')
    };

    // Helper: format hotspot string
    function formatHotspot(h) {
        const parts = [];
        if (h.level1) parts.push(h.level1);
        if (h.level2) parts.push(h.level2);
        if (h.level3) parts.push(h.level3);
        return parts.join(' / ');
    }

    // Init Filters with Groups
    data.grouped_concepts.forEach(group => {
        const og = document.createElement('optgroup');
        og.label = `字母 ${group.letter}`;
        group.items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = opt.textContent = item;
            og.appendChild(opt);
        });
        ui.concept.appendChild(og);
    });

    Object.keys(data.predefined_hotspots).sort().forEach(l1 => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = l1;
        ui.l1.appendChild(opt);
    });

    ui.l1.onchange = () => {
        const val = ui.l1.value;
        ui.l2.innerHTML = '<option value="">全部二级</option>';
        ui.l3.innerHTML = '<option value="">全部三级</option>';
        if (val && data.predefined_hotspots[val]) {
            ui.l2.style.display = 'block';
            Object.keys(data.predefined_hotspots[val]).sort().forEach(l2 => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = l2;
                ui.l2.appendChild(opt);
            });
        } else {
            ui.l2.style.display = 'none';
            ui.l3.style.display = 'none';
        }
        filter();
    };

    ui.l2.onchange = () => {
        const l1 = ui.l1.value;
        const val = ui.l2.value;
        ui.l3.innerHTML = '<option value="">全部三级</option>';
        if (l1 && val && data.predefined_hotspots[l1][val] && data.predefined_hotspots[l1][val].length) {
            ui.l3.style.display = 'block';
            data.predefined_hotspots[l1][val].forEach(l3 => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = l3;
                ui.l3.appendChild(opt);
            });
        } else {
            ui.l3.style.display = 'none';
        }
        filter();
    };

    ui.l3.onchange = filter;
    ui.concept.onchange = filter;

    function filter() {
        const cVal = ui.concept.value;
        const l1 = ui.l1.value;
        const l2 = ui.l2.value;
        const l3 = ui.l3.value;

        const filtered = data.stocks.filter(s => {
            if (cVal && !s.concept_boards.some(cb => cb.concept_name === cVal)) return false;
            if (l1) {
                const matches = [...s.hooked_hotspots, ...s.potential_hotspots].some(h => {
                    if (h.level1 !== l1) return false;
                    if (l2 && h.level2 !== l2) return false;
                    if (l3 && h.level3 !== l3) return false;
                    return true;
                });
                if (!matches) return false;
            }
            return true;
        });
        renderList(filtered);
    }

    function renderList(stocks) {
        ui.stats.textContent = `共找到 ${stocks.length} 支股票`;
        ui.list.innerHTML = '';
        stocks.forEach(s => {
            const div = document.createElement('div');
            div.className = 'stock-card';
            div.innerHTML = `<div class="name">${s.name}</div><div class="meta">${s.code} • ${s.market_cap_adjusted}亿</div>`;
            div.onclick = () => {
                document.querySelectorAll('.stock-card').forEach(c => c.classList.remove('active'));
                div.classList.add('active');
                showDetail(s);
            };
            ui.list.appendChild(div);
        });
    }

    function showDetail(s) {
        ui.detail.innerHTML = `
            <div class="view-wrapper">
                <h1>${s.name} <small style="font-weight:300; font-size:1.2rem; color:var(--secondary)">${s.code}</small></h1>
                <div style="margin-bottom:32px; background:#f8fafc; padding:20px; border-radius:12px; border:1px solid var(--border)">
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
                        <div><strong style="color:var(--secondary); font-size:0.8rem; text-transform:uppercase;">自由市值</strong><br>${s.market_cap_adjusted} 亿元</div>
                        <div><strong style="color:var(--secondary); font-size:0.8rem; text-transform:uppercase;">查询代码</strong><br>${s.code}</div>
                    </div>
                    <div style="margin-top:16px;"><strong style="color:var(--secondary); font-size:0.8rem; text-transform:uppercase;">业务简介</strong><br>${s.business_description}</div>
                </div>
                
                <div style="margin-bottom:24px">
                    <div style="font-weight:600; margin-bottom:10px; font-size:0.9rem;">🎯 直接挂钩</div>
                    ${s.hooked_hotspots.map(h => `<span class="tag tag-hooked">${formatHotspot(h)}</span>`).join('') || '<span style="color:#94a3b8; font-size:0.8rem">无</span>'}
                </div>
                <div style="margin-bottom:24px">
                    <div style="font-weight:600; margin-bottom:10px; font-size:0.9rem;">🔎 潜在关联</div>
                    ${s.potential_hotspots.map(h => `<span class="tag tag-potential">${formatHotspot(h)}</span>`).join('') || '<span style="color:#94a3b8; font-size:0.8rem">无</span>'}
                </div>
                <div style="margin-bottom:24px">
                    <div style="font-weight:600; margin-bottom:10px; font-size:0.9rem;">📋 所属概念</div>
                    ${s.concept_boards.map(cb => `<span class="tag tag-concept">${cb.concept_name}</span>`).join('') || '<span style="color:#94a3b8; font-size:0.8rem">无</span>'}
                </div>
                <hr style="border:0; border-top:1px solid var(--border); margin:40px 0;">
                <div class="markdown-body">${s.md_content ? marked.parse(s.md_content) : '暂无深度投研报告。'}</div>
            </div>
        `;
        ui.detail.className = '';
        ui.detail.scrollTop = 0;
    }

    renderList(data.stocks);
</script>
</body>
</html>
    """

    data_json_str = json.dumps(final_data, ensure_ascii=False)
    final_html = html_template.replace("%DATA_JSON%", data_json_str)
    
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(final_html)
    
    print(f"Successfully generated {output_html}")

if __name__ == "__main__":
    main()
