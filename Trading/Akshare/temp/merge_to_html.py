import os
import mammoth
import markdown
import json

def generate_report():
    report_dir = r"d:\WorkSpace\Trading\Akshare\data\strategy_result\reports\603280"
    docx_path = os.path.join(report_dir, "南方路机核电关联深度分析.docx")
    md_path = os.path.join(report_dir, "核电信息.md")
    output_html = os.path.join(report_dir, "核电关联分析汇总.html")

    # Read DOCX
    with open(docx_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        docx_html = result.value
        messages = result.messages

    # Read MD
    with open(md_path, "r", encoding="utf-8") as md_file:
        md_text = md_file.read()
        md_html = markdown.markdown(md_text, extensions=['extra', 'codehilite', 'toc'])

    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>核电关联分析汇总 - 南方路机 (603280)</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary-gradient: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            --secondary-gradient: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            --accent-color: #60a5fa;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --bg-dark: #020617;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            line-height: 1.6;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(30, 58, 138, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 80% 80%, rgba(59, 130, 246, 0.1) 0%, transparent 40%);
        }}

        header {{
            padding: 3rem 1rem;
            text-align: center;
            background: var(--secondary-gradient);
            position: relative;
            overflow: hidden;
            border-bottom: 1px solid var(--glass-border);
        }}

        header h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(to right, #fff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        header p {{
            color: var(--text-muted);
            font-size: 1.1rem;
            letter-spacing: 1px;
        }}

        .container {{
            max-width: 1000px;
            margin: -2rem auto 4rem;
            position: relative;
            z-index: 10;
            padding: 0 1rem;
        }}

        .tabs-header {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
            padding: 0.5rem;
            border-radius: 12px;
            border: 1px solid var(--glass-border);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }}

        .tab-btn {{
            padding: 0.75rem 2rem;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }}

        .tab-btn:hover {{
            color: #fff;
            background: rgba(255,255,255,0.05);
        }}

        .tab-btn.active {{
            color: #fff;
            background: var(--primary-gradient);
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }}

        .tab-content {{
            display: none;
            animation: fadeIn 0.5s ease-out;
            background: var(--glass-bg);
            backdrop-filter: blur(10px);
            padding: 3rem;
            border-radius: 20px;
            border: 1px solid var(--glass-border);
            box-shadow: 0 20px 50px rgba(0,0,0,0.4);
        }}

        .tab-content.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Content Styling */
        .content-body {{
            font-size: 1.1rem;
            color: #cbd5e1;
        }}

        .content-body h1, .content-body h2, .content-body h3 {{
            font-family: 'Outfit', sans-serif;
            color: #fff;
            margin: 2rem 0 1rem;
        }}

        .content-body h3 {{
            border-left: 4px solid var(--accent-color);
            padding-left: 1rem;
            margin-top: 2.5rem;
        }}

        .content-body p {{
            margin-bottom: 1.5rem;
        }}

        .content-body ul, .content-body ol {{
            margin-left: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .content-body li {{
            margin-bottom: 0.75rem;
        }}

        .content-body strong {{
            color: var(--accent-color);
        }}

        .content-body blockquote {{
            background: rgba(59, 130, 246, 0.1);
            border-left: 4px solid var(--accent-color);
            padding: 1rem 1.5rem;
            margin: 2rem 0;
            font-style: italic;
        }}

        .content-body img {{
            max-width: 100%;
            height: auto;
            border-radius: 12px;
            margin: 2rem 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}

        hr {{
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, var(--glass-border), transparent);
            margin: 3rem 0;
        }}

        footer {{
            text-align: center;
            padding: 4rem 1rem;
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        /* Media Queries */
        @media (max-width: 768px) {{
            header h1 {{ font-size: 1.8rem; }}
            .tab-content {{ padding: 1.5rem; }}
            .tab-btn {{ padding: 0.6rem 1rem; font-size: 0.9rem; }}
        }}
    </style>
</head>
<body>

    <header>
        <h1>核电关联分析汇总</h1>
        <p>南方路机 (603280) · 行业深度与个股关联</p>
    </header>

    <div class="container">
        <div class="tabs-header">
            <button class="tab-btn active" onclick="openTab(event, 'tab-docx')">南方路机深度分析</button>
            <button class="tab-btn" onclick="openTab(event, 'tab-md')">核电行业动态</button>
        </div>

        <div id="tab-docx" class="tab-content active">
            <div class="content-body">
                {docx_html}
            </div>
        </div>

        <div id="tab-md" class="tab-content">
            <div class="content-body">
                {md_html}
            </div>
        </div>
    </div>

    <footer>
        <p>&copy; 2026 证券分析系统 · 生成时间: {os.path.basename(output_html).split('.')[0]}</p>
    </footer>

    <script>
        function openTab(evt, tabName) {{
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {{
                tabcontent[i].style.display = "none";
                tabcontent[i].classList.remove("active");
            }}
            tablinks = document.getElementsByClassName("tab-btn");
            for (i = 0; i < tablinks.length; i++) {{
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }}
            document.getElementById(tabName).style.display = "block";
            document.getElementById(tabName).classList.add("active");
            evt.currentTarget.className += " active";
        }}
    </script>
</body>
</html>
    """

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_template)
    
    print(f"Successfully generated combined HTML: {output_html}")

if __name__ == "__main__":
    generate_report()
