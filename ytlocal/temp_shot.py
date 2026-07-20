import subprocess
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
shots = [
    ('home', 'http://127.0.0.1:7890/'),
    ('download', 'http://127.0.0.1:7890/download'),
    ('history', 'http://127.0.0.1:7890/history'),
    ('watch', 'http://127.0.0.1:7890/w/1'),
]
for name, url in shots:
    out = rf'D:\workspace\ytlocal\screenshot_{name}.png'
    subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--window-size=390,844', f'--screenshot={out}', url],
                   timeout=30, capture_output=True)
    print(name, '->', out)
import os
for f in os.listdir(r'D:\workspace\ytlocal'):
    if f.startswith('screenshot_'): print(' ', f, os.path.getsize(rf'D:\workspace\ytlocal\{f}'), 'B')