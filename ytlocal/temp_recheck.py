import yt_dlp
urls = [
    ('worked 720p', 'https://youtu.be/Lem3ILH4sKE'),
    ('worked 360p', 'https://www.youtube.com/watch?v=jNQXAC9IVRw'),
    ('failing now', 'https://youtu.be/ovT5JdEyOGg'),
]
for label, url in urls:
    print(f'\n=== {label}: {url} ===')
    opts = {
        'quiet': True,
        'cookiefile': r'D:\workspace\ytlocal\cookies.txt',
        'remote_components': ['ejs:github'],
        'js_runtimes': {'node': {}},
        'simulate': True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f'  TITLE: {info.get("title")}')
            print(f'  AVAILABILITY: {info.get("availability")}')
            print(f'  FORMATS: {len(info.get("formats", []))}')
    except Exception as e:
        msg = str(e).split('\n')[0][:150]
        print(f'  FAIL: {msg}')