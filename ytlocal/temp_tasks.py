import urllib.request, json
r = urllib.request.urlopen('http://127.0.0.1:7890/api/tasks').read().decode()
d = json.loads(r)
print('=== 最近任务 ===')
for t in d['items'][:8]:
    err = '  err: ' + t['error'][:140] if t.get('error') else ''
    print(f"  #{t['id']} {t['status']:9s} {t['quality']:5s} {t['progress_pct']:>3}%  url={t['url'][:60]}{err}")
print()
r = urllib.request.urlopen('http://127.0.0.1:7890/api/videos').read().decode()
d = json.loads(r)
n = len(d['items'])
print(f'=== 库 ({n} 条) ===')
for v in d['items']:
    mb = v.get('size_bytes', 0) / 1048576
    print(f"  #{v['id']} {v['source']:12s} {v['title'][:55]}  size={mb:.1f}MB")