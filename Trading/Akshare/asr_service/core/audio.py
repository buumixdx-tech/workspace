import subprocess
import os

def convert_to_wav(input_path, output_path):
    """
    Convert any audio file to 16kHz mono WAV for ASR using FFmpeg.
    """
    if os.path.exists(output_path):
        os.remove(output_path)
        
    command = [
        'ffmpeg',
        '-i', input_path,
        '-ar', '16000',
        '-ac', '1',
        '-y', # Overwrite output
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
