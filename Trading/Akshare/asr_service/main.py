import os
import sys
from datetime import datetime
from core.audio import convert_to_wav
from core.transcriber import Transcriber  # FunASR/SenseVoice
from core.volcengine_asr import VolcEngineTranscriber  # 火山引擎
from core.summarizer import Summarizer

# ⚡ ASR Provider 选择器
# 可选："funasr" (SenseVoiceSmall) 或 "volcengine" (火山引擎)
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "funasr").lower()

def get_transcriber(provider):
    """根据环境变量选择 ASR provider"""
    if provider == "volcengine":
        # 火山引擎需要 AK/SK
        ak = os.getenv("VOLCENGINE_AK")
        sk = os.getenv("VOLCENGINE_SK")
        if not ak or not sk:
            print("⚠️ 火山引擎需要设置 VOLCENGINE_AK 和 VOLCENGINE_SK 环境变量")
            print("使用默认的 FunASR/SenseVoice...")
            return Transcriber(device="cpu")
        return VolcEngineTranscriber(ak, sk)
    else:
        # 默认使用 FunASR SenseVoiceSmall
        return Transcriber(device="cpu")

def main():
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    temp_dir = os.path.join(base_dir, "temp")
    
    # Print current config
    print(f"🎯 ASR Provider: {ASR_PROVIDER.upper()}")
    if ASR_PROVIDER == "volcengine":
        print(f"   🌋 VolcEngine AK: {os.getenv('VOLCENGINE_AK', '****')[:8]}...")
    
    # Init modules
    transcriber = get_transcriber(ASR_PROVIDER)
    summarizer = Summarizer(model="qwen3:1.7b") # Adjust model name if needed
    
    # 1. Scan for mp3
    files = [f for f in os.listdir(input_dir) if f.endswith(".mp3")]
    if not files:
        print(f"No MP3 files found in {input_dir}")
        return

    for filename in files:
        print(f"\nProcessing: {filename}")
        input_path = os.path.join(input_dir, filename)
        name_no_ext = os.path.splitext(filename)[0]
        temp_wav = os.path.join(temp_dir, f"{name_no_ext}.wav")
        output_md = os.path.join(output_dir, f"{name_no_ext}_summary.md")
        
        # 2. Convert to WAV
        print("Step 1: Converting to WAV...")
        if not convert_to_wav(input_path, temp_wav):
            print(f"Failed to convert {filename}")
            continue
            
        # 3. Transcribe
        print("Step 2: Transcribing (STT)...")
        raw_text = transcriber.transcribe(temp_wav)
        if not raw_text:
            print(f"No text recognized for {filename}")
            continue
            
        # 4. Summarize
        print("Step 3: Summarizing (LLM)...")
        chunks = summarizer.chunk_text(raw_text)
        cleaned_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"  Cleaning chunk {i+1}/{len(chunks)}...")
            cleaned = summarizer.summarize_chunk(chunk)
            cleaned_chunks.append(cleaned)
            
        combined_cleaned = "\n".join(cleaned_chunks)
        final_report = summarizer.final_summary(combined_cleaned)
        
        # 5. Save
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(f"# 语音摘要报告: {name_no_ext}\n\n")
            f.write(f"**处理日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## 最终摘要\n\n")
            f.write(final_report)
            f.write("\n\n---\n## 原始整理文本 (RAW)\n\n")
            f.write(combined_cleaned)
            
        print(f"✅ Finished! Report saved to: {output_md}")
        
        # Cleanup temp wav
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

if __name__ == "__main__":
    # Ensure directories exist (caller responsibility normally, but check here)
    main()
