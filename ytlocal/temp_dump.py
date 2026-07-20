import urllib.request, re
r = urllib.request.urlopen('http://127.0.0.1:7890/download').read().decode()
# 找失败任务的 HTML
for m in re.finditer(r'<div class="task"[^>]*>.*?</div>\s*</div>', r, re.S):
    s = m.group(0)
    if 'failed' in s.lower() or 'DownloadError' in s:
        print(s[:1000])
        print('---')