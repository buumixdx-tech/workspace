import yt_dlp, sys
url = 'https://youtu.be/ovT5JdEyOGg'
for client in ['mweb', 'ios', 'tv_embedded', 'tv', 'web_safari', 'android_vr']:
    print(f'--- client={client} ---')
    try:
        opts = {
            'quiet': True,
            'cookiefile': r'D:\workspace\ytlocal\cookies.txt',
            'remote_components': ['ejs:github'],
            'js_runtimes': {'node': {}},
            'simulate': True,
            'extractor_args': {'youtube': {'player_client': [client]}},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f'  TITLE: {info.get("title")}')
            print(f'  FORMATS: {len(info.get("formats", []))}')
    except Exception as e:
        msg = str(e)[:200]
        print(f'  FAIL: {msg}')