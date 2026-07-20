import yt_dlp
opts = {
    'quiet': True,
    'cookiefile': r'D:\workspace\ytlocal\cookies.txt',
    'remote_components': ['ejs:github'],
    'js_runtimes': {'node': {}},
    'simulate': True,
    'skip_download': True,
}
with yt_dlp.YoutubeDL(opts) as ydl:
    try:
        info = ydl.extract_info('https://youtu.be/ovT5JdEyOGg', download=False)
        # 即使没 formats 也会拿到 partial info
        print('TITLE:', info.get('title'))
        print('AVAILABILITY:', info.get('availability'))
        print('AGE_LIMIT:', info.get('age_limit'))
        print('DURATION:', info.get('duration'))
        print('UPLOADER:', info.get('uploader'))
        print('CHANNEL_ID:', info.get('channel_id'))
        print('ERRORS:', info.get('errors'))
        print('PLAYABILITY_STATUS:', info.get('playability_status'))
        fmts = info.get('formats') or []
        print(f'FORMATS: {len(fmts)}')
    except Exception as e:
        print('EXTRACT FAIL:', str(e)[:300])