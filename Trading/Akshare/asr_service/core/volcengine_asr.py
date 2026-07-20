import subprocess
import os

def convert_to_wav(input_path, output_path):
    """
    Convert any audio file to 16kHz mono WAV for ASR using FFmpeg.
    适配火山引擎要求：16000Hz, mono, wav
    """
    if os.path.exists(output_path):
        os.remove(output_path)
        
    command = [
        'ffmpeg',
        '-i', input_path,
        '-ar', '16000',      # 采样率 16kHz (火山引擎推荐)
        '-ac', '1',          # 单声道
        '-f', 'wav',         # 明确指定格式
        '-y',               # Overwrite output
        output_path
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("Error: FFmpeg not found in PATH.")
        return False


def transcribe_with_volcengine(wav_path, access_key_id, access_key_secret, region="cn-beijing"):
    """
    使用火山引擎语音识别服务转录音频
    
    Args:
        wav_path: WAV 文件路径
        access_key_id: 火山引擎 AK
        access_key_secret: 火山引擎 SK
        region: 区域，默认 cn-beijing
    
    Returns:
        str: 转录文本
    """
    import requests
    from datetime import datetime
    import hashlib
    import base64
    
    # 读取 WAV 文件
    with open(wav_path, 'rb') as f:
        audio_data = f.read()
    
    # 构造请求参数
    endpoint = "open.volcengineapi.com"
    service = "ivp"
    action = "RealTimeTranscription"
    version = "2022-06-30"
    
    # 生成时间戳
    timestamp = int(datetime.utcnow().timestamp())
    
    # 构造签名
    canonical_request = f"POST\n/\n{action}\n{version}"
    string_to_sign = f"POST\n*/*\n{timestamp}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    signature = base64.b64encode(
        hashlib.sha256((string_to_sign + access_key_secret).encode()).digest()
    ).decode()
    
    headers = {
        "Host": endpoint,
        "X-Date": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "X-Content-Sha256": hashlib.sha256(audio_data).hexdigest(),
        "Authorization": f"TLS-HMAC-SHA256 Credential={access_key_id}/{timestamp}/ivp/request, SignedHeaders=host;x-content-sha256;x-date, Signature={signature}"
    }
    
    payload = {
        "SubService": "ASR",
        "ModelConfig": {
            "Lang": "zh-CN",
            "SampleRate": 16000,
            "ChannelNum": 1
        },
        "EnablePunctuationPrediction": True,
        "EnableNumberNorm": True,
        "EnableSpeechDetection": False
    }
    
    url = f"https://{endpoint}/{service}/{action}?{action}={version}"
    
    try:
        response = requests.post(url, headers=headers, json=payload, data=audio_data)
        result = response.json()
        
        if response.status_code == 200 and "ResponseMetadata" in result:
            # 火山引擎实时转写返回的是流式结果，这里简化处理
            # 实际使用时可能需要配置 WebSocket 连接
            return result.get("Result", {}).get("Text", "")
        else:
            print(f"VolcEngine error: {result}")
            return ""
            
    except Exception as e:
        print(f"VolcEngine transcription failed: {e}")
        return ""


class VolcEngineTranscriber:
    """
    火山引擎语音识别封装类
    """
    
    def __init__(self, access_key_id, access_key_secret, device="auto"):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.device = device
        print(f"Initializing VolcEngine ASR with AK: {access_key_id[:8]}...")
    
    def transcribe(self, wav_path):
        """
        转录单个 WAV 文件
        
        Args:
            wav_path: WAV 文件路径
        
        Returns:
            str: 转录文本
        """
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"WAV file not found: {wav_path}")
        
        print("Converting to 16kHz WAV...")
        temp_wav = wav_path.replace('.mp3', '.wav').replace('.m4a', '.wav')
        
        # 如果输入不是 wav，先转换
        if not wav_path.endswith('.wav'):
            if not convert_to_wav(wav_path, temp_wav):
                print(f"Failed to convert {wav_path}")
                return ""
            wav_path = temp_wav
        
        print("Transcribing with VolcEngine...")
        text = transcribe_with_volcengine(
            wav_path, 
            self.access_key_id, 
            self.access_key_secret
        )
        
        return text
    
    def transcribe_long_audio(self, mp3_path, timeout_per_min=30):
        """
        处理长音频（自动分段）
        
        Args:
            mp3_path: MP3 文件路径
            timeout_per_min: 每分钟音频的处理超时时间（秒）
        
        Returns:
            str: 完整转录文本
        """
        # 获取时长
        try:
            cmd = ['ffprobe', '-i', mp3_path, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0']
            duration = float(subprocess.check_output(cmd).decode().strip())
        except:
            duration = 0
        
        if duration < 300:  # < 5 分钟
            return self.transcribe(mp3_path)
        
        print(f"Long audio ({duration:.1f}s), processing in chunks...")
        chunk_size = 300  # 5 分钟
        full_text = []
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            for start in range(0, int(duration), chunk_size):
                chunk_wav = os.path.join(tmpdir, f"chunk_{start}.wav")
                
                # 切片
                cmd = [
                    'ffmpeg', '-y', '-ss', str(start), '-t', str(chunk_size),
                    '-i', mp3_path, '-ar', '16000', '-ac', '1', chunk_wav
                ]
                subprocess.run(cmd, capture_output=True)
                
                if os.path.exists(chunk_wav):
                    text = self.transcribe(chunk_wav)
                    full_text.append(text)
        
        return "".join(full_text)
