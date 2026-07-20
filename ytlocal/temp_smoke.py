import urllib.request
for p in ['/api/health', '/', '/download', '/history', '/w/1', '/static/app.css']:
    try:
        r = urllib.request.urlopen('http://127.0.0.1:7890'+p, timeout=5)
        b = r.read()
        ct = r.headers.get('Content-Type')
        print(f'{r.status} {p:25} {len(b):>6}B  ct={ct}')
    except Exception as e: print(f'ERR {p}: {e}')