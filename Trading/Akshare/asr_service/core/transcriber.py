from funasr import AutoModel
import os
import subprocess

class Transcriber:
    def __init__(self, model_name="iic/SenseVoiceSmall", device="cpu"):
        print(f"Loading ASR model: {model_name} on {device}...")
        self.model = AutoModel(
            model=model_name,
            device=device,
            disable_pbar=True,
            disable_log=True
        )

    def transcribe(self, wav_path):
        """
        Transcribe WAV file and return cleaned text.
        Handles long audio by chunking it if necessary.
        """
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"WAV file not found: {wav_path}")
            
        # Get duration using ffprobe
        try:
            cmd = ['ffprobe', '-i', wav_path, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0']
            duration = float(subprocess.check_output(cmd).decode().strip())
        except:
            duration = 0 # Fallback 

        # If audio is short (< 5 mins), transcribe directly
        if duration < 300:
            return self._transcribe_segment(wav_path)
            
        # Otherwise, slice into 5-minute chunks
        print(f"  Long audio detected ({duration:.1f}s). Processing in 5-minute chunks...")
        chunk_size = 300 # 5 minutes
        full_text = []
        
        temp_dir = os.path.dirname(wav_path)
        
        for start in range(0, int(duration), chunk_size):
            chunk_wav = os.path.join(temp_dir, f"chunk_{start}.wav")
            # Slice using ffmpeg
            cmd = ['ffmpeg', '-y', '-ss', str(start), '-t', str(chunk_size), '-i', wav_path, '-ar', '16000', '-ac', '1', chunk_wav]
            subprocess.run(cmd, capture_output=True)
            
            if os.path.exists(chunk_wav):
                print(f"    Transcribing chunk at {start}s...")
                text = self._transcribe_segment(chunk_wav)
                full_text.append(text)
                os.remove(chunk_wav)
                
        return "".join(full_text)

    def _transcribe_segment(self, wav_path):
        res = self.model.generate(
            input=wav_path,
            cache={},
            language="zh", 
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        if res and len(res) > 0:
            return res[0]['text']
        return ""
