import os
import subprocess
from funasr import AutoModel

def test():
    input_mp3 = r"d:\WorkSpace\Trading\Akshare\asr_service\input\地缘叙事再起，油金如何看20260313.mp3"
    temp_wav = r"d:\WorkSpace\Trading\Akshare\asr_service\temp\test_10s.wav"
    
    # Extract 10s
    cmd = ['ffmpeg', '-y', '-i', input_mp3, '-t', '10', '-ar', '16000', '-ac', '1', temp_wav]
    subprocess.run(cmd, check=True)
    
    print("Loading model...")
    model = AutoModel(model="iic/SenseVoiceSmall", device="cpu")
    
    print("Starting generation...")
    try:
        res = model.generate(input=temp_wav, language="zh", use_itn=True)
        print("Result:", res)
    except Exception as e:
        print("Error during generate:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
